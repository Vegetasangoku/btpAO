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
)


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
        # Check broker reachability using Celery connection
        with celery_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=1, interval_start=0.1)
        return {
            "status": "healthy",
            "broker": configured_broker,
            "mode": "distributed_broker",
            "message": "Celery broker connected successfully.",
        }
    except Exception as e:
        logger.error(f"Celery broker healthcheck failed for {configured_broker}: {e}")
        return {
            "status": "unhealthy",
            "broker": configured_broker,
            "mode": "distributed_broker",
            "error": str(e),
        }
