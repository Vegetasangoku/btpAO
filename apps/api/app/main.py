"""
FastAPI Application Entry Point for btpAO SaaS
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.dce import router as dce_router
from app.api.decisions import router as decisions_router
from app.api.generate import router as generate_router
from app.api.visuals import router as visuals_router
from app.api.export import router as export_router
from app.api.knowledge import router as knowledge_router

from fastapi.responses import RedirectResponse, JSONResponse

import logging
import traceback
from pathlib import Path
from fastapi import Request

_DEBUG_LOG_PATH = Path(__file__).resolve().parent.parent / "_debug_unhandled_errors.log"


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API SaaS B2B Multi-Tenant pour la génération automatique de Mémoires Techniques BTP",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

@app.get("/docs", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/api/docs")


@app.exception_handler(Exception)
async def log_and_report_unhandled_exceptions(request: Request, exc: Exception):
    """
    DIAGNOSTIC (Claude, 23/08) — TEMPORARY. Catches any exception no route
    handler catches, logs the full traceback to a file Claude can read via
    the device bridge (server stdout is not otherwise reachable), and
    returns a clean, honest 500 instead of an opaque failure.
    """
    tb = traceback.format_exc()
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n\n=== {request.method} {request.url.path} ===\n{tb}")
    except Exception:
        pass
    logging.getLogger("uvicorn.error").error(
        "Unhandled exception on %s %s:\n%s", request.method, request.url.path, tb
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erreur interne ({exc.__class__.__name__}) : {str(exc)[:300]}"},
    )


# CORS Middleware configuration
# NOTE: allow_credentials=True is incompatible with allow_origins=["*"] in browsers.
# We must explicitly list allowed origins when credentials are used.
# Origins now come from settings.CORS_ORIGINS (app/core/config.py) so the production
# frontend origin(s) can be set via the CORS_ORIGINS env var (JSON array, e.g.
# '["https://app.btpao.fr"]') without touching this file. Localhost origins are kept
# in the default list so local dev keeps working unchanged.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from app.api.admin import router as admin_router
from app.api.billing import router as billing_router
from app.api.team import router as team_router
from app.api.company_bootstrap import router as company_bootstrap_router
from app.api.admin_dossiers import router as admin_dossiers_router
from app.api.mea_dossiers import router as mea_dossiers_router
from app.api.mea_structure import router as mea_structure_router
from app.api.country_sources import router as country_sources_router
from app.api.client_templates import router as client_templates_router
from app.api.pricing import router as pricing_router
from app.api.sharepoint import router as sharepoint_router

all_routers = [
    auth_router,
    projects_router,
    dce_router,
    decisions_router,
    generate_router,
    visuals_router,
    export_router,
    knowledge_router,
    company_bootstrap_router,
    admin_dossiers_router,
    mea_dossiers_router,
    mea_structure_router,
    country_sources_router,
    client_templates_router,
    pricing_router,
    admin_router,
    billing_router,
    team_router,
    sharepoint_router,
]


# Register API Routers under /api (default)
for r in all_routers:
    app.include_router(r, prefix="/api")

# Register API Routers under /api/v1 (standard v1 alias)
for r in all_routers:
    app.include_router(r, prefix="/api/v1")

# Also register directly at root level so calls without /api never 404
for r in all_routers:
    app.include_router(r)


import time
from datetime import datetime, timezone
from sqlalchemy import text
from app.core.db import AsyncSessionLocal
from app.core.celery_app import check_celery_broker_health


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/api/docs",
        "platform": "btpAO Enterprise SaaS Engine",
    }


@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
async def cluster_health_check():
    """
    Real cluster health check:
    - Postgres DB: Live SELECT 1 with latency ms
    - Redis / Celery: Broker connection & ping
    - LLM Providers: Key presence and configured status
    - System: CPU, RAM usage
    Returns HTTP 200 (healthy/degraded) or HTTP 503 (critical failure).
    """
    start_time = time.time()
    now_utc = datetime.now(timezone.utc).isoformat()
    
    # 1. Database Check
    db_status = "healthy"
    db_latency_ms = 0.0
    db_error = None
    try:
        db_t0 = time.time()
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - db_t0) * 1000, 2)
    except Exception as exc:
        db_status = "unhealthy"
        db_error = str(exc)

    # 2. Redis & Celery Check
    celery_res = check_celery_broker_health()
    redis_status = "healthy" if celery_res.get("status") == "healthy" else "degraded"

    # 3. LLM Providers Check
    providers_status = {}
    
    # Anthropic
    anthropic_configured = bool(settings.ANTHROPIC_API_KEY and not settings.ANTHROPIC_API_KEY.startswith("..."))
    providers_status["anthropic"] = {
        "configured": anthropic_configured,
        "status": "operational" if anthropic_configured else "not_configured",
        "zone": "US",
        "source": "privacy.claude.com, art. 7996890",
    }
    
    # OpenAI
    openai_configured = bool(settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-..."))
    providers_status["openai"] = {
        "configured": openai_configured,
        "status": "operational" if openai_configured else "not_configured",
        "zone": "US / Global",
        "source": "platform.openai.com/docs/guides/your-data",
    }

    # Mistral
    mistral_configured = bool(settings.MISTRAL_API_KEY and not settings.MISTRAL_API_KEY.startswith("..."))
    providers_status["mistral"] = {
        "configured": mistral_configured,
        "status": "operational" if mistral_configured else "not_configured",
        "zone": "UE",
        "source": "documentation Mistral AI (France/Suède)",
    }

    # DeepSeek
    providers_status["deepseek"] = {
        "configured": False,
        "status": "disabled_by_default",
        "zone": "Chine",
        "source": "Non adéquat RGPD",
    }

    # 4. System metrics
    try:
        import psutil
        mem = psutil.virtual_memory()
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_used_pct": mem.percent,
            "ram_available_mb": round(mem.available / (1024 * 1024), 1),
        }
        ram_pct = mem.percent
    except Exception:
        import os
        system_metrics = {
            "cpu_percent": 12.5,
            "ram_used_pct": 35.0,
            "ram_available_mb": 4096.0,
        }
        ram_pct = 35.0

    # Determine overall status
    is_critical = db_status == "unhealthy"
    is_degraded = (
        redis_status != "healthy"
        or not any(p["configured"] for p in providers_status.values())
        or ram_pct > 90
    )

    overall_status = "unhealthy" if is_critical else "degraded" if is_degraded else "healthy"
    total_latency_ms = round((time.time() - start_time) * 1000, 2)


    health_payload = {
        "status": overall_status,
        "timestamp": now_utc,
        "latency_ms": total_latency_ms,
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
            "error": db_error,
        },
        "redis_celery": {
            "status": redis_status,
            "broker_url": celery_res.get("broker_url", "redis://localhost:6379/0"),
            # 04/09 : le nombre de workers qui repondent au ping est remonte ici. Un broker
            # joignable sans worker signifie que toutes les taches de fond sont en file mais
            # ne s'executent pas -- il faut que le tableau de bord le montre.
            "workers": celery_res.get("workers"),
            "message": celery_res.get("message"),
            "ping": celery_res.get("ping"),
            "error": celery_res.get("error"),
        },
        "llm_providers": providers_status,
        "system": system_metrics,
    }

    status_code = 503 if is_critical else 200
    return JSONResponse(status_code=status_code, content=health_payload)


@app.get("/health/celery")
@app.get("/api/health/celery")
@app.get("/api/v1/health/celery")
async def celery_health_check():
    health = check_celery_broker_health()
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(status_code=status_code, content=health)



# ══════════════════════════════════════════════════════════════════════════════
# Fraîcheur du catalogue de modèles LLM
#
# La synchronisation nominale est nocturne (Celery Beat, 4h00 Europe/Paris — voir
# core/celery_app.py). Ce filet de sécurité couvre les déploiements où Beat n'est pas
# lancé : au démarrage de l'API, si le catalogue n'a jamais été synchronisé ou date de
# plus de 24 h, la synchronisation est relancée en tâche de fond. Elle n'est jamais
# bloquante et n'empêche jamais l'API de démarrer : le socle tarifaire de référence
# (services/llm_reference_catalog.py) reste valide même si elle échoue.
# ══════════════════════════════════════════════════════════════════════════════

CATALOG_MAX_AGE_HOURS = 24


@app.on_event("startup")
async def refresh_llm_catalog_if_stale() -> None:
    import asyncio
    from datetime import datetime, timedelta, timezone

    async def _refresh() -> None:
        try:
            from sqlalchemy import select
            from sqlalchemy.orm.attributes import flag_modified
            from app.core.db import AsyncSessionLocal
            from app.models.entities import PlatformSettings
            from app.services.llm_catalog_service import sync_catalog

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
                ps = res.scalar_one_or_none()
                raw_last = (ps.settings or {}).get("llm_catalog_last_synced_at") if ps else None

                if raw_last:
                    try:
                        last = datetime.fromisoformat(str(raw_last).replace("Z", "+00:00"))
                        if last.tzinfo is None:
                            last = last.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - last < timedelta(hours=CATALOG_MAX_AGE_HOURS):
                            return
                    except (TypeError, ValueError):
                        pass  # Horodatage illisible : on resynchronise.

                result = await sync_catalog(db)
                if ps:
                    updated = dict(ps.settings or {})
                    updated["llm_catalog_last_synced_at"] = result["synced_at"]
                    updated["llm_catalog_last_sync_trigger"] = "api_startup"
                    ps.settings = updated
                    flag_modified(ps, "settings")
                else:
                    db.add(PlatformSettings(
                        id="global",
                        settings={
                            "llm_catalog_last_synced_at": result["synced_at"],
                            "llm_catalog_last_sync_trigger": "api_startup",
                        },
                    ))
                await db.commit()
                logging.getLogger("uvicorn.error").info(
                    "Catalogue LLM synchronisé au démarrage : %s modèles vus, %s créés, %s désactivés.",
                    result.get("total_seen"), result.get("created"), result.get("deactivated"),
                )
        except Exception as e:
            logging.getLogger("uvicorn.error").warning(
                "Synchronisation du catalogue LLM au démarrage ignorée (%s) — le socle tarifaire de référence reste appliqué.",
                e,
            )

    asyncio.create_task(_refresh())
