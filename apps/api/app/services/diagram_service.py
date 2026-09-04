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


def _readable_text_color(hex_color: Optional[str]) -> str:
    """Pique blanc ou anthracite selon la luminance perçue de hex_color, pour que le
    texte reste lisible quel que soit la couleur de marque choisie par le client (une
    couleur de marque claire avec du texte blanc dessus serait illisible)."""
    try:
        h = (hex_color or "").lstrip("#")
        if len(h) != 6:
            return "#ffffff"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#0f172a" if luminance > 0.6 else "#ffffff"
    except Exception:
        return "#ffffff"


def _get_aspect(ax) -> float:
    """Facteur de correction (display/data) applique a mutation_aspect d'un FancyBboxPatch
    pour qu'un rounding_size donne produise un arrondi visuellement correct meme quand les
    axes x et y de la figure n'ont pas la meme echelle -- verifie empiriquement (rendu PNG
    compare avec/sans correction) avant integration, 01/09 : sans elle, un rounding_size
    assez grand pour un rendu "pilule" apparait ecrase ou etire selon l'axe le plus large.
    Ne leve jamais d'exception (repli sur 1.0, un arrondi "presque correct" plutot qu'un
    crash de la generation)."""
    try:
        ll, ur = ax.transAxes.transform([(0, 0), (1, 1)])
        disp_w, disp_h = (ur - ll)
        axes_ratio = disp_h / disp_w
        data_ratio = ax.get_data_ratio()
        if not data_ratio:
            return 1.0
        return axes_ratio / data_ratio
    except Exception:
        return 1.0


def _boxstyle_for(shape_style: Optional[str], pad: float, height: float, default_rounding: float = 2.0) -> str:
    """Traduit le prereglage de formes du tenant (branding_config.shape_style, BT02) en
    boxstyle matplotlib pour une boite de l'organigramme donnee. "anguleux" -> coins
    carres ; "pilule" -> arrondi prononce proportionnel a la hauteur de la boite (rendu
    "gelule") ; valeur absente/inconnue ou "arrondi" -> rendu historique inchange
    (default_rounding, identique box par box a ce qui existait avant ce parametre --
    aucune regression pour les tenants n'ayant jamais choisi de style)."""
    style = (shape_style or "arrondi").strip().lower()
    if style == "anguleux":
        return f"square,pad={pad}"
    if style == "pilule":
        return f"round,pad={pad},rounding_size={round(height / 2.0, 2)}"
    return f"round,pad={pad},rounding_size={default_rounding}"


class DiagramService:
    def generate_organigramme_png(
        self,
        tenant_id: str,
        project_id: str,
        project_title: str,
        cadres: Optional[List[Dict[str, Any]]] = None,
        brand_color: Optional[str] = None,
        shape_style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds a hierarchical site management organigramme PNG. `brand_color` (hex),
        when supplied, is the client's own branding_config.primary_color -- replaces
        the default steel-blue accent on the connecting lines and the lead's box so the
        chart reflects the client's own color charter (30/08, demande explicite).
        `shape_style` (branding_config.shape_style, BT02, 01/09) is one of "anguleux" /
        "arrondi" / "pilule" ; absent ou non reconnu retombe sur "arrondi", le rendu
        historique code en dur, donc aucun changement visuel pour les tenants existants.
        """
        accent = brand_color or "#0284c7"
        accent_text = _readable_text_color(accent)
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
        mutation_aspect = _get_aspect(ax)

        # Title
        ax.text(
            50, 94,
            f"ORGANIGRAMME D'ENCADREMENT ET DE CONDUITE DE TRAVAUX\n{project_title.upper()}",
            ha="center", va="center", fontsize=12, fontweight="bold", color="#0f172a"
        )

        # 1. MOA / MOE Box (Top Level)
        moa_box = patches.FancyBboxPatch((32, 75), 36, 11, boxstyle=_boxstyle_for(shape_style, 1.5, 11),
                                         facecolor="#f1f5f9", edgecolor="#64748b", linewidth=1.5,
                                         mutation_aspect=mutation_aspect)
        ax.add_patch(moa_box)
        ax.text(50, 80.5, "MAÎTRISE D'OUVRAGE & MAÎTRISE D'ŒUVRE", ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#334155")

        # Connecting vertical line
        ax.plot([50, 50], [75, 63], color=accent, linewidth=2.5)

        # 2. Main Project Manager Box (Level 2)
        lead = cadres[0] if cadres else {"nom": "Conducteur Principal", "role": "Directeur de Projet"}
        pm_box = patches.FancyBboxPatch((28, 51), 44, 12, boxstyle=_boxstyle_for(shape_style, 1.5, 12),
                                        facecolor=accent, edgecolor=accent, linewidth=1.5,
                                        mutation_aspect=mutation_aspect)
        ax.add_patch(pm_box)
        ax.text(50, 58, f"{lead.get('role', 'Conducteur Principal').upper()}", ha="center", va="center",
                fontsize=10, fontweight="bold", color=accent_text)
        ax.text(50, 53.5, f"{lead.get('nom', 'Jean-Marc Alibert')} ({lead.get('experience_ans', 15)} ans exp.) - Présence : 100%",
                ha="center", va="center", fontsize=8.5, color=accent_text)

        # Connecting vertical branch
        ax.plot([50, 50], [51, 41], color=accent, linewidth=2.5)
        ax.plot([18, 82], [41, 41], color=accent, linewidth=2.5)

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
            ax.plot([x, x], [41, 33], color=accent, linewidth=2.0)
            
            c_box = patches.FancyBboxPatch((x - 13, 18), 26, 14, boxstyle=_boxstyle_for(shape_style, 1.2, 14),
                                           facecolor="#ffffff", edgecolor=colors[i % len(colors)], linewidth=2.0,
                                           mutation_aspect=mutation_aspect)
            ax.add_patch(c_box)
            ax.text(x, 27.5, cadre.get("role", "Rôle").upper()[:28], ha="center", va="center",
                    fontsize=8.5, fontweight="bold", color="#0f172a")
            ax.text(x, 23.5, cadre.get("nom", "Nom"), ha="center", va="center",
                    fontsize=8, fontweight="semibold", color="#334155")
            ax.text(x, 20.0, f"Présence : {cadre.get('presence_hebdo_pct', 100)}% | {cadre.get('experience_ans', 10)} ans exp.",
                    ha="center", va="center", fontsize=7.5, color="#64748b")

        # Bottom Level: Production Teams Box
        prod_box = patches.FancyBboxPatch((20, 3), 60, 8, boxstyle=_boxstyle_for(shape_style, 1.0, 8, default_rounding=1.5),
                                          facecolor="#f8fafc", edgecolor="#94a3b8", linewidth=1.2, linestyle="--",
                                          mutation_aspect=mutation_aspect)
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
