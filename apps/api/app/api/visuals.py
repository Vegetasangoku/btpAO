"""
Visuals, Gantt & Organigramme Generator Endpoints
"""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.core.storage import storage_service
from app.models.entities import Project, ProjectDecision, ProjectGanttTask
from app.models.schemas import (
    DiagramGenerationRequest,
    GanttGenerationRequest,
    GanttTaskCreate,
    GanttTaskOut,
    GanttTaskUpdate,
)
from app.services.diagram_service import diagram_service
from app.services.gantt_service import gantt_service

router = APIRouter(prefix="/visuals", tags=["Visuals & Planning"])


async def _fetch_gantt_task_rows(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(ProjectGanttTask)
        .where(ProjectGanttTask.tenant_id == uuid.UUID(tenant_id))
        .where(ProjectGanttTask.project_id == uuid.UUID(project_id))
        .order_by(ProjectGanttTask.sequence, ProjectGanttTask.start_date)
    )
    return result.scalars().all()


def _row_to_task_dict(row: ProjectGanttTask) -> Dict[str, Any]:
    """Shape consumed by gantt_service (compute_critical_path / PNG renderer)."""
    return {
        "id": str(row.id),
        "name": row.name,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "progress": row.progress,
        "sequence": row.sequence,
        "is_milestone": row.is_milestone,
        "milestone_label": row.milestone_label,
        "depends_on": [str(d) for d in (row.depends_on or [])],
    }


def _row_to_out(row: ProjectGanttTask, critical_ids: Optional[set] = None) -> GanttTaskOut:
    return GanttTaskOut(
        id=str(row.id),
        project_id=str(row.project_id),
        name=row.name,
        start_date=row.start_date.isoformat(),
        end_date=row.end_date.isoformat(),
        progress=row.progress,
        sequence=row.sequence,
        is_milestone=row.is_milestone,
        milestone_label=row.milestone_label,
        depends_on=[str(d) for d in (row.depends_on or [])],
        is_critical=bool(critical_ids and str(row.id) in critical_ids),
    )


@router.get("/gantt-tasks/{project_id}", response_model=List[GanttTaskOut])
async def list_gantt_tasks(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists the interactive Gantt tasks for a project. On first call for a project with
    no tasks yet, lazily seeds them from ProjectDecision.form_data['phasage_travaux']
    (the existing Go/No-Go phase list) so the chart doesn't start empty -- see
    migration 00026 for the rationale on keeping the two lists separate after that
    one-time seed.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    rows = await _fetch_gantt_task_rows(db, current_user.tenant_id, project_id)

    if not rows:
        dec_stmt = select(ProjectDecision).where(
            ProjectDecision.project_id == p_uuid, ProjectDecision.tenant_id == t_uuid
        )
        dec_res = await db.execute(dec_stmt)
        decision = dec_res.scalar_one_or_none()
        decision_form = decision.form_data if decision and decision.form_data else {}
        phases = decision_form.get("phasage_travaux") or []
        start_date_str = decision_form.get("date_demarrage") or "2026-10-01"
        seeded = gantt_service.seed_tasks_from_phases(phases, start_date_str)
        for idx, t in enumerate(seeded):
            db.add(ProjectGanttTask(
                id=uuid.UUID(t["id"]),
                tenant_id=t_uuid,
                project_id=p_uuid,
                name=t["name"],
                start_date=t["start_date"],
                end_date=t["end_date"],
                progress=0,
                sequence=idx,
                is_milestone=False,
                milestone_label=t.get("milestone_label"),
                depends_on=[uuid.UUID(d) for d in (t.get("depends_on") or [])],
            ))
        if seeded:
            await db.commit()
            rows = await _fetch_gantt_task_rows(db, current_user.tenant_id, project_id)

    task_dicts = [_row_to_task_dict(r) for r in rows]
    critical_ids = gantt_service.compute_critical_path(task_dicts)
    return [_row_to_out(r, critical_ids) for r in rows]


@router.post("/gantt-tasks/{project_id}", response_model=GanttTaskOut)
async def create_gantt_task(
    project_id: str,
    payload: GanttTaskCreate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Adds one task to a project's interactive Gantt (the "+ Ajouter une tâche" action)."""
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    existing = await _fetch_gantt_task_rows(db, current_user.tenant_id, project_id)
    try:
        start_d = date.fromisoformat(payload.start_date)
        end_d = date.fromisoformat(payload.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de date invalide (attendu AAAA-MM-JJ).")
    if end_d < start_d:
        raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début.")

    existing_ids = {str(r.id) for r in existing}
    depends_on_uuids = [uuid.UUID(d) for d in payload.depends_on if d in existing_ids]

    row = ProjectGanttTask(
        tenant_id=t_uuid,
        project_id=p_uuid,
        name=payload.name,
        start_date=start_d,
        end_date=end_d,
        progress=payload.progress,
        sequence=len(existing),
        is_milestone=payload.is_milestone,
        milestone_label=payload.milestone_label,
        depends_on=depends_on_uuids,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _row_to_out(row)


@router.patch("/gantt-tasks/{project_id}/{task_id}", response_model=GanttTaskOut)
async def update_gantt_task(
    project_id: str,
    task_id: str,
    payload: GanttTaskUpdate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Persists a drag-and-drop date change, a progress-bar drag, or any other edit made
    in the interactive Gantt. This is the write path behind on_date_change /
    on_progress_change in the frontend component.
    """
    try:
        t_uuid_check = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de tâche invalide.")

    row = await db.get(ProjectGanttTask, t_uuid_check)
    if not row or str(row.tenant_id) != current_user.tenant_id or str(row.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")

    if payload.name is not None:
        row.name = payload.name
    if payload.start_date is not None:
        try:
            row.start_date = date.fromisoformat(payload.start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Format de date invalide (attendu AAAA-MM-JJ).")
    if payload.end_date is not None:
        try:
            row.end_date = date.fromisoformat(payload.end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Format de date invalide (attendu AAAA-MM-JJ).")
    if row.end_date < row.start_date:
        raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début.")
    if payload.progress is not None:
        row.progress = payload.progress
    if payload.is_milestone is not None:
        row.is_milestone = payload.is_milestone
    if payload.milestone_label is not None:
        row.milestone_label = payload.milestone_label
    if payload.depends_on is not None:
        existing = await _fetch_gantt_task_rows(db, current_user.tenant_id, project_id)
        existing_ids = {str(r.id) for r in existing}
        row.depends_on = [uuid.UUID(d) for d in payload.depends_on if d in existing_ids and d != task_id]
    row.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(row)
    return _row_to_out(row)


@router.delete("/gantt-tasks/{project_id}/{task_id}")
async def delete_gantt_task(
    project_id: str,
    task_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        t_uuid_check = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de tâche invalide.")

    row = await db.get(ProjectGanttTask, t_uuid_check)
    if not row or str(row.tenant_id) != current_user.tenant_id or str(row.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    await db.delete(row)
    await db.commit()
    return {"success": True}


@router.post("/gantt")
async def generate_project_gantt(
    payload: GanttGenerationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a high-definition BTP Gantt chart PNG using matplotlib.
    If the project already has structured tasks in project_gantt_tasks (the
    interactive Gantt, Batch 11), those are used -- reflecting the user's real, edited
    plan and highlighting the critical path -- instead of the legacy stateless
    `phases` payload, which is now only a fallback for projects with no tasks yet.
    """
    rows = await _fetch_gantt_task_rows(db, current_user.tenant_id, payload.project_id)
    if rows:
        task_dicts = [_row_to_task_dict(r) for r in rows]
        result = gantt_service.generate_gantt_chart_png_from_tasks(
            tenant_id=current_user.tenant_id,
            project_id=payload.project_id,
            project_title=payload.project_title or "Chantier BTP",
            tasks=task_dicts,
        )
        return result

    phases_dict = [p.dict() for p in payload.phases] if payload.phases else []
    result = gantt_service.generate_gantt_chart_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.project_title or "Chantier BTP",
        phases=phases_dict,
        start_date_str=payload.start_date or "2026-10-01"
    )
    return result


@router.post("/organigramme")
async def generate_project_organigramme(
    payload: DiagramGenerationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Generates a site management organigramme PNG.
    """
    result = diagram_service.generate_organigramme_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.title or "Chantier BTP",
        cadres=payload.nodes
    )
    return result


@router.get("/file/{file_path:path}")
async def get_visual_file(
    file_path: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Streams image file bytes directly to browser/frontend.
    """
    try:
        data = storage_service.download_file(current_user.tenant_id, file_path)
        content_type = "image/png"
        if file_path.endswith(".pdf"):
            content_type = "application/pdf"
        elif file_path.endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return Response(content=data, media_type=content_type)
    except Exception as e:
        # Generate a live Gantt on the fly if not found
        gantt_res = gantt_service.generate_gantt_chart_png(
            tenant_id=current_user.tenant_id,
            project_id="33333333-3333-3333-3333-333333333333",
            project_title="Construction du Groupe Scolaire & Gymnase HQE",
            phases=[]
        )
        data = storage_service.download_file(current_user.tenant_id, gantt_res["s3_key"])
        return Response(content=data, media_type="image/png")
