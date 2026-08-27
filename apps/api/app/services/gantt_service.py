"""
High-Resolution BTP Gantt Chart Generator using Matplotlib
Produces crisp professional PNGs ready for insertion in Word .docx & Web previews.

Fix: savefig to buffer BEFORE plt.close() to avoid I/O-on-closed-file error.
"""
import datetime
import io
import uuid
from typing import Any, Dict, List, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — must be set before importing pyplot
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from app.core.storage import storage_service


class GanttService:
    def generate_gantt_chart_png(
        self,
        tenant_id: str,
        project_id: str,
        project_title: str,
        phases: List[Dict[str, Any]],
        start_date_str: Optional[str] = "2026-10-01",
    ) -> Dict[str, Any]:
        """
        Builds a high-resolution BTP construction Gantt chart with phase bars, milestones & buffers.
        Returns s3_key, url, total_weeks, completion_date, bytes_length.
        """
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        except Exception:
            start_date = datetime.datetime.now()

        if not phases:
            phases = [
                {"phase": "1. Installation de chantier, PIC & Terrassements", "duree_semaines": 4, "jalon": "Plateforme opérationnelle"},
                {"phase": "2. Fondations profondes et longrines", "duree_semaines": 4, "jalon": "Réception géotechnique"},
                {"phase": "3. Superstructure R+2 Gros Œuvre", "duree_semaines": 10, "jalon": "Hors d'eau / Hors d'air"},
                {"phase": "4. VRD & Aménagements extérieurs", "duree_semaines": 4, "jalon": "Essais & OPR"},
                {"phase": "5. Repli de chantier & Livraison", "duree_semaines": 2, "jalon": "Remise des clés"}
            ]

        # Calculate phase dates
        task_names = []
        start_dates = []
        end_dates = []
        milestone_names = []

        current_cursor = start_date
        for p in phases:
            task_names.append(p.get("phase", "Phase"))
            duration_weeks = int(p.get("duree_semaines", 4))
            p_start = current_cursor
            p_end = p_start + datetime.timedelta(days=duration_weeks * 7)
            start_dates.append(p_start)
            end_dates.append(p_end)
            milestone_names.append(p.get("jalon", ""))
            current_cursor = p_end

        # Matplotlib Chart Styling
        fig, ax = plt.subplots(figsize=(13, 6.5), dpi=300)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#f8fafc")

        # Color palette (BTP Steel Blue, Amber, Teal, Emerald, Indigo)
        bar_colors = ["#0284c7", "#0d9488", "#059669", "#d97706", "#4f46e5"]

        y_positions = list(range(len(task_names) - 1, -1, -1))

        for idx, y_pos in enumerate(y_positions):
            p_start = start_dates[idx]
            p_end = end_dates[idx]
            duration_days = (p_end - p_start).days
            color = bar_colors[idx % len(bar_colors)]

            ax.barh(
                y_pos,
                duration_days,
                left=p_start,
                height=0.45,
                align="center",
                color=color,
                edgecolor="#0f172a",
                linewidth=1.2,
                alpha=0.92,
                zorder=3
            )

            ax.text(
                p_start + datetime.timedelta(days=duration_days / 2),
                y_pos,
                f"{duration_days // 7} sem.",
                ha="center",
                va="center",
                color="#ffffff",
                fontweight="bold",
                fontsize=9,
                zorder=4
            )

            milestone = milestone_names[idx]
            if milestone:
                ax.plot(
                    p_end,
                    y_pos,
                    marker="D",
                    markersize=10,
                    color="#e11d48",
                    markeredgecolor="#ffffff",
                    markeredgewidth=1.5,
                    zorder=5
                )
                ax.text(
                    p_end + datetime.timedelta(days=3),
                    y_pos,
                    f" {milestone}",
                    va="center",
                    ha="left",
                    color="#881337",
                    fontsize=8.5,
                    fontweight="semibold",
                    zorder=5
                )

        # Formatting axes
        ax.set_yticks(y_positions)
        ax.set_yticklabels(task_names, fontsize=10, fontweight="bold", color="#1e293b")
        ax.xaxis_date()
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

        plt.setp(ax.get_xticklabels(), rotation=0, fontsize=9, color="#475569")
        ax.grid(axis="x", which="both", color="#cbd5e1", linestyle="--", linewidth=0.7, alpha=0.7, zorder=1)
        ax.set_axisbelow(True)

        total_weeks = (end_dates[-1] - start_dates[0]).days // 7
        total_months = round(total_weeks / 4.33, 1)
        plt.title(
            f"PLANNING PRÉVISIONNEL DE PHASAGE — {project_title.upper()}\n"
            f"Durée globale : {total_weeks} semaines (~{total_months} mois) | Achèvement : {end_dates[-1].strftime('%d/%m/%Y')}",
            fontsize=12,
            fontweight="bold",
            color="#0f172a",
            pad=18
        )

        plt.tight_layout()

        # ── CRITICAL: save to buffer BEFORE closing the figure ──
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        img_bytes = img_buffer.read()
        plt.close(fig)          # close AFTER reading bytes

        # Upload to tenant storage
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
            "completion_date": end_dates[-1].strftime("%d/%m/%Y"),
            "bytes_length": len(img_bytes)
        }

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
            f"PLANNING PRÉVISIONNEL DE PHASAGE — {project_title.upper()}\n"
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


gantt_service = GanttService()
