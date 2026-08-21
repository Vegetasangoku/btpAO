"""
Technical Memo Generation & WYSIWYG Section Management Endpoints.
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
Guarantees 100% tenant isolation for LLM prompt context injection.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import (
    CompanyAsset,
    DCEEmbedding,
    GeneratedSection,
    GeneratedSectionVersion,
    Project,
    ProjectDecision,
)
from app.models.schemas import (
    GenerateSectionRequest,
    GeneratedSectionOut,
    GeneratedSectionVersionOut,
    UpdateSectionContent,
)

from app.services.billing_service import billing_service
from app.services.llm_generator import llm_generator_service

router = APIRouter(prefix="/generate", tags=["AI Generation & Sections"])

SECTION_DEFINITIONS = {
    "moyens_humains": {"title": "1. Moyens Humains & Organisation du Chantier", "order": 1},
    "moyens_materiels": {"title": "2. Moyens Matériels & Plan d'Installation de Chantier (PIC)", "order": 2},
    "methodologie_phasage": {"title": "3. Méthodologie d'Exécution & Phasage des Travaux", "order": 3},
    "qse_environnement": {"title": "4. Démarche RSE, Environnement & Gestion des Déchets", "order": 4},
    "securite_ppsps": {"title": "5. Sécurité, Santé (PPSPS) & Plan d'Assurance Qualité (PAQ)", "order": 5},
}


@router.get("/sections/{project_id}", response_model=List[GeneratedSectionOut])
async def get_project_sections(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves all generated/edited sections for the given project.
    Strictly scoped by Postgres RLS and tenant_id.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    stmt = (
        select(GeneratedSection)
        .where(
            GeneratedSection.project_id == p_uuid,
            GeneratedSection.tenant_id == t_uuid,
        )
        .order_by(GeneratedSection.order_index.asc())
    )
    result = await db.execute(stmt)
    sections = result.scalars().all()

    return [
        GeneratedSectionOut(
            id=str(s.id),
            tenant_id=str(s.tenant_id),
            project_id=str(s.project_id),
            section_key=s.section_key,
            title=s.title,
            order_index=int(s.order_index),
            content_html=s.content_html,
            content_json=s.content_json or {},
            visual_placeholders=s.visual_placeholders or [],
            compliance_score=float(s.compliance_score) if s.compliance_score is not None else 100.0,
            compliance_notes=s.compliance_notes or "Conforme",
            status=s.status,
            locked_for_export=str(s.locked_for_export).lower() in ("true", "1"),
            updated_at=s.updated_at,
        )
        for s in sections
    ]


@router.post("/section", response_model=GeneratedSectionOut)
async def generate_single_section(
    payload: GenerateSectionRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers the RAG + LLM engine to generate or refine a technical memo section.
    RAG Context is strictly retrieved from the authenticated tenant's database rows ONLY.
    """
    try:
        p_uuid = uuid.UUID(payload.project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    # 1. Enforce Subscription Quota
    await billing_service.check_and_enforce_quota(current_user.tenant_id, action="section", db=db)

    # 2. Fetch real project (guarantees tenant ownership)
    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")


    sec_meta = SECTION_DEFINITIONS.get(
        payload.section_key,
        {"title": f"Section {payload.section_key}", "order": 99}
    )

    now = datetime.utcnow()

    # 3. Upsert section in PostgreSQL with status 'processing'
    sec_stmt = select(GeneratedSection).where(
        GeneratedSection.project_id == p_uuid,
        GeneratedSection.tenant_id == t_uuid,
        GeneratedSection.section_key == payload.section_key,
    )
    sec_res = await db.execute(sec_stmt)
    existing_sec = sec_res.scalar_one_or_none()

    if existing_sec:
        existing_sec.title = sec_meta["title"]
        existing_sec.order_index = sec_meta["order"]
        existing_sec.status = "processing"
        existing_sec.updated_at = now
        saved_sec = existing_sec
    else:
        new_sec = GeneratedSection(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            project_id=p_uuid,
            section_key=payload.section_key,
            title=sec_meta["title"],
            order_index=sec_meta["order"],
            content_html="<p>Génération en cours d'exécution par le worker d'IA en tâche de fond...</p>",
            content_json={},
            visual_placeholders=[],
            compliance_score=0.0,
            compliance_notes="Génération en cours (Celery worker)",
            status="processing",
            locked_for_export=False,
            updated_at=now,
        )

        db.add(new_sec)
        saved_sec = new_sec

    await db.flush()

    # 4. Asynchronously dispatch Celery background generator task
    from app.workers.tasks import generate_section_task
    generate_section_task.delay(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        section_key=payload.section_key,
        custom_instructions=payload.custom_instructions,
    )

    return GeneratedSectionOut(
        id=str(saved_sec.id),
        tenant_id=str(saved_sec.tenant_id),
        project_id=str(saved_sec.project_id),
        section_key=saved_sec.section_key,
        title=saved_sec.title,
        order_index=saved_sec.order_index,
        content_html=saved_sec.content_html,
        content_json=saved_sec.content_json or {},
        visual_placeholders=saved_sec.visual_placeholders or [],
        compliance_score=float(saved_sec.compliance_score) if saved_sec.compliance_score is not None else 0.0,
        compliance_notes=saved_sec.compliance_notes or "Génération lancée",
        status="processing",
        locked_for_export=saved_sec.locked_for_export,
        updated_at=saved_sec.updated_at,
    )



@router.put("/section/{section_id}", response_model=GeneratedSectionOut)
async def update_section_content(
    section_id: str,
    payload: UpdateSectionContent,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates the section text directly from the WYSIWYG editor.
    Automatically archives the prior state to generated_section_versions before writing new content.
    Strictly scoped to the authenticated tenant under Postgres RLS.
    """
    try:
        s_uuid = uuid.UUID(section_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid section or tenant UUID")

    stmt = select(GeneratedSection).where(
        GeneratedSection.id == s_uuid,
        GeneratedSection.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found or access denied")

    # 1. Determine next version number for this section
    ver_stmt = (
        select(func.max(GeneratedSectionVersion.version_number))
        .where(
            GeneratedSectionVersion.section_id == s_uuid,
            GeneratedSectionVersion.tenant_id == t_uuid,
        )
    )
    ver_res = await db.execute(ver_stmt)
    last_version = ver_res.scalar() or 0
    next_version_num = last_version + 1

    # 2. Archive current version before overwriting
    archived_version = GeneratedSectionVersion(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        project_id=section.project_id,
        section_id=section.id,
        version_number=next_version_num,
        title=section.title,
        content_html=section.content_html,
        content_json=section.content_json or {},
        compliance_score=section.compliance_score,
        compliance_notes=section.compliance_notes,
        status=section.status,
        created_by=uuid.UUID(current_user.user_id) if current_user.user_id else None,
        created_at=datetime.utcnow(),
        change_summary=payload.change_summary or f"Version archivée avant modification (v{next_version_num})",
    )
    db.add(archived_version)

    # 3. Apply new updates to current section
    section.content_html = payload.content_html
    if payload.content_json is not None:
        section.content_json = payload.content_json
    if payload.status:
        section.status = payload.status
    if payload.locked_for_export is not None:
        section.locked_for_export = payload.locked_for_export
    section.updated_at = datetime.utcnow()

    await db.flush()

    return GeneratedSectionOut(
        id=str(section.id),
        tenant_id=str(section.tenant_id),
        project_id=str(section.project_id),
        section_key=section.section_key,
        title=section.title,
        order_index=int(section.order_index),
        content_html=section.content_html,
        content_json=section.content_json or {},
        visual_placeholders=section.visual_placeholders or [],
        compliance_score=float(section.compliance_score) if section.compliance_score is not None else 100.0,
        compliance_notes=section.compliance_notes or "Conforme",
        status=section.status,
        locked_for_export=bool(section.locked_for_export),
        updated_at=section.updated_at,
    )


@router.get("/section/{section_id}/history", response_model=List[GeneratedSectionVersionOut])
async def get_section_version_history(
    section_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all previous archived versions of a generated section in reverse chronological order.
    Strictly scoped to authenticated tenant under Postgres RLS.
    """
    try:
        s_uuid = uuid.UUID(section_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid section or tenant UUID")

    # Verify section exists and belongs to tenant
    sec_stmt = select(GeneratedSection).where(
        GeneratedSection.id == s_uuid,
        GeneratedSection.tenant_id == t_uuid,
    )
    sec_res = await db.execute(sec_stmt)
    section = sec_res.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found or access denied")

    hist_stmt = (
        select(GeneratedSectionVersion)
        .where(
            GeneratedSectionVersion.section_id == s_uuid,
            GeneratedSectionVersion.tenant_id == t_uuid,
        )
        .order_by(
            GeneratedSectionVersion.version_number.desc(),
            GeneratedSectionVersion.created_at.desc(),
        )
    )
    hist_res = await db.execute(hist_stmt)
    versions = hist_res.scalars().all()

    return [
        GeneratedSectionVersionOut(
            id=str(v.id),
            tenant_id=str(v.tenant_id),
            project_id=str(v.project_id),
            section_id=str(v.section_id),
            version_number=int(v.version_number),
            title=v.title,
            content_html=v.content_html,
            content_json=v.content_json or {},
            compliance_score=float(v.compliance_score) if v.compliance_score is not None else 100.0,
            compliance_notes=v.compliance_notes,
            status=v.status,
            created_by=str(v.created_by) if v.created_by else None,
            created_at=v.created_at,
            change_summary=v.change_summary,
        )
        for v in versions
    ]


@router.post("/section/{section_id}/restore/{version_id}", response_model=GeneratedSectionOut)
async def restore_section_version(
    section_id: str,
    version_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restores a previous section version.
    Archives the current active version before restoring so no content is ever lost.
    Strictly scoped to authenticated tenant under Postgres RLS.
    """
    try:
        s_uuid = uuid.UUID(section_id)
        v_uuid = uuid.UUID(version_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid section, version or tenant UUID")

    # Verify section exists and belongs to tenant
    sec_stmt = select(GeneratedSection).where(
        GeneratedSection.id == s_uuid,
        GeneratedSection.tenant_id == t_uuid,
    )
    sec_res = await db.execute(sec_stmt)
    section = sec_res.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found or access denied")

    # Fetch target version to restore
    v_stmt = select(GeneratedSectionVersion).where(
        GeneratedSectionVersion.id == v_uuid,
        GeneratedSectionVersion.section_id == s_uuid,
        GeneratedSectionVersion.tenant_id == t_uuid,
    )
    v_res = await db.execute(v_stmt)
    target_version = v_res.scalar_one_or_none()
    if not target_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target version not found or access denied")

    # Determine next version number to archive current state
    ver_stmt = (
        select(func.max(GeneratedSectionVersion.version_number))
        .where(
            GeneratedSectionVersion.section_id == s_uuid,
            GeneratedSectionVersion.tenant_id == t_uuid,
        )
    )
    ver_res = await db.execute(ver_stmt)
    last_version = ver_res.scalar() or 0
    next_version_num = last_version + 1

    # Archive current version state before rollback
    archived_current = GeneratedSectionVersion(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        project_id=section.project_id,
        section_id=section.id,
        version_number=next_version_num,
        title=section.title,
        content_html=section.content_html,
        content_json=section.content_json or {},
        compliance_score=section.compliance_score,
        compliance_notes=section.compliance_notes,
        status=section.status,
        created_by=uuid.UUID(current_user.user_id) if current_user.user_id else None,
        created_at=datetime.utcnow(),
        change_summary=f"Archivé avant restauration de la version v{target_version.version_number}",
    )

    db.add(archived_current)

    # Restore content from target version
    section.content_html = target_version.content_html
    section.content_json = target_version.content_json or {}
    section.title = target_version.title
    section.compliance_score = target_version.compliance_score
    section.compliance_notes = f"Restauré depuis la version v{target_version.version_number}"
    section.status = "restored"
    section.updated_at = datetime.utcnow()

    await db.flush()

    return GeneratedSectionOut(
        id=str(section.id),
        tenant_id=str(section.tenant_id),
        project_id=str(section.project_id),
        section_key=section.section_key,
        title=section.title,
        order_index=int(section.order_index),
        content_html=section.content_html,
        content_json=section.content_json or {},
        visual_placeholders=section.visual_placeholders or [],
        compliance_score=float(section.compliance_score) if section.compliance_score is not None else 100.0,
        compliance_notes=section.compliance_notes,
        status=section.status,
        locked_for_export=bool(section.locked_for_export),
        updated_at=section.updated_at,
    )


