"""
Celery Worker Configuration & Task Registry
"""
import os
import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger("celery_app")


def get_celery_broker_urls(app_env: str = None, always_eager: str = None) -> tuple[str, str]:
    """
    Returns (broker_url, backend_url).
    Fallback to in-memory broker is strictly restricted to test mode or explicit CELERY_ALWAYS_EAGER=true.
    Never silently switches to memory:// in development or production.
    """
    env = app_env if app_env is not None else settings.APP_ENV
    eager = always_eager if always_eager is not None else os.getenv("CELERY_ALWAYS_EAGER", "false")

    if eager.lower() in ("true", "1") or env in ("test", "testing"):
        return "memory://", "rpc://"

    # In dev/staging/prod: strictly keep the configured distributed broker (Redis/AMQP)
    return settings.CELERY_BROKER_URL, settings.CELERY_RESULT_BACKEND


broker_url, backend_url = get_celery_broker_urls()

celery_app = Celery(
    "btp_workers",
    broker=broker_url,
    backend=backend_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    # 03/09 (nuit) : le conteneur worker ecoute "-Q default,ocr,generation" (docker-compose.yml)
    # mais rien ici ne routait les taches vers ces files -- Celery publiait donc CHAQUE tache
    # (generate_section_task y compris) sur sa file par defaut interne "celery", que ce worker
    # n'ecoute justement pas. Consequence : toute tache .delay()'ee restait invisible pour le
    # worker, pour toujours, sans la moindre erreur ni cote API ni cote worker (le worker tourne,
    # healthy, mais ne voit jamais rien passer) -- c'est la cause racine du dossier bloque sur
    # "processing" ce soir (03/09, 71260018_CCTP_VDEF). task_default_queue aligne la file par
    # defaut de Celery sur une file reellement ecoutee ; task_routes isole en plus les 2 taches
    # les plus lourdes sur leurs files dediees, comme le nommage -Q le laissait deviner.
    task_default_queue="default",
    task_routes={
        "tasks.parse_dce_task": {"queue": "ocr"},
        "tasks.generate_section_task": {"queue": "generation"},
    },
)

# ── Celery Beat Scheduled Tasks ──────────────────────────────────────────────
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "daily-gdpr-account-purge": {
        "task": "tasks.purge_expired_accounts_task",
        "schedule": crontab(hour=3, minute=0),  # Everyday at 3:00 AM Paris time
    },
    "daily-llm-catalog-sync": {
        "task": "tasks.sync_llm_catalog_daily_task",
        "schedule": crontab(hour=4, minute=0),  # Everyday at 4:00 AM Paris time
    },
    "daily-regulatory-watch": {
        # 04/09 : veille des portails officiels par pays. A 5h00, apres la purge RGPD (3h)
        # et la synchro du catalogue LLM (4h), pour ne pas empiler les taches longues.
        "task": "tasks.regulatory_watch_daily_task",
        "schedule": crontab(hour=5, minute=0),
    },
    "sharepoint-delta-sync": {
        # 03/09 : toutes les 6h -- assez frequent pour que "les nouveaux fichiers"
        # deposes par le client apparaissent vite dans son RAG, assez espace pour que
        # le cout ne soit jamais celui d'un balayage complet (chaque cycle ne traite
        # QUE le delta Microsoft Graph depuis le cycle precedent, voir
        # app/workers/tasks.py:sharepoint_sync_task).
        "task": "tasks.sharepoint_sync_all_tenants_task",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}



def check_celery_broker_health() -> dict:
    """
    Inspects connectivity to the configured Celery broker.
    Returns structured healthcheck status.
    """
    configured_broker = celery_app.conf.broker_url or settings.CELERY_BROKER_URL
    is_memory = configured_broker.startswith("memory://")

    if is_memory:
        return {
            "status": "healthy",
            "broker": "memory://",
            "mode": "test_in_memory",
            "message": "In-memory test broker is active for test suite execution.",
        }

    try:
        # 1. Joignabilite du broker.
        with celery_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=1, interval_start=0.1)

        # 2. Presence d'un worker (04/09). Avant ce correctif, ce controle ne testait QUE
        # Redis et renvoyait "healthy" meme sans aucun worker : la file pouvait n'etre
        # consommee par personne -- generation de sections, synchro SharePoint, purge RGPD
        # et veille reglementaire toutes a l'arret -- pendant que le tableau de bord
        # affichait un voyant vert. Un broker joignable ne dit rien de l'execution.
        workers: dict = {}
        try:
            workers = celery_app.control.ping(timeout=1.0) or {}
        except Exception as ping_exc:  # noqa: BLE001
            logger.warning("Celery worker ping failed: %s", ping_exc)

        worker_count = len(workers)
        if worker_count == 0:
            return {
                "status": "degraded",
                "broker": configured_broker,
                "mode": "distributed_broker",
                "workers": 0,
                "message": (
                    "Broker joignable mais AUCUN worker Celery ne repond. Les taches de fond "
                    "(generation de sections, synchro SharePoint, veille reglementaire, purge RGPD) "
                    "sont mises en file mais ne s'executent pas."
                ),
            }

        # Taches reellement enregistrees par les workers. Un worker demarre avant l'ajout
        # d'une tache ne la connait pas (Celery n'enregistre pas a chaud) : la tache part
        # en file et n'est jamais executee, sans erreur visible cote appelant. Ce champ
        # rend ce cas diagnosticable au lieu de le laisser deviner.
        registered: list = []
        try:
            reg = celery_app.control.inspect(timeout=1.0).registered() or {}
            for task_names in reg.values():
                registered.extend(task_names or [])
            registered = sorted(set(registered))
        except Exception as reg_exc:  # noqa: BLE001
            logger.warning("Celery registered-tasks inspect failed: %s", reg_exc)

        return {
            "status": "healthy",
            "broker": configured_broker,
            "mode": "distributed_broker",
            "workers": worker_count,
            "registered_tasks": registered,
            "message": f"Broker connecte, {worker_count} worker(s) actif(s).",
        }
    except Exception as e:
        logger.error(f"Celery broker healthcheck failed for {configured_broker}: {e}")
        return {
            "status": "unhealthy",
            "broker": configured_broker,
            "mode": "distributed_broker",
            "error": str(e),
        }
