"""
High-Resolution BTP Gantt Chart Generator using Matplotlib
Produces crisp professional PNGs ready for insertion in Word .docx & Web previews.

Fix: savefig to buffer BEFORE plt.close() to avoid I/O-on-closed-file error.
"""
import datetime
import io
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


gantt_service = GanttService()
