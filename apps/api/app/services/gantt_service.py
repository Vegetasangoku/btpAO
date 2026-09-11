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
import matplotlib.patches as mpatches
from app.core.storage import storage_service


def _readable_text_color(hex_color: str) -> str:
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
    """Facteur mutation_aspect pour les barres arrondies/pilule. Volontairement PAS la
    correction "complete" (display_ratio / data_ratio) qu'utilise diagram_service._get_
    aspect : sur un Gantt, l'axe x (dates, ~des dizaines/centaines de jours) et l'axe y
    (index de tache, quelques unites) ont un rapport de donnees si extreme (souvent >30:1)
    que cette division fait exploser mutation_aspect (valeurs ~15-20+), ce qui casse le
    calcul de coin arrondi de FancyBboxPatch (des pointes verticales parasites plutot
    qu'un coin arrondi -- constate empiriquement par rendu PNG avant integration, 01/09).
    Le ratio d'affichage seul (hauteur/largeur des axes en pixels, independant de l'echelle
    des donnees) reste dans une plage raisonnable (~0.5-0.7 pour ce format de figure) et
    produit un arrondi propre et borne -- verifie de meme par rendu PNG compare. Pour
    diagram_service (organigramme), les deux formules coincident de toute facon puisque
    ses axes sont deja carres (0-100 / 0-100, data_ratio=1)."""
    try:
        ll, ur = ax.transAxes.transform([(0, 0), (1, 1)])
        disp_w, disp_h = (ur - ll)
        return disp_h / disp_w
    except Exception:
        return 1.0


def _draw_phase_bar(ax, y_pos, p_start, duration_days, bar_height, color, edgecolor, linewidth, alpha, zorder, shape_style, mutation_aspect):
    """Dessine une barre de phase Gantt. "anguleux" (par defaut, ou valeur absente/
    inconnue) garde EXACTEMENT le rendu historique (ax.barh, rectangle net) -- aucune
    regression pour les tenants n'ayant jamais choisi de style. "arrondi"/"pilule"
    dessinent un FancyBboxPatch avec correction d'aspect (voir _get_aspect) pour un
    arrondi visuellement correct malgre l'echelle tres differente des axes x (dates) et y
    (index de tache) -- verifie empiriquement avant integration (rendu PNG compare)."""
    style = (shape_style or "anguleux").strip().lower()
    if style not in ("arrondi", "pilule"):
        ax.barh(
            y_pos, duration_days, left=p_start, height=bar_height, align="center",
            color=color, edgecolor=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder,
        )
        return
    # Facteurs verifies par rendu PNG (01/09) : au-dela d'environ 1.5-2x bar_height, le
    # rayon d'arrondi depasse la moitie de la hauteur de la barre et FancyBboxPatch produit
    # le meme artefact de pointes parasites que mentionne dans _get_aspect ci-dessus, donc
    # rester nettement en-dessous de ce seuil pour les deux presets.
    rounding_factor = 0.7 if style == "arrondi" else 1.3
    x0 = mdates.date2num(p_start)
    box = mpatches.FancyBboxPatch(
        (x0, y_pos - bar_height / 2), duration_days, bar_height,
        boxstyle=f"round,pad=0,rounding_size={bar_height * rounding_factor}",
        facecolor=color, edgecolor=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder,
        mutation_aspect=mutation_aspect,
    )
    ax.add_patch(box)


def _milestone_marker(shape_style: Optional[str]) -> str:
    """"anguleux" (par defaut/valeur absente) -> losange (rendu historique inchange) ;
    "arrondi"/"pilule" -> cercle."""
    style = (shape_style or "anguleux").strip().lower()
    return "o" if style in ("arrondi", "pilule") else "D"


# ---------------------------------------------------------------------------
# Planning hierarchique et reglages d'affichage (11/09)
# ---------------------------------------------------------------------------
# Retour Charbel : « le Gantt est trop macro, pas assez de taches et sous-taches ;
# on devrait pouvoir choisir le niveau, les couleurs, certains parametres ».
# Les reglages ci-dessous sont PARTAGES par la vue interactive (frontend) et par
# le PNG insere dans le Word/PDF : ce que l'utilisateur regle a l'ecran est ce qui
# part dans le memoire.

# Palettes proposees. "charte" est calculee a partir des couleurs du client.
GANTT_PALETTES: Dict[str, List[str]] = {
    "btp": ["#0369a1", "#0f766e", "#b45309", "#7c3aed", "#be123c", "#4d7c0f", "#1d4ed8", "#a16207"],
    "contraste": ["#1e3a8a", "#c2410c", "#15803d", "#7e22ce", "#b91c1c", "#0e7490", "#a16207", "#334155"],
    "pastel": ["#60a5fa", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#fb923c", "#2dd4bf", "#94a3b8"],
    "sobre": ["#334155", "#475569", "#64748b", "#1e293b", "#52525b", "#3f3f46", "#57534e", "#44403c"],
}

DEFAULT_GANTT_SETTINGS: Dict[str, Any] = {
    "niveau_detail": "sous_taches",
    "couleur_par": "phase",
    "palette": [],
    "chemin_critique": True,
    "jalons": True,
    "durees": True,
    "liens": True,
}

_HEX_OK = __import__("re").compile(r"^#[0-9a-fA-F]{6}$")


def _hex_ok(value: Any) -> Optional[str]:
    v = str(value or "").strip()
    if v and not v.startswith("#"):
        v = "#" + v
    return v if _HEX_OK.match(v) else None


def normalize_gantt_settings(*layers: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Fusionne reglages par defaut < entreprise < projet, en ecartant toute valeur
    invalide (une palette mal formee retombe sur la charte, jamais une erreur)."""
    out = dict(DEFAULT_GANTT_SETTINGS)
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        for key in DEFAULT_GANTT_SETTINGS:
            if key in layer and layer[key] is not None:
                out[key] = layer[key]
    if out["niveau_detail"] not in ("phases", "taches", "sous_taches"):
        out["niveau_detail"] = "sous_taches"
    if out["couleur_par"] not in ("phase", "lot", "uniforme"):
        out["couleur_par"] = "phase"
    palette = out.get("palette")
    if isinstance(palette, str):
        palette = GANTT_PALETTES.get(palette, [])
    out["palette"] = [c for c in (_hex_ok(x) for x in (palette or [])) if c][:12]
    for key in ("chemin_critique", "jalons", "durees", "liens"):
        out[key] = bool(out[key])
    return out


def _shade(hex_color: str, amount: float) -> str:
    """Eclaircit (amount > 0, vers le blanc) ou fonce (amount < 0)."""
    h = (_hex_ok(hex_color) or "#0284c7").lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if amount >= 0:
        r, g, b = (int(c + (255 - c) * amount) for c in (r, g, b))
    else:
        r, g, b = (int(c * (1 + amount)) for c in (r, g, b))
    return "#{:02x}{:02x}{:02x}".format(max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255)))


def order_gantt_hierarchy(tasks: List[Dict[str, Any]]) -> List[tuple]:
    """Ordre d'affichage : chaque phase suivie de ses taches, chaque tache de ses
    sous-taches (parcours en profondeur). Renvoie [(tache, niveau)]. Une tache dont le
    parent n'existe plus est traitee comme une phase plutot que perdue ; un cycle
    parent/enfant (impossible via l'API, mais possible en base) est coupe."""
    by_id = {str(t["id"]): t for t in tasks}
    children: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for t in tasks:
        parent = str(t.get("parent_id") or "") or None
        if parent is not None and parent not in by_id:
            parent = None
        children.setdefault(parent, []).append(t)
    for lst in children.values():
        lst.sort(key=lambda t: (t.get("sequence", 0), t["start_date"]))
    ordered: List[tuple] = []
    seen: set = set()

    def walk(parent: Optional[str], level: int) -> None:
        for t in children.get(parent, []):
            tid = str(t["id"])
            if tid in seen:
                continue
            seen.add(tid)
            ordered.append((t, level))
            walk(tid, min(level + 1, 3))

    walk(None, 0)
    for t in tasks:  # orphelins pris dans un cycle
        if str(t["id"]) not in seen:
            ordered.append((t, 0))
    return ordered


def resolve_gantt_palette(settings: Dict[str, Any], brand_color: Optional[str]) -> List[str]:
    palette = list(settings.get("palette") or [])
    if palette:
        return palette
    base = GANTT_PALETTES["btp"]
    brand = _hex_ok(brand_color)
    return ([brand] + [c for c in base if c.lower() != brand.lower()]) if brand else base


class GanttService:
    def generate_gantt_chart_png(
        self,
        tenant_id: str,
        project_id: str,
        project_title: str,
        phases: List[Dict[str, Any]],
        start_date_str: Optional[str] = "2026-10-01",
        brand_color: Optional[str] = None,
        shape_style: Optional[str] = None,
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

        # Couleur de marque du client en tete de palette (branding_config.primary_color,
        # 30/08) -- les 4 teintes suivantes restent fixes pour garder les phases
        # visuellement distinctes (un Gantt entierement monochrome perdrait sa lisibilite).
        bar_colors = [brand_color or "#0284c7", "#0d9488", "#059669", "#d97706", "#4f46e5"]

        y_positions = list(range(len(task_names) - 1, -1, -1))

        use_rounded_bars = (shape_style or "").strip().lower() in ("arrondi", "pilule")
        if use_rounded_bars:
            # Bornes explicites AVANT le tracé pour que get_data_ratio() (donc la
            # correction d'aspect du rounding, voir _get_aspect) soit stable quel que
            # soit l'ordre de tracé des barres -- laissé à l'autoscale par défaut pour
            # "anguleux" afin de ne rien changer au comportement historique.
            x_margin_days = max((end_dates[-1] - start_dates[0]).days * 0.02, 1)
            ax.set_xlim(
                mdates.date2num(start_dates[0] - datetime.timedelta(days=x_margin_days)),
                mdates.date2num(end_dates[-1] + datetime.timedelta(days=x_margin_days)),
            )
            ax.set_ylim(-0.5, len(y_positions) - 0.5)
        mutation_aspect = _get_aspect(ax) if use_rounded_bars else 1.0

        for idx, y_pos in enumerate(y_positions):
            p_start = start_dates[idx]
            p_end = end_dates[idx]
            duration_days = (p_end - p_start).days
            color = bar_colors[idx % len(bar_colors)]

            _draw_phase_bar(
                ax, y_pos, p_start, duration_days, 0.45, color, "#0f172a", 1.2, 0.92, 3,
                shape_style, mutation_aspect,
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
                    marker=_milestone_marker(shape_style),
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

    ROWS_PER_PAGE = 42

    def generate_gantt_chart_png_from_tasks(self, tenant_id, project_id, project_title, tasks,
                                            brand_color=None, shape_style=None, settings=None):
        """
        PNG haute definition du planning REEL du projet (project_gantt_tasks), tel que
        l'utilisateur l'a edite -- hierarchique depuis le 11/09 :

        - phase avec detail visible : barre de synthese fine et foncee, crochets aux
          extremites (convention MS Project / Primavera que les jurys connaissent) ;
        - tache : barre pleine a la couleur de sa phase (ou de son lot) ;
        - sous-tache : barre plus fine et plus claire, libelle indente.

        `settings` (voir normalize_gantt_settings) : niveau de detail, coloration par
        phase / lot / uniforme, palette, chemin critique, jalons, durees.
        Au-dela de ROWS_PER_PAGE lignes, le planning est coupe en plusieurs images
        (meme echelle de temps) : une seule image de 120 lignes serait illisible une
        fois reduite a la largeur d'une page A4. La premiere image garde la cle
        historique gantt_planning.png ; les suivantes sont listees dans "pages".
        """
        cfg = normalize_gantt_settings(settings)
        if not tasks:
            return self.generate_gantt_chart_png(tenant_id, project_id, project_title, phases=[], brand_color=brand_color, shape_style=shape_style)

        ordered_all = order_gantt_hierarchy(tasks)
        max_level = {"phases": 0, "taches": 1, "sous_taches": 3}[cfg["niveau_detail"]]
        rows = [(t, lvl) for (t, lvl) in ordered_all if lvl <= max_level]
        visible_ids = {str(t["id"]) for t, _ in rows}
        has_visible_children = {
            str(t.get("parent_id")) for t, _ in rows if t.get("parent_id") and str(t.get("parent_id")) in visible_ids
        }

        # Couleurs : chaque phase recoit une teinte ; ses descendants en heritent
        # (ou prennent celle de leur lot). Une couleur posee sur la ligne l'emporte.
        palette = resolve_gantt_palette(cfg, brand_color)
        phase_color: Dict[str, str] = {}
        lot_color: Dict[str, str] = {}
        by_id = {str(t["id"]): t for t in tasks}

        def root_of(t):
            seen = set()
            cur = t
            while cur.get("parent_id") and str(cur["parent_id"]) in by_id and str(cur["id"]) not in seen:
                seen.add(str(cur["id"]))
                cur = by_id[str(cur["parent_id"])]
            return cur

        for t, lvl in ordered_all:
            if lvl == 0:
                phase_color[str(t["id"])] = _hex_ok(t.get("color")) or palette[len(phase_color) % len(palette)]

        def color_for(t, lvl):
            own = _hex_ok(t.get("color"))
            if own:
                return own
            if cfg["couleur_par"] == "uniforme":
                base = palette[0]
            elif cfg["couleur_par"] == "lot" and (t.get("lot") or "").strip():
                key = t["lot"].strip().lower()
                if key not in lot_color:
                    lot_color[key] = palette[len(lot_color) % len(palette)]
                base = lot_color[key]
            else:
                base = phase_color.get(str(root_of(t)["id"]), palette[0])
            return _shade(base, 0.35) if lvl >= 2 else base

        critical_ids = self.compute_critical_path(tasks) if cfg["chemin_critique"] else set()
        # Un chemin critique qui couvre toutes les lignes ne distingue rien : on ne le
        # dessine pas (meme regle que la vue interactive).
        if critical_ids and visible_ids.issubset(critical_ids):
            critical_ids = set()

        overall_start = min(t["start_date"] for t in tasks)
        overall_end = max(t["end_date"] for t in tasks)
        total_days = max((overall_end - overall_start).days, 1)
        x_margin = max(total_days * 0.02, 1)
        # Place a droite pour le libelle des jalons.
        x_right = max(total_days * 0.16, 10) if cfg["jalons"] else x_margin

        pages = [rows[i:i + self.ROWS_PER_PAGE] for i in range(0, len(rows), self.ROWS_PER_PAGE)] or [[]]
        keys: List[str] = []
        total_bytes = 0
        use_rounded_bars = (shape_style or "").strip().lower() in ("arrondi", "pilule")

        for page_idx, page_rows in enumerate(pages):
            n = len(page_rows)
            fig_h = max(4.8, 1.9 + 0.34 * n)
            fig, ax = plt.subplots(figsize=(13, fig_h), dpi=250)
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#ffffff")
            ax.set_xlim(
                mdates.date2num(overall_start - datetime.timedelta(days=x_margin)),
                mdates.date2num(overall_end + datetime.timedelta(days=x_right)),
            )
            ax.set_ylim(-0.6, n - 0.4)
            mutation_aspect = _get_aspect(ax) if use_rounded_bars else 1.0

            labels = []
            y_positions = []
            band = False
            for idx, (t, lvl) in enumerate(page_rows):
                y = n - 1 - idx
                y_positions.append(y)
                tid = str(t["id"])
                if lvl == 0:
                    band = not band
                if band:
                    ax.axhspan(y - 0.5, y + 0.5, color="#f1f5f9", zorder=0, linewidth=0)

                p_start, p_end = t["start_date"], t["end_date"]
                days = max((p_end - p_start).days, 1)
                col = color_for(t, lvl)
                is_summary = lvl == 0 and tid in has_visible_children
                is_critical = tid in critical_ids
                edge = "#dc2626" if is_critical else _shade(col, -0.35)
                lw = 1.8 if is_critical else 0.8

                if is_summary:
                    dark = _shade(col, -0.25)
                    x0 = mdates.date2num(p_start)
                    ax.barh(y + 0.08, days, left=p_start, height=0.16, color=dark, zorder=3, linewidth=0)
                    for xe in (x0, x0 + days):
                        ax.add_patch(mpatches.Polygon(
                            [(xe - total_days * 0.004, y + 0.16), (xe + total_days * 0.004, y + 0.16), (xe, y - 0.12)],
                            closed=True, color=dark, zorder=4,
                        ))
                elif t.get("is_milestone") and p_end == p_start:
                    ax.plot(p_start, y, marker="D", markersize=9, color=col, markeredgecolor="#0f172a", zorder=5)
                else:
                    height = {0: 0.56, 1: 0.5}.get(lvl, 0.34)
                    _draw_phase_bar(ax, y, p_start, days, height, col, edge, lw, 0.95, 3, shape_style, mutation_aspect)
                    if cfg["durees"]:
                        weeks = days / 7
                        txt = f"{round(weeks)} sem." if weeks >= 1.5 else f"{days} j"
                        if days >= total_days * 0.06:
                            ax.text(p_start + datetime.timedelta(days=days / 2), y, txt, ha="center", va="center",
                                    color=_readable_text_color(col), fontsize=7.5 if lvl >= 2 else 8.5,
                                    fontweight="bold", zorder=4)
                        else:
                            ax.text(p_end + datetime.timedelta(days=total_days * 0.005), y, txt, ha="left", va="center",
                                    color="#475569", fontsize=7, zorder=4)

                milestone = (t.get("milestone_label") or "").strip()
                if cfg["jalons"] and milestone and lvl <= 1:
                    ax.plot(p_end, y, marker=_milestone_marker(shape_style), markersize=8, color="#e11d48",
                            markeredgecolor="#ffffff", markeredgewidth=1.2, zorder=6)
                    ax.text(p_end + datetime.timedelta(days=total_days * 0.012), y - 0.02, milestone[:48],
                            va="center", ha="left", color="#881337", fontsize=7.5, fontweight="semibold", zorder=6)

                name = str(t.get("name") or "")
                lot = (t.get("lot") or "").strip()
                if lvl >= 1 and lot and cfg["couleur_par"] == "lot":
                    name = f"{name} [{lot}]"
                limit = 58 - 4 * lvl
                name = name if len(name) <= limit else name[: limit - 1] + "…"
                labels.append(("    " * lvl) + (name.upper() if lvl == 0 else name))

            ax.set_yticks(y_positions)
            tick_labels = ax.set_yticklabels(labels)
            for (t, lvl), lab in zip(page_rows, tick_labels):
                lab.set_fontsize({0: 9.5, 1: 8.8}.get(lvl, 8))
                lab.set_fontweight({0: "bold", 1: "semibold"}.get(lvl, "normal"))
                lab.set_color({0: "#0f172a", 1: "#1e293b"}.get(lvl, "#475569"))
                lab.set_horizontalalignment("left")
            ax.tick_params(axis="y", length=0, pad=0)
            # Libelles alignes a gauche : on decale d'autant la zone de texte.
            fig.canvas.draw()
            # get_window_extent est en pixels, `pad` en points : conversion obligatoire,
            # sinon l'ecart libelles/barres est multiplie par dpi/72 (~3,5).
            max_w_px = max((lab.get_window_extent().width for lab in tick_labels), default=0)
            ax.yaxis.set_tick_params(pad=max_w_px * 72.0 / fig.dpi + 4)

            ax.xaxis_date()
            span_months = total_days / 30.4
            if span_months > 14:
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            else:
                ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            if total_days <= 200:
                ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
            ax.xaxis.tick_top()
            plt.setp(ax.get_xticklabels(), rotation=0, fontsize=8.5, color="#475569")
            ax.grid(axis="x", which="major", color="#cbd5e1", linestyle="-", linewidth=0.6, zorder=1)
            ax.grid(axis="x", which="minor", color="#e2e8f0", linestyle=":", linewidth=0.5, zorder=1)
            ax.set_axisbelow(True)
            for side in ("right", "left", "bottom"):
                ax.spines[side].set_visible(False)
            ax.spines["top"].set_color("#94a3b8")

            total_weeks = total_days // 7
            if page_idx == 0:
                nb = {0: 0, 1: 0, 2: 0}
                for _, lvl in ordered_all:
                    nb[min(lvl, 2)] += 1
                detail = f"{nb[0]} phase(s)"
                if nb[1]:
                    detail += f", {nb[1]} tâche(s)"
                if nb[2]:
                    detail += f", {nb[2]} sous-tâche(s)"
                crit = f" | Chemin critique : {len(critical_ids)} ligne(s)" if critical_ids else ""
                fig.suptitle(
                    f"PLANNING PRÉVISIONNEL D'EXÉCUTION — {str(project_title).upper()[:80]}\n"
                    f"Durée globale : {total_weeks} semaines (~{round(total_weeks / 4.33, 1)} mois) | "
                    f"Du {overall_start.strftime('%d/%m/%Y')} au {overall_end.strftime('%d/%m/%Y')} | {detail}{crit}",
                    fontsize=11, fontweight="bold", color="#0f172a", y=0.995,
                )
            else:
                fig.suptitle(f"PLANNING PRÉVISIONNEL (suite {page_idx + 1}/{len(pages)})",
                             fontsize=10, fontweight="bold", color="#0f172a", y=0.995)
            plt.tight_layout(rect=(0, 0, 1, 1 - 0.5 / fig_h))

            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=250, bbox_inches="tight")
            img_bytes = img_buffer.getvalue()
            plt.close(fig)
            total_bytes += len(img_bytes)
            name = "gantt_planning.png" if page_idx == 0 else f"gantt_planning_p{page_idx + 1}.png"
            keys.append(storage_service.upload_file(
                tenant_id=tenant_id, subpath=f"visuals/{project_id}/{name}",
                file_obj=img_bytes, content_type="image/png",
            ))

        return {
            "s3_key": keys[0],
            "url": f"/api/visuals/file/{keys[0]}",
            "pages": keys,
            "total_weeks": total_days // 7,
            "completion_date": overall_end.strftime("%d/%m/%Y"),
            "bytes_length": total_bytes,
            "critical_task_count": len(critical_ids),
            "rows": len(rows),
        }


gantt_service = GanttService()
