"""
Construction Site Decisions & Technical Constraints (Conducteur de Travaux) Endpoints.
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import Project, ProjectDecision
from app.models.schemas import ProjectDecisionsForm

router = APIRouter(prefix="/decisions", tags=["Project Decisions"])


@router.get("/{project_id}", response_model=ProjectDecisionsForm)
async def get_project_decisions(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the saved site constraints and decisions for the project.
    Strictly scoped by Postgres RLS and tenant_id.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    # 1. Verify project exists and belongs to the authenticated tenant
    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    if not proj_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")

    # 2. Query saved decisions
    stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid,
        ProjectDecision.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    decision = result.scalar_one_or_none()

    if decision and decision.form_data:
        return ProjectDecisionsForm(**decision.form_data)

    # If no decisions saved yet, return default template
    return ProjectDecisionsForm()


@router.post("/{project_id}", response_model=ProjectDecisionsForm)
async def save_project_decisions(
    project_id: str,
    payload: ProjectDecisionsForm,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Saves or updates the technical decisions made by the construction project manager.
    Strictly scoped by Postgres RLS and tenant_id.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    # 1. Verify project exists and belongs to the authenticated tenant
    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    if not proj_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")

    # 2. Query existing decisions record
    stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid,
        ProjectDecision.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    decision = result.scalar_one_or_none()

    now = datetime.utcnow()
    form_dict = payload.dict()

    if decision:
        decision.form_data = form_dict
        decision.updated_at = now
    else:
        # 29/08 (fin de journée) : `created_at` retiré -- cette colonne n'existe pas dans la
        # vraie table (voir la note dans entities.py::ProjectDecision), passer ce kwarg lève
        # une TypeError SQLAlchemy ("invalid keyword argument").
        decision = ProjectDecision(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            project_id=p_uuid,
            form_data=form_dict,
            updated_at=now,
        )
        db.add(decision)

    await db.flush()
    return payload
