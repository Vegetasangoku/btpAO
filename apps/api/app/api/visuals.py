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
from app.models.entities import (
    Project,
    ProjectDecision,
    ProjectGanttTask,
    ProjectOrganigrammeNode,
    Tenant,
)
from app.models.schemas import (
    DiagramGenerationRequest,
    GanttGenerationRequest,
    GanttLearningCheckResponse,
    GanttTaskCreate,
    GanttTaskOut,
    GanttTaskUpdate,
    LearningProposal,
    OrganigrammeLearningCheckResponse,
    OrganigrammeNodeCreate,
    OrganigrammeNodeOut,
    OrganigrammeNodeUpdate,
)
from app.services.diagram_service import diagram_service
from app.services.gantt_service import gantt_service
from app.services.learning_service import learning_service

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


async def _get_tenant_brand_color(db: AsyncSession, tenant_id: str) -> Optional[str]:
    """Lit branding_config.primary_color pour adapter les visuels generes (Gantt &
    Organigramme) a la charte graphique reelle du client (30/08, demande explicite --
    voir gantt_service.py / diagram_service.py pour l'application du brand_color).
    Ne leve jamais d'exception : une couleur absente ou invalide retombe simplement sur
    le bleu par defaut des generateurs."""
    try:
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        color = (tenant.branding_config or {}).get("primary_color") if tenant else None
        return str(color).strip() if color and str(color).strip() else None
    except Exception:
        return None


async def _get_tenant_shape_style(db: AsyncSession, tenant_id: str) -> Optional[str]:
    """Lit branding_config.shape_style (BT02, 01/09 -- personnalisation des formes Gantt
    & Organigramme, au-dela de la couleur de marque deja branchee ci-dessus). Ne leve
    jamais d'exception : une valeur absente ou invalide retombe simplement sur le rendu
    historique de chaque generateur (voir gantt_service.py / diagram_service.py)."""
    try:
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        style = (tenant.branding_config or {}).get("shape_style") if tenant else None
        return str(style).strip().lower() if style and str(style).strip() else None
    except Exception:
        return None


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


@router.get("/gantt-tasks/{project_id}/learning-check", response_model=GanttLearningCheckResponse)
async def check_gantt_learning_opportunity(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Boucle d'apprentissage par corrections (03/09, demande client), volet planning :
    compare le Gantt actuel (project_gantt_tasks, librement edite par le tenant) au
    plan initial encore intact dans ProjectDecision.form_data['phasage_travaux'] --
    voir learning_service.calculate_gantt_diff_significance pour la logique de
    comparaison. Additif et sans effet de bord : lecture seule, n'ecrit jamais rien --
    contrairement a POST /generate/learnings qui persiste l'ajustement une fois
    confirme par l'utilisateur (meme flux de confirmation que pour le texte, voir
    TiptapEditor.handleSaveLearning, reutilise tel quel cote frontend).
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    dec_stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid, ProjectDecision.tenant_id == t_uuid
    )
    dec_res = await db.execute(dec_stmt)
    decision = dec_res.scalar_one_or_none()
    baseline_phases = (decision.form_data.get("phasage_travaux") or []) if decision and decision.form_data else []

    rows = await _fetch_gantt_task_rows(db, current_user.tenant_id, project_id)
    current_tasks = [_row_to_task_dict(r) for r in rows]

    is_significant, diff_pct, summary = learning_service.calculate_gantt_diff_significance(
        baseline_phases=baseline_phases,
        current_tasks=current_tasks,
        threshold_pct=15.0,
    )

    if not is_significant:
        return GanttLearningCheckResponse(learning_opportunity=False)

    return GanttLearningCheckResponse(
        learning_opportunity=True,
        learning_proposal=LearningProposal(
            section_type="planning_phasage",
            summary=summary,
            suggested_content=summary,
            diff_percentage=diff_pct,
        ),
    )


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
    brand_color = await _get_tenant_brand_color(db, current_user.tenant_id)
    shape_style = await _get_tenant_shape_style(db, current_user.tenant_id)
    if rows:
        task_dicts = [_row_to_task_dict(r) for r in rows]
        result = gantt_service.generate_gantt_chart_png_from_tasks(
            tenant_id=current_user.tenant_id,
            project_id=payload.project_id,
            project_title=payload.project_title or "Chantier BTP",
            tasks=task_dicts,
            brand_color=brand_color,
            shape_style=shape_style,
        )
        return result

    phases_dict = [p.dict() for p in payload.phases] if payload.phases else []
    result = gantt_service.generate_gantt_chart_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.project_title or "Chantier BTP",
        phases=phases_dict,
        start_date_str=payload.start_date or "2026-10-01",
        brand_color=brand_color,
        shape_style=shape_style,
    )
    return result


async def _fetch_organigramme_node_rows(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(ProjectOrganigrammeNode)
        .where(ProjectOrganigrammeNode.tenant_id == uuid.UUID(tenant_id))
        .where(ProjectOrganigrammeNode.project_id == uuid.UUID(project_id))
        .order_by(ProjectOrganigrammeNode.sequence)
    )
    return result.scalars().all()


def _node_row_to_cadre_dict(row: ProjectOrganigrammeNode) -> Dict[str, Any]:
    """Shape consumed by diagram_service.generate_organigramme_png's `cadres` param."""
    return {
        "nom": row.nom,
        "role": row.role,
        "experience_ans": row.experience_ans,
        "presence_hebdo_pct": row.presence_hebdo_pct,
        "qualif": row.qualif,
    }


def _node_row_to_out(row: ProjectOrganigrammeNode) -> OrganigrammeNodeOut:
    return OrganigrammeNodeOut(
        id=str(row.id),
        project_id=str(row.project_id),
        nom=row.nom,
        role=row.role,
        experience_ans=row.experience_ans,
        presence_hebdo_pct=row.presence_hebdo_pct,
        qualif=row.qualif,
        sequence=row.sequence,
    )


@router.get("/organigramme-nodes/{project_id}", response_model=List[OrganigrammeNodeOut])
async def list_organigramme_nodes(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists the interactive organigramme nodes (intervenants d'encadrement) for a
    project. On first call for a project with no nodes yet, lazily seeds them from
    ProjectDecision.form_data['equipe_cadres'] (the existing Go/No-Go team list) --
    see migration 00036 for the rationale on keeping the two lists separate after
    that one-time seed. Mirrors list_gantt_tasks exactly.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    rows = await _fetch_organigramme_node_rows(db, current_user.tenant_id, project_id)

    if not rows:
        dec_stmt = select(ProjectDecision).where(
            ProjectDecision.project_id == p_uuid, ProjectDecision.tenant_id == t_uuid
        )
        dec_res = await db.execute(dec_stmt)
        decision = dec_res.scalar_one_or_none()
        decision_form = decision.form_data if decision and decision.form_data else {}
        cadres = decision_form.get("equipe_cadres") or []
        for idx, c in enumerate(cadres):
            db.add(ProjectOrganigrammeNode(
                tenant_id=t_uuid,
                project_id=p_uuid,
                nom=c.get("nom") or "Intervenant",
                role=c.get("role") or "Rôle",
                experience_ans=int(c.get("experience_ans") or 10),
                presence_hebdo_pct=int(c.get("presence_hebdo_pct") or 100),
                qualif=c.get("qualif"),
                sequence=idx,
            ))
        if cadres:
            await db.commit()
            rows = await _fetch_organigramme_node_rows(db, current_user.tenant_id, project_id)

    return [_node_row_to_out(r) for r in rows]


@router.get("/organigramme-nodes/{project_id}/learning-check", response_model=OrganigrammeLearningCheckResponse)
async def check_organigramme_learning_opportunity(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Boucle d'apprentissage par corrections (03/09, demande client -- "y compris
    pour les schemas / tableaux"), volet organigramme : compare l'equipe actuelle
    (project_organigramme_nodes, librement editee par le tenant) a l'equipe
    initiale encore intacte dans ProjectDecision.form_data['equipe_cadres'] -- voir
    learning_service.calculate_organigramme_diff_significance pour la logique de
    comparaison. Additif et sans effet de bord, exactement comme
    check_gantt_learning_opportunity : lecture seule, n'ecrit jamais rien.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    dec_stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid, ProjectDecision.tenant_id == t_uuid
    )
    dec_res = await db.execute(dec_stmt)
    decision = dec_res.scalar_one_or_none()
    baseline_cadres = (decision.form_data.get("equipe_cadres") or []) if decision and decision.form_data else []

    rows = await _fetch_organigramme_node_rows(db, current_user.tenant_id, project_id)
    current_nodes = [_node_row_to_cadre_dict(r) for r in rows]

    is_significant, diff_pct, summary = learning_service.calculate_organigramme_diff_significance(
        baseline_cadres=baseline_cadres,
        current_nodes=current_nodes,
        threshold_pct=15.0,
    )

    if not is_significant:
        return OrganigrammeLearningCheckResponse(learning_opportunity=False)

    return OrganigrammeLearningCheckResponse(
        learning_opportunity=True,
        learning_proposal=LearningProposal(
            section_type="organigramme_equipe",
            summary=summary,
            suggested_content=summary,
            diff_percentage=diff_pct,
        ),
    )


@router.post("/organigramme-nodes/{project_id}", response_model=OrganigrammeNodeOut)
async def create_organigramme_node(
    project_id: str,
    payload: OrganigrammeNodeCreate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Adds one intervenant to a project's interactive organigramme."""
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    existing = await _fetch_organigramme_node_rows(db, current_user.tenant_id, project_id)

    row = ProjectOrganigrammeNode(
        tenant_id=t_uuid,
        project_id=p_uuid,
        nom=payload.nom,
        role=payload.role,
        experience_ans=payload.experience_ans,
        presence_hebdo_pct=payload.presence_hebdo_pct,
        qualif=payload.qualif,
        sequence=len(existing),
    )
    db.add(row)
    await db.commit()
    return _node_row_to_out(row)


@router.patch("/organigramme-nodes/{project_id}/{node_id}", response_model=OrganigrammeNodeOut)
async def update_organigramme_node(
    project_id: str,
    node_id: str,
    payload: OrganigrammeNodeUpdate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Persists an inline edit made in the interactive organigramme editor."""
    try:
        n_uuid = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant d'intervenant invalide.")

    row = await db.get(ProjectOrganigrammeNode, n_uuid)
    if not row or str(row.tenant_id) != current_user.tenant_id or str(row.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Intervenant introuvable.")

    if payload.nom is not None:
        row.nom = payload.nom
    if payload.role is not None:
        row.role = payload.role
    if payload.experience_ans is not None:
        row.experience_ans = payload.experience_ans
    if payload.presence_hebdo_pct is not None:
        row.presence_hebdo_pct = payload.presence_hebdo_pct
    if payload.qualif is not None:
        row.qualif = payload.qualif
    row.updated_at = datetime.utcnow()

    # Pas de db.refresh() apres le commit (retire le 04/09 des 4 endpoints Gantt +
    # organigramme qui l'avaient). get_db() ouvre la session dans un context manager :
    # une fois le commit fait, la transaction est fermee et toute requete SQL
    # supplementaire leve "Can't operate on closed transaction". Concretement, CHAQUE
    # ecriture commitait correctement puis repondait en erreur -- la valeur etait bien
    # en base mais le frontend croyait l'echec et n'affichait jamais la modification.
    # Le refresh etait de toute facon inutile : la session est creee avec
    # expire_on_commit=False et tous les defauts de colonnes sont cote Python, donc
    # `row` porte deja les valeurs definitives. Bonus : une requete DB de moins par
    # ecriture, ce qui compte quand la latence base monte a plusieurs secondes.
    await db.commit()
    return _node_row_to_out(row)


@router.delete("/organigramme-nodes/{project_id}/{node_id}")
async def delete_organigramme_node(
    project_id: str,
    node_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        n_uuid = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant d'intervenant invalide.")

    row = await db.get(ProjectOrganigrammeNode, n_uuid)
    if not row or str(row.tenant_id) != current_user.tenant_id or str(row.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Intervenant introuvable.")
    await db.delete(row)
    await db.commit()
    return {"success": True}


@router.post("/organigramme")
async def generate_project_organigramme(
    payload: DiagramGenerationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a site management organigramme PNG. If the project already has
    structured intervenants in project_organigramme_nodes (the interactive
    organigramme, 03/09), those are used -- reflecting the user's real, edited
    team -- instead of the legacy stateless `nodes` payload, which is now only a
    fallback for projects with no persisted nodes yet (mirrors
    generate_project_gantt's fallback pattern above). Correctif au passage :
    jusqu'ici le frontend appelait toujours cette route avec nodes=[], donc le
    PNG affichait TOUJOURS les 4 noms fictifs par defaut de diagram_service,
    jamais la vraie equipe_cadres du client.
    """
    rows = await _fetch_organigramme_node_rows(db, current_user.tenant_id, payload.project_id)
    brand_color = await _get_tenant_brand_color(db, current_user.tenant_id)
    shape_style = await _get_tenant_shape_style(db, current_user.tenant_id)
    cadres = [_node_row_to_cadre_dict(r) for r in rows] if rows else payload.nodes
    result = diagram_service.generate_organigramme_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.title or "Chantier BTP",
        cadres=cadres,
        brand_color=brand_color,
        shape_style=shape_style,
    )
    return result


@router.get("/file/{file_path:path}")
async def get_visual_file(
    file_path: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Streams image file bytes directly to browser/frontend.

    `file_path` is normally a full storage key already prefixed with
    "tenants/{tenant_id}/..." -- exactly what the generation endpoints return as
    s3_key. A leading "self/" is also accepted as an alias for "my own tenant",
    substituted below from the AUTHENTICATED user's real tenant_id (never from
    anything client-supplied) -- so the frontend never has to guess or hardcode a
    tenant UUID before a first generation has happened (see the initial-load path
    in organigramme-preview.tsx / gantt-preview.tsx).

    Bug fixed (30/08): this used to swallow EVERY failure (missing file,
    wrong-tenant path, real storage error) into a fabricated fallback Gantt PNG
    returned with 200 OK -- so a genuinely missing or unauthorized file silently
    rendered as fake, mislabeled content (a hardcoded demo Gantt chart) instead of
    the proper empty/error state the frontend already handles correctly. A missing
    file is now a real 404 and a cross-tenant path is now a real 403.
    """
    resolved_path = file_path
    if resolved_path.startswith("self/"):
        resolved_path = f"tenants/{current_user.tenant_id}/{resolved_path[len('self/'):]}"

    try:
        data = storage_service.download_file(current_user.tenant_id, resolved_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    content_type = "image/png"
    if resolved_path.endswith(".pdf"):
        content_type = "application/pdf"
    elif resolved_path.endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(content=data, media_type=content_type)
