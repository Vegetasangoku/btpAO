"""
Detection du pays d'un marche a partir des pieces du DCE (04/09).

Pourquoi ce service existe
--------------------------
Le cadre reglementaire applique a un dossier (normes techniques, regime de commande
publique, qualifications reconnues, whitelist de sources officielles) venait jusqu'ici du
pays du TENANT. Une entreprise francaise repondant a un marche au Qatar se voyait donc
appliquer les normes FRANCAISES, et les profils pays non-FR deja charges en base etaient
inatteignables sans changer le pays du tenant lui-meme.

Principes de conception
-----------------------
1. **Signaux deterministes d'abord.** Un marqueur reglementaire ("QCS 2014", "VOB/B",
   "TenderNed") ou un domaine de portail officiel est verifiable, explicable et gratuit.
   Le LLM n'est qu'un dernier recours quand ces signaux ne tranchent pas.
2. **Jamais de bascule silencieuse.** Le service ne fait que DETECTER : il renvoie le
   code, la confiance, la methode et la liste des marqueurs trouves avec leur emplacement.
   L'appelant decide d'appliquer ou non, et l'interface doit toujours afficher pourquoi.
   Un mauvais cadre applique sans le dire est pire que pas de detection du tout.
3. **Aucune invention.** Un pays n'est propose que s'il a un profil reglementaire ACTIF en
   base. Rien de concluant => on le dit, et on retombe explicitement sur le pays du tenant.
"""
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CountryOfficialSource,
    CountryRegulatoryProfile,
    DCEDocument,
    Project,
)

# Marqueurs a forte valeur discriminante, verifies un par un. Un marqueur present dans
# deux pays ne sert a rien : on ne garde que ce qui identifie SANS ambiguite. Volontairement
# minces et complementaires des donnees deja en base (noms de pays, devises, domaines des
# portails officiels), qui sont exploitees dynamiquement plus bas.
STRONG_MARKERS: Dict[str, List[str]] = {
    "FR": ["code de la commande publique", "nf dtu", "ccag travaux", "boamp", "qualibat",
           "acte d'engagement", "cctp", "ccap", "dpgf", "dume", "reglement de consultation",
           "marches-publics.gouv"],
    "BE": ["publicprocurement.be", "nbn en", "arrete royal", "cahier special des charges", "peb"],
    "LU": ["portail des marches publics", "grand-duche", "itm"],
    "DE": ["vob/a", "vob/b", "vergabeverordnung", "leistungsverzeichnis", "din 18", "hoai"],
    "NL": ["tenderned", "aanbestedingswet", "bouwbesluit", "besluit bouwwerken", "arw 2016",
           "beng", "gids proportionaliteit"],
    "IT": ["codice dei contratti", "ntc 2018", "capitolato speciale", "attestazione soa"],
    "ES": ["ley 9/2017", "codigo tecnico de la edificacion", "pliego de clausulas", "roleco"],
    "QA": ["qatar construction specifications", "qcs 2014", "ashghal", "kahramaa"],
    "SA": ["saudi building code", "sbc 201", "etimad", "monshaat"],
    "AE": ["dubai municipality", "estidama", "trakhees", "abu dhabi"],
    "LB": ["council for development and reconstruction", "libnor", "lebanese standards"],
}

# Devises reellement discriminantes. L'euro est partage par 7 pays configures : le compter
# fausserait le score au profit du hasard, on l'ignore donc totalement.
AMBIGUOUS_CURRENCIES = {"EUR", "USD"}

W_OFFICIAL_DOMAIN = 4.0
W_STRONG_MARKER = 3.0
W_CURRENCY = 3.0
W_COUNTRY_NAME = 2.0
W_LOCATION = 3.0

# Un score gagnant faible ou trop proche du suivant n'est pas une detection : c'est un
# hasard. Ces deux seuils decident si on ose appliquer automatiquement.
MIN_SCORE_HIGH = 6.0
MIN_MARGIN_HIGH = 3.0
MIN_SCORE_MEDIUM = 3.0


def _normalize(text: str) -> str:
    """Minuscules, accents aplatis, et separateurs ramenes a l'espace.

    Le passage des separateurs est indispensable : les pieces d'un DCE s'appellent
    "71260018_CCTP_VDEF.pdf" ou "RC-2026-014", et en regex `_` est un caractere de mot,
    donc `\bcctp\b` ne matchait PAS dans "71260018_cctp_vdef". Constate en test reel le
    04/09 : un marqueur francais parfaitement present etait ignore.
    """
    if not text:
        return ""
    lowered = text.lower()
    for accented, plain in (
        ("àâä", "a"), ("éèêë", "e"), ("îï", "i"), ("ôö", "o"), ("ûüù", "u"), ("ç", "c"),
    ):
        for ch in accented:
            lowered = lowered.replace(ch, plain)
    return re.sub(r"[_\-/\\.,;:()\[\]]+", " ", lowered)


def _find(haystack: str, needle: str) -> bool:
    """Recherche bornee sur les mots pour les marqueurs courts (evite que 'itm' matche
    'algorithme'), simple sous-chaine pour les expressions longues."""
    if len(needle) <= 6 and " " not in needle:
        return re.search(r"\b" + re.escape(needle) + r"\b", haystack) is not None
    return needle in haystack


class CountryDetectionService:
    async def _corpus(
        self, db: AsyncSession, project: Project
    ) -> List[Tuple[str, str]]:
        """Texte disponible pour la detection, chaque morceau etiquete par sa provenance
        (on veut pouvoir dire A L'UTILISATEUR ou le marqueur a ete trouve)."""
        parts: List[Tuple[str, str]] = []
        for label, value in (
            ("titre du projet", project.title),
            ("maitre d'ouvrage", project.client_name),
            ("localisation", project.location),
            ("directives", project.strategic_directives),
        ):
            if value:
                parts.append((label, str(value)))

        res = await db.execute(
            select(DCEDocument).where(DCEDocument.project_id == project.id)
        )
        for doc in res.scalars().all():
            if doc.filename:
                parts.append((f"nom de fichier ({doc.filename})", doc.filename))
            if doc.parsed_summary:
                # Borne volontaire : les marqueurs reglementaires apparaissent en tete de
                # piece (page de garde, references du reglement), pas a la page 180.
                parts.append((doc.filename or "piece DCE", doc.parsed_summary[:20000]))
        return parts

    async def detect(
        self,
        db: AsyncSession,
        project: Project,
        tenant_country_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Renvoie la detection SANS jamais l'appliquer. L'appelant decide."""
        profiles_res = await db.execute(
            select(CountryRegulatoryProfile).where(CountryRegulatoryProfile.is_active == True)  # noqa: E712
        )
        profiles = profiles_res.scalars().all()
        if not profiles:
            return self._inconclusive("Aucun profil pays actif n'est configure sur la plateforme.",
                                      tenant_country_code)

        sources_res = await db.execute(
            select(CountryOfficialSource).where(CountryOfficialSource.status == "active")
        )
        sources = sources_res.scalars().all()

        corpus = await self._corpus(db, project)
        if not corpus:
            return self._inconclusive("Aucune piece exploitable n'est encore rattachee a ce dossier.",
                                      tenant_country_code)

        scores: Dict[str, float] = {p.country_code: 0.0 for p in profiles}
        signals: List[Dict[str, Any]] = []

        def add(code: str, weight: float, marker: str, where: str, kind: str) -> None:
            if code not in scores:
                return
            scores[code] += weight
            signals.append({"country_code": code, "marker": marker, "where": where,
                            "weight": weight, "kind": kind})

        for where, raw in corpus:
            hay = _normalize(raw)

            # 1. Domaine d'un portail officiel cite dans la piece : le signal le plus fort.
            for src in sources:
                if not src.portal_url:
                    continue
                domain = _normalize(src.portal_url).replace("https://", "").replace("http://", "").split("/")[0]
                if domain and domain in hay:
                    add(src.country_code, W_OFFICIAL_DOMAIN, domain, where, "portail officiel")

            # 2. Marqueurs reglementaires / techniques propres a un pays.
            for code, markers in STRONG_MARKERS.items():
                for marker in markers:
                    if _find(hay, _normalize(marker)):
                        add(code, W_STRONG_MARKER, marker, where, "marqueur reglementaire")

            # 3. Devise, uniquement si elle est discriminante.
            for prof in profiles:
                cur = (prof.currency or "").strip().upper()
                if cur and cur not in AMBIGUOUS_CURRENCIES and _find(hay, cur.lower()):
                    add(prof.country_code, W_CURRENCY, cur, where, "devise")

            # 4. Nom du pays en toutes lettres.
            for prof in profiles:
                name = _normalize(prof.country_name or "")
                if name and name in hay:
                    weight = W_LOCATION if where == "localisation" else W_COUNTRY_NAME
                    add(prof.country_code, weight, prof.country_name, where, "nom de pays")

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_code, top_score = ranked[0]
        runner_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = top_score - runner_score

        if top_score >= MIN_SCORE_HIGH and margin >= MIN_MARGIN_HIGH:
            confidence = "high"
        elif top_score >= MIN_SCORE_MEDIUM:
            confidence = "medium"
        else:
            return self._inconclusive(
                "Aucun marqueur reglementaire suffisamment discriminant dans les pieces fournies.",
                tenant_country_code, scores=scores, signals=signals,
            )

        kept = [s for s in signals if s["country_code"] == top_code]
        top_markers = sorted({s["marker"] for s in kept})[:4]
        country_name = next((p.country_name for p in profiles if p.country_code == top_code), top_code)
        reason = (
            f"{country_name} retenu sur {len(kept)} indice(s) concordant(s) : "
            + ", ".join(top_markers)
            + (f" — devant {ranked[1][0]} ({runner_score:.0f} pt)" if runner_score > 0 else "")
        )

        return {
            "detected_code": top_code,
            "confidence": confidence,
            "method": "signals",
            "reason": reason,
            "signals": kept[:12],
            "scores": {k: v for k, v in scores.items() if v > 0},
            "tenant_fallback_code": tenant_country_code,
            "detected_at": datetime.utcnow().isoformat(),
        }

    def _inconclusive(
        self,
        reason: str,
        tenant_country_code: Optional[str],
        scores: Optional[Dict[str, float]] = None,
        signals: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return {
            "detected_code": None,
            "confidence": "none",
            "method": "tenant_fallback",
            "reason": reason,
            "signals": (signals or [])[:12],
            "scores": {k: v for k, v in (scores or {}).items() if v > 0},
            "tenant_fallback_code": tenant_country_code,
            "detected_at": datetime.utcnow().isoformat(),
        }


country_detection_service = CountryDetectionService()
