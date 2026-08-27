"""
Export & Compilation Endpoints — Technical Memo Word & PDF Generation.
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
Guarantees tenant-isolated document storage and download protection.
"""
import io
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.core.storage import storage_service
from app.models.entities import ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, ProjectGanttTask, Tenant
from app.models.schemas import ExportDocumentRequest, ExportJobOut
from app.services.billing_service import billing_service
from app.services.exporter_service import exporter_service

router = APIRouter(prefix="/export", tags=["Document Export"])


@router.post("/compile", response_model=ExportJobOut)
async def compile_technical_memo(
    payload: ExportDocumentRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compiles all real sections of a project into a Word .docx.
    Stores the compiled document in tenant-scoped storage and records the job in PostgreSQL.
    """
    try:
        p_uuid = uuid.UUID(payload.project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    # 1. Enforce Subscription Quota
    await billing_service.check_and_enforce_quota(current_user.tenant_id, action="export", db=db)

    # 2. Fetch real project (guarantees tenant ownership)
    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable ou accès non autorisé."
        )


    # 2. Fetch generated sections (guarantees tenant ownership)
    sec_stmt = (
        select(GeneratedSection)
        .where(
            GeneratedSection.project_id == p_uuid,
            GeneratedSection.tenant_id == t_uuid,
        )
        .order_by(GeneratedSection.order_index.asc())
    )
    sec_res = await db.execute(sec_stmt)
    db_sections = sec_res.scalars().all()
    sections = [
        {
            "id": str(s.id),
            "section_key": s.section_key,
            "title": s.title,
            "order_index": int(s.order_index),
            "content_html": s.content_html,
            "compliance_score": float(s.compliance_score) if s.compliance_score is not None else 100.0,
        }
        for s in db_sections
    ]

    # 3. Fetch conductor's decision form (guarantees tenant ownership)
    dec_stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid,
        ProjectDecision.tenant_id == t_uuid,
    )
    dec_res = await db.execute(dec_stmt)
    decision = dec_res.scalar_one_or_none()
    decision_form = decision.form_data if decision else {}

    job_id = uuid.uuid4()
    now = datetime.utcnow()

    # 4. Fetch Word template (guarantees tenant ownership)
    tmpl_stmt = select(ExportTemplate).where(
        ExportTemplate.tenant_id == t_uuid,
        ExportTemplate.is_default == True,
    )
    tmpl_res = await db.execute(tmpl_stmt)
    template = tmpl_res.scalar_one_or_none()

    # 5. Record export job in PostgreSQL with initial status 'processing'
    new_job = ExportJob(
        id=job_id,
        tenant_id=t_uuid,
        project_id=p_uuid,
        template_id=template.id if template else None,
        format=payload.format,
        status="processing",
        s3_docx_url=None,
        s3_pdf_url=None,
        file_size_bytes=0,
        error_message=None,
        created_at=now,
        completed_at=None,
    )
    db.add(new_job)
    await db.flush()

    # 6. Dispatch asynchronous compilation task to Celery workers
    try:
        from app.workers.tasks import build_export_doc_task
        build_export_doc_task.delay(
            tenant_id=current_user.tenant_id,
            project_id=str(p_uuid),
            export_job_id=str(job_id),
            doc_format=payload.format,
            include_visuals=payload.include_gantt or payload.include_organigramme,
        )
    except Exception as e:
        new_job.status = "failed"
        new_job.error_message = f"Échec du lancement de la tâche de génération : {e.__class__.__name__}: {e}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de génération de documents est temporairement indisponible. Veuillez réessayer dans quelques instants ; si le problème persiste, contactez le support.",
        )

    return ExportJobOut(
        id=str(new_job.id),
        tenant_id=str(new_job.tenant_id),
        project_id=str(new_job.project_id),
        format=new_job.format,
        status="processing",
        s3_docx_url=f"/api/export/download/{new_job.id}",
        s3_pdf_url=None,
        file_size_bytes=0,
        created_at=new_job.created_at,
        completed_at=None,
    )



@router.get("/job/{job_id}", response_model=ExportJobOut)
async def get_export_job(
    job_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns export job status ensuring strict tenant ownership.
    """
    try:
        j_uuid = uuid.UUID(job_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job or tenant UUID")

    stmt = select(ExportJob).where(
        ExportJob.id == j_uuid,
        ExportJob.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found or access denied")

    return ExportJobOut(
        id=str(job.id),
        tenant_id=str(job.tenant_id),
        project_id=str(job.project_id),
        format=job.format,
        status=job.status,
        s3_docx_url=f"/api/export/download/{job.id}",
        s3_pdf_url=job.s3_pdf_url,
        file_size_bytes=int(job.file_size_bytes) if job.file_size_bytes else 0,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/download/{job_id}")
async def download_exported_job_file(
    job_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Secure download endpoint: verifies that the requested export job belongs to the authenticated tenant
    before downloading and streaming the file. Rejects cross-tenant access directly by job ID.
    """
    try:
        j_uuid = uuid.UUID(job_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job UUID")

    stmt = select(ExportJob).where(
        ExportJob.id == j_uuid,
        ExportJob.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job or not job.s3_docx_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier d'export introuvable ou accès non autorisé."
        )

    try:
        file_bytes = storage_service.download_file(current_user.tenant_id, job.s3_docx_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier introuvable dans le stockage: {e}"
        )

    download_filename = f"Memoire_Technique_{job.project_id}.docx"
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
    )


@router.get("/stream/{project_id}.docx")
async def stream_project_docx(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compiles and streams the project memo directly to the browser.
    Strictly verifies that the project belongs to the authenticated tenant.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project UUID")

    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable ou accès non autorisé")

    sec_stmt = (
        select(GeneratedSection)
        .where(
            GeneratedSection.project_id == p_uuid,
            GeneratedSection.tenant_id == t_uuid,
        )
        .order_by(GeneratedSection.order_index.asc())
    )
    sec_res = await db.execute(sec_stmt)
    db_sections = sec_res.scalars().all()
    sections = [
        {
            "id": str(s.id),
            "title": s.title,
            "content_html": s.content_html,
            "compliance_score": float(s.compliance_score) if s.compliance_score is not None else 100.0,
        }
        for s in db_sections
    ]

    dec_stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid,
        ProjectDecision.tenant_id == t_uuid,
    )
    dec_res = await db.execute(dec_stmt)
    decision = dec_res.scalar_one_or_none()
    decision_form = decision.form_data if decision else {}

    gantt_tasks_stmt = select(ProjectGanttTask).where(
        ProjectGanttTask.tenant_id == t_uuid,
        ProjectGanttTask.project_id == p_uuid,
    ).order_by(ProjectGanttTask.sequence, ProjectGanttTask.start_date)
    gantt_tasks_res = await db.execute(gantt_tasks_stmt)
    gantt_task_rows = gantt_tasks_res.scalars().all()
    gantt_tasks = [
        {
            "id": str(r.id), "name": r.name, "start_date": r.start_date, "end_date": r.end_date,
            "sequence": r.sequence, "milestone_label": r.milestone_label,
            "depends_on": [str(d) for d in (r.depends_on or [])],
        }
        for r in gantt_task_rows
    ] or None

    tmpl_stmt = select(ExportTemplate).where(
        ExportTemplate.tenant_id == t_uuid,
        ExportTemplate.is_default == True,
    )
    tmpl_res = await db.execute(tmpl_stmt)
    template = tmpl_res.scalar_one_or_none()
    template_bytes = None
    if template and template.s3_docx_key:
        try:
            template_bytes = storage_service.download_file(current_user.tenant_id, template.s3_docx_key)
        except Exception:
            template_bytes = None

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant_row = tenant_res.scalar_one_or_none()
    company_name = None
    if tenant_row:
        branding = tenant_row.branding_config or {}
        company_name = branding.get("company_name") or tenant_row.name
    company_name = company_name or "Votre Entreprise"

    project_dict = {
        "id": str(project.id),
        "title": project.title,
        "reference_code": project.reference_code,
        "client_name": project.client_name,
        "location": project.location,
        "lot_number": project.lot_number,
        "budget_estimate": float(project.budget_estimate) if project.budget_estimate is not None else 0.0,
        "company_name": company_name,
    }

    from app.api.generate import SECTION_DEFINITIONS
    required_section_titles = sorted({v["title"] for k, v in SECTION_DEFINITIONS.items() if k != "qse_environnement"})
    docx_res = exporter_service.build_memo_docx(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        project_data=project_dict,
        sections=sections,
        decision_form=decision_form,
        template_bytes=template_bytes,
        include_visuals=False,
        required_section_titles=required_section_titles,
        gantt_tasks=gantt_tasks,
    )

    raw_title = project.title or "Memoire_Technique"
    ascii_title = unicodedata.normalize('NFKD', str(raw_title)).encode('ascii', 'ignore').decode('ascii')
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', ascii_title)[:50].strip('_') or "Memoire_Technique"
    download_filename = f"{safe_title}.docx"

    return Response(
        content=docx_res["docx_bytes"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
    )
