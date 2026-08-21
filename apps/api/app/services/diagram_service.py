"""
Diagram Generator for BTP Organigrammes & Site Logistics
Generates clean structural diagrams and saves them to tenant storage as PNGs.
"""
import io
from typing import Any, Dict, List, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from app.core.storage import storage_service


class DiagramService:
    def generate_organigramme_png(
        self,
        tenant_id: str,
        project_id: str,
        project_title: str,
        cadres: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Builds a hierarchical site management organigramme PNG.
        """
        if not cadres:
            cadres = [
                {"nom": "Jean-Marc Alibert", "role": "Directeur de Projet & Conducteur Principal", "experience_ans": 15, "presence_hebdo_pct": 100},
                {"nom": "Sébastien Vasseur", "role": "Chef de Chantier Gros Œuvre", "experience_ans": 12, "presence_hebdo_pct": 100},
                {"nom": "Chloé Fontaine", "role": "Ingénieur QSE & Environnement", "experience_ans": 7, "presence_hebdo_pct": 50},
                {"nom": "Tarek Benali", "role": "Chef d'Équipe Coffrage / Banches", "experience_ans": 9, "presence_hebdo_pct": 100}
            ]

        fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")

        # Title
        ax.text(
            50, 94,
            f"ORGANIGRAMME D'ENCADREMENT ET DE CONDUITE DE TRAVAUX\n{project_title.upper()}",
            ha="center", va="center", fontsize=12, fontweight="bold", color="#0f172a"
        )

        # 1. MOA / MOE Box (Top Level)
        moa_box = patches.FancyBboxPatch((32, 75), 36, 11, boxstyle="round,pad=1.5,rounding_size=2",
                                         facecolor="#f1f5f9", edgecolor="#64748b", linewidth=1.5)
        ax.add_patch(moa_box)
        ax.text(50, 80.5, "MAÎTRISE D'OUVRAGE & MAÎTRISE D'ŒUVRE", ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#334155")

        # Connecting vertical line
        ax.plot([50, 50], [75, 63], color="#0284c7", linewidth=2.5)

        # 2. Main Project Manager Box (Level 2)
        lead = cadres[0] if cadres else {"nom": "Conducteur Principal", "role": "Directeur de Projet"}
        pm_box = patches.FancyBboxPatch((28, 51), 44, 12, boxstyle="round,pad=1.5,rounding_size=2",
                                        facecolor="#0284c7", edgecolor="#0369a1", linewidth=1.5)
        ax.add_patch(pm_box)
        ax.text(50, 58, f"{lead.get('role', 'Conducteur Principal').upper()}", ha="center", va="center",
                fontsize=10, fontweight="bold", color="#ffffff")
        ax.text(50, 53.5, f"{lead.get('nom', 'Jean-Marc Alibert')} ({lead.get('experience_ans', 15)} ans exp.) - Présence : 100%",
                ha="center", va="center", fontsize=8.5, color="#e0f2fe")

        # Connecting vertical branch
        ax.plot([50, 50], [51, 41], color="#0284c7", linewidth=2.5)
        ax.plot([18, 82], [41, 41], color="#0284c7", linewidth=2.5)

        # 3. Sub-roles (Level 3)
        sub_cadres = cadres[1:] if len(cadres) > 1 else [
            {"nom": "Chef de Chantier", "role": "Gros Œuvre"},
            {"nom": "Ingénieur QSE", "role": "Sécurité / RSE"}
        ]

        n_subs = len(sub_cadres)
        x_positions = [18 + i * (64 / max(1, n_subs - 1)) for i in range(n_subs)] if n_subs > 1 else [50]

        colors = ["#0d9488", "#4f46e5", "#d97706", "#059669"]

        for i, cadre in enumerate(sub_cadres):
            x = x_positions[i]
            # Vertical drop
            ax.plot([x, x], [41, 33], color="#0284c7", linewidth=2.0)
            
            c_box = patches.FancyBboxPatch((x - 13, 18), 26, 14, boxstyle="round,pad=1.2,rounding_size=2",
                                           facecolor="#ffffff", edgecolor=colors[i % len(colors)], linewidth=2.0)
            ax.add_patch(c_box)
            ax.text(x, 27.5, cadre.get("role", "Rôle").upper()[:28], ha="center", va="center",
                    fontsize=8.5, fontweight="bold", color="#0f172a")
            ax.text(x, 23.5, cadre.get("nom", "Nom"), ha="center", va="center",
                    fontsize=8, fontweight="semibold", color="#334155")
            ax.text(x, 20.0, f"Présence : {cadre.get('presence_hebdo_pct', 100)}% | {cadre.get('experience_ans', 10)} ans exp.",
                    ha="center", va="center", fontsize=7.5, color="#64748b")

        # Bottom Level: Production Teams Box
        prod_box = patches.FancyBboxPatch((20, 3), 60, 8, boxstyle="round,pad=1.0,rounding_size=1.5",
                                          facecolor="#f8fafc", edgecolor="#94a3b8", linewidth=1.2, linestyle="--")
        ax.add_patch(prod_box)
        ax.text(50, 7, "ÉQUIPES DE PRODUCTION GROS ŒUVRE & CORPS D'ÉTAT SECONDAIRES (18 COMPAGNONS & CHEFS D'ÉQUIPE)",
                ha="center", va="center", fontsize=8, fontweight="bold", color="#475569")

        plt.tight_layout()

        # ── CRITICAL: read bytes BEFORE closing the figure ──
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        img_bytes = img_buffer.read()
        plt.close(fig)       # close AFTER reading bytes

        # Save to tenant storage
        s3_key = storage_service.upload_file(
            tenant_id=tenant_id,
            subpath=f"visuals/{project_id}/organigramme_chantier.png",
            file_obj=img_bytes,
            content_type="image/png"
        )

        return {
            "s3_key": s3_key,
            "url": f"/api/visuals/file/{s3_key}",
            "bytes_length": len(img_bytes)
        }


diagram_service = DiagramService()
