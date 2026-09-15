"""
Détecteur de spécificité / généricité avant export (14/09, demande Charbel :
« je veux une qualité incroyable peu importe la langue basé sur les meilleurs
dossiers » -- item jamais construit de analyse-concurrentielle-et-differenciation).

Objectif : repérer les paragraphes qui pourraient être copiés-collés dans
n'importe quel dossier BTP, faute de reprendre un fait réel de CE marché (site,
délai, référence, chiffre, nom d'intervenant...) ou de l'entreprise. Volontairement
PAS une note auto-déclarée par un LLM (cf. compliance_score/compliance_checklist
dans llm_generator.py, qui vérifie la couverture des critères -- un sujet
différent) : un vocabulaire de faits réels est construit à partir des données déjà
en base pour CE projet (DCE, planning, organigramme, formulaire « Données
chantier », fiche entreprise), puis chaque paragraphe rédigé est vérifié par
recherche de ces faits -- mécanique, vérifiable, indépendant de la langue de
rédaction (FR / EN / AR) puisqu'il repose sur des noms propres et des nombres
recopiés tels quels, pas sur une compréhension sémantique du texte.

Limite assumée et documentée (voir aussi specificite-card.tsx) : un fait
reformulé sans reprendre le nom propre ou le chiffre exact (ex. traduction libre
d'une donnée, paraphrase) peut échapper à la détection. C'est un filet de
sécurité mécanique et auditable, pas une relecture éditoriale.
"""
import re
import unicodedata
import uuid
from html import unescape
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    DCECriterionEntity, GeneratedSection, Project, ProjectDecision,
    ProjectGanttTask, ProjectOrganigrammeNode, Tenant,
)

# Longueur minimale (apres normalisation) pour qu'une phrase du vocabulaire soit
# retenue : evite que des mots triviaux ne matchent un peu partout.
_MIN_PHRASE_LEN = 5
# Sequences numeriques ignorees (trop courtes pour etre un identifiant/quantite fiable).
_MIN_DIGITS_LEN = 2
# Longueur minimale d'un paragraphe pour etre juge (les transitions courtes ne
# sont pas de la "generalite", juste de la structure).
_MIN_BLOC_LEN = 40

# Valeurs par defaut/gabarit poseee par l'application elle-meme (voir
# transparence_service.py) : les compter comme "specifiques" donnerait un faux
# bon score a un projet dont les infos de base n'ont pas ete completees.
_STOP_PHRASES = {
    "acheteur public detecte", "lot 01 - gros oeuvre", "lot 01 - gros œuvre",
}

_FORMULES_GENERIQUES: Dict[str, Tuple[str, ...]] = {
    "fr": (
        "notre entreprise s'engage à", "nous mettrons tout en œuvre",
        "un savoir-faire reconnu", "forte de son expérience",
        "à l'écoute de ses clients", "dans les règles de l'art",
        "une qualité irréprochable", "un interlocuteur unique",
        "un gage de qualité", "les moyens nécessaires",
    ),
    "en": (
        "we are committed to", "our team will ensure", "a proven track record",
        "our extensive experience", "tailored to your needs",
        "in accordance with best practice", "a single point of contact",
        "utmost importance", "the necessary resources",
    ),
    "ar": (
        "تلتزم شركتنا بـ", "سنبذل قصارى جهدنا", "خبرة واسعة",
        "بأعلى معايير الجودة", "جهة اتصال واحدة", "الموارد اللازمة",
    ),
}

MESSAGES: Dict[str, Dict[str, str]] = {
    "raison_vide": {
        "fr": "Aucun élément propre à ce marché (site, délai, référence, chiffre, nom) n'a été repéré dans ce paragraphe.",
        "en": "No element specific to this tender (site, deadline, reference, figure, name) was found in this paragraph.",
        "ar": "لم يُعثر في هذه الفقرة على أي عنصر خاص بهذه المناقصة (الموقع، الأجل، المرجع، رقم، اسم).",
    },
    "raison_formule": {
        "fr": "Formulation générique repérée (« {phrase} ») sans élément propre à ce chantier à proximité.",
        "en": "Generic wording detected (“{phrase}”) with no project-specific element nearby.",
        "ar": "عبارة عامة مُكتشفة (« {phrase} ») دون عنصر خاص بهذا المشروع بجوارها.",
    },
    "verdict_excellent": {"fr": "Excellent — ancré dans ce marché", "en": "Excellent — grounded in this tender", "ar": "ممتاز — مرتكز على هذه المناقصة"},
    "verdict_correct": {"fr": "Correct — encore perfectible", "en": "Fair — can be improved", "ar": "مقبول — قابل للتحسين"},
    "verdict_insuffisant": {"fr": "Insuffisant — trop générique", "en": "Insufficient — too generic", "ar": "غير كافٍ — عام جداً"},
}


def _lang(l: Optional[str]) -> str:
    l = (l or "fr").lower()[:2]
    return l if l in ("fr", "en", "ar") else "fr"


def _normalize(s: str) -> str:
    """Casse-fold + retire accents/tashkeel (NFKD, marques combinantes jetees) :
    sert aussi bien a comparer du francais accentue que de l'arabe avec ou sans
    voyelles courtes, sans traitement particulier par langue."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _strip_tags(html: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", html or "")
    txt = unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def _extract_blocks(html: str) -> List[str]:
    """Paragraphes/items de liste (unites de prose), tags imbriques retires. Les
    cellules de tableau ne sont pas prises comme unites individuelles (trop
    courtes, deja generalement factuelles) -- le vocabulaire/les nombres, eux,
    parcourent tout le contenu y compris les tableaux (_build_gazetteer)."""
    blocks = re.findall(r"<p[^>]*>(.*?)</p>|<li[^>]*>(.*?)</li>", html or "", flags=re.IGNORECASE | re.DOTALL)
    out = []
    for a, b in blocks:
        txt = _strip_tags(a or b)
        if txt:
            out.append(txt)
    return out


def _numbers_of(text: str) -> Set[str]:
    return set(re.findall(r"\d{%d,}" % _MIN_DIGITS_LEN, text or ""))


def _flatten_strings(value: Any, out: List[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        v = value.strip()
        if v:
            out.append(v)
    elif isinstance(value, (int, float)):
        out.append(str(value))
    elif isinstance(value, dict):
        for v in value.values():
            _flatten_strings(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _flatten_strings(v, out)


async def _build_gazetteer(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project) -> Tuple[Set[str], Set[str]]:
    """Renvoie (phrases_normalisees, nombres) issus des vraies donnees de CE
    projet et de l'entreprise -- jamais generes, jamais devines."""
    raw: List[str] = []
    numbers: Set[str] = set()

    for v in (project.title, project.client_name, project.location, project.reference_code, project.lot_number):
        if v:
            raw.append(v)
    if project.budget_estimate is not None:
        entier = int(project.budget_estimate)
        numbers |= _numbers_of(str(entier))
        numbers |= _numbers_of(f"{entier:,}".replace(",", " "))
    if project.submission_deadline:
        numbers.add(str(project.submission_deadline.year))

    tenant = await db.get(Tenant, tenant_uuid)
    if tenant:
        if tenant.name:
            raw.append(tenant.name)
        if tenant.siret:
            numbers |= _numbers_of(tenant.siret)

    crit_res = await db.execute(
        select(DCECriterionEntity).where(DCECriterionEntity.project_id == project.id, DCECriterionEntity.tenant_id == tenant_uuid)
    )
    for c in crit_res.scalars().all():
        if c.criterion_title:
            raw.append(c.criterion_title)
        _flatten_strings(c.key_expectations, raw)
        _flatten_strings(c.required_evidence, raw)

    gantt_res = await db.execute(
        select(ProjectGanttTask).where(ProjectGanttTask.project_id == project.id, ProjectGanttTask.tenant_id == tenant_uuid)
    )
    for g in gantt_res.scalars().all():
        if g.name:
            raw.append(g.name)
        if g.lot:
            raw.append(g.lot)

    orga_res = await db.execute(
        select(ProjectOrganigrammeNode).where(ProjectOrganigrammeNode.project_id == project.id, ProjectOrganigrammeNode.tenant_id == tenant_uuid)
    )
    for o in orga_res.scalars().all():
        if o.nom and "pourvoir" not in o.nom.lower():
            raw.append(o.nom)
        if o.role:
            raw.append(o.role)
        if o.qualif:
            raw.append(o.qualif)

    dec = (await db.execute(
        select(ProjectDecision).where(ProjectDecision.project_id == project.id, ProjectDecision.tenant_id == tenant_uuid)
    )).scalar_one_or_none()
    if dec and dec.form_data:
        _flatten_strings(dec.form_data, raw)

    phrases: Set[str] = set()
    for r in raw:
        n = _normalize(r)
        if len(n) >= _MIN_PHRASE_LEN and n not in _STOP_PHRASES:
            phrases.add(n)
        numbers |= _numbers_of(r)

    return phrases, numbers


def _score_section(html: str, phrases: Set[str], numbers: Set[str], langue: str) -> Optional[Dict[str, Any]]:
    blocs = _extract_blocks(html)
    substantifs = [b for b in blocs if len(b) >= _MIN_BLOC_LEN]
    if not substantifs:
        return None

    marqueurs_utilises: Set[str] = set()
    generiques: List[Dict[str, str]] = []
    nb_specifiques = 0

    for b in substantifs:
        nb = _normalize(b)
        hits = {p for p in phrases if p in nb}
        num_hits = _numbers_of(b) & numbers
        if hits or num_hits:
            nb_specifiques += 1
            marqueurs_utilises |= hits
        elif len(generiques) < 2:
            raison = MESSAGES["raison_vide"][langue]
            for phr in _FORMULES_GENERIQUES.get(langue, ()):
                if phr in b.lower():
                    raison = MESSAGES["raison_formule"][langue].format(phrase=phr)
                    break
            extrait = b if len(b) <= 170 else b[:167].rstrip() + "…"
            generiques.append({"extrait": extrait, "raison": raison})

    ratio = nb_specifiques / len(substantifs)
    profondeur = min(1.0, len(marqueurs_utilises) / 5.0)
    score = round(100 * (0.7 * ratio + 0.3 * profondeur), 1)

    return {
        "score": score,
        "marqueurs_distincts": len(marqueurs_utilises),
        "paragraphes_generiques": generiques,
        "total_paragraphes": len(substantifs),
        "paragraphes_specifiques": nb_specifiques,
    }


def _verdict(score: float) -> str:
    if score >= 75:
        return "excellent"
    if score >= 45:
        return "correct"
    return "insuffisant"


async def rapport_specificite(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project, langue: str = "fr") -> Dict[str, Any]:
    L = _lang(langue)
    phrases, numbers = await _build_gazetteer(db, tenant_uuid, project)

    sec_res = await db.execute(
        select(GeneratedSection)
        .where(GeneratedSection.project_id == project.id, GeneratedSection.tenant_id == tenant_uuid)
        .order_by(GeneratedSection.order_index.asc())
    )
    sections_out: List[Dict[str, Any]] = []
    scores: List[float] = []
    for s in sec_res.scalars().all():
        if s.status in ("failed", "processing") or not (s.content_html or "").strip():
            continue
        res = _score_section(s.content_html, phrases, numbers, L)
        if res is None:
            continue
        scores.append(res["score"])
        sections_out.append({
            "section_key": s.section_key,
            "title": s.title,
            "score": res["score"],
            "verdict": _verdict(res["score"]),
            "marqueurs_distincts": res["marqueurs_distincts"],
            "total_paragraphes": res["total_paragraphes"],
            "paragraphes_specifiques": res["paragraphes_specifiques"],
            "paragraphes_generiques": res["paragraphes_generiques"],
        })

    score_global = round(sum(scores) / len(scores), 1) if scores else None
    resume = {"excellent": 0, "correct": 0, "insuffisant": 0}
    for s in sections_out:
        resume[s["verdict"]] += 1
    sections_out.sort(key=lambda s: s["score"])

    return {
        "langue": L,
        "score_global": score_global,
        "verdict_global": _verdict(score_global) if score_global is not None else None,
        "nb_faits_disponibles": len(phrases) + len(numbers),
        "sections": sections_out,
        "resume": resume,
        "libelles_verdict": {k: MESSAGES[f"verdict_{k}"][L] for k in ("excellent", "correct", "insuffisant")},
    }
