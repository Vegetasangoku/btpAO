"""
Remplissage du cadre de reponse de l'acheteur (.docx) -- en place, styles conserves.

Refonte du 11/09. Constat en test reel sur un cadre de memoire technique type
(titres « 1. Moyens humains affectes », « 2. Methodologie et planning »,
« 3. Demarche qualite, securite et environnement », un tableau d'equipe vide,
cinq champs {{...}}) :
  - AUCUNE des quatre parties n'etait remplie : le service ne connaissait que les
    champs entre accolades ; les titres, les consignes et les tableaux etaient
    ignores, alors que c'est la forme de 99 % des cadres d'acheteurs ;
  - le rapport annoncait pourtant 80 % de completude ;
  - « Maitre d'ouvrage : Acheteur Public Detecte » etait compte comme rempli :
    c'est la valeur par defaut de l'assistant, pas une donnee ;
  - le niveau « RAG » collait le premier extrait du DCE contenant le MOT du champ
    (« lot » -> n'importe quel paragraphe citant un lot) ;
  - un champ coupe sur plusieurs « runs » Word etait compte rempli sans l'etre ;
  - un modele sans champ obtenait 100 % et « pret pour depot ».

Ce que fait le service desormais :
  1. Champs {{x}} / <<x>> / [[x]] : resolus depuis les donnees reelles du projet,
     de l'entreprise et du phasage declare ; valeurs par defaut refusees ; texte
     reecrit meme quand Word a coupe le champ en plusieurs morceaux.
  2. Titres du cadre : chaque partie est rapprochee des sections redigees (par
     themes : moyens humains, methodologie, qualite, securite, environnement...) et
     leur contenu est insere SOUS la consigne de l'acheteur, dans les styles du cadre.
     Une partie sans correspondance recoit un [A COMPLETER] rouge explicite.
  3. Tableau d'equipe (Fonction / Nom / Experience...) : rempli avec l'organigramme
     du projet, jamais avec des noms inventes.
  4. Partie « planning » : le planning du projet (PNG) y est insere.
  5. Score = parties et champs reellement remplis / total. Zero element detecte =
     0 %, jamais 100 %.
"""
import io
import logging
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import docx
from docx.shared import Inches, RGBColor
from pydantic import BaseModel

logger = logging.getLogger("client_template_filler")

RED_ALERT_COLOR = RGBColor(220, 38, 38)  # Tailwind red-600

# Valeurs que l'application pose par defaut : ce ne sont PAS des donnees du marche.
VALEURS_PAR_DEFAUT = {
    "acheteur public détecté", "acheteur public detecte", "lot 01 - gros œuvre", "lot 01 - gros oeuvre",
    "non renseigné", "non renseigne", "votre entreprise", "n/a", "",
}

# Themes de chaque section redigee, pour les rapprocher des titres du cadre.
THEMES_SECTIONS: Dict[str, Tuple[str, ...]] = {
    "presentation_entreprise": ("presentation", "entreprise", "candidat", "societe", "capacite"),
    "references_similaires": ("reference", "similaire", "experience", "chantiers realises"),
    "moyens_humains": ("humain", "personnel", "equipe", "encadrement", "organigramme", "effectif", "intervenant"),
    "moyens_materiels": ("materiel", "engin", "moyens techniques", "equipement"),
    "methodologie_phasage": ("methodologie", "methode", "phasage", "planning", "organisation du chantier", "organisation des travaux", "mode operatoire"),
    "qualite_controle": ("qualite", "controle", "autocontrole", "paq"),
    "securite_ppsps": ("securite", "ppsps", "prevention", "sante", "hygiene"),
    "rse_environnement": ("environnement", "dechet", "rse", "developpement durable", "carbone", "nuisance"),
    "sous_traitance": ("sous-traitance", "sous traitance", "sous-traitant", "cotraitance"),
}


def _norm(txt: str) -> str:
    t = unicodedata.normalize("NFKD", (txt or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


class CompletenessItem(BaseModel):
    section_name: str
    status: str  # 'filled', 'action_required'
    source_used: Optional[str] = None
    missing_elements: List[str] = []
    kind: str = "champ"  # 'champ' | 'partie' | 'tableau'


class CompletenessReport(BaseModel):
    total_fields: int
    filled_fields: int
    pending_actions_count: int
    completeness_score_pct: float
    is_ready_for_submission: bool
    sections: List[CompletenessItem]
    generated_at: str
    message: Optional[str] = None


class _HtmlVersBlocs(HTMLParser):
    """HTML des sections redigees -> blocs simples (titre, paragraphe, puce, tableau)."""

    def __init__(self):
        super().__init__()
        self.blocs: List[Tuple[str, Any]] = []
        self._buf: List[str] = []
        self._kind: Optional[str] = None
        self._table: Optional[List[List[str]]] = None
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in ("h1", "h2", "h3", "h4", "h5"):
            self._flush()
            self._kind = "titre"
        elif tag == "li":
            self._flush()
            self._kind = "puce"
        elif tag in ("p", "div"):
            self._flush()
            self._kind = "para"
        elif tag == "br":
            self._buf.append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.blocs.append(("tableau", self._table))
            self._table = None
        elif tag in ("h1", "h2", "h3", "h4", "h5", "li", "p", "div"):
            self._flush()

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._table is None:
            self._buf.append(data)

    def _flush(self):
        texte = " ".join("".join(self._buf).split())
        if texte:
            self.blocs.append((self._kind or "para", texte))
        self._buf = []
        self._kind = None

    def close(self):
        super().close()
        self._flush()


def html_vers_blocs(html: str) -> List[Tuple[str, Any]]:
    p = _HtmlVersBlocs()
    p.feed(html or "")
    p.close()
    return p.blocs


class ClientTemplateFillerService:
    PATTERN = re.compile(r"\{\{([^\}]+)\}\}|<<([^>]+)>>|\[\[([^\]]+)\]\]")

    # ------------------------------------------------------------------ champs
    @staticmethod
    def _resolve_field_value(
        field_key: str,
        project_data: Dict[str, Any],
        rag_chunks: List[str],
        company_assets: Dict[str, Any],
        tenant_learnings: List[Dict[str, Any]],
        declarations: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolution depuis des donnees REELLES uniquement. Une valeur par defaut de
        l'application n'est jamais renvoyee comme si c'etait une donnee du marche."""
        k = _norm(field_key).strip().replace(" ", "_").replace("-", "_")
        decl = declarations or {}

        def ok(v):
            return v is not None and _norm(str(v)).strip() not in VALEURS_PAR_DEFAUT

        table = [
            (("client_name", "acheteur", "maitre_ouvrage", "maitre_d_ouvrage", "pouvoir_adjudicateur"), project_data.get("client_name"), "Projet (acheteur)"),
            (("project_title", "titre_marche", "operation", "objet", "objet_du_marche", "intitule"), project_data.get("title"), "Projet (intitulé)"),
            (("reference_code", "reference", "consultation", "numero_consultation"), project_data.get("reference_code"), "Projet (référence)"),
            (("lot_number", "lot", "numero_lot"), project_data.get("lot_number"), "Projet (lot)"),
            (("lieu", "localisation", "adresse_chantier", "location"), project_data.get("location"), "Projet (lieu)"),
            (("company_name", "raison_sociale", "entreprise", "candidat", "nom_entreprise"), company_assets.get("name"), "Entreprise"),
            (("siret", "siren"), company_assets.get("siret"), "Entreprise"),
            (("headcount", "effectif"), company_assets.get("headcount"), "Entreprise"),
            (("insurance", "assurance", "decennale"), company_assets.get("insurance"), "Entreprise"),
            (("date_demarrage", "date_debut", "demarrage"), decl.get("date_demarrage"), "Données déclarées (démarrage)"),
        ]
        for cles, valeur, source in table:
            if k in cles and ok(valeur):
                return str(valeur), source

        # Delai : calcule depuis le phasage DECLARE (somme des durees), jamais estime.
        if k.startswith("delai") or k in ("duree", "duree_travaux"):
            phases = decl.get("phasage_travaux") or []
            semaines = 0
            for p in phases if isinstance(phases, list) else []:
                try:
                    semaines += int(float(p.get("duree_semaines") or 0))
                except (TypeError, ValueError, AttributeError):
                    pass
            if semaines <= 0 and decl.get("delai_mois"):
                try:
                    semaines = round(float(decl["delai_mois"]) * 4.33)
                except (TypeError, ValueError):
                    semaines = 0
            if semaines > 0:
                if "mois" in k:
                    return f"{round(semaines / 4.33, 1)}", "Phasage déclaré"
                if "semaine" in k:
                    return str(semaines), "Phasage déclaré"
                return f"{semaines} semaines", "Phasage déclaré"
        return None, None

    @staticmethod
    def _reecrire_paragraphe(paragraph, nouveau_texte: str, rouge: bool = False) -> None:
        """Remplace le texte d'un paragraphe en gardant la mise en forme de son
        premier morceau -- fonctionne meme quand Word a coupe un champ {{x}} sur
        plusieurs runs (cas frequent apres une correction orthographique)."""
        runs = paragraph.runs
        if not runs:
            r = paragraph.add_run(nouveau_texte)
            if rouge:
                r.font.color.rgb = RED_ALERT_COLOR
                r.font.bold = True
            return
        runs[0].text = nouveau_texte
        for r in runs[1:]:
            r.text = ""
        if rouge:
            runs[0].font.color.rgb = RED_ALERT_COLOR
            runs[0].font.bold = True

    # ------------------------------------------------------------------ parties
    @staticmethod
    def _niveau_titre(paragraph) -> Optional[int]:
        """Niveau de titre (1, 2, 3) ou None. Reconnait les styles Titre/Heading et,
        pour les cadres mal styles, les lignes courtes numerotees en gras."""
        style = _norm(paragraph.style.name if paragraph.style is not None else "")
        m = re.match(r"(heading|titre)\s*(\d)", style)
        if m:
            return int(m.group(2))
        if style in ("title", "titre"):
            return 0
        texte = paragraph.text.strip()
        if 3 < len(texte) < 140 and re.match(r"^(\d+(\.\d+)*[\.\)]?|[IVX]+[\.\)]|[A-H][\.\)])\s+\S", texte):
            gras = [r for r in paragraph.runs if r.text.strip()]
            if gras and all(r.bold for r in gras):
                return texte.split()[0].count(".") + 1 if re.match(r"^\d", texte) else 1
        return None

    @staticmethod
    def _sections_pour_titre(titre: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        t = _norm(titre)
        retenues = []
        for s in sections:
            key = s.get("section_key") or ""
            themes = THEMES_SECTIONS.get("rse_environnement" if key == "qse_environnement" else key, ())
            if any(th in t for th in themes):
                retenues.append(s)
        # Une meme section ne doit pas etre inseree deux fois (alias qse/rse).
        vues, uniques = set(), []
        for s in retenues:
            cle = "rse_environnement" if s.get("section_key") == "qse_environnement" else s.get("section_key")
            if cle not in vues:
                vues.add(cle)
                uniques.append(s)
        return uniques

    @staticmethod
    def _inserer_apres(ancre_elm, nouveaux: List[Any]) -> Any:
        for elm in nouveaux:
            ancre_elm.addnext(elm)
            ancre_elm = elm
        return ancre_elm

    def _blocs_en_elements(self, doc, blocs: List[Tuple[str, Any]], sous_titre: Optional[str]) -> List[Any]:
        """Cree les paragraphes/tableaux a la fin du document (styles du cadre) puis
        renvoie leurs elements XML, a deplacer sous le bon titre."""
        noms_styles = {s.name for s in doc.styles}
        style_puce = "List Bullet" if "List Bullet" in noms_styles else None
        elements = []
        if sous_titre:
            p = doc.add_paragraph()
            r = p.add_run(sous_titre)
            r.bold = True
            elements.append(p._p)
        for kind, contenu in blocs:
            if kind == "tableau":
                lignes = contenu
                ncol = max(len(l) for l in lignes)
                tab = doc.add_table(rows=len(lignes), cols=ncol)
                if "Table Grid" in noms_styles:
                    tab.style = "Table Grid"
                for i, ligne in enumerate(lignes):
                    for j in range(ncol):
                        tab.cell(i, j).text = ligne[j] if j < len(ligne) else ""
                        if i == 0:
                            for run in tab.cell(i, j).paragraphs[0].runs:
                                run.bold = True
                elements.append(tab._tbl)
            elif kind == "titre":
                p = doc.add_paragraph()
                r = p.add_run(contenu)
                r.bold = True
                elements.append(p._p)
            elif kind == "puce":
                p = doc.add_paragraph(contenu, style=style_puce) if style_puce else doc.add_paragraph("• " + contenu)
                elements.append(p._p)
            else:
                elements.append(doc.add_paragraph(contenu)._p)
        return elements

    @staticmethod
    def _remplir_tableau_equipe(table, equipe: List[Dict[str, Any]]) -> Optional[int]:
        """Remplit un tableau dont l'en-tete ressemble a Fonction / Nom / Experience.
        Renvoie le nombre de lignes remplies, ou None si ce n'est pas un tableau d'equipe."""
        if not table.rows or not equipe:
            return None
        entete = [_norm(c.text) for c in table.rows[0].cells]
        def col(*mots):
            for i, h in enumerate(entete):
                if any(m in h for m in mots):
                    return i
            return None
        c_role, c_nom = col("fonction", "role", "poste", "qualite"), col("nom", "intervenant", "identite")
        if c_role is None and c_nom is None:
            return None
        c_exp, c_pres, c_qual = col("experience", "anciennete"), col("presence", "temps", "taux"), col("qualification", "diplome", "formation")
        vides = [r for r in table.rows[1:] if not "".join(c.text for c in r.cells).strip()]
        remplies = 0
        for membre in equipe:
            if vides:
                ligne = vides.pop(0)
            else:
                ligne = table.add_row()
            valeurs = {
                c_role: membre.get("role"),
                c_nom: membre.get("nom"),
                c_exp: f"{membre.get('experience_ans')} ans" if membre.get("experience_ans") is not None else None,
                c_pres: f"{membre.get('presence_hebdo_pct')} %" if membre.get("presence_hebdo_pct") is not None else None,
                c_qual: membre.get("qualif"),
            }
            for idx, v in valeurs.items():
                if idx is not None and v and idx < len(ligne.cells):
                    ligne.cells[idx].text = str(v)
            remplies += 1
        return remplies

    # ------------------------------------------------------------------ point d'entree
    def fill_docx_template_inplace(
        self,
        template_bytes: bytes,
        project_data: Dict[str, Any],
        rag_chunks: Optional[List[str]] = None,
        company_assets: Optional[Dict[str, Any]] = None,
        tenant_learnings: Optional[List[Dict[str, Any]]] = None,
        sections: Optional[List[Dict[str, Any]]] = None,
        equipe: Optional[List[Dict[str, Any]]] = None,
        declarations: Optional[Dict[str, Any]] = None,
        planning_png: Optional[bytes] = None,
    ) -> Tuple[bytes, CompletenessReport]:
        doc = docx.Document(io.BytesIO(template_bytes))
        assets = company_assets or {}
        items: List[CompletenessItem] = []
        sections = [s for s in (sections or []) if (s.get("content_html") or "").strip() and s.get("status") != "failed"]
        equipe = equipe or []

        # 1. Champs
        avec_champs = set()  # elements XML des paragraphes qui portaient un champ

        def traiter(paragraph):
            texte = paragraph.text
            correspondances = list(self.PATTERN.finditer(texte))
            if not correspondances:
                return
            avec_champs.add(paragraph._p)
            nouveau, manque = texte, False
            for m in correspondances:
                cle = (m.group(1) or m.group(2) or m.group(3)).strip()
                val, source = self._resolve_field_value(cle, project_data, rag_chunks or [], assets, tenant_learnings or [], declarations)
                if val:
                    nouveau = nouveau.replace(m.group(0), val, 1)
                    items.append(CompletenessItem(section_name=cle, status="filled", source_used=source, kind="champ"))
                else:
                    nouveau = nouveau.replace(m.group(0), f"[À COMPLÉTER : {cle}]", 1)
                    manque = True
                    items.append(CompletenessItem(section_name=cle, status="action_required",
                                                  missing_elements=[f"Donnée absente du dossier : {cle}"], kind="champ"))
            self._reecrire_paragraphe(paragraph, nouveau, rouge=manque)

        for p in doc.paragraphs:
            traiter(p)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        traiter(p)

        # 2. Parties du cadre : on recense les titres dans l'ordre du corps.
        body = doc.element.body
        ordre = list(body.iterchildren())
        par_elm = {p._p: p for p in doc.paragraphs}
        tables_par_elm = {t._tbl: t for t in doc.tables}
        titres = []
        for idx, elm in enumerate(ordre):
            p = par_elm.get(elm)
            if p is None:
                continue
            niveau = self._niveau_titre(p)
            if niveau is not None and niveau >= 1:
                titres.append((idx, niveau, p))

        planning_insere = False
        deja_inserees: Dict[str, str] = {}  # section_key -> titre de la partie qui l'a recue
        for n, (idx, niveau, p) in enumerate(titres):
            fin = len(ordre)
            for idx2, niveau2, _ in titres[n + 1:]:
                if niveau2 <= niveau:
                    fin = idx2
                    break
            # Une partie qui a des sous-titres est traitee au niveau des sous-titres.
            a_des_enfants = n + 1 < len(titres) and titres[n + 1][0] < fin and titres[n + 1][1] > niveau
            if a_des_enfants:
                continue
            bloc = ordre[idx + 1:fin]
            prochain_titre = next((t[0] for t in titres[n + 1:]), len(ordre))
            bloc = ordre[idx + 1:min(fin, prochain_titre)]
            ancre = bloc[-1] if bloc else p._p
            titre = p.text.strip()

            # Tableaux d'equipe dans la partie
            for elm in bloc:
                t = tables_par_elm.get(elm)
                if t is not None:
                    nb = self._remplir_tableau_equipe(t, equipe)
                    if nb:
                        items.append(CompletenessItem(section_name=f"{titre} — tableau d'équipe", status="filled",
                                                      source_used=f"Organigramme du projet ({nb} intervenant(s))", kind="tableau"))
            # Ne jamais ancrer apres un sectPr (proprietes de section en fin de corps).
            while ancre is not None and ancre.tag.endswith("}sectPr"):
                ancre = ancre.getprevious()

            # Une partie qui ne demande qu'une valeur (« Délai : [[x]] ») est traitée
            # par ses champs : on n'y colle pas une section entière.
            if any(elm in avec_champs for elm in bloc) and ("delai" in _norm(titre) or len(bloc) <= 2):
                continue
            correspondantes = self._sections_pour_titre(titre, sections)
            deja = [s for s in correspondantes if s.get("section_key") in deja_inserees]
            correspondantes = [s for s in correspondantes if s.get("section_key") not in deja_inserees]
            nouveaux = []
            if not correspondantes and deja:
                renvoi = deja_inserees[deja[0].get("section_key")]
                pa = doc.add_paragraph(f"Voir la partie « {renvoi} ».")
                nouveaux.append(pa._p)
                items.append(CompletenessItem(section_name=titre, status="filled", kind="partie",
                                              source_used=f"Renvoi vers « {renvoi} »"))
                self._inserer_apres(ancre, nouveaux)
                continue
            if correspondantes:
                for s in correspondantes:
                    deja_inserees[s.get("section_key")] = titre
                for s in correspondantes:
                    blocs = html_vers_blocs(s.get("content_html") or "")
                    sous_titre = s.get("title") if len(correspondantes) > 1 else None
                    nouveaux += self._blocs_en_elements(doc, blocs, sous_titre)
                if planning_png and not planning_insere and "planning" in _norm(titre):
                    doc.add_picture(io.BytesIO(planning_png), width=Inches(6.3))
                    nouveaux.append(doc.paragraphs[-1]._p)
                    planning_insere = True
                items.append(CompletenessItem(
                    section_name=titre, status="filled", kind="partie",
                    source_used="Section(s) rédigée(s) : " + ", ".join(s.get("title") or s.get("section_key") for s in correspondantes),
                ))
            else:
                pa = doc.add_paragraph()
                r = pa.add_run(f"[À COMPLÉTER : aucune section rédigée ne répond à « {titre} »]")
                r.bold = True
                r.font.color.rgb = RED_ALERT_COLOR
                nouveaux.append(pa._p)
                items.append(CompletenessItem(section_name=titre, status="action_required", kind="partie",
                                              missing_elements=["Aucune section rédigée ne correspond à cette partie du cadre"]))
            self._inserer_apres(ancre, nouveaux)

        total = len(items)
        remplis = sum(1 for i in items if i.status == "filled")
        message = None
        if total == 0:
            message = ("Aucun champ ni aucune partie reconnue dans ce modèle : vérifiez qu'il utilise des titres "
                       "Word (styles Titre 1/2) ou des champs {{...}}.")
        report = CompletenessReport(
            total_fields=total,
            filled_fields=remplis,
            pending_actions_count=total - remplis,
            completeness_score_pct=round(remplis / total * 100, 1) if total else 0.0,
            is_ready_for_submission=bool(total) and remplis == total,
            sections=items,
            generated_at=datetime.now(timezone.utc).isoformat(),
            message=message,
        )
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue(), report


client_template_filler_service = ClientTemplateFillerService()
