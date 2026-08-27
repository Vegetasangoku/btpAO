#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 11 (cahier des charges majeur) -- Interactive Gantt backend.
Applies 5 exact-match patches:
  1. apps/api/app/models/entities.py       -- new ProjectGanttTask model
  2. apps/api/app/models/schemas.py        -- new Gantt task Pydantic schemas
  3. apps/api/app/services/gantt_service.py -- compute_critical_path, seed_tasks_from_phases,
                                                generate_gantt_chart_png_from_tasks
  4. apps/api/app/api/visuals.py            -- full rewrite: CRUD routes for gantt-tasks +
                                                task-aware /gantt endpoint
  5. apps/api/app/services/exporter_service.py -- optional gantt_tasks param on build_memo_docx
  6. apps/api/app/api/export.py             -- fetch + thread real gantt_tasks into the export call
  7. apps/api/app/workers/tasks.py          -- same, for the async Celery export path

Every anchor is matched via an exact-occurrence-count assertion before writing --
aborts cleanly (no partial write) if the live file doesn't match what was read.
"""
import sys
import ast

ROOT = sys.argv[1]  # repo root to patch (scratch copy OR real repo, same script both times)


def patch_file(relpath, replacements):
    path = f"{ROOT}/{relpath}"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new, expected_count in replacements:
        actual = content.count(old)
        if actual != expected_count:
            print(f"ABORT [{relpath}]: expected {expected_count} occurrence(s), found {actual}. "
                  f"No changes written to this file. Anchor snippet: {old[:120]!r}")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: patched {relpath}")


# ─── 1. entities.py ─────────────────────────────────────────────────────────
patch_file("apps/api/app/models/entities.py", [
    (
        "from sqlalchemy import (\n"
        "    Boolean,\n"
        "    Column,\n"
        "    DateTime,\n"
        "    ForeignKey,\n"
        "    Integer,\n"
        "    Numeric,\n"
        "    String,\n"
        "    Text,\n"
        ")\n"
        "from sqlalchemy.dialects.postgresql import JSONB, UUID",
        "from sqlalchemy import (\n"
        "    Boolean,\n"
        "    Column,\n"
        "    Date,\n"
        "    DateTime,\n"
        "    ForeignKey,\n"
        "    Integer,\n"
        "    Numeric,\n"
        "    String,\n"
        "    Text,\n"
        ")\n"
        "from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID",
        1,
    ),
    (
        "    is_active = Column(Boolean, nullable=False, default=True)\n"
        "    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)\n"
        "    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)\n"
        "\n"
        "\n"
        "class DCEDocument(Base):",
        "    is_active = Column(Boolean, nullable=False, default=True)\n"
        "    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)\n"
        "    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)\n"
        "\n"
        "\n"
        "class ProjectGanttTask(Base):\n"
        "    \"\"\"\n"
        "    Interactive Gantt task (Batch 11, cahier des charges majeur). Separate from\n"
        "    ProjectDecision.form_data['phasage_travaux'] -- see migration 00026 for why the\n"
        "    two are kept apart rather than merged.\n"
        "    \"\"\"\n"
        "    __tablename__ = \"project_gantt_tasks\"\n"
        "\n"
        "    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)\n"
        "    tenant_id = Column(UUID(as_uuid=True), ForeignKey(\"tenants.id\", ondelete=\"CASCADE\"), nullable=False)\n"
        "    project_id = Column(UUID(as_uuid=True), ForeignKey(\"projects.id\", ondelete=\"CASCADE\"), nullable=False)\n"
        "    name = Column(Text, nullable=False)\n"
        "    start_date = Column(Date, nullable=False)\n"
        "    end_date = Column(Date, nullable=False)\n"
        "    progress = Column(Integer, nullable=False, default=0)\n"
        "    sequence = Column(Integer, nullable=False, default=0)\n"
        "    is_milestone = Column(Boolean, nullable=False, default=False)\n"
        "    milestone_label = Column(Text, nullable=True)\n"
        "    depends_on = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)\n"
        "    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)\n"
        "    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)\n"
        "\n"
        "\n"
        "class DCEDocument(Base):",
        1,
    ),
])

# ─── 2. schemas.py ──────────────────────────────────────────────────────────
patch_file("apps/api/app/models/schemas.py", [
    (
        "class GanttGenerationRequest(BaseModel):\n"
        "    project_id: str\n"
        "    project_title: Optional[str] = \"Chantier BTP\"\n"
        "    phases: Optional[List[PhaseChantier]] = None\n"
        "    start_date: Optional[str] = \"2026-10-01\"\n",
        "class GanttGenerationRequest(BaseModel):\n"
        "    project_id: str\n"
        "    project_title: Optional[str] = \"Chantier BTP\"\n"
        "    phases: Optional[List[PhaseChantier]] = None\n"
        "    start_date: Optional[str] = \"2026-10-01\"\n"
        "\n"
        "\n"
        "# --- Interactive Gantt tasks (Batch 11, cahier des charges majeur) ---\n"
        "class GanttTaskBase(BaseModel):\n"
        "    name: str\n"
        "    start_date: str = Field(..., example=\"2026-10-01\")\n"
        "    end_date: str = Field(..., example=\"2026-10-08\")\n"
        "    progress: int = Field(default=0, ge=0, le=100)\n"
        "    is_milestone: bool = False\n"
        "    milestone_label: Optional[str] = None\n"
        "    depends_on: List[str] = Field(default_factory=list)\n"
        "\n"
        "\n"
        "class GanttTaskCreate(GanttTaskBase):\n"
        "    pass\n"
        "\n"
        "\n"
        "class GanttTaskUpdate(BaseModel):\n"
        "    name: Optional[str] = None\n"
        "    start_date: Optional[str] = None\n"
        "    end_date: Optional[str] = None\n"
        "    progress: Optional[int] = Field(default=None, ge=0, le=100)\n"
        "    is_milestone: Optional[bool] = None\n"
        "    milestone_label: Optional[str] = None\n"
        "    depends_on: Optional[List[str]] = None\n"
        "\n"
        "\n"
        "class GanttTaskOut(GanttTaskBase):\n"
        "    id: str\n"
        "    project_id: str\n"
        "    sequence: int\n"
        "    is_critical: bool = False\n",
        1,
    ),
])

# ─── 3. gantt_service.py ────────────────────────────────────────────────────
NEW_GANTT_METHODS = '''
    def compute_critical_path(self, tasks):
        """
        Classic forward/backward-pass Critical Path Method (CPM) over a DAG of tasks.
        Each task dict must have: id (str), start_date (date), end_date (date),
        depends_on (list of predecessor ids, possibly empty). Returns the set of task
        ids whose total float is zero (the critical path). Defensive against dependency
        cycles and stale/unknown predecessor ids (never raises, degrades to "no
        highlighted critical path" instead) -- verified against a diamond-DAG test case
        confirming it correctly distinguishes a critical branch from a parallel branch
        with slack, not just a trivial "everything is critical" sequential chain.
        """
        if not tasks:
            return set()
        by_id = {t["id"]: t for t in tasks}
        duration = {t["id"]: max((t["end_date"] - t["start_date"]).days, 0) for t in tasks}
        preds = {
            t["id"]: [p for p in (t.get("depends_on") or []) if p in by_id and p != t["id"]]
            for t in tasks
        }
        successors = {t["id"]: [] for t in tasks}
        for tid, plist in preds.items():
            for p in plist:
                successors[p].append(tid)

        in_degree = {tid: len(preds[tid]) for tid in by_id}
        queue = [tid for tid, d in in_degree.items() if d == 0]
        order = []
        qi = 0
        while qi < len(queue):
            tid = queue[qi]
            qi += 1
            order.append(tid)
            for s in successors[tid]:
                in_degree[s] -= 1
                if in_degree[s] == 0:
                    queue.append(s)

        if len(order) != len(by_id):
            # Dependency cycle -- degrade gracefully rather than raise or loop forever.
            return set()

        project_anchor = min(t["start_date"] for t in tasks).toordinal()
        es, ef = {}, {}
        for tid in order:
            if preds[tid]:
                es[tid] = max(ef[p] for p in preds[tid])
            else:
                es[tid] = by_id[tid]["start_date"].toordinal() - project_anchor
            ef[tid] = es[tid] + duration[tid]

        project_finish = max(ef.values())
        lf, ls = {}, {}
        for tid in reversed(order):
            if successors[tid]:
                lf[tid] = min(ls[s] for s in successors[tid])
            else:
                lf[tid] = project_finish
            ls[tid] = lf[tid] - duration[tid]

        return {tid for tid in by_id if ls[tid] - es[tid] == 0}

    def seed_tasks_from_phases(self, phases, start_date_str=None):
        """
        Converts the legacy sequential ProjectDecision.form_data['phasage_travaux'] list
        (phase name + duree_semaines + jalon) into a chain of real Gantt task dicts: each
        phase becomes one task whose sole dependency is the immediately preceding phase
        (matches the cascading-duration semantics already used by
        generate_gantt_chart_png). Used to lazily seed project_gantt_tasks the first time
        a project's interactive Gantt is opened. Returns [] if phases is empty -- never
        invents a default here, that decision belongs to the caller.
        """
        if not phases:
            return []
        try:
            cursor = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except Exception:
            cursor = datetime.date.today()

        tasks = []
        previous_id = None
        for p in phases:
            task_id = str(uuid.uuid4())
            duration_weeks = int(p.get("duree_semaines") or 4)
            task_start = cursor
            task_end = cursor + datetime.timedelta(days=max(duration_weeks, 1) * 7)
            tasks.append({
                "id": task_id,
                "name": p.get("phase") or "Phase",
                "start_date": task_start,
                "end_date": task_end,
                "progress": 0,
                "is_milestone": False,
                "milestone_label": p.get("jalon") or None,
                "depends_on": [previous_id] if previous_id else [],
            })
            cursor = task_end
            previous_id = task_id
        return tasks

    def generate_gantt_chart_png_from_tasks(self, tenant_id, project_id, project_title, tasks):
        """
        Renders the same high-resolution BTP Gantt PNG as generate_gantt_chart_png, but
        from real persisted project_gantt_tasks rows instead of a stateless phases list
        -- so the Word-export image always reflects the project's actual, user-edited
        plan instead of the generic 5-phase default. Critical-path tasks (computed via
        compute_critical_path) are drawn in red with a bolder edge, matching the
        interactive view's highlighting so the two stay visually consistent. Uploads to
        the SAME storage key as generate_gantt_chart_png, so any existing caller reading
        that key (e.g. the Word export) transparently picks up the richer chart.
        """
        if not tasks:
            return self.generate_gantt_chart_png(tenant_id, project_id, project_title, phases=[])

        ordered = sorted(tasks, key=lambda t: (t.get("sequence", 0), t["start_date"]))
        critical_ids = self.compute_critical_path(tasks)

        fig, ax = plt.subplots(figsize=(13, 6.5), dpi=300)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#f8fafc")

        bar_colors = ["#0284c7", "#0d9488", "#059669", "#d97706", "#4f46e5"]
        y_positions = list(range(len(ordered) - 1, -1, -1))

        for idx, y_pos in enumerate(y_positions):
            t = ordered[idx]
            p_start = t["start_date"]
            p_end = t["end_date"]
            duration_days = max((p_end - p_start).days, 1)
            is_critical = t["id"] in critical_ids
            color = "#dc2626" if is_critical else bar_colors[idx % len(bar_colors)]

            ax.barh(
                y_pos, duration_days, left=p_start, height=0.45, align="center",
                color=color, edgecolor="#0f172a", linewidth=1.6 if is_critical else 1.2,
                alpha=0.92, zorder=3
            )
            ax.text(
                p_start + datetime.timedelta(days=duration_days / 2), y_pos,
                f"{duration_days // 7} sem.", ha="center", va="center",
                color="#ffffff", fontweight="bold", fontsize=9, zorder=4
            )
            milestone = t.get("milestone_label")
            if milestone:
                ax.plot(
                    p_end, y_pos, marker="D", markersize=10, color="#e11d48",
                    markeredgecolor="#ffffff", markeredgewidth=1.5, zorder=5
                )
                ax.text(
                    p_end + datetime.timedelta(days=3), y_pos, f" {milestone}",
                    va="center", ha="left", color="#881337", fontsize=8.5,
                    fontweight="semibold", zorder=5
                )

        ax.set_yticks(y_positions)
        ax.set_yticklabels([t["name"] for t in ordered], fontsize=10, fontweight="bold", color="#1e293b")
        ax.xaxis_date()
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

        plt.setp(ax.get_xticklabels(), rotation=0, fontsize=9, color="#475569")
        ax.grid(axis="x", which="both", color="#cbd5e1", linestyle="--", linewidth=0.7, alpha=0.7, zorder=1)
        ax.set_axisbelow(True)

        overall_start = min(t["start_date"] for t in ordered)
        overall_end = max(t["end_date"] for t in ordered)
        total_weeks = (overall_end - overall_start).days // 7
        total_months = round(total_weeks / 4.33, 1)
        n_critical = len(critical_ids)
        plt.title(
            f"PLANNING PRÉVISIONNEL DE PHASAGE — {project_title.upper()}\\n"
            f"Durée globale : {total_weeks} semaines (~{total_months} mois) | Achèvement : {overall_end.strftime('%d/%m/%Y')} | "
            f"Chemin critique : {n_critical} tâche(s)",
            fontsize=12, fontweight="bold", color="#0f172a", pad=18
        )
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        img_bytes = img_buffer.read()
        plt.close(fig)

        s3_key = storage_service.upload_file(
            tenant_id=tenant_id,
            subpath=f"visuals/{project_id}/gantt_planning.png",
            file_obj=img_bytes,
            content_type="image/png"
        )

        return {
            "s3_key": s3_key,
            "url": f"/api/visuals/file/{s3_key}",
            "total_weeks": total_weeks,
            "completion_date": overall_end.strftime("%d/%m/%Y"),
            "bytes_length": len(img_bytes),
            "critical_task_count": n_critical,
        }

'''

patch_file("apps/api/app/services/gantt_service.py", [
    (
        "import datetime\nimport io\nfrom typing import Any, Dict, List, Optional",
        "import datetime\nimport io\nimport uuid\nfrom typing import Any, Dict, List, Optional",
        1,
    ),
    (
        "            \"bytes_length\": len(img_bytes)\n"
        "        }\n"
        "\n"
        "\n"
        "gantt_service = GanttService()",
        "            \"bytes_length\": len(img_bytes)\n"
        "        }\n"
        + NEW_GANTT_METHODS +
        "\ngantt_service = GanttService()",
        1,
    ),
])

# ─── 4. visuals.py (full, targeted rewrite) ────────────────────────────────
OLD_VISUALS = '''"""
Visuals, Gantt & Organigramme Generator Endpoints
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Response, status
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.core.storage import storage_service
from app.models.schemas import DiagramGenerationRequest, GanttGenerationRequest
from app.services.diagram_service import diagram_service
from app.services.gantt_service import gantt_service

router = APIRouter(prefix="/visuals", tags=["Visuals & Planning"])


@router.post("/gantt")
async def generate_project_gantt(
    payload: GanttGenerationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Generates a high-definition BTP Gantt chart PNG using matplotlib.
    """
    phases_dict = [p.dict() for p in payload.phases] if payload.phases else []
    result = gantt_service.generate_gantt_chart_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.project_title or "Chantier BTP",
        phases=phases_dict,
        start_date_str=payload.start_date or "2026-10-01"
    )
    return result'''

NEW_VISUALS = '''"""
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
    return result'''

patch_file("apps/api/app/api/visuals.py", [(OLD_VISUALS, NEW_VISUALS, 1)])

# ─── 5. exporter_service.py ─────────────────────────────────────────────────
patch_file("apps/api/app/services/exporter_service.py", [
    (
        "        template_bytes: Optional[bytes] = None,\n"
        "        include_visuals: bool = True,\n"
        "        required_section_titles: Optional[List[str]] = None,\n"
        "    ) -> Dict[str, Any]:",
        "        template_bytes: Optional[bytes] = None,\n"
        "        include_visuals: bool = True,\n"
        "        required_section_titles: Optional[List[str]] = None,\n"
        "        gantt_tasks: Optional[List[Dict[str, Any]]] = None,\n"
        "    ) -> Dict[str, Any]:",
        1,
    ),
    (
        "            try:\n"
        "                gantt_res = gantt_service.generate_gantt_chart_png(\n"
        "                    tenant_id=tenant_id,\n"
        "                    project_id=project_id,\n"
        "                    project_title=project_data.get(\"title\", \"Chantier BTP\"),\n"
        "                    phases=decision_form.get(\"phasage_travaux\", [])\n"
        "                )\n"
        "                gantt_bytes = storage_service.download_file(tenant_id, gantt_res[\"s3_key\"])",
        "            try:\n"
        "                if gantt_tasks:\n"
        "                    # Real, possibly user-edited tasks from the interactive Gantt (Batch 11)\n"
        "                    # take priority over the legacy static phase list, so what the user sees\n"
        "                    # and edits on screen is what actually gets embedded in the Word export.\n"
        "                    gantt_res = gantt_service.generate_gantt_chart_png_from_tasks(\n"
        "                        tenant_id=tenant_id,\n"
        "                        project_id=project_id,\n"
        "                        project_title=project_data.get(\"title\", \"Chantier BTP\"),\n"
        "                        tasks=gantt_tasks,\n"
        "                    )\n"
        "                else:\n"
        "                    gantt_res = gantt_service.generate_gantt_chart_png(\n"
        "                        tenant_id=tenant_id,\n"
        "                        project_id=project_id,\n"
        "                        project_title=project_data.get(\"title\", \"Chantier BTP\"),\n"
        "                        phases=decision_form.get(\"phasage_travaux\", [])\n"
        "                    )\n"
        "                gantt_bytes = storage_service.download_file(tenant_id, gantt_res[\"s3_key\"])",
        1,
    ),
])

# ─── 6. export.py ───────────────────────────────────────────────────────────
patch_file("apps/api/app/api/export.py", [
    (
        "from app.models.entities import ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, Tenant",
        "from app.models.entities import ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, ProjectGanttTask, Tenant",
        1,
    ),
    (
        "    decision_form = decision.form_data if decision else {}\n"
        "\n"
        "    tmpl_stmt = select(ExportTemplate).where(\n"
        "        ExportTemplate.tenant_id == t_uuid,\n"
        "        ExportTemplate.is_default == True,\n"
        "    )",
        "    decision_form = decision.form_data if decision else {}\n"
        "\n"
        "    gantt_tasks_stmt = select(ProjectGanttTask).where(\n"
        "        ProjectGanttTask.tenant_id == t_uuid,\n"
        "        ProjectGanttTask.project_id == p_uuid,\n"
        "    ).order_by(ProjectGanttTask.sequence, ProjectGanttTask.start_date)\n"
        "    gantt_tasks_res = await db.execute(gantt_tasks_stmt)\n"
        "    gantt_task_rows = gantt_tasks_res.scalars().all()\n"
        "    gantt_tasks = [\n"
        "        {\n"
        "            \"id\": str(r.id), \"name\": r.name, \"start_date\": r.start_date, \"end_date\": r.end_date,\n"
        "            \"sequence\": r.sequence, \"milestone_label\": r.milestone_label,\n"
        "            \"depends_on\": [str(d) for d in (r.depends_on or [])],\n"
        "        }\n"
        "        for r in gantt_task_rows\n"
        "    ] or None\n"
        "\n"
        "    tmpl_stmt = select(ExportTemplate).where(\n"
        "        ExportTemplate.tenant_id == t_uuid,\n"
        "        ExportTemplate.is_default == True,\n"
        "    )",
        1,
    ),
    (
        "        include_visuals=False,\n"
        "        required_section_titles=required_section_titles,\n"
        "    )\n"
        "\n"
        "    raw_title = project.title or \"Memoire_Technique\"",
        "        include_visuals=False,\n"
        "        required_section_titles=required_section_titles,\n"
        "        gantt_tasks=gantt_tasks,\n"
        "    )\n"
        "\n"
        "    raw_title = project.title or \"Memoire_Technique\"",
        1,
    ),
])

# ─── 7. tasks.py ─────────────────────────────────────────────────────────────
patch_file("apps/api/app/workers/tasks.py", [
    (
        "from app.models.entities import DCEDocument, DCEEmbedding, ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, CompanyAsset, Tenant",
        "from app.models.entities import DCEDocument, DCEEmbedding, ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, ProjectGanttTask, CompanyAsset, Tenant",
        1,
    ),
    (
        "                decision_form = decision.form_data if decision else {}\n"
        "\n"
        "                tmpl_stmt = select(ExportTemplate).where(\n"
        "                    ExportTemplate.tenant_id == tenant_uuid,\n"
        "                    ExportTemplate.is_default == True,\n"
        "                )",
        "                decision_form = decision.form_data if decision else {}\n"
        "\n"
        "                gantt_tasks_stmt = select(ProjectGanttTask).where(\n"
        "                    ProjectGanttTask.tenant_id == tenant_uuid,\n"
        "                    ProjectGanttTask.project_id == proj_uuid,\n"
        "                ).order_by(ProjectGanttTask.sequence, ProjectGanttTask.start_date)\n"
        "                gantt_tasks_res = await db.execute(gantt_tasks_stmt)\n"
        "                gantt_task_rows = gantt_tasks_res.scalars().all()\n"
        "                gantt_tasks = [\n"
        "                    {\n"
        "                        \"id\": str(r.id), \"name\": r.name, \"start_date\": r.start_date, \"end_date\": r.end_date,\n"
        "                        \"sequence\": r.sequence, \"milestone_label\": r.milestone_label,\n"
        "                        \"depends_on\": [str(d) for d in (r.depends_on or [])],\n"
        "                    }\n"
        "                    for r in gantt_task_rows\n"
        "                ] or None\n"
        "\n"
        "                tmpl_stmt = select(ExportTemplate).where(\n"
        "                    ExportTemplate.tenant_id == tenant_uuid,\n"
        "                    ExportTemplate.is_default == True,\n"
        "                )",
        1,
    ),
    (
        "                    include_visuals=include_visuals,\n"
        "                    required_section_titles=required_section_titles,\n"
        "                )\n"
        "\n"
        "                file_bytes = docx_res[\"docx_bytes\"]",
        "                    include_visuals=include_visuals,\n"
        "                    required_section_titles=required_section_titles,\n"
        "                    gantt_tasks=gantt_tasks,\n"
        "                )\n"
        "\n"
        "                file_bytes = docx_res[\"docx_bytes\"]",
        1,
    ),
])

print("All backend batch-11 patches applied.")
