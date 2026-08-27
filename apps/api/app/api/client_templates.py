"""
Client Template In-Place Processing & Completeness Report API Endpoints.
Preserves existing styles, resolves multi-tier sources, and flags missing fields in red.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import CompanyAsset, DCEEmbedding, Project, Tenant, TenantLearning
from app.services.client_template_filler_service import client_template_filler_service

router = APIRouter(prefix="/client-templates", tags=["Client Template In-Place Filler & Completeness"])


async def _gather_context(
    project_id: str,
    current_user: CurrentTenantUser,
    db: AsyncSession,
):
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant introuvable")

    proj_res = await db.execute(select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid))
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable ou accès refusé")

    # Fetch Company Assets
    assets_res = await db.execute(select(CompanyAsset).where(CompanyAsset.tenant_id == t_uuid))
    assets = assets_res.scalars().all()
    company_assets_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "Non renseigné",
    }
    for a in assets:
        if a.validated_by_user and a.metadata_json:
            company_assets_dict.update(a.metadata_json)

    # Fetch Tenant Learnings
    learnings_res = await db.execute(select(TenantLearning).where(TenantLearning.tenant_id == t_uuid))
    learnings = [
        {"category": l.category, "directive": l.actionable_directive, "insight": l.learning_insight}
        for l in learnings_res.scalars().all()
    ]

    # Fetch Project RAG Chunks via Cosine Distance ranking
    from app.services.embedding_service import embedding_service
    query_vector = embedding_service.generate_embedding(project.title) if embedding_service else None
    rag_chunks = []
    try:
        if query_vector is not None:
            async with db.begin_nested():
                rag_dist_expr = DCEEmbedding.embedding.cosine_distance(query_vector)
                rag_stmt = (
                    select(DCEEmbedding.content)
                    .where(
                        DCEEmbedding.tenant_id == t_uuid,
                        DCEEmbedding.project_id == p_uuid,
                        DCEEmbedding.embedding.isnot(None),
                    )
                    .order_by(rag_dist_expr)
                    .limit(10)
                )
                rag_res = await db.execute(rag_stmt)
                rag_chunks = [r[0] for r in rag_res.fetchall() if r[0]]
    except Exception as rag_exc:
        logger.warning("[client_templates.py] Semantic RAG ranking fallback: %s", rag_exc)

    if not rag_chunks:
        rag_res = await db.execute(
            select(DCEEmbedding.content)
            .where(DCEEmbedding.tenant_id == t_uuid, DCEEmbedding.project_id == p_uuid)
            .order_by(DCEEmbedding.created_at.desc())
            .limit(10)
        )
        rag_chunks = [r[0] for r in rag_res.fetchall() if r[0]]

    project_data = {
        "title": project.title,
        "client_name": project.client_name,
        "reference_code": project.reference_code,
        "lot_number": project.lot_number,
    }

    return tenant, project, project_data, company_assets_dict, learnings, rag_chunks


@router.post("/{project_id}/fill")
async def fill_client_template(
    project_id: str,
    file: UploadFile = File(...),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fills placeholders in an uploaded client DOCX template in-place.
    Preserves exact font, colors, and layouts while injecting red [À COMPLÉTER] flags for missing fields.
    """
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seuls les fichiers Word (.docx) sont acceptés")

    template_bytes = await file.read()
    if len(template_bytes) < 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier template vide ou invalide")

    tenant, project, project_data, assets, learnings, rag_chunks = await _gather_context(project_id, current_user, db)

    filled_docx, report = client_template_filler_service.fill_docx_template_inplace(
        template_bytes=template_bytes,
        project_data=project_data,
        rag_chunks=rag_chunks,
        company_assets=assets,
        tenant_learnings=learnings,
    )

    filename = f"Memoire_Technique_Rempli_{project.reference_code or 'AO'}.docx"
    return Response(
        content=filled_docx,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Completeness-Score": str(report.completeness_score_pct),
            "X-Pending-Actions": str(report.pending_actions_count),
        },
    )


@router.post("/{project_id}/analyze-completeness")
async def analyze_template_completeness(
    project_id: str,
    file: UploadFile = File(...),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyzes an uploaded template against project context and returns coverage score & missing actions.
    """
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seuls les fichiers Word (.docx) sont acceptés")

    template_bytes = await file.read()
    tenant, project, project_data, assets, learnings, rag_chunks = await _gather_context(project_id, current_user, db)

    _, report = client_template_filler_service.fill_docx_template_inplace(
        template_bytes=template_bytes,
        project_data=project_data,
        rag_chunks=rag_chunks,
        company_assets=assets,
        tenant_learnings=learnings,
    )

    return report
