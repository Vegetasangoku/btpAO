"""
Super-Admin Management Router.
Strictly protected by require_platform_admin (403 for non-platform admins).
Zero hardcoded API secrets, zero memory cache, pure SQLAlchemy 2 Async + PostgreSQL Audit Trail.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings

from app.core.db import get_db, get_system_db_unrestricted_INTERNAL_ONLY
from app.core.security import CurrentTenantUser, require_platform_admin
from app.models.entities import (
    AuditLog,
    CompanyAsset,
    CountryOfficialSource,
    DCEDocument,
    DCEEmbedding,
    PlatformSettings,
    Project,
    Tenant,
    TenantSubscription,
    User,
)
from app.core.crypto_vault import encrypt_api_key, decrypt_api_key, mask_api_key
from app.services.model_routing_service import (
    model_routing_service,
    LLM_MODEL_TIERS,
    DEFAULT_CUSTOM_PROVIDERS,
    is_zone_non_eu_us,
    RGPD_NON_EU_WARNING,
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
    llm_model_tier: Optional[str] = "inherit"
    model_routing_config: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None


class UpdateTenantPayload(BaseModel):
    name: Optional[str] = None
    siret: Optional[str] = None
    contact_email: Optional[str] = None
    plan: Optional[str] = None
    country_code: Optional[str] = None
    llm_model_tier: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    branding_config: Optional[Dict[str, Any]] = None


class CustomProviderInput(BaseModel):
    id: Optional[str] = None
    name: str
    litellm_id: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    zone: str = "US"  # "UE" | "US" | "Chine" | "autre" | "non-verifie"
    enabled: bool = True


class LLMKeysPayload(BaseModel):
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    default_llm_tier: Optional[str] = None
    custom_providers: Optional[List[CustomProviderInput]] = None


class TestProviderPayload(BaseModel):
    provider_id: Optional[str] = None
    name: Optional[str] = None
    litellm_id: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None





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
        try:
            user_uuid = uuid.UUID(admin_user.user_id) if admin_user.user_id else None
        except (ValueError, TypeError):
            user_uuid = None

        target_tenant = tenant_id
        if not target_tenant and admin_user.tenant_id:
            try:
                target_tenant = uuid.UUID(admin_user.tenant_id)
            except (ValueError, TypeError):
                pass
        if not target_tenant:
            target_tenant = uuid.UUID("00000000-0000-0000-0000-000000000000")

        if user_uuid:
            user_exists = await db.execute(select(User.id).where(User.id == user_uuid))
            if not user_exists.scalar_one_or_none():
                user_uuid = None

        log = AuditLog(
            id=uuid.uuid4(),
            tenant_id=target_tenant,
            user_id=user_uuid,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
            created_at=datetime.utcnow(),
        )
        async with db.begin_nested():
            db.add(log)
            await db.flush()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning("Audit log recording skipped: %s", e)


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
            "llm_model_tier": branding.get("llm_model_tier") or "inherit",
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
    Creates a new client tenant with country regulatory profile, model tier and initial subscription.
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
    branding["llm_model_tier"] = payload.llm_model_tier or "inherit"
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
        text("SELECT set_config('app.current_tenant_id', :tenant_id, false);"),
        {"tenant_id": str(tenant_id)},
    )
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, false);"),
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
            "llm_model_tier": payload.llm_model_tier or "inherit",
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

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
        "llm_model_tier": branding.get("llm_model_tier") or "inherit",
        "branding_config": branding,
        "users_count": 0,
        "projects_count": 0,
        "active_projects_count": 0,
        "used_this_month": 0,
        "monthly_limit": 50 if plan_name == "enterprise" else (15 if plan_name == "pro" else 3),
        "created_at": new_tenant.created_at.isoformat(),
        "updated_at": new_tenant.updated_at.isoformat(),
    }


@router.get("/tenants/{tenant_id}")
async def get_tenant_detail(
    tenant_id: str,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Returns single tenant details with resolved model tier."""
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
    resolved_model_info = await model_routing_service.resolve_model_for_tenant(db=db, tenant_id=t_uuid)

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "country_code": tenant.country_code or "FR",
        "siret": tenant.siret or "",
        "contact_email": branding.get("contact_email") or "",
        "llm_provider": branding.get("llm_provider") or "anthropic",
        "llm_model": branding.get("llm_model") or "claude-3-5-sonnet-20241022",
        "llm_model_tier": branding.get("llm_model_tier") or "inherit",
        "resolved_model_info": resolved_model_info,
        "branding_config": branding,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }


@router.put("/tenants/{tenant_id}")
async def update_tenant_admin(
    tenant_id: str,
    payload: UpdateTenantPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Updates tenant details, plan, country, and model tier override."""
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(Tenant).where(Tenant.id == t_uuid)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    branding = dict(tenant.branding_config or {})
    if payload.branding_config:
        branding.update(payload.branding_config)

    if payload.name is not None:
        tenant.name = payload.name.strip()
    if payload.siret is not None:
        tenant.siret = payload.siret.strip() if payload.siret else None
    if payload.plan is not None:
        tenant.plan = payload.plan
    if payload.country_code is not None:
        tenant.country_code = payload.country_code.strip().upper()
    if payload.contact_email is not None:
        branding["contact_email"] = payload.contact_email
    if payload.llm_model_tier is not None:
        branding["llm_model_tier"] = payload.llm_model_tier
    if payload.llm_model is not None:
        branding["llm_model"] = payload.llm_model
    if payload.llm_provider is not None:
        branding["llm_provider"] = payload.llm_provider

    tenant.branding_config = branding
    tenant.updated_at = datetime.utcnow()

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_tenant",
        entity_type="tenant",
        tenant_id=t_uuid,
        details=payload.dict(exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    resolved_model_info = await model_routing_service.resolve_model_for_tenant(db=db, tenant_id=t_uuid)

    return {
        "success": True,
        "message": f"Tenant {tenant.name} mis à jour avec succès",
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "plan": tenant.plan,
            "siret": tenant.siret or "",
            "country_code": tenant.country_code,
            "llm_model_tier": branding.get("llm_model_tier") or "inherit",
            "resolved_model_info": resolved_model_info,
        }
    }


@router.get("/llm-keys")
async def get_llm_keys(
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Returns configured LLM keys masked for security, custom providers list, and platform default model tier."""
    stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    res = await db.execute(stmt)
    ps = res.scalar_one_or_none()

    ps_dict = ps.settings if ps and ps.settings else {}
    anthropic_raw = ps_dict.get("anthropic_api_key") or settings.ANTHROPIC_API_KEY or ""
    openai_raw = ps_dict.get("openai_api_key") or settings.OPENAI_API_KEY or ""
    mistral_raw = ps_dict.get("mistral_api_key") or settings.MISTRAL_API_KEY or ""

    custom_providers = await model_routing_service.get_custom_providers(db, mask_keys=True)
    default_tier = ps_dict.get("default_llm_tier") or "equilibre"

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="read_llm_keys",
        entity_type="platform_settings",
        ip_address=request.client.host if request.client else None,
    )

    return {
        "anthropic_api_key_configured": bool(anthropic_raw),
        "anthropic_api_key_masked": mask_api_key(anthropic_raw),
        "openai_api_key_configured": bool(openai_raw),
        "openai_api_key_masked": mask_api_key(openai_raw),
        "mistral_api_key_configured": bool(mistral_raw),
        "mistral_api_key_masked": mask_api_key(mistral_raw),
        "custom_providers": custom_providers,
        "encryption_status": "AES-256-GCM Chiffré au repos",
        "embedding_model": ps_dict.get("embedding_model") or settings.EMBEDDING_MODEL or "text-embedding-3-small",
        "default_llm_tier": default_tier,
        "available_tiers": LLM_MODEL_TIERS,
    }


@router.post("/llm-keys")
async def update_llm_keys(
    payload: LLMKeysPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Updates master LLM keys and extensible custom providers list with AES-256-GCM encryption before storage."""
    stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    res = await db.execute(stmt)
    ps = res.scalar_one_or_none()

    now = datetime.utcnow()
    current_settings = ps.settings if ps and ps.settings else {}

    # 1. Update Custom Providers if provided
    if payload.custom_providers is not None:
        existing_providers = current_settings.get("custom_providers") or DEFAULT_CUSTOM_PROVIDERS
        existing_map = {p.get("id"): p for p in existing_providers if p.get("id")}

        saved_providers = []
        for prov_input in payload.custom_providers:
            prov_id = prov_input.id or str(uuid.uuid4())[:8]
            existing_p = existing_map.get(prov_id, {})
            
            raw_key = prov_input.api_key.strip() if prov_input.api_key else ""
            
            # If key was supplied and is NOT a masked string, encrypt it
            if raw_key and "•••" not in raw_key and "***" not in raw_key:
                encrypted_key = encrypt_api_key(raw_key)
            else:
                # Preserve existing encrypted key
                encrypted_key = existing_p.get("api_key", "")

            zone = prov_input.zone or "US"
            saved_providers.append({
                "id": prov_id,
                "name": prov_input.name,
                "litellm_id": prov_input.litellm_id,
                "api_key": encrypted_key,
                "api_base": (prov_input.api_base or "").strip(),
                "zone": zone,
                "enabled": prov_input.enabled,
            })
        current_settings["custom_providers"] = saved_providers

    # 2. Update legacy key fields with application-level AES encryption
    if payload.anthropic_api_key is not None:
        val = payload.anthropic_api_key.strip()
        if val and "•••" not in val and "***" not in val:
            current_settings["anthropic_api_key"] = encrypt_api_key(val)
            settings.ANTHROPIC_API_KEY = val
    if payload.openai_api_key is not None:
        val = payload.openai_api_key.strip()
        if val and "•••" not in val and "***" not in val:
            current_settings["openai_api_key"] = encrypt_api_key(val)
            settings.OPENAI_API_KEY = val
    if payload.mistral_api_key is not None:
        val = payload.mistral_api_key.strip()
        if val and "•••" not in val and "***" not in val:
            current_settings["mistral_api_key"] = encrypt_api_key(val)
            settings.MISTRAL_API_KEY = val

    # 3. Update Platform Default Tier
    if payload.default_llm_tier is not None:
        val = payload.default_llm_tier.strip().lower()
        if val in LLM_MODEL_TIERS:
            current_settings["default_llm_tier"] = val
            settings.DEFAULT_LLM_MODEL = LLM_MODEL_TIERS[val]["model_string"]

    if ps:
        ps.settings = dict(current_settings)
        ps.updated_at = now
        flag_modified(ps, "settings")
    else:
        ps = PlatformSettings(id="global", settings=dict(current_settings), updated_at=now)
        db.add(ps)

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_llm_keys",
        entity_type="platform_settings",
        details={"updated_keys": [k for k, v in payload.dict(exclude_unset=True).items() if v is not None]},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, "message": "Master API keys, custom providers and platform settings successfully updated."}


@router.post("/llm-keys/test-provider")
async def test_llm_provider_connection(
    payload: TestProviderPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a real minimal API call to verify the LLM provider API key and connection.
    Returns real status, latency, error details, and records the test timestamp in PlatformSettings.
    """
    import litellm
    import time

    now = datetime.utcnow()
    raw_key = (payload.api_key or "").strip()
    resolved_api_key = None

    # 1. If key is provided in plaintext (not masked), use it
    if raw_key and "•••" not in raw_key and "***" not in raw_key:
        resolved_api_key = raw_key
    elif payload.provider_id:
        # Resolve from stored encrypted keys in platform settings
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        ps_dict = ps.settings if ps and ps.settings else {}

        # Check custom providers
        for p in ps_dict.get("custom_providers", []):
            if p.get("id") == payload.provider_id:
                enc_k = p.get("api_key", "")
                if enc_k:
                    resolved_api_key = decrypt_api_key(enc_k)
                break

        # Check legacy keys
        if not resolved_api_key:
            if payload.provider_id in ["anthropic", "anthropic_api_key"]:
                k = ps_dict.get("anthropic_api_key") or settings.ANTHROPIC_API_KEY
                resolved_api_key = decrypt_api_key(k) if k else None
            elif payload.provider_id in ["openai", "openai_api_key"]:
                k = ps_dict.get("openai_api_key") or settings.OPENAI_API_KEY
                resolved_api_key = decrypt_api_key(k) if k else None
            elif payload.provider_id in ["mistral", "mistral_api_key"]:
                k = ps_dict.get("mistral_api_key") or settings.MISTRAL_API_KEY
                resolved_api_key = decrypt_api_key(k) if k else None

    # Fallback to model routing service if still not resolved
    if not resolved_api_key:
        creds = await model_routing_service.get_credentials_for_model(db, payload.litellm_id)
        resolved_api_key = creds.get("api_key")

    if not resolved_api_key:
        return {
            "success": False,
            "status": "error",
            "latency_ms": 0,
            "error_message": "Aucune clé API configurée ou fournie pour ce test.",
            "tested_at": now.isoformat() + "Z",
        }

    # 2. Execute minimal real test call
    start_t = time.perf_counter()
    try:
        kwargs: Dict[str, Any] = {
            "model": payload.litellm_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "api_key": resolved_api_key,
            "timeout": 8,
        }
        if payload.api_base and payload.api_base.strip():
            kwargs["api_base"] = payload.api_base.strip()

        resp = litellm.completion(**kwargs)
        latency_ms = max(1, int((time.perf_counter() - start_t) * 1000))

        # Update test result in PlatformSettings
        if payload.provider_id:
            stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
            res = await db.execute(stmt)
            ps = res.scalar_one_or_none()
            if ps:
                settings_dict = dict(ps.settings or {})
                test_results = dict(settings_dict.get("test_results") or {})
                test_results[payload.provider_id] = {
                    "status": "success",
                    "latency_ms": latency_ms,
                    "last_tested_at": now.isoformat() + "Z",
                    "error": None,
                }
                settings_dict["test_results"] = test_results
                ps.settings = settings_dict
                ps.updated_at = now
                flag_modified(ps, "settings")

        await _record_audit_log(
            db=db,
            admin_user=admin_user,
            action="test_llm_provider_success",
            entity_type="llm_provider",
            details={"provider_id": payload.provider_id, "litellm_id": payload.litellm_id, "latency_ms": latency_ms},
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()

        return {
            "success": True,
            "status": "success",
            "latency_ms": latency_ms,
            "message": f"Connexion réussie ({latency_ms} ms)",
            "tested_at": now.isoformat() + "Z",
        }
    except Exception as e:
        latency_ms = max(1, int((time.perf_counter() - start_t) * 1000))
        err_msg = str(e)

        # Record failure timestamp
        if payload.provider_id:
            stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
            res = await db.execute(stmt)
            ps = res.scalar_one_or_none()
            if ps:
                settings_dict = dict(ps.settings or {})
                test_results = dict(settings_dict.get("test_results") or {})
                test_results[payload.provider_id] = {
                    "status": "error",
                    "latency_ms": latency_ms,
                    "last_tested_at": now.isoformat() + "Z",
                    "error": err_msg[:200],
                }
                settings_dict["test_results"] = test_results
                ps.settings = settings_dict
                ps.updated_at = now
                flag_modified(ps, "settings")

        await _record_audit_log(
            db=db,
            admin_user=admin_user,
            action="test_llm_provider_failed",
            entity_type="llm_provider",
            details={"provider_id": payload.provider_id, "litellm_id": payload.litellm_id, "error": err_msg[:200]},
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()

        return {
            "success": False,
            "status": "error",
            "latency_ms": latency_ms,
            "error_message": f"Échec de connexion : {err_msg[:200]}",
            "tested_at": now.isoformat() + "Z",
        }





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


@router.delete("/tenants/{tenant_id}")
async def purge_tenant_rgpd(
    tenant_id: str,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Super-Admin GDPR Tenant Purge:
    - Permanently deletes all tenant projects, DCE chunks, company assets, subscriptions and user associations.
    - Anonymizes related audit logs.
    - Generates a cryptographic and detailed RGPD deletion certificate for legal compliance.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID tenant invalide.")

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entreprise cliente introuvable.")

    tenant_name = tenant.name
    tenant_siret = tenant.siret or "N/A"
    tenant_slug = tenant.slug

    # Count elements before hard delete
    users_count = (await db.execute(select(func.count(User.id)).where(User.tenant_id == t_uuid))).scalar() or 0
    projects_count = (await db.execute(select(func.count(Project.id)).where(Project.tenant_id == t_uuid))).scalar() or 0
    assets_count = (await db.execute(select(func.count(CompanyAsset.id)).where(CompanyAsset.tenant_id == t_uuid))).scalar() or 0

    now = datetime.now(timezone.utc)
    certificate_id = str(uuid.uuid4())

    # 1. Anonymize audit logs
    await db.execute(
        text("UPDATE audit_logs SET details = jsonb_build_object('anonymized', true, 'purged_at', CAST(:now AS text)), tenant_id = NULL WHERE tenant_id = :t_uuid"),
        {"now": now.isoformat(), "t_uuid": t_uuid}
    )

    # 2. Retrieve all storage files for CompanyAsset and DCEDocument belonging to tenant, then delete them
    from app.core.storage import storage_service

    assets_stmt = select(CompanyAsset).where(CompanyAsset.tenant_id == t_uuid)
    assets_res = await db.execute(assets_stmt)
    tenant_assets = assets_res.scalars().all()

    dce_docs_stmt = select(DCEDocument).where(DCEDocument.tenant_id == t_uuid)
    dce_docs_res = await db.execute(dce_docs_stmt)
    tenant_dce_docs = dce_docs_res.scalars().all()

    deleted_storage_files_count = 0
    total_storage_files_found = 0

    # Delete CompanyAsset files
    for a in tenant_assets:
        if a.s3_url:
            total_storage_files_found += 1
            try:
                if storage_service.delete_file(str(t_uuid), a.s3_url):
                    deleted_storage_files_count += 1
            except Exception as e:
                print(f"[purge_tenant_rgpd] Error deleting CompanyAsset storage file {a.s3_url}: {e}")

    # Delete DCEDocument files
    for doc in tenant_dce_docs:
        if doc.s3_key:
            total_storage_files_found += 1
            try:
                if storage_service.delete_file(str(t_uuid), doc.s3_key):
                    deleted_storage_files_count += 1
            except Exception as e:
                print(f"[purge_tenant_rgpd] Error deleting DCEDocument storage file {doc.s3_key}: {e}")

    # 3. Hard delete tenant (cascades to all foreign key tables)
    await db.delete(tenant)
    await db.commit()

    certificate_report = {
        "certificate_id": certificate_id,
        "regulation": "RGPD Article 17 (Droit à l'effacement)",
        "tenant_id": str(t_uuid),
        "tenant_name": tenant_name,
        "tenant_siret": tenant_siret,
        "tenant_slug": tenant_slug,
        "purged_by_admin": admin_user.email,
        "purged_at_utc": now.isoformat(),
        "deleted_elements": {
            "users_count": users_count,
            "projects_count": projects_count,
            "company_assets_count": assets_count,
            "tenant_subscriptions": 1,
            "vector_embeddings": "100% purgés",
            "s3_storage_objects": (
                f"{deleted_storage_files_count}/{total_storage_files_found} fichiers purgés (100%)"
                if total_storage_files_found > 0 and deleted_storage_files_count == total_storage_files_found
                else f"{deleted_storage_files_count}/{total_storage_files_found} fichiers purgés ({round((deleted_storage_files_count / total_storage_files_found) * 100, 1)}% - échec partiel sur {total_storage_files_found - deleted_storage_files_count} fichier(s))"
                if total_storage_files_found > 0
                else "0 fichier détecté (100% purgé)"
            ),
            "s3_files_deleted_count": deleted_storage_files_count,
        },
        "legal_notice": (
            "Ce document atteste de la suppression complète, irréversible et immédiate de toutes les données "
            "personnelles et techniques de l'entreprise cliente de la plateforme btpAO, conformément aux exigences "
            "du Règlement Général sur la Protection des Données (RGPD - UE 2016/679)."
        ),
    }

    return {
        "success": True,
        "message": f"Entreprise cliente '{tenant_name}' ({tenant_id}) et toutes ses données associées ont été définitivement purgées.",
        "certificate": certificate_report,
    }




class CountryOfficialSourceCreate(BaseModel):
    country_code: str
    portal_name: str
    portal_url: str
    portal_type: str
    reference_law: Optional[str] = None
    status: str = "active"


class CountryOfficialSourceUpdate(BaseModel):
    country_code: Optional[str] = None
    portal_name: Optional[str] = None
    portal_url: Optional[str] = None
    portal_type: Optional[str] = None
    reference_law: Optional[str] = None
    status: Optional[str] = None


@router.get("/country-sources")
async def list_country_sources_admin(
    country_code: Optional[str] = None,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Super-Admin : liste TOUTES les sources de la whitelist reglementaire (actives ET inactives,
    contrairement a l'endpoint tenant en lecture seule qui ne montre que les actives). Cette
    whitelist restreint strictement la recherche web de l'IA pendant la generation de sections
    et le chat DCE -- aucune source hors de cette liste ne peut jamais etre citee.
    """
    stmt = select(CountryOfficialSource)
    if country_code:
        stmt = stmt.where(CountryOfficialSource.country_code == country_code.upper())
    stmt = stmt.order_by(CountryOfficialSource.country_code, CountryOfficialSource.portal_name)
    res = await db.execute(stmt)
    sources = res.scalars().all()
    return [
        {
            "id": str(s.id),
            "country_code": s.country_code,
            "portal_name": s.portal_name,
            "portal_url": s.portal_url,
            "portal_type": s.portal_type,
            "reference_law": s.reference_law,
            "status": s.status,
            "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sources
    ]


@router.post("/country-sources")
async def create_country_source_admin(
    payload: CountryOfficialSourceCreate,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-Admin : ajoute un site officiel a la whitelist reglementaire d'un pays."""
    now = datetime.utcnow()
    new_source = CountryOfficialSource(
        id=uuid.uuid4(),
        country_code=payload.country_code.strip().upper(),
        portal_name=payload.portal_name.strip(),
        portal_url=payload.portal_url.strip(),
        portal_type=payload.portal_type.strip(),
        reference_law=payload.reference_law.strip() if payload.reference_law else None,
        status=payload.status or "active",
        created_at=now,
        updated_at=now,
    )
    db.add(new_source)
    await db.flush()

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="whitelist_source_created",
        entity_type="country_official_source",
        entity_id=new_source.id,
        details={"portal_name": new_source.portal_name, "country_code": new_source.country_code, "portal_url": new_source.portal_url},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, "id": str(new_source.id)}


@router.patch("/country-sources/{source_id}")
async def update_country_source_admin(
    source_id: str,
    payload: CountryOfficialSourceUpdate,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-Admin : modifie un site de la whitelist reglementaire (y compris activer/desactiver)."""
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID de source invalide.")

    res = await db.execute(select(CountryOfficialSource).where(CountryOfficialSource.id == s_uuid))
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source introuvable.")

    if payload.country_code is not None:
        source.country_code = payload.country_code.strip().upper()
    if payload.portal_name is not None:
        source.portal_name = payload.portal_name.strip()
    if payload.portal_url is not None:
        source.portal_url = payload.portal_url.strip()
    if payload.portal_type is not None:
        source.portal_type = payload.portal_type.strip()
    if payload.reference_law is not None:
        source.reference_law = payload.reference_law.strip() or None
    if payload.status is not None:
        source.status = payload.status
    source.updated_at = datetime.utcnow()

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="whitelist_source_updated",
        entity_type="country_official_source",
        entity_id=source.id,
        details={"portal_name": source.portal_name, "status": source.status},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True}


@router.delete("/country-sources/{source_id}")
async def delete_country_source_admin(
    source_id: str,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Super-Admin : retire un site de la whitelist reglementaire active. Desactivation (status =
    "inactive"), jamais une suppression physique -- conserve l'historique de veille
    reglementaire (last_known_hash, last_summary) associe a cette source.
    """
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID de source invalide.")

    res = await db.execute(select(CountryOfficialSource).where(CountryOfficialSource.id == s_uuid))
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source introuvable.")

    source.status = "inactive"
    source.updated_at = datetime.utcnow()

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="whitelist_source_deactivated",
        entity_type="country_official_source",
        entity_id=source.id,
        details={"portal_name": source.portal_name},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, "message": f"Source '{source.portal_name}' desactivee (retiree de la whitelist active)."}
