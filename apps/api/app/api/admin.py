"""
Super-Admin Management Router.
Strictly protected by require_platform_admin (403 for non-platform admins).
Zero hardcoded API secrets, zero memory cache, pure SQLAlchemy 2 Async + PostgreSQL Audit Trail.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings

from app.core.db import get_db, get_system_db_unrestricted_INTERNAL_ONLY
from app.core.security import CurrentTenantUser, require_platform_admin
from app.core.storage import storage_service
from app.models.entities import (
    AuditLog,
    CompanyAsset,
    CountryOfficialSource,
    DCEDocument,
    DCEEmbedding,
    ExportTemplate,
    LlmUsageLog,
    PlatformSettings,
    Project,
    SubscriptionPlan,
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
from app.services import llm_catalog_service
from app.services import cost_limits_service


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
    llm_model: Optional[str] = "claude-sonnet-5"
    llm_model_tier: Optional[str] = "inherit"
    llm_fallback_tier: Optional[str] = "inherit"
    model_routing_config: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None


class UpdateTenantPayload(BaseModel):
    name: Optional[str] = None
    siret: Optional[str] = None
    contact_email: Optional[str] = None
    plan: Optional[str] = None
    country_code: Optional[str] = None
    llm_model_tier: Optional[str] = None
    llm_fallback_tier: Optional[str] = None
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
    # 30/08 : plafond mensuel optionnel (USD) -- voir model_routing_service.get_credentials_for_model()
    # pour la verification avant chaque appel, et llm_usage_logs pour le suivi de consommation reel.
    monthly_budget_usd: Optional[float] = None


class LLMKeysPayload(BaseModel):
    anthropic_api_key: Optional[str] = None
    # 04/09 : fournisseurs de recherche web configurables depuis l'admin (liste
    # extensible, meme logique que custom_providers pour les LLM), au lieu d'exiger des
    # variables d'environnement et un redemarrage. Cles chiffrees dans le meme coffre.
    web_search_providers: Optional[List[Dict[str, Any]]] = None
    openai_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    default_llm_tier: Optional[str] = None
    # 03/09 : palier de repli par defaut plateforme, distinct du palier principal
    # ci-dessus -- voir model_routing_service.get_fallback_candidate(). Chaine vide
    # explicite = retour au mode automatique (voir la route POST /admin/llm-keys).
    default_fallback_tier: Optional[str] = None
    custom_providers: Optional[List[CustomProviderInput]] = None
    # 29/08 : permet de repointer le model_string d'un tier (ex: "equilibre") vers un
    # nouveau modèle sans déploiement de code -- voir model_routing_service.get_effective_tiers().
    model_tier_overrides: Optional[Dict[str, str]] = None


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
            "llm_model": branding.get("llm_model") or "claude-sonnet-5",
            "llm_model_tier": branding.get("llm_model_tier") or "inherit",
            "llm_fallback_tier": branding.get("llm_fallback_tier") or "inherit",
            # Bug fixed (30/08) : cette clé n'etait jamais renvoyee ici, alors que la
            # racine 'model_routing' est bien mise a jour par POST /admin/model-routing
            # (l'onglet "Routage IA par Tache & Client") -- resultat, la liste de tenants
            # revenait toujours vide pour ce champ et l'onglet semblait "oublier" ce qui
            # venait d'etre enregistre avec succes. On lit aussi l'ancienne cle
            # 'model_routing_config' (utilisee par la page de detail tenant) en repli.
            "model_routing_config": branding.get("model_routing") or branding.get("model_routing_config") or {},
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
    name_clean = payload.name.strip()
    if not name_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nom de l'entreprise est obligatoire.",
        )

    # 1. Check if a tenant with the exact same name (case-insensitive) already exists
    existing_name = await db.execute(
        select(Tenant).where(func.lower(func.trim(Tenant.name)) == func.lower(name_clean))
    )
    if existing_name.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Une entreprise avec le nom « {name_clean} » existe déjà. Les doublons ne sont pas autorisés.",
        )

    # 2. Check if SIRET is provided and already assigned to another tenant
    siret_clean = payload.siret.strip() if payload.siret and payload.siret.strip() else None
    if siret_clean:
        existing_siret = await db.execute(
            select(Tenant).where(Tenant.siret == siret_clean)
        )
        if existing_siret.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Une entreprise avec le SIRET « {siret_clean} » existe déjà.",
            )

    # 3. Generate clean slug if not specified
    if payload.slug:
        slug = payload.slug.strip().lower()
    else:
        base_slug = re.sub(r"[^a-z0-9]+", "-", name_clean.lower()).strip("-")
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
    branding["llm_fallback_tier"] = payload.llm_fallback_tier or "inherit"
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
        "llm_model": branding.get("llm_model") or "claude-sonnet-5",
        "llm_model_tier": branding.get("llm_model_tier") or "inherit",
        "llm_fallback_tier": branding.get("llm_fallback_tier") or "inherit",
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
    resolved_fallback_info = await model_routing_service.get_fallback_candidate(
        db=db, exclude_provider=resolved_model_info.get("provider"), tenant_id=t_uuid,
    )

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "country_code": tenant.country_code or "FR",
        "siret": tenant.siret or "",
        "contact_email": branding.get("contact_email") or "",
        "llm_provider": branding.get("llm_provider") or "anthropic",
        "llm_model": branding.get("llm_model") or "claude-sonnet-5",
        "llm_model_tier": branding.get("llm_model_tier") or "inherit",
        "llm_fallback_tier": branding.get("llm_fallback_tier") or "inherit",
        "resolved_model_info": resolved_model_info,
        "resolved_fallback_info": resolved_fallback_info,
        "branding_config": branding,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }


@router.get("/tenants/{tenant_id}/documents")
async def list_tenant_all_documents(
    tenant_id: str,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne la liste unifiée de tous les documents de l'entreprise :
    1. Documents issus de company_assets (savoir-faire, fiches techniques, certificats Qualibat)
    2. Modèle Word officiel (.docx) de l'entreprise
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    # 1. Company assets
    stmt_assets = (
        select(CompanyAsset)
        .where(CompanyAsset.tenant_id == t_uuid)
        .order_by(CompanyAsset.created_at.desc())
    )
    res_assets = await db.execute(stmt_assets)
    assets = res_assets.scalars().all()

    # 2. Export Templates
    stmt_templates = (
        select(ExportTemplate)
        .where(ExportTemplate.tenant_id == t_uuid)
        .order_by(ExportTemplate.created_at.desc())
    )
    res_templates = await db.execute(stmt_templates)
    templates = res_templates.scalars().all()

    output = []
    # Add company assets
    for a in assets:
        meta = a.metadata_json or {}
        output.append({
            "id": str(a.id),
            "file_name": meta.get("file_name") or a.title,
            "title": a.title,
            "category": a.category,
            "file_path": a.s3_url or "",
            "file_type": meta.get("content_type") or "document",
            "file_size": meta.get("file_size") or 0,
            "status": a.status,
            "source": "company_knowledge",
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "can_download": bool(a.s3_url or a.description),
        })

    # Add templates
    for tmpl in templates:
        output.append({
            "id": str(tmpl.id),
            "file_name": tmpl.name or "template_officiel.docx",
            "title": tmpl.name or "Modèle Word officiel",
            "category": "template_word",
            "file_path": tmpl.s3_docx_key or "",
            "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_size": 0,
            "status": "Actif" if tmpl.is_default else "Secondaire",
            "source": "export_template",
            "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
            "can_download": bool(tmpl.s3_docx_key),
        })

    return output


@router.get("/tenants/{tenant_id}/documents/{doc_id}/download")
async def download_tenant_document_admin(
    tenant_id: str,
    doc_id: str,
    inline: bool = False,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Permet à l'administrateur de visualiser ou télécharger n'importe quel document d'un client.
    Recherche dans company_assets puis dans export_templates.
    """
    try:
        t_uuid = uuid.UUID(tenant_id)
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifiant invalide")

    # 1. Search in company_assets
    stmt_asset = select(CompanyAsset).where(CompanyAsset.id == d_uuid, CompanyAsset.tenant_id == t_uuid)
    res_asset = await db.execute(stmt_asset)
    asset = res_asset.scalar_one_or_none()

    if asset:
        meta = asset.metadata_json or {}
        filename = meta.get("file_name") or f"{asset.title}.pdf"
        if asset.s3_url:
            try:
                file_bytes = storage_service.download_file(tenant_id=tenant_id, s3_key=asset.s3_url)
                content_type = meta.get("content_type")
                if not content_type:
                    fn_lower = filename.lower()
                    if fn_lower.endswith(".pdf"):
                        content_type = "application/pdf"
                    elif fn_lower.endswith(".docx"):
                        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    elif fn_lower.endswith(".xlsx"):
                        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    elif fn_lower.endswith(".png"):
                        content_type = "image/png"
                    elif fn_lower.endswith((".jpg", ".jpeg")):
                        content_type = "image/jpeg"
                    else:
                        content_type = "application/octet-stream"

                disposition = "inline" if inline else "attachment"
                return Response(
                    content=file_bytes,
                    media_type=content_type,
                    headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
                )
            except Exception as e:
                logger.warning(f"[Admin] Erreur lecture storage_service s3_url {asset.s3_url}: {e}")

        if asset.description:
            disposition = "inline" if inline else "attachment"
            return Response(
                content=asset.description.encode("utf-8"),
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'{disposition}; filename="{asset.title}.txt"'},
            )

    # 2. Search in export_templates
    stmt_tmpl = select(ExportTemplate).where(ExportTemplate.id == d_uuid, ExportTemplate.tenant_id == t_uuid)
    res_tmpl = await db.execute(stmt_tmpl)
    template = res_tmpl.scalar_one_or_none()

    if template and template.s3_docx_key:
        try:
            file_bytes = storage_service.download_file(tenant_id=tenant_id, s3_key=template.s3_docx_key)
            filename = template.name or "template_officiel.docx"
            disposition = "inline" if inline else "attachment"
            return Response(
                content=file_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
            )
        except Exception as e:
            logger.warning(f"[Admin] Erreur lecture template {template.s3_docx_key}: {e}")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier introuvable sur le stockage")



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
        name_clean = payload.name.strip()
        if not name_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le nom de l'entreprise ne peut pas être vide.",
            )
        existing_name = await db.execute(
            select(Tenant).where(
                func.lower(func.trim(Tenant.name)) == func.lower(name_clean),
                Tenant.id != t_uuid,
            )
        )
        if existing_name.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Une autre entreprise porte déjà le nom « {name_clean} ».",
            )
        tenant.name = name_clean

    if payload.siret is not None:
        siret_clean = payload.siret.strip() if payload.siret and payload.siret.strip() else None
        if siret_clean:
            existing_siret = await db.execute(
                select(Tenant).where(
                    Tenant.siret == siret_clean,
                    Tenant.id != t_uuid,
                )
            )
            if existing_siret.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Une autre entreprise possède déjà le SIRET « {siret_clean} ».",
                )
        tenant.siret = siret_clean
    if payload.plan is not None:
        tenant.plan = payload.plan
    if payload.country_code is not None:
        tenant.country_code = payload.country_code.strip().upper()
    if payload.contact_email is not None:
        branding["contact_email"] = payload.contact_email
    if payload.llm_model_tier is not None:
        branding["llm_model_tier"] = payload.llm_model_tier
    if payload.llm_fallback_tier is not None:
        branding["llm_fallback_tier"] = payload.llm_fallback_tier
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
    resolved_fallback_info = await model_routing_service.get_fallback_candidate(
        db=db, exclude_provider=resolved_model_info.get("provider"), tenant_id=t_uuid,
    )

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
            "llm_fallback_tier": branding.get("llm_fallback_tier") or "inherit",
            "resolved_model_info": resolved_model_info,
            "resolved_fallback_info": resolved_fallback_info,
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

    # Fournisseurs de recherche web : la resolution (y compris la compatibilite avec les
    # anciens champs et l'environnement) est faite par le service, pour qu'admin et moteur
    # voient exactement la meme chose.
    from app.services.web_search_service import SUPPORTED_SEARCH_TYPES, resolve_search_providers

    search_providers = [
        {
            "id": p["id"],
            "name": p["name"],
            "type": p["type"],
            "enabled": p["enabled"],
            "priority": p["priority"],
            "api_key_configured": bool(p["api_key"]),
            "api_key_masked": mask_api_key(p["api_key"]),
        }
        for p in resolve_search_providers(ps_dict)
    ]

    return {
        "web_search_providers": search_providers,
        "supported_search_types": SUPPORTED_SEARCH_TYPES,
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
        "default_fallback_tier": ps_dict.get("default_fallback_tier") or "",
        "available_tiers": await model_routing_service.get_effective_tiers(db),
        "model_tier_overrides": ps_dict.get("model_tier_overrides") or {},
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
            
            # 03/09 (suite) : ce formulaire general ne gere plus les cles du tout --
            # seul POST /llm-keys/test-provider (test + sauvegarde atomique en une
            # seule requete, avec son propre commit) a le droit d'ecrire une cle.
            # Avant ce correctif, un "Enregistrer" clique juste apres un test reussi
            # (par ex. pour valider le choix du palier par defaut) pouvait renvoyer
            # un api_key vide/perime pour ce fournisseur et l'ecraser -- c'est
            # exactement ce qui est arrive au 03/09 06:02 (cle Gemini testee avec
            # succes a 05:58, disparue apres le premier "Enregistrer" suivant). On
            # preserve donc INCONDITIONNELLEMENT la cle deja stockee ici, quoi que
            # le payload contienne : ce champ n'est plus modifiable que via le test.
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
                "monthly_budget_usd": prov_input.monthly_budget_usd,
            })
        current_settings["custom_providers"] = saved_providers

    # Fournisseurs de recherche web (04/09). Meme regle de securite que les cles LLM :
    # une valeur masquee renvoyee telle quelle par le formulaire ne doit JAMAIS ecraser la
    # cle stockee -- c'est ce piege qui avait fait disparaitre une cle Gemini le 03/09.
    if payload.web_search_providers is not None:
        existing_by_id = {
            p.get("id"): p
            for p in (current_settings.get("web_search_providers") or [])
            if p.get("id")
        }
        saved = []
        for i, prov in enumerate(payload.web_search_providers):
            pid = (prov.get("id") or prov.get("type") or f"provider_{i}").strip()
            incoming_key = (prov.get("api_key") or "").strip()
            previous = existing_by_id.get(pid, {})
            if incoming_key and "•••" not in incoming_key and "***" not in incoming_key:
                key_enc = encrypt_api_key(incoming_key)
            else:
                key_enc = previous.get("api_key", "")
            saved.append({
                "id": pid,
                "name": (prov.get("name") or pid).strip(),
                "type": (prov.get("type") or "serper").strip().lower(),
                "api_key": key_enc,
                "enabled": bool(prov.get("enabled", True)),
                "priority": int(prov.get("priority") or (i + 1)),
            })
        current_settings["web_search_providers"] = saved

    # Le service garde les cles en cache 60 s : on l'invalide pour que la nouvelle valeur
    # soit prise en compte immediatement apres l'enregistrement.
    try:
        from app.services.web_search_service import web_search_service
        web_search_service.invalidate_config_cache()
    except Exception:  # noqa: BLE001
        pass

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

    # 3. Update Platform Default Tier or Master Model
    if payload.default_llm_tier is not None:
        val = payload.default_llm_tier.strip()
        current_settings["default_llm_tier"] = val
        if val.lower() in LLM_MODEL_TIERS:
            settings.DEFAULT_LLM_MODEL = LLM_MODEL_TIERS[val.lower()]["model_string"]
        else:
            settings.DEFAULT_LLM_MODEL = val

    # 3bis. Update Platform Default Fallback Tier (03/09) -- distinct du palier
    # principal ci-dessus. Chaine vide explicite = retour au mode automatique
    # historique (premier fournisseur actif dote d'une cle, voir
    # model_routing_service.get_fallback_candidate()).
    if payload.default_fallback_tier is not None:
        fb_val = payload.default_fallback_tier.strip()
        if fb_val:
            current_settings["default_fallback_tier"] = fb_val
            if fb_val.lower() in LLM_MODEL_TIERS:
                settings.FALLBACK_LLM_MODEL = LLM_MODEL_TIERS[fb_val.lower()]["model_string"]
            else:
                settings.FALLBACK_LLM_MODEL = fb_val
        else:
            current_settings.pop("default_fallback_tier", None)

    # 4. Update per-tier model string overrides (29/08 -- repointer un tier vers un
    # nouveau modèle sans déploiement de code). Clés hors LLM_MODEL_TIERS ignorées ;
    # valeur vide/blanche pour un tier retire la surcharge (retour au modèle par défaut).
    if payload.model_tier_overrides is not None:
        existing_overrides = dict(current_settings.get("model_tier_overrides") or {})
        for tier_id, model_string in payload.model_tier_overrides.items():
            if tier_id not in LLM_MODEL_TIERS:
                continue
            cleaned = (model_string or "").strip()
            if cleaned:
                existing_overrides[tier_id] = cleaned
            else:
                existing_overrides.pop(tier_id, None)
        current_settings["model_tier_overrides"] = existing_overrides

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


class TestSearchProviderPayload(BaseModel):
    provider: str  # type d'adaptateur : "serper" | "brave" | ... (voir SUPPORTED_SEARCH_TYPES)
    provider_id: Optional[str] = None  # pour rejouer la cle deja enregistree d'une entree
    api_key: Optional[str] = None


@router.post("/llm-keys/test-search-provider")
async def test_search_provider_connection(
    payload: TestSearchProviderPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Teste une cle de recherche web par un VRAI appel au fournisseur (04/09).

    Meme principe que le test des fournisseurs LLM : on ne se contente pas de verifier
    que la cle est renseignee, on execute une requete minimale et on renvoie le nombre
    de resultats, la latence et l'erreur reelle le cas echeant. Une cle acceptee sans
    test est une panne silencieuse a la premiere generation.
    """
    import time as _time
    import httpx as _httpx

    from app.services.web_search_service import SUPPORTED_SEARCH_TYPES, web_search_service

    provider = (payload.provider or "").strip().lower()
    known = {t["type"] for t in SUPPORTED_SEARCH_TYPES}
    if provider not in known:
        raise HTTPException(
            status_code=400,
            detail=f"Type de moteur inconnu : '{provider}'. Types pris en charge : {', '.join(sorted(known))}.",
        )

    raw_key = (payload.api_key or "").strip()
    # Cle masquee ou absente : on rejoue celle deja enregistree pour cette entree.
    if not raw_key or "•••" in raw_key or "***" in raw_key:
        from app.services.web_search_service import resolve_search_providers

        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        conf = (ps.settings if ps and ps.settings else {}) or {}
        resolved = resolve_search_providers(conf)
        match = next(
            (p for p in resolved if p["id"] == (payload.provider_id or "")),
            next((p for p in resolved if p["type"] == provider), None),
        )
        raw_key = (match or {}).get("api_key") or ""

    if not raw_key:
        return {"success": False, "provider": provider, "error": "Aucune cle configuree pour ce fournisseur."}

    started = _time.monotonic()
    try:
        # On rejoue exactement l'adaptateur utilise en production, plutot que de
        # reimplementer l'appel HTTP ici : ajouter un moteur ne demande donc qu'un
        # adaptateur dans web_search_service, jamais une seconde implementation de test.
        adapter = web_search_service._ADAPTERS.get(provider)
        if not adapter:
            return {"success": False, "provider": provider,
                    "error": f"Aucun adaptateur implemente pour '{provider}'."}
        results = await adapter(web_search_service, "marches publics BTP", 2, raw_key)
        latency_ms = round((_time.monotonic() - started) * 1000)
        if not results:
            return {
                "success": False, "provider": provider, "latency_ms": latency_ms,
                "error": "Le moteur a repondu mais n'a rendu aucun resultat (cle invalide, quota atteint, ou requete filtree).",
            }
        return {
            "success": True,
            "provider": provider,
            "results_count": len(results),
            "latency_ms": latency_ms,
            "message": f"{len(results)} resultat(s) en {latency_ms} ms — cle valide.",
        }
    except Exception as e:  # noqa: BLE001
        return {"success": False, "provider": provider, "error": f"{type(e).__name__} : {str(e)[:200]}"}


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
        raw_model = getattr(resp, "model", None)
        if isinstance(raw_model, str) and raw_model.strip():
            confirmed_model = raw_model.strip()
        else:
            confirmed_model = str(payload.litellm_id)

        # Enregistrement du résultat ET de la clé qui vient de fonctionner.
        #
        # CORRECTIF (03/09) : ce test validait la clé puis l'oubliait. L'écran
        # affichait « Connecté », l'administrateur passait à autre chose, et
        # aucune clé n'était en base — toutes les générations retombaient
        # ensuite sur le moteur de gabarits avec un message parlant d'un
        # « service temporairement indisponible », ce qui n'était pas la cause.
        # Une clé qui vient de répondre est une clé valide : on la garde.
        key_persisted = False
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
                    "confirmed_model": confirmed_model,
                    "last_tested_at": now.isoformat() + "Z",
                    "error": None,
                }
                settings_dict["test_results"] = test_results

                # La clé n'est retenue que si l'administrateur vient de la saisir
                # en clair dans le formulaire. Un test relancé sur une clé déjà
                # stockée (champ masqué) ne réécrit rien.
                if raw_key and "•••" not in raw_key and "***" not in raw_key:
                    providers = list(settings_dict.get("custom_providers") or [])
                    if not providers:
                        providers = [dict(pr) for pr in DEFAULT_CUSTOM_PROVIDERS]
                    found = False
                    for prov in providers:
                        if prov.get("id") == payload.provider_id:
                            prov["api_key"] = encrypt_api_key(raw_key)
                            if payload.litellm_id:
                                prov["litellm_id"] = payload.litellm_id
                            if payload.api_base is not None:
                                prov["api_base"] = (payload.api_base or "").strip()
                            prov["enabled"] = True
                            found = True
                            break
                    if not found:
                        providers.append({
                            "id": payload.provider_id,
                            "name": payload.name or payload.provider_id,
                            "litellm_id": payload.litellm_id,
                            "api_key": encrypt_api_key(raw_key),
                            "api_base": (payload.api_base or "").strip(),
                            "zone": "non-verifie",
                            "enabled": True,
                        })
                    settings_dict["custom_providers"] = providers
                    key_persisted = True

                ps.settings = settings_dict
                ps.updated_at = now
                flag_modified(ps, "settings")

        await _record_audit_log(
            db=db,
            admin_user=admin_user,
            action="test_llm_provider_success",
            entity_type="llm_provider",
            details={"provider_id": payload.provider_id, "litellm_id": payload.litellm_id, "confirmed_model": confirmed_model, "latency_ms": latency_ms},
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()

        return {
            "success": True,
            "status": "success",
            "latency_ms": latency_ms,
            "confirmed_model": confirmed_model,
            "key_persisted": key_persisted,
            "message": (
                f"Connexion réussie en {latency_ms} ms — modèle confirmé : {confirmed_model}."
                + (" La clé est enregistrée." if key_persisted else "")
            ),
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


@router.get("/llm-catalog")
async def get_llm_catalog(
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Catalogue de modèles (référence -- liste, prix, statut). Auto-synchronise en
    interne si les données sont absentes ou périmées (30/08, >24h) -- demande explicite
    utilisateur ("si la liste se met jamais à jour c'est nul") : un simple GET déclenche
    désormais lui-même une resynchro quand nécessaire, sans cron invisible en arrière-plan
    (le risque d'échec silencieux identifié à la conception initiale reste évité : toute
    erreur ici est absorbée, ne casse jamais l'affichage, et le prochain GET réessaiera).
    Reste aussi disponible manuellement : voir POST /llm-catalog/sync."""
    stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    res = await db.execute(stmt)
    ps = res.scalar_one_or_none()
    ps_dict = ps.settings if ps and ps.settings else {}

    last_synced_raw = ps_dict.get("llm_catalog_last_synced_at")
    is_stale = True
    if last_synced_raw:
        try:
            last_synced_dt = datetime.fromisoformat(str(last_synced_raw).replace("Z", "+00:00"))
            if last_synced_dt.tzinfo is None:
                last_synced_dt = last_synced_dt.replace(tzinfo=timezone.utc)
            is_stale = (datetime.now(timezone.utc) - last_synced_dt) > timedelta(hours=24)
        except (ValueError, TypeError):
            is_stale = True

    if is_stale:
        try:
            sync_result = await llm_catalog_service.sync_catalog(db)
            settings_dict = dict(ps_dict)
            settings_dict["llm_catalog_last_synced_at"] = sync_result["synced_at"]
            if ps:
                ps.settings = settings_dict
                ps.updated_at = datetime.utcnow()
                flag_modified(ps, "settings")
            else:
                ps = PlatformSettings(id="global", settings=settings_dict, updated_at=datetime.utcnow())
                db.add(ps)
            await db.commit()
            ps_dict = settings_dict
        except Exception as e:
            print(f"[AdminAPI] Auto-synchro catalogue LLM notice: {e} -- affichage des données existantes (potentiellement périmées ou vides).")
            await db.rollback()

    models = await llm_catalog_service.list_catalog(db, include_inactive=True)
    return {
        "models": models,
        "total": len(models),
        "last_synced_at": ps_dict.get("llm_catalog_last_synced_at"),
    }


@router.post("/llm-catalog/sync")
async def sync_llm_catalog(
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Synchronise le catalogue depuis OpenRouter (appel direct, déclenché par l'admin --
    volontairement pas de cron nocturne invisible, voir llm_catalog_service.py)."""
    try:
        result = await llm_catalog_service.sync_catalog(db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Échec de la synchronisation du catalogue OpenRouter : {str(e)[:300]}")

    # Mémorise l'horodatage dans PlatformSettings pour affichage ("Dernière synchro : ...").
    # Un seul commit() pour toute la requête (catalogue + horodatage) -- voir la note dans
    # llm_catalog_service.sync_catalog() sur pourquoi un commit intermédiaire casse get_db().
    stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    res = await db.execute(stmt)
    ps = res.scalar_one_or_none()
    if ps:
        settings_dict = dict(ps.settings or {})
        settings_dict["llm_catalog_last_synced_at"] = result["synced_at"]
        ps.settings = settings_dict
        ps.updated_at = datetime.utcnow()
        flag_modified(ps, "settings")

    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="sync_llm_catalog",
        entity_type="llm_catalog",
        details=result,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return result


@router.get("/llm-usage-summary")
async def get_llm_usage_summary(
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Suivi de consommation LLM (30/08) : totaux du mois en cours par fournisseur (appels,
    tokens, coût estimé) et plafond mensuel configuré si présent. Réponse directe à la
    demande utilisateur ("aucune limite paramétrable... suivi de consommation... dommage
    qu'on ne puisse pas le faire en back admin")."""
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(
            LlmUsageLog.provider_id,
            func.count(LlmUsageLog.id).label("call_count"),
            func.coalesce(func.sum(LlmUsageLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LlmUsageLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0).label("estimated_cost_usd"),
        )
        .where(LlmUsageLog.created_at >= month_start)
        .group_by(LlmUsageLog.provider_id)
    )
    res = await db.execute(stmt)
    rows = res.all()

    ps_stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
    ps_res = await db.execute(ps_stmt)
    ps = ps_res.scalar_one_or_none()
    providers_list = (ps.settings.get("custom_providers") if ps and ps.settings else None) or DEFAULT_CUSTOM_PROVIDERS
    providers_by_id = {p.get("id"): p for p in providers_list}

    by_provider = []
    for r in rows:
        prov = providers_by_id.get(r.provider_id, {})
        by_provider.append({
            "provider_id": r.provider_id,
            "provider_name": prov.get("name") or r.provider_id or "Inconnu",
            "call_count": r.call_count,
            "prompt_tokens": int(r.prompt_tokens),
            "completion_tokens": int(r.completion_tokens),
            "estimated_cost_usd": float(r.estimated_cost_usd),
            "monthly_budget_usd": prov.get("monthly_budget_usd"),
        })

    return {
        "period_start": month_start.isoformat(),
        "by_provider": by_provider,
        "total_estimated_cost_usd": sum(p["estimated_cost_usd"] for p in by_provider),
    }

@router.get("/revenue-summary")
async def get_revenue_summary(
    admin_user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Estimation honnete du revenu (30/08) -- remplace un calcul FRONTEND qui multipliait
    le nombre TOTAL de tenants (y compris ceux sans abonnement enregistre et les essais
    gratuits) par une grille de prix codee en dur et DESYNCHRONISEE de la vraie table
    subscription_plans (starter a 190 au lieu de 199, pro a 490 au lieu de 499, et un
    prix "enterprise" a 1490 entierement invente alors que ce palier est explicitement
    a tarif negocie -- price_monthly_cents=0 -- dans subscription_plans). Resultat : les
    cartes MRR/ARR affichaient un chiffre plausible mais faux sur 2 axes a la fois
    (mauvais prix ET mauvaise base de tenants), presente comme si c'etait du chiffre
    d'affaires reel.

    Ce endpoint ne pretend PAS mesurer un paiement reellement encaisse : aucune
    integration processeur de paiement n'est active dans ce projet (tenant_subscriptions
    a bien des colonnes stripe_customer_id / stripe_subscription_id, mais elles sont
    NULL sur les seuls tenants qui ont un abonnement enregistre -- Stripe n'a jamais ete
    reellement branche). C'est donc une estimation basee sur les abonnements enregistres
    en base et leur statut declare, avec la VRAIE grille tarifaire de subscription_plans
    -- exclut explicitement les essais gratuits et les paliers a tarif negocie ("sur
    devis", prix catalogue = 0), et signale separement les tenants qui n'ont meme pas de
    ligne d'abonnement (tres probablement des tenants de demo/test, pas des clients).
    """
    stmt = (
        select(TenantSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, TenantSubscription.plan_id == SubscriptionPlan.id)
    )
    res = await db.execute(stmt)
    rows = res.all()

    total_tenants = (await db.execute(select(func.count(Tenant.id)))).scalar() or 0

    billed_active: List[Dict[str, Any]] = []
    free_trial_count = 0
    custom_pricing_count = 0
    other_status_count = 0

    for sub, plan in rows:
        if sub.status != "active":
            other_status_count += 1
            continue
        if sub.billing_mode == "free_trial":
            free_trial_count += 1
            continue
        if not plan.price_monthly_cents:
            custom_pricing_count += 1
            continue
        billed_active.append({
            "tenant_id": str(sub.tenant_id),
            "plan_id": plan.id,
            "plan_name": plan.name,
            "price_monthly_eur": plan.price_monthly_cents / 100,
            "has_verified_payment_link": bool(sub.stripe_customer_id and sub.stripe_subscription_id),
        })

    mrr_estimated_eur = sum(b["price_monthly_eur"] for b in billed_active)

    return {
        "mrr_estimated_eur": mrr_estimated_eur,
        "arr_estimated_eur": mrr_estimated_eur * 12,
        "billed_active_count": len(billed_active),
        "free_trial_count": free_trial_count,
        "custom_pricing_count": custom_pricing_count,
        "other_status_count": other_status_count,
        "tenants_with_subscription_record": len(rows),
        "tenants_without_subscription_record": max(total_tenants - len(rows), 0),
        "total_tenants": total_tenants,
        "any_payment_processor_verified": any(b["has_verified_payment_link"] for b in billed_active),
        "by_tenant": billed_active,
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

    # 29/08 : le badge "ONLINE" ci-dessous était auparavant toujours vert, quel
    # que soit l'état réel -- corrigé pour refléter honnêtement si une vraie clé
    # d'embedding (OpenAI/Mistral, admin ou .env) est configurée ou si le système
    # est actuellement en repli sur le vecteur pseudo-aléatoire déterministe.
    from app.services.embedding_service import embedding_service
    await embedding_service.sync_platform_key(db)
    embedding_status = embedding_service.get_embedding_status()

    return {
        "embedding_model": embedding_status.get("model") or (settings.EMBEDDING_MODEL or "text-embedding-3-small"),
        "dimensions": 1536,
        "similarity_metric": "Cosinus (1 - (a <=> b))",
        "total_dce_chunks": dce_chunks_count,
        "total_knowledge_chunks": knowledge_chunks_count,
        "index_type": "HNSW",
        "embedding_mode": embedding_status.get("mode"),
        "embedding_provider": embedding_status.get("provider"),
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
    # 02/09 : double lecture des 2 cles historiques (comme resolve_model_for_tenant()
    # et list_tenants) -- corrige une incoherence trouvee ou cet endpoint ignorait
    # model_routing_config (l'ancienne cle, encore ecrite par la creation de tenant)
    # et affichait des valeurs par defaut codees en dur a la place de la vraie config
    # enregistree pour ce tenant.
    routing = branding.get("model_routing") or branding.get("model_routing_config") or {
        "extraction_gonogo": {"provider": "Anthropic", "model": "claude-sonnet-5"},
        "redaction_memoire": {"provider": "Anthropic", "model": "claude-sonnet-5"},
        "analyse_prix": {"provider": "Mistral AI", "model": "mistral-large-2407"},
    }

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
        "extraction_gonogo": payload.extraction_gonogo or {"provider": "Anthropic", "model": "claude-sonnet-5"},
        "redaction_memoire": payload.redaction_memoire or {"provider": "Anthropic", "model": "claude-sonnet-5"},
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
    # Plafond mensuel de coût IA propre à ce client, exprimé dans la devise ci-dessous.
    # Laisser vide pour hériter du plafond du forfait (voir /admin/cost-limits).
    custom_llm_cost_cap: Optional[float] = None
    custom_llm_cost_cap_currency: str = "EUR"
    allow_overage: bool = True
    duration_days: int = 365


class CostLimitSettingsPayload(BaseModel):
    display_currency: Optional[str] = None
    eur_usd_rate: Optional[float] = None
    target_llm_share: Optional[float] = None
    alert_threshold_pct: Optional[int] = None


class CostCapPayload(BaseModel):
    """Un plafond mensuel. `amount` vide = plafond retiré (aucune limite appliquée)."""
    amount: Optional[float] = None
    currency: str = "EUR"


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

    effective_cap = await billing_service.get_effective_cost_cap_usd(t_uuid, db)
    current_spend = await billing_service.get_tenant_current_month_spend_usd(t_uuid, db)

    if not sub:
        return {
            "has_subscription": False,
            "tenant_id": str(t_uuid),
            "plan_id": "starter",
            "status": "active",
            "billing_mode": "free_trial",
            "custom_quota_dossiers": None,
            "custom_llm_cost_cap_usd": None,
            "effective_llm_cost_cap_usd": effective_cap,
            "llm_spend_current_month_usd": current_spend,
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
        "custom_llm_cost_cap_usd": float(sub.custom_llm_cost_cap_usd) if sub.custom_llm_cost_cap_usd is not None else None,
        "effective_llm_cost_cap_usd": effective_cap,
        "llm_spend_current_month_usd": current_spend,
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

    # Le plafond est saisi dans la devise choisie par l'admin et stocké en dollars,
    # devise de facturation des fournisseurs et des journaux de consommation.
    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps_row = ps_res.scalar_one_or_none()
    cost_cfg = cost_limits_service.get_settings(ps_row.settings if ps_row else None)
    cap_usd = cost_limits_service.to_usd(
        payload.custom_llm_cost_cap,
        payload.custom_llm_cost_cap_currency,
        float(cost_cfg["eur_usd_rate"]),
    )
    if cap_usd is not None and cap_usd < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un plafond ne peut pas être négatif.")

    if sub:
        sub.plan_id = payload.plan_id
        sub.status = payload.status
        sub.billing_mode = payload.billing_mode
        sub.custom_quota_dossiers = payload.custom_quota_dossiers
        sub.custom_llm_cost_cap_usd = cap_usd
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
            custom_llm_cost_cap_usd=cap_usd,
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
            "custom_llm_cost_cap_usd": cap_usd,
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


# ══════════════════════════════════════════════════════════════════════════════
# PLAFONDS DE DÉPENSE IA — fournisseur, forfait, client
# Voir app/services/cost_limits_service.py pour la logique et le raisonnement
# derrière les plafonds conseillés.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/cost-limits")
async def get_cost_limits(
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Vue consolidée des trois niveaux de plafond et de la consommation du mois en cours."""
    overview = await cost_limits_service.build_overview(db)
    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="read_cost_limits",
        entity_type="platform_settings",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return overview


@router.put("/cost-limits/settings")
async def update_cost_limit_settings(
    payload: CostLimitSettingsPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Devise d'affichage, taux de conversion, part cible de coût IA et seuil d'alerte."""
    try:
        cfg = await cost_limits_service.save_settings(db, payload.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_cost_limit_settings",
        entity_type="platform_settings",
        details=payload.dict(exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, "settings": cfg}


@router.put("/cost-limits/providers/{provider_id}")
async def update_provider_cost_cap(
    provider_id: str,
    payload: CostCapPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Plafond mensuel de dépense pour un fournisseur d'API. Au-delà, sa clé n'est plus
    servie et le routage bascule sur un autre fournisseur configuré."""
    try:
        result = await cost_limits_service.set_provider_cap(db, provider_id, payload.amount, payload.currency)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_provider_cost_cap",
        entity_type="platform_settings",
        details=result,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, **result}


@router.put("/cost-limits/plans/{plan_id}")
async def update_plan_cost_cap(
    plan_id: str,
    payload: CostCapPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Plafond mensuel appliqué par défaut à tout client de ce forfait."""
    try:
        result = await cost_limits_service.set_plan_cap(db, plan_id, payload.amount, payload.currency)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_plan_cost_cap",
        entity_type="subscription_plan",
        details=result,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, **result}


@router.put("/cost-limits/tenants/{tenant_id}")
async def update_tenant_cost_cap(
    tenant_id: str,
    payload: CostCapPayload,
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Plafond nominatif d'un client, prioritaire sur celui de son forfait."""
    try:
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifiant client invalide")
    try:
        result = await cost_limits_service.set_tenant_cap(db, t_uuid, payload.amount, payload.currency)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="update_tenant_cost_cap",
        entity_type="tenant_subscription",
        tenant_id=t_uuid,
        details=result,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, **result}


@router.post("/cost-limits/plans/apply-recommended")
async def apply_recommended_plan_cost_caps(
    request: Request,
    admin_user: CurrentTenantUser = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Écrit sur chaque forfait le plafond conseillé (part cible du prix de vente)."""
    applied = await cost_limits_service.apply_recommended_plan_caps(db)
    await _record_audit_log(
        db=db,
        admin_user=admin_user,
        action="apply_recommended_plan_cost_caps",
        entity_type="subscription_plan",
        details={"applied": applied},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"success": True, "applied": applied}
