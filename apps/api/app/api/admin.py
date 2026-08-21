"""
Super-Admin Management Router.
Strictly protected by require_platform_admin (403 for non-platform admins).
Zero hardcoded API secrets, zero memory cache, pure SQLAlchemy 2 Async + PostgreSQL Audit Trail.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, require_platform_admin
from app.models.entities import (
    AuditLog,
    CompanyAsset,
    DCEEmbedding,
    PlatformSettings,
    Project,
    Tenant,
    TenantSubscription,
    User,
)

router = APIRouter(
    prefix="/admin",
    tags=["SuperAdmin"],
    dependencies=[Depends(require_platform_admin)],
)


class CreateTenantPayload(BaseModel):
    name: str
    slug: Optional[str] = None
    siret: Optional[str] = None
    contact_email: Optional[str] = None
    plan: Optional[str] = "pro"
    country_code: Optional[str] = "FR"
    llm_provider: Optional[str] = "anthropic"
    llm_model: Optional[str] = "claude-3-5-sonnet-20241022"
    model_routing_config: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None


class LLMKeysPayload(BaseModel):
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None



class ModelRoutingPayload(BaseModel):
    tenant_id: str
    extraction_gonogo: Optional[Dict[str, str]] = None
    redaction_memoire: Optional[Dict[str, str]] = None
    analyse_prix: Optional[Dict[str, str]] = None


class SystemPromptPayload(BaseModel):
    tenant_id: str
    system_prompt: str


async def _record_audit_log(
    db: AsyncSession,
    admin_user: CurrentTenantUser,
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    tenant_id: Optional[uuid.UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    """Records an immutable audit log entry in PostgreSQL."""
    try:
        user_uuid = uuid.UUID(admin_user.user_id) if admin_user.user_id else None
    except ValueError:
        user_uuid = None

    log = AuditLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_uuid,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip_address=ip_address,
        created_at=datetime.utcnow(),
    )
    db.add(log)
    await db.flush()


@router.get("/tenants")
async def list_tenants(
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all client tenants with user counts, active project counts, subscription, and metadata.
    """
    users_subq = (
        select(User.tenant_id, func.count(User.id).label("users_count"))
        .group_by(User.tenant_id)
        .subquery()
    )
    projects_subq = (
        select(Project.tenant_id, func.count(Project.id).label("projects_count"))
        .group_by(Project.tenant_id)
        .subquery()
    )

    stmt = (
        select(
            Tenant,
            func.coalesce(users_subq.c.users_count, 0).label("users_count"),
            func.coalesce(projects_subq.c.projects_count, 0).label("projects_count"),
        )
        .outerjoin(users_subq, Tenant.id == users_subq.c.tenant_id)
        .outerjoin(projects_subq, Tenant.id == projects_subq.c.tenant_id)
        .order_by(Tenant.created_at.desc())
    )

    res = await db.execute(stmt)
    rows = res.all()

    # Also fetch subscriptions for accurate plan & quotas
    sub_res = await db.execute(select(TenantSubscription))
    subs_by_tenant = {str(sub.tenant_id): sub for sub in sub_res.scalars().all()}

    results = []
    for tenant, users_count, projects_count in rows:
        t_id_str = str(tenant.id)
        branding = tenant.branding_config or {}
        sub = subs_by_tenant.get(t_id_str)
        plan_name = sub.plan_id if sub and sub.plan_id else (tenant.plan or "pro")
        monthly_limit = (
            sub.custom_quota_dossiers
            if sub and sub.custom_quota_dossiers is not None
            else (50 if plan_name == "enterprise" else (15 if plan_name == "pro" else 3))
        )

        results.append({
            "id": t_id_str,
            "name": tenant.name,
            "slug": tenant.slug,
            "plan": plan_name,
            "country_code": tenant.country_code or "FR",
            "siret": tenant.siret or "",
            "contact_email": branding.get("contact_email") or "",
            "llm_provider": branding.get("llm_provider") or "anthropic",
            "llm_model": branding.get("llm_model") or "claude-3-5-sonnet-20241022",
            "branding_config": branding,
            "users_count": int(users_count),
            "projects_count": int(projects_count),
            "active_projects_count": int(projects_count),
            "used_this_month": 0,
            "monthly_limit": monthly_limit,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else datetime.utcnow().isoformat(),
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else datetime.utcnow().isoformat(),
        })

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="list_tenants",
        entity_type="tenant",
        details={"count": len(results)},
        ip_address=request.client.host if request.client else None,
    )
    return results


@router.post("/tenants")
async def create_tenant(
    payload: CreateTenantPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new client tenant with country regulatory profile and initial subscription.
    """
    import random
    import re

    # 1. Generate clean slug if not specified
    if payload.slug:
        slug = payload.slug.strip().lower()
    else:
        base_slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")
        slug = f"{base_slug}-{random.randint(100, 999)}"

    # Check slug uniqueness
    existing_slug = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if existing_slug.scalar_one_or_none():
        slug = f"{slug}-{random.randint(1000, 9999)}"

    country = (payload.country_code or "FR").upper()

    # 2. Build branding config dictionary (without SIRET, which is on dedicated column)
    branding = payload.branding_config or {}
    if payload.contact_email:
        branding["contact_email"] = payload.contact_email
    if payload.llm_provider:
        branding["llm_provider"] = payload.llm_provider
    if payload.llm_model:
        branding["llm_model"] = payload.llm_model
    if payload.model_routing_config:
        branding["model_routing_config"] = payload.model_routing_config

    tenant_id = uuid.uuid4()
    plan_name = payload.plan or "pro"
    siret_clean = payload.siret.strip() if payload.siret else None

    new_tenant = Tenant(
        id=tenant_id,
        name=payload.name.strip(),
        slug=slug,
        siret=siret_clean,
        plan=plan_name,
        country_code=country,
        branding_config=branding,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_tenant)


    # Set PostgreSQL tenant context so initial subscription and audit log pass RLS
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
        {"tenant_id": str(tenant_id)},
    )
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true);"),
        {"tenant_id": str(tenant_id)},
    )

    # 3. Create initial TenantSubscription
    now = datetime.utcnow()
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan_name,
        status="active",
        billing_mode="subscription",
        custom_quota_dossiers=50 if plan_name == "enterprise" else (15 if plan_name == "pro" else 3),
        allow_overage=False,
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
        created_at=now,
        updated_at=now,
    )
    db.add(sub)



    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="create_tenant",
        entity_type="tenant",
        tenant_id=tenant_id,
        details={
            "name": new_tenant.name,
            "slug": new_tenant.slug,
            "plan": plan_name,
            "country_code": country,
            "siret": payload.siret,
            "contact_email": payload.contact_email,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {
        "id": str(new_tenant.id),
        "name": new_tenant.name,
        "slug": new_tenant.slug,
        "plan": new_tenant.plan,
        "country_code": new_tenant.country_code,
        "siret": new_tenant.siret or "",
        "contact_email": branding.get("contact_email") or "",
        "llm_provider": branding.get("llm_provider") or "anthropic",

        "llm_model": branding.get("llm_model") or "claude-3-5-sonnet-20241022",
        "branding_config": branding,
        "users_count": 0,
        "projects_count": 0,
        "active_projects_count": 0,
        "used_this_month": 0,
        "monthly_limit": 50 if plan_name == "enterprise" else (15 if plan_name == "pro" else 3),
        "created_at": new_tenant.created_at.isoformat(),
        "updated_at": new_tenant.updated_at.isoformat(),
    }


@router.get("/llm-keys")
async def get_llm_keys(
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Returns configured LLM keys masked for security."""
    stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    res = await db.execute(stmt)
    ps = res.scalar_one_or_none()

    ps_dict = ps.settings if ps and ps.settings else {}
    anthropic_key = ps_dict.get("anthropic_api_key") or settings.ANTHROPIC_API_KEY or ""
    openai_key = ps_dict.get("openai_api_key") or settings.OPENAI_API_KEY or ""
    mistral_key = ps_dict.get("mistral_api_key") or settings.MISTRAL_API_KEY or ""

    anthropic_masked = f"{anthropic_key[:10]}...{anthropic_key[-4:]}" if len(anthropic_key) > 14 else ("sk-ant-***" if anthropic_key else "")
    openai_masked = f"{openai_key[:7]}...{openai_key[-4:]}" if len(openai_key) > 11 else ("sk-***" if openai_key else "")
    mistral_masked = f"{mistral_key[:6]}...{mistral_key[-4:]}" if len(mistral_key) > 10 else ("mis-***" if mistral_key else "")

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="read_llm_keys",
        entity_type="platform_settings",
        ip_address=request.client.host if request.client else None,
    )

    return {
        "anthropic_api_key_configured": bool(anthropic_key),
        "anthropic_api_key_masked": anthropic_masked,
        "openai_api_key_configured": bool(openai_key),
        "openai_api_key_masked": openai_masked,
        "mistral_api_key_configured": bool(mistral_key),
        "mistral_api_key_masked": mistral_masked,
        "embedding_model": ps_dict.get("embedding_model") or settings.EMBEDDING_MODEL or "text-embedding-3-small",
    }


@router.post("/llm-keys")
async def update_llm_keys(
    payload: LLMKeysPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Updates master LLM keys dynamically in PostgreSQL and settings."""
    stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    res = await db.execute(stmt)
    ps = res.scalar_one_or_none()

    now = datetime.utcnow()
    current_settings = ps.settings if ps and ps.settings else {}

    if payload.anthropic_api_key is not None:
        val = payload.anthropic_api_key.strip()
        current_settings["anthropic_api_key"] = val
        settings.ANTHROPIC_API_KEY = val
    if payload.openai_api_key is not None:
        val = payload.openai_api_key.strip()
        current_settings["openai_api_key"] = val
        settings.OPENAI_API_KEY = val
    if payload.mistral_api_key is not None:
        val = payload.mistral_api_key.strip()
        current_settings["mistral_api_key"] = val
        settings.MISTRAL_API_KEY = val

    if ps:
        ps.settings = current_settings
        ps.updated_at = now
    else:
        ps = PlatformSettings(id="global", settings=current_settings, updated_at=now)
        db.add(ps)

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_llm_keys",
        entity_type="platform_settings",
        details={"updated_keys": [k for k, v in payload.dict(exclude_unset=True).items() if v is not None]},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"success": True, "message": "Clés API Master enregistrées dans PostgreSQL avec audit log"}


@router.get("/rag-supervision")
async def get_rag_supervision(
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Supervises real pgvector embeddings and counts across all tenants."""
    dce_count_stmt = select(func.count(DCEEmbedding.id))
    dce_res = await db.execute(dce_count_stmt)
    dce_chunks_count = dce_res.scalar() or 0

    assets_count_stmt = select(func.count(CompanyAsset.id))
    assets_res = await db.execute(assets_count_stmt)
    knowledge_chunks_count = assets_res.scalar() or 0

    return {
        "embedding_model": settings.EMBEDDING_MODEL or "text-embedding-3-small",
        "dimensions": 1536,
        "similarity_metric": "Cosinus (1 - (a <=> b))",
        "total_dce_chunks": dce_chunks_count,
        "total_knowledge_chunks": knowledge_chunks_count,
        "index_type": "HNSW",
    }



@router.get("/model-routing/{tenant_id}")
async def get_tenant_model_routing(
    tenant_id: str,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Gets task-based LLM model routing for a specific tenant from PostgreSQL."""
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(Tenant).where(Tenant.id == t_uuid)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    branding = tenant.branding_config or {}
    routing = branding.get("model_routing", {
        "extraction_gonogo": {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022"},
        "redaction_memoire": {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022"},
        "analyse_prix": {"provider": "Mistral AI", "model": "mistral-large-2407"},
    })

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="read_model_routing",
        entity_type="tenant",
        entity_id=t_uuid,
        tenant_id=t_uuid,
        ip_address=request.client.host if request.client else None,
    )

    return {"tenant_id": str(t_uuid), "routing": routing}


@router.post("/model-routing")
async def update_tenant_model_routing(
    payload: ModelRoutingPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Saves task-based LLM model routing per tenant in PostgreSQL."""
    try:
        t_uuid = uuid.UUID(payload.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(Tenant).where(Tenant.id == t_uuid)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    routing_config = {
        "extraction_gonogo": payload.extraction_gonogo or {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022"},
        "redaction_memoire": payload.redaction_memoire or {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022"},
        "analyse_prix": payload.analyse_prix or {"provider": "Mistral AI", "model": "mistral-large-2407"},
    }

    branding = dict(tenant.branding_config or {})
    branding["model_routing"] = routing_config
    tenant.branding_config = branding
    tenant.updated_at = datetime.utcnow()

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_model_routing",
        entity_type="tenant",
        entity_id=t_uuid,
        tenant_id=t_uuid,
        details={"routing": routing_config},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"success": True, "message": "Routage LLM par tâche enregistré avec succès"}


@router.get("/system-prompt/{tenant_id}")
async def get_tenant_system_prompt(
    tenant_id: str,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves custom system prompt memory for a tenant from PostgreSQL."""
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(Tenant).where(Tenant.id == t_uuid)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    branding = tenant.branding_config or {}
    memory = branding.get("system_prompt", "")
    if not memory:
        memory = """### RÈGLES DE RÉDACTION MÉTIER BTP (ENTREPRISE)
- Toujours mentionner nos certifications QUALIBAT 2152 (Béton armé courant) et 1112 (Maçonnerie).
- Préconiser systématiquement des bétons bas carbone CEM III/A avec FDES vérifiée.
- Imposer le quart d'heure sécurité hebdomadaire sous l'autorité du conducteur de travaux principal.
- Cadencement strict par trame de 48h sur les voiles et planchers de compression.
- Coefficient d'actualisation économique BT01 appliqué (+3.5% par an)."""

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="read_system_prompt",
        entity_type="tenant",
        entity_id=t_uuid,
        tenant_id=t_uuid,
        ip_address=request.client.host if request.client else None,
    )

    return {"tenant_id": str(t_uuid), "system_prompt": memory}


@router.post("/system-prompt")
async def update_tenant_system_prompt(
    payload: SystemPromptPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Updates tenant custom system prompt memory in PostgreSQL."""
    try:
        t_uuid = uuid.UUID(payload.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(Tenant).where(Tenant.id == t_uuid)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    branding = dict(tenant.branding_config or {})
    branding["system_prompt"] = payload.system_prompt
    tenant.branding_config = branding
    tenant.updated_at = datetime.utcnow()

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_system_prompt",
        entity_type="tenant",
        entity_id=t_uuid,
        tenant_id=t_uuid,
        details={"prompt_length": len(payload.system_prompt)},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"success": True, "message": "System Prompt client enregistré"}


class AdminSubscriptionPayload(BaseModel):
    plan_id: str = "enterprise"
    status: str = "active"
    billing_mode: str = "manual_enterprise"
    custom_quota_dossiers: Optional[int] = None
    allow_overage: bool = True
    duration_days: int = 365


@router.get("/audit-logs")
async def get_audit_logs(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 50,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Returns immutable platform audit logs filterable by tenant, user/admin, and action."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if tenant_id:
        try:
            t_uuid = uuid.UUID(tenant_id)
            stmt = stmt.where(AuditLog.tenant_id == t_uuid)
        except ValueError:
            pass
    if user_id:
        try:
            u_uuid = uuid.UUID(user_id)
            stmt = stmt.where(AuditLog.user_id == u_uuid)
        except ValueError:
            pass
    if action:
        stmt = stmt.where(AuditLog.action == action)

    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        {
            "id": str(log.id),
            "tenant_id": str(log.tenant_id) if log.tenant_id else None,
            "user_id": str(log.user_id) if log.user_id else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/tenants/{tenant_id}/subscription")
async def get_tenant_subscription_admin(
    tenant_id: str,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Platform Admin: view any tenant subscription, consumption, and quota."""
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    from sqlalchemy import text
    from app.models.entities import TenantSubscription, TenantUsageCounter
    from app.services.billing_service import billing_service

    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
        {"tenant_id": str(t_uuid)},
    )
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true);"),
        {"tenant_id": str(t_uuid)},
    )

    sub_stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == t_uuid)
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalar_one_or_none()

    usage = await billing_service.get_or_create_usage(t_uuid, db)

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="read_tenant_subscription",
        entity_type="tenant_subscription",
        tenant_id=t_uuid,
        ip_address=request.client.host if request.client else None,
    )

    if not sub:
        return {
            "has_subscription": False,
            "tenant_id": str(t_uuid),
            "plan_id": "starter",
            "status": "active",
            "billing_mode": "free_trial",
            "custom_quota_dossiers": None,
            "quota": 3,
            "dossiers_used": usage.dossiers_generated,
            "allow_overage": True,
        }

    return {
        "has_subscription": True,
        "subscription_id": str(sub.id),
        "tenant_id": str(t_uuid),
        "plan_id": sub.plan_id,
        "status": sub.status,
        "billing_mode": sub.billing_mode,
        "custom_quota_dossiers": sub.custom_quota_dossiers,
        "allow_overage": sub.allow_overage,
        "dossiers_used": usage.dossiers_generated,
        "current_period_start": sub.current_period_start.isoformat(),
        "current_period_end": sub.current_period_end.isoformat(),
    }


@router.put("/tenants/{tenant_id}/subscription")
async def update_tenant_subscription_admin(
    tenant_id: str,
    payload: AdminSubscriptionPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Platform Admin: Manually configure custom Enterprise / sur-devis plan, quota, status, and overage options.
    Generates an immutable audit log entry.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    from datetime import timedelta
    from sqlalchemy import text
    from app.models.entities import TenantSubscription

    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
        {"tenant_id": str(t_uuid)},
    )
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true);"),
        {"tenant_id": str(t_uuid)},
    )

    sub_stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == t_uuid)
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalar_one_or_none()


    now = datetime.utcnow()
    period_end = now + timedelta(days=payload.duration_days)

    if sub:
        sub.plan_id = payload.plan_id
        sub.status = payload.status
        sub.billing_mode = payload.billing_mode
        sub.custom_quota_dossiers = payload.custom_quota_dossiers
        sub.allow_overage = payload.allow_overage
        sub.current_period_start = now
        sub.current_period_end = period_end
        sub.updated_at = now
    else:
        sub = TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            plan_id=payload.plan_id,
            status=payload.status,
            billing_mode=payload.billing_mode,
            custom_quota_dossiers=payload.custom_quota_dossiers,
            allow_overage=payload.allow_overage,
            current_period_start=now,
            current_period_end=period_end,
            created_at=now,
            updated_at=now,
        )
        db.add(sub)

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_tenant_subscription",
        entity_type="tenant_subscription",
        tenant_id=t_uuid,
        details={
            "plan_id": payload.plan_id,
            "status": payload.status,
            "custom_quota": payload.custom_quota_dossiers,
            "allow_overage": payload.allow_overage,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {
        "success": True,
        "message": f"Abonnement du tenant {tenant_id} mis à jour avec succès (statut: {payload.status}, quota: {payload.custom_quota_dossiers})",
    }

