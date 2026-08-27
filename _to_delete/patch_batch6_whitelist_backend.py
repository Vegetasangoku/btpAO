#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 6 (backend) — "Veille Réglementaire & Whitelist BTP Internationale" from the user's new
spec: a Super-Admin-managed whitelist of official government/procurement sites per country, and
a STRICT enforcement of that whitelist on every AI web search tied to AO generation/Q&A.

Investigation first (no guessing): apps/api/app/models/entities.py already has a
CountryOfficialSource table (country_code, portal_name, portal_url, portal_type, status), already
seeded with 27 rows across FR/LB/AE/SA/QA (confirmed live via Supabase SQL), and already exposed
read-only to tenants via apps/api/app/api/country_sources.py. What was missing, confirmed by
reading the real code (not assumed):
  1. No Super-Admin CRUD for it at all (admin.py has zero references to CountryOfficialSource).
  2. It was NOT wired as a restriction on the two web-search call sites tied to AO
     generation/Q&A (apps/api/app/workers/tasks.py's section-generation enrichment search, and
     apps/api/app/api/projects.py's ask_project_assistant web mode) -- both called
     web_search_service.search() with allowed_sites left at its default None (unrestricted),
     even though the allowed_sites mechanism itself already exists (built in an earlier batch
     this session for the Mon Entreprise assistant) and needed no changes, just new callers.

Fix:
  1. admin.py: 4 new Super-Admin-only endpoints (require_platform_admin) -- list ALL sources
     (active+inactive, unlike the tenant-facing endpoint), create, update (PATCH), and
     deactivate (DELETE = soft: status="inactive", never a hard delete, so regulatory-watch
     history is preserved). Every write goes through the existing _record_audit_log helper,
     matching this file's own established convention.
  2. tasks.py: resolves the tenant's country_code (already done one step earlier in this exact
     function, reg_profile.country_code, unused until now for this purpose), queries the ACTIVE
     CountryOfficialSource rows for that country, and passes their domains as allowed_sites to
     the section-generation web search. Zero configured sources for a country = zero results
     (existing allowed_sites=[] semantics), never a fallback to the open internet.
  3. projects.py: same restriction for ask_project_assistant's web mode -- fetches Tenant to
     resolve country_code (not otherwise loaded in this endpoint), same domain-allowlist query.

Exact-match-count-of-1 verified live against the running files immediately before writing this
script (protects against drift from the other AI's concurrent edits). Aborts per-file with zero
writes on any mismatch.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected 1). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_batch6_whitelist_backend.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
ADMIN_PY = f"{REPO_ROOT}/apps/api/app/api/admin.py"
TASKS_PY = f"{REPO_ROOT}/apps/api/app/workers/tasks.py"
PROJECTS_PY = f"{REPO_ROOT}/apps/api/app/api/projects.py"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. admin.py — CRUD for the regulatory whitelist
# ─────────────────────────────────────────────────────────────────────────
WHITELIST_ENDPOINTS = '''

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
'''

results.append(apply_patch(ADMIN_PY, [
    (
        "import CountryOfficialSource",
        '''from app.models.entities import (
    AuditLog,
    CompanyAsset,
    DCEDocument,
    DCEEmbedding,
    PlatformSettings,
    Project,
    Tenant,
    TenantSubscription,
    User,
)''',
        '''from app.models.entities import (
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
)''',
    ),
]))

# Append the new endpoints at the very end of the file (matches this session's established
# convention of adding new feature blocks at file end rather than interleaving).
with open(ADMIN_PY, "r", encoding="utf-8") as f:
    admin_content = f.read()
if admin_content.rstrip().endswith(WHITELIST_ENDPOINTS.rstrip()):
    print(f"OK: {ADMIN_PY} whitelist endpoints already appended, skipping duplicate append.")
else:
    with open(ADMIN_PY, "a", encoding="utf-8") as f:
        f.write(WHITELIST_ENDPOINTS)
    print(f"OK: {ADMIN_PY} whitelist CRUD endpoints appended.")

# ─────────────────────────────────────────────────────────────────────────
# 2. tasks.py — enforce whitelist on section-generation web search
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TASKS_PY, [
    (
        "restrict section-generation web search to the tenant's country whitelist",
        '''                # 7. Targeted Web Search Enrichment (Serper API) strictly scoped to tenant request
                from app.services.web_search_service import web_search_service
                search_query = f"{project.title} {section_key} BTP normes {reg_profile.technical_standards_reference[:25]}"
                if custom_instructions:
                    search_query += f" {custom_instructions[:60]}"
                web_results = await web_search_service.search(
                    tenant_id=tenant_id,
                    query=search_query,
                    num_results=3,
                    project_id=project_id,
                )''',
        '''                # 7. Targeted Web Search Enrichment (Serper API) strictly scoped to tenant request
                # AND strictement restreinte a la whitelist reglementaire Super Admin du pays du
                # tenant : jamais un site hors whitelist, jamais un repli vers l'internet ouvert.
                # Zero source configuree pour ce pays = zero recherche (pas un repli non restreint).
                from app.services.web_search_service import web_search_service
                from app.models.entities import CountryOfficialSource
                from urllib.parse import urlparse
                whitelist_res = await db.execute(
                    select(CountryOfficialSource).where(
                        CountryOfficialSource.country_code == reg_profile.country_code,
                        CountryOfficialSource.status == "active",
                    )
                )
                whitelist_domains = sorted({
                    urlparse(s.portal_url).netloc for s in whitelist_res.scalars().all() if s.portal_url
                })
                search_query = f"{project.title} {section_key} BTP normes {reg_profile.technical_standards_reference[:25]}"
                if custom_instructions:
                    search_query += f" {custom_instructions[:60]}"
                web_results = await web_search_service.search(
                    tenant_id=tenant_id,
                    query=search_query,
                    num_results=3,
                    project_id=project_id,
                    allowed_sites=whitelist_domains,
                )''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. projects.py — enforce whitelist on ask_project_assistant's web mode
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(PROJECTS_PY, [
    (
        "import Tenant model",
        "from app.models.entities import CompanyAsset, DCEEmbedding, Project, ProjectGoNoGoAnalysis, TenantLearning",
        "from app.models.entities import CompanyAsset, CountryOfficialSource, DCEEmbedding, Project, ProjectGoNoGoAnalysis, Tenant, TenantLearning",
    ),
    (
        "restrict ask_project_assistant web search to the tenant's country whitelist",
        '''    if is_web_only_mode or is_combined_mode:
        from app.services.web_search_service import web_search_service
        search_query = f"{project.title} BTP {clean_question}"
        web_results = await web_search_service.search(
            tenant_id=current_user.tenant_id,
            query=search_query,
            num_results=3,
            project_id=str(p_uuid),
        )''',
        '''    if is_web_only_mode or is_combined_mode:
        from app.services.web_search_service import web_search_service
        from urllib.parse import urlparse
        tenant_row_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant_row = tenant_row_res.scalar_one_or_none()
        tenant_country_code = tenant_row.country_code if tenant_row else "FR"
        whitelist_res = await db.execute(
            select(CountryOfficialSource).where(
                CountryOfficialSource.country_code == tenant_country_code,
                CountryOfficialSource.status == "active",
            )
        )
        whitelist_domains = sorted({
            urlparse(s.portal_url).netloc for s in whitelist_res.scalars().all() if s.portal_url
        })
        search_query = f"{project.title} BTP {clean_question}"
        web_results = await web_search_service.search(
            tenant_id=current_user.tenant_id,
            query=search_query,
            num_results=3,
            project_id=str(p_uuid),
            allowed_sites=whitelist_domains,
        )''',
    ),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL BATCH-6 WHITELIST BACKEND PATCHES APPLIED SUCCESSFULLY.")
