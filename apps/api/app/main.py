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

from fastapi.responses import RedirectResponse

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


# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev/preview
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.admin import router as admin_router
from app.api.billing import router as billing_router
from app.api.team import router as team_router

all_routers = [
    auth_router,
    projects_router,
    dce_router,
    decisions_router,
    generate_router,
    visuals_router,
    export_router,
    knowledge_router,
    admin_router,
    billing_router,
    team_router,
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


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/api/docs",
        "supabase_project": "boyloyvoy@gmail.com's ProjectBTP (Appel offre Charb)"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "btpao-fastapi"}


from fastapi.responses import JSONResponse
from app.core.celery_app import check_celery_broker_health


@app.get("/health/celery")
@app.get("/api/health/celery")
@app.get("/api/v1/health/celery")
async def celery_health_check():
    health = check_celery_broker_health()
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(status_code=status_code, content=health)

