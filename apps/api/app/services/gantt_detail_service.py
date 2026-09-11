"""
Decomposition du planning en taches et sous-taches (11/09).

Retour Charbel : « le Gantt n'est pas assez detaille, trop macro ». Le planning
se limitait aux phases du phasage declare (Installation, Gros oeuvre, Second
oeuvre, Finitions, Reception) : cinq barres, aucune tache. Un jury lit un planning
d'execution pour verifier que l'entreprise a compris l'ouvrage ; cinq barres ne le
montrent pas.

Principe
--------
1. Les PHASES existantes ne bougent pas : leurs dates sont celles que le client a
   declarees ou editees (regle nº1 de visual_spec_service : la saisie fait foi).
2. Le detail est construit A L'INTERIEUR de chaque phase, a partir :
   - du CCTP / DCE du projet (les ouvrages reellement decrits) ;
   - des anciens dossiers de l'entreprise quand ils contiennent un planning
     (se caler sur les exemples les plus fournis du client) ;
   - des enseignements « planning » memorises par l'entreprise.
3. Toute date proposee hors des bornes de sa phase est ramenee dans la phase, et
   c'est dit dans le rapport. Rien n'est applique en silence.
4. Sans modele IA disponible, un gabarit BTP generique sert de repli -- et le
   rapport le dit explicitement, pour qu'il soit relu avant depot.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CompanyAsset,
    DCEDocument,
    DCEEmbedding,
    Project,
    ProjectDecision,
    ProjectGanttTask,
    TenantLearning,
)

logger = logging.getLogger(__name__)

MAX_TACHES_PAR_PHASE = 10
MAX_SOUS_TACHES_PAR_TACHE = 6
MAX_LIGNES = 180
CCTP_MAX_CHARS = 26000
REFERENCES_MAX_CHARS = 7000

CATEGORIES_ANCIENS_MEMOIRES = ("memoire_reference", "memoire", "dossier_reference", "reference_chantier")
_MOTS_OUVRAGES = re.compile(
    r"(d[ée]moli|d[ée]samiant|curage|terrass|fondation|b[ée]ton|ma[çc]onn|charpent|couvertur|"
    r"[ée]tanch|menuiser|cloison|doublage|pl[âa]tr|isolation|[ée]lectri|plomberie|chauffage|"
    r"ventil|cvc|peinture|rev[êe]tement|carrel|vrd|r[ée]seau|voirie|fa[çc]ade|ravalement|"
    r"serrurerie|m[ée]tallerie|ascenseur|ssi|d[ée]senfum|dallage|plancher|enduit|faux.plafond|"
    r"sanitaire|lot\s*n?[°o]?\s*\d)", re.I)
_SOMMAIRE = re.compile(r"\.{8,}")
_MOTS_PLANNING = re.compile(r"(planning|phasage|ordonnancement|d[ée]lai d.ex[ée]cution|semaine|cadence|encha[iî]nement)", re.I)


# ---------------------------------------------------------------------------
# Gabarit de repli (sans IA) : decomposition BTP courante, par mots-cles de phase.
# ---------------------------------------------------------------------------
_GABARIT: List[tuple] = [
    (("installation", "prepar", "pic", "base"), [
        ("Préparation : DICT, constat d'huissier, référé préventif", ["Envoi des DICT", "Constat d'huissier contradictoire"]),
        ("Plan d'installation de chantier et PPSPS", ["Rédaction PPSPS", "Validation du PIC par la MOE"]),
        ("Clôtures, signalisation et accès", ["Pose des clôtures", "Signalisation provisoire"]),
        ("Base-vie et branchements provisoires", ["Livraison des cantonnements", "Raccordements eau / électricité"]),
    ]),
    (("terrass", "vrd", "réseau", "reseau"), [
        ("Implantation et piquetage", ["Implantation par géomètre", "Contrôle contradictoire"]),
        ("Terrassements généraux", ["Décapage de la terre végétale", "Déblais / remblais"]),
        ("Réseaux enterrés", ["Tranchées", "Pose et essais des réseaux"]),
    ]),
    (("fondation", "gros", "structure", "maçon", "macon"), [
        ("Terrassements en fouilles", ["Fouilles en rigole / en puits", "Réception des fonds de fouille"]),
        ("Fondations", ["Béton de propreté", "Ferraillage et coulage des semelles"]),
        ("Réseaux sous dallage et dallage", ["Réseaux sous dallage", "Coulage du dallage"]),
        ("Élévations et planchers", ["Voiles et poteaux", "Planchers et poutres"]),
        ("Toiture et étanchéité", ["Charpente / couverture", "Étanchéité"]),
    ]),
    (("second", "clos", "couvert", "menuiser", "lot"), [
        ("Menuiseries extérieures", ["Pose des châssis", "Calfeutrements"]),
        ("Cloisons et doublages", ["Rails et ossatures", "Plaques et bandes"]),
        ("Lots techniques : électricité", ["Passage des gaines", "Tirage des câbles et appareillage"]),
        ("Lots techniques : plomberie / CVC", ["Réseaux d'alimentation et d'évacuation", "Équipements terminaux"]),
    ]),
    (("finition", "peinture", "revêt", "revet"), [
        ("Revêtements de sols", ["Préparation des supports", "Pose des revêtements"]),
        ("Peintures", ["Enduits et impressions", "Couches de finition"]),
        ("Nettoyage et levée des réserves internes", ["Nettoyage fin de chantier", "Autocontrôle et levée des réserves"]),
    ]),
    (("récep", "recep", "livraison", "repli", "opr"), [
        ("Essais et autocontrôles", ["Essais des installations", "Dossier des autocontrôles"]),
        ("Opérations préalables à la réception (OPR)", ["Visite OPR avec la MOE", "Levée des réserves"]),
        ("Repli et DOE", ["Repli des installations", "Remise du DOE / DIUO"]),
    ]),
]


def _gabarit_pour(nom_phase: str) -> List[tuple]:
    n = (nom_phase or "").lower()
    for mots, taches in _GABARIT:
        if any(m in n for m in mots):
            return taches
    return [("Préparation et approvisionnements", ["Commandes", "Livraisons"]),
            ("Exécution des ouvrages", ["Réalisation", "Autocontrôles"]),
            ("Contrôles et réception de la phase", ["Contrôle MOE", "Levée des réserves"])]


def _parse(v: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except Exception:
        return None


def _txt(v: Any, n: int = 160) -> str:
    return " ".join(str(v or "").split())[:n]


def _cle(nom: str) -> str:
    """Cle de doublon : sans accents, sans ponctuation, sans mots vides."""
    import unicodedata
    t = unicodedata.normalize("NFKD", nom.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    mots = [m for m in re.findall(r"[a-z0-9]+", t) if m not in ("de", "des", "du", "la", "le", "les", "et", "a", "au", "aux", "l", "d", "en")]
    return " ".join(mots)


def _repartir(debut: date, fin: date, n: int) -> List[tuple]:
    """Decoupe [debut, fin] en n creneaux successifs (au moins 1 jour chacun)."""
    total = max((fin - debut).days, n)
    pas = total / n
    out = []
    for i in range(n):
        s = debut + timedelta(days=round(i * pas))
        e = debut + timedelta(days=round((i + 1) * pas))
        if e <= s:
            e = s + timedelta(days=1)
        out.append((s, min(e, fin) if fin > s else e))
    return out


# ---------------------------------------------------------------------------
# Contexte : CCTP, anciens dossiers, enseignements
# ---------------------------------------------------------------------------
async def _contexte(db: AsyncSession, tenant_id: uuid.UUID, project: Project) -> Dict[str, Any]:
    docs = (await db.execute(
        select(DCEDocument.id, DCEDocument.filename, DCEDocument.doc_type)
        .where(DCEDocument.tenant_id == tenant_id, DCEDocument.project_id == project.id)
    )).all()
    # Le CCTP d'abord (il decrit les ouvrages), puis DPGF/BPU, puis le reste.
    priorite = {"cctp": 0, "dpgf": 1, "bpu": 1, "dqe": 1, "planning": 1, "rc": 3}
    docs = sorted(docs, key=lambda d: priorite.get(str(d.doc_type or "").lower(), 2))
    # Constat du 11/09 sur le CCTP « Ressourcerie » (38 pages) : lire le dossier
    # dans l'ordre remplissait tout le budget avec le sommaire et la definition des
    # etudes (APS, APD...), et le modele ne voyait jamais la description des
    # ouvrages -- d'ou des taches generiques (« Recueillir les plans »). On retient
    # donc en priorite les passages qui decrivent des OUVRAGES, puis on les remet
    # dans l'ordre du document.
    morceaux: List[str] = []
    sources: List[str] = []
    candidats: List[tuple] = []
    for rang_doc, d in enumerate(docs):
        chunks = (await db.execute(
            select(DCEEmbedding.chunk_index, DCEEmbedding.section_title, DCEEmbedding.content)
            .where(DCEEmbedding.document_id == d.id)
            .order_by(DCEEmbedding.chunk_index)
        )).all()
        if not chunks:
            continue
        sources.append(d.filename)
        for c in chunks:
            texte = c.content or ""
            score = len(_MOTS_OUVRAGES.findall(texte)) / max(len(texte) / 1000, 1)
            if _SOMMAIRE.search(texte):
                score *= 0.2  # un sommaire cite tout mais ne decrit rien
            candidats.append((score - rang_doc * 0.5, rang_doc, float(c.chunk_index or 0), d, c))
    total = 0
    retenus = []
    for cand in sorted(candidats, key=lambda x: -x[0]):
        bloc_len = len(cand[4].content or "")
        if total + bloc_len > CCTP_MAX_CHARS:
            continue
        retenus.append(cand)
        total += bloc_len
    doc_courant = None
    for _, _, _, d, c in sorted(retenus, key=lambda x: (x[1], x[2])):
        if doc_courant != d.id:
            morceaux.append(f"=== {d.filename} ({d.doc_type}) ===")
            doc_courant = d.id
        morceaux.append((f"[{c.section_title}] " if c.section_title else "") + (c.content or ""))

    # Anciens dossiers : on retient les passages qui parlent de planning, en
    # commencant par les dossiers les plus fournis.
    refs = (await db.execute(
        select(CompanyAsset.title, CompanyAsset.description)
        .where(CompanyAsset.tenant_id == tenant_id,
               CompanyAsset.category.in_(CATEGORIES_ANCIENS_MEMOIRES),
               CompanyAsset.obsolete_at.is_(None))
    )).all()
    refs = sorted(refs, key=lambda r: len(r.description or ""), reverse=True)
    extraits: List[str] = []
    ref_titres: List[str] = []
    budget = REFERENCES_MAX_CHARS
    for r in refs:
        texte = r.description or ""
        passages = []
        for m in _MOTS_PLANNING.finditer(texte):
            a, b = max(0, m.start() - 500), min(len(texte), m.end() + 1200)
            if passages and a <= passages[-1][1]:
                passages[-1] = (passages[-1][0], b)
            else:
                passages.append((a, b))
        if not passages:
            continue
        extrait = "\n…\n".join(texte[a:b] for a, b in passages)[:max(0, budget)]
        if not extrait:
            break
        extraits.append(f"--- Ancien dossier : {r.title} ---\n{extrait}")
        ref_titres.append(r.title)
        budget -= len(extrait)
        if budget <= 0:
            break

    lecons = (await db.execute(
        select(TenantLearning.learning_insight, TenantLearning.actionable_directive)
        .where(TenantLearning.tenant_id == tenant_id, TenantLearning.is_active.is_(True),
               TenantLearning.category.in_(("planning", "planning_phasage")))
        .limit(8)
    )).all()
    return {
        "dce": "\n".join(morceaux),
        "dce_sources": sources,
        "references": "\n\n".join(extraits),
        "reference_titres": ref_titres,
        "lecons": [f"- {l.actionable_directive or l.learning_insight}" for l in lecons],
    }


# ---------------------------------------------------------------------------
# Appel au modele
# ---------------------------------------------------------------------------
async def _proposer_par_ia(db, tenant_id, project, phases, niveau, ctx) -> tuple[Optional[Dict[str, Any]], str]:
    from app.services.billing_service import billing_service
    from app.services.model_routing_service import model_routing_service
    import litellm

    cap, _c, _s = await billing_service.is_cost_cap_exceeded(tenant_id, db)
    if cap:
        return None, "plafond de coût IA mensuel atteint"
    resolved = await model_routing_service.resolve_model_for_tenant(db=db, tenant_id=tenant_id, task_type="redaction_memoire")
    model = resolved["model_string"]
    creds = await model_routing_service.get_credentials_for_model(db=db, model_string=model)
    if not creds.get("api_key"):
        return None, "aucune clé de modèle IA configurée"

    lignes_phases = "\n".join(
        f'{i + 1}. "{p.name}" du {p.start_date.isoformat()} au {p.end_date.isoformat()}'
        + (f" — jalon : {p.milestone_label}" if p.milestone_label else "")
        for i, p in enumerate(phases)
    )
    sous = niveau == "sous_taches"
    consigne_sous = (
        "Chaque tâche contient 2 à 5 sous-tâches (\"sous_taches\"), elles aussi datées DANS la tâche."
        if sous else "Ne produis PAS de sous-tâches (\"sous_taches\": [])."
    )
    systeme = (
        "Tu es un ingénieur méthodes BTP qui établit des plannings d'exécution pour des mémoires "
        "techniques d'appels d'offres. Tu décomposes des phases déjà datées en tâches concrètes, "
        "fidèles aux ouvrages décrits dans le CCTP. Tu n'inventes ni quantité, ni nom de personne, "
        "ni ouvrage absent du dossier : si le CCTP ne décrit pas un ouvrage, tu ne le planifies pas."
    )
    utilisateur = f"""PROJET : {project.title} — {project.client_name or ''} — {project.location or ''}

PHASES (dates FIXES, décidées par le client — ne les modifie pas) :
{lignes_phases}

CONSIGNES :
- Pour CHAQUE phase, 3 à 8 tâches opérationnelles, datées au format AAAA-MM-JJ et comprises
  entre le début et la fin de la phase. Les tâches peuvent se chevaucher quand c'est réaliste
  (corps d'état en parallèle) ; sinon elles s'enchaînent.
- {consigne_sous}
- "lot" : le lot ou corps d'état du marché tel qu'il est nommé dans le CCTP (ex. "Lot 02 — Gros œuvre"),
  ou null s'il n'est pas identifiable.
- "depends_on" : noms EXACTS de tâches de la même phase qui doivent être finies avant.
- "source" : "cctp" si la tâche découle d'un article du CCTP, "reference" si elle reprend un ancien
  dossier de l'entreprise, "usage" pour une tâche d'usage courant (préparation, contrôles, réception).
- Intitulés courts (moins de 60 caractères), vocabulaire du CCTP et des anciens dossiers.
- Chaque intitulé est UNIQUE dans le planning : pas deux tâches qui disent la même chose
  avec d'autres mots. Une sous-tâche détaille SA tâche, elle ne la répète pas.
- Priorité aux OUVRAGES à réaliser (démolition, gros œuvre, menuiseries, lots techniques…),
  pas aux tâches administratives : au plus UNE tâche de préparation/coordination par phase.
- Si une phase ne correspond à aucun ouvrage du CCTP, garde-la avec 2 ou 3 tâches d'usage.

ENSEIGNEMENTS DE L'ENTREPRISE SUR SES PLANNINGS :
{chr(10).join(ctx['lecons']) or '(aucun)'}

EXTRAITS DE PLANNINGS DE SES ANCIENS DOSSIERS (s'en inspirer pour le niveau de détail et les intitulés) :
{ctx['references'] or '(aucun ancien dossier avec planning)'}

DOSSIER DE CONSULTATION (CCTP en priorité, peut être tronqué) :
{ctx['dce'] or '(aucun document de consultation analysé)'}

Réponds en JSON strict :
{{"phases": [{{"phase": "nom exact de la phase", "taches": [{{"name": "...", "start": "AAAA-MM-JJ",
"end": "AAAA-MM-JJ", "lot": null, "depends_on": [], "source": "cctp",
"sous_taches": [{{"name": "...", "start": "AAAA-MM-JJ", "end": "AAAA-MM-JJ"}}]}}]}}]}}"""

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
        "response_format": {"type": "json_object"},
        "max_tokens": 9000 if sous else 5000,
        "api_key": creds["api_key"],
    }
    if creds.get("api_base"):
        kwargs["api_base"] = creds["api_base"]
    try:
        resp = await litellm.acompletion(**kwargs)
    except Exception as exc:
        # Certains modeles refusent response_format ou temperature : un second essai sans.
        logger.warning("[GanttDetail] 1er appel en echec (%s) -- nouvel essai sans response_format", exc)
        kwargs.pop("response_format", None)
        try:
            resp = await litellm.acompletion(**kwargs)
        except Exception as exc2:
            return None, f"appel au modèle en échec ({type(exc2).__name__})"
    usage = getattr(resp, "usage", None)
    try:
        await billing_service.log_llm_usage(
            db=db, tenant_id=tenant_id, project_id=project.id, provider_id=creds.get("provider_id"),
            model_string=model,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        )
    except Exception as exc:
        logger.warning("[GanttDetail] journal de consommation non ecrit : %s", exc)
    brut = (resp.choices[0].message.content or "").strip()
    brut = re.sub(r"^```(?:json)?\s*|\s*```$", "", brut)
    try:
        return json.loads(brut), model
    except Exception:
        m = re.search(r"\{.*\}", brut, re.S)
        if m:
            try:
                return json.loads(m.group(0)), model
            except Exception:
                pass
    return None, "réponse du modèle illisible"


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------
async def detailler_planning(db: AsyncSession, tenant_id: uuid.UUID, project: Project,
                             niveau: str = "taches", remplacer: bool = False) -> Dict[str, Any]:
    rows = (await db.execute(
        select(ProjectGanttTask).where(ProjectGanttTask.tenant_id == tenant_id,
                                       ProjectGanttTask.project_id == project.id)
        .order_by(ProjectGanttTask.sequence, ProjectGanttTask.start_date)
    )).scalars().all()
    phases = [r for r in rows if r.parent_id is None]
    enfants = [r for r in rows if r.parent_id is not None]
    if not phases:
        return {"erreur": "Le planning n'a encore aucune phase : ouvrez le planning (il se crée à partir du "
                          "phasage déclaré) ou ajoutez des phases, puis relancez le détail."}
    if enfants and not remplacer:
        return {"deja_detaille": True, "lignes_existantes": len(enfants),
                "message": f"Le planning contient déjà {len(enfants)} tâche(s) de détail. "
                           "Confirmez pour les remplacer — vos phases ne seront pas modifiées."}

    ctx = await _contexte(db, tenant_id, project)
    rapport: Dict[str, Any] = {"created": 0, "taches": 0, "sous_taches": 0, "ajustements": [],
                               "origine": "", "sources": ctx["dce_sources"],
                               "references_utilisees": ctx["reference_titres"]}

    proposition, info = await _proposer_par_ia(db, tenant_id, project, phases, niveau, ctx)
    par_phase: Dict[str, List[Dict[str, Any]]] = {}
    if proposition and isinstance(proposition.get("phases"), list):
        rapport["origine"] = f"Proposé par l'IA ({info}) à partir de " + (
            ", ".join(ctx["dce_sources"]) if ctx["dce_sources"] else "l'intitulé du projet (aucun CCTP analysé)")
        noms = {p.name.strip().lower(): p for p in phases}
        for i, bloc in enumerate(proposition["phases"]):
            if not isinstance(bloc, dict):
                continue
            cible = noms.get(_txt(bloc.get("phase")).lower())
            if cible is None and i < len(phases):
                cible = phases[i]  # meme ordre que la liste envoyee
            if cible is not None:
                par_phase.setdefault(str(cible.id), []).extend(
                    [t for t in (bloc.get("taches") or []) if isinstance(t, dict)])
    else:
        rapport["origine"] = (f"Gabarit BTP générique — IA indisponible ({info}). "
                              "À relire et adapter au CCTP avant dépôt.")
        for p in phases:
            creneaux = _repartir(p.start_date, p.end_date, len(_gabarit_pour(p.name)))
            items = []
            for (nom, sous), (s, e) in zip(_gabarit_pour(p.name), creneaux):
                sc = _repartir(s, e, len(sous)) if niveau == "sous_taches" else []
                items.append({"name": nom, "start": s.isoformat(), "end": e.isoformat(), "source": "usage",
                              "sous_taches": [{"name": n2, "start": a.isoformat(), "end": b.isoformat()}
                                              for n2, (a, b) in zip(sous, sc)]})
            par_phase[str(p.id)] = items

    if remplacer and enfants:
        await db.execute(delete(ProjectGanttTask).where(
            ProjectGanttTask.tenant_id == tenant_id, ProjectGanttTask.project_id == project.id,
            ProjectGanttTask.parent_id.isnot(None)))

    def borner(nom, s, e, lo, hi):
        ajuste = False
        if s is None or e is None:
            return None, None, False
        if e < s:
            s, e = e, s
        if s < lo:
            s, ajuste = lo, True
        if e > hi:
            e, ajuste = hi, True
        if s > hi:
            s, ajuste = hi, True
        if e < s:
            e = s
        return s, e, ajuste

    nouvelles: List[ProjectGanttTask] = []
    for p in phases:
        items = par_phase.get(str(p.id), [])[:MAX_TACHES_PAR_PHASE]
        noms_ids: Dict[str, uuid.UUID] = {}
        pending_deps: List[tuple] = []
        vus_phase: set = set()
        for rang, it in enumerate(items):
            if len(nouvelles) >= MAX_LIGNES:
                rapport["ajustements"].append(f"Détail tronqué à {MAX_LIGNES} lignes.")
                break
            nom = _txt(it.get("name"), 120)
            if not nom:
                continue
            if _cle(nom) in vus_phase:
                rapport["ajustements"].append(f"« {nom} » : doublon d'une autre tâche de « {p.name} » — ignoré.")
                continue
            vus_phase.add(_cle(nom))
            s, e, aj = borner(nom, _parse(it.get("start")), _parse(it.get("end")), p.start_date, p.end_date)
            if s is None:
                rapport["ajustements"].append(f"« {nom} » : dates illisibles — tâche non créée.")
                continue
            if aj:
                rapport["ajustements"].append(f"« {nom} » : dates ramenées dans la phase « {p.name} ».")
            tid = uuid.uuid4()
            noms_ids.setdefault(nom.lower(), tid)
            lot = _txt(it.get("lot"), 80) or None
            if lot and lot.lower() in ("null", "none", "-"):
                lot = None
            nouvelles.append(ProjectGanttTask(
                id=tid, tenant_id=tenant_id, project_id=project.id, parent_id=p.id, name=nom,
                start_date=s, end_date=e, progress=0, sequence=rang, is_milestone=False,
                milestone_label=None, depends_on=[], lot=lot,
            ))
            rapport["taches"] += 1
            deps = it.get("depends_on") or []
            if isinstance(deps, str):
                deps = [deps]
            pending_deps.append((nouvelles[-1], [_txt(d, 120).lower() for d in deps if _txt(d)]))
            if niveau == "sous_taches":
                for r2, st in enumerate((it.get("sous_taches") or [])[:MAX_SOUS_TACHES_PAR_TACHE]):
                    if not isinstance(st, dict) or len(nouvelles) >= MAX_LIGNES:
                        continue
                    n2 = _txt(st.get("name"), 120)
                    s2, e2, aj2 = borner(n2, _parse(st.get("start")), _parse(st.get("end")), s, e)
                    if not n2 or s2 is None or _cle(n2) in vus_phase:
                        continue
                    vus_phase.add(_cle(n2))
                    if aj2:
                        rapport["ajustements"].append(f"« {n2} » : dates ramenées dans la tâche « {nom} ».")
                    nouvelles.append(ProjectGanttTask(
                        id=uuid.uuid4(), tenant_id=tenant_id, project_id=project.id, parent_id=tid, name=n2,
                        start_date=s2, end_date=e2, progress=0, sequence=r2, is_milestone=False,
                        depends_on=[], lot=lot,
                    ))
                    rapport["sous_taches"] += 1
        for row, deps in pending_deps:
            row.depends_on = [noms_ids[d] for d in deps if d in noms_ids and noms_ids[d] != row.id]

    db.add_all(nouvelles)
    rapport["created"] = len(nouvelles)
    # Trace pour « Ce que l'application a fait à votre place » (transparence_service).
    from datetime import datetime as _dt
    meta = dict(project.metadata_json or {})
    meta["gantt_detail"] = {"origine": rapport["origine"], "taches": rapport["taches"],
                            "sous_taches": rapport["sous_taches"], "le": _dt.utcnow().isoformat()}
    project.metadata_json = meta
    if not nouvelles:
        rapport["ajustements"].append("Aucune tâche exploitable n'a pu être produite.")
    # Limiter la liste affichee : au-dela, c'est du bruit.
    if len(rapport["ajustements"]) > 12:
        reste = len(rapport["ajustements"]) - 12
        rapport["ajustements"] = rapport["ajustements"][:12] + [f"… et {reste} autre(s) ajustement(s)."]
    logger.info("[GanttDetail] projet %s : %d ligne(s) creee(s) (%s)", project.id, len(nouvelles), rapport["origine"])
    return rapport
