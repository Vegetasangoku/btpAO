"""
Pieces administratives et formulaires manquants (11/09).

Demande Charbel : « qu'il cherche bien sur les sites du pays correspondant s'il manque
des formulaires ou autres ». Jusqu'ici rien ne le faisait : la recherche web servait
seulement a sourcer la redaction.

Ce que fait ce service, pour un projet :
  1. EXIGENCES : pieces exigees par le dossier de consultation (passages du DCE qui
     parlent de candidature / pieces a fournir, lus par le modele avec obligation de
     citer le passage) + pieces standard du profil reglementaire du PAYS DU MARCHE.
  2. DISPONIBLE : pieces du DCE deposees, documents de l'entreprise (base de
     connaissances), et formulaires que l'application sait produire (DC1, DC2, DUME
     pour la France).
  3. Pour chaque piece manquante : recherche restreinte aux portails officiels du
     pays, lecture des resultats (HTML/PDF/Word) pour verifier qu'ils sont
     accessibles, et lien vers le formulaire officiel -- les PDF/Word en premier.
Rien n'est invente : une exigence sans source n'est pas listee, un lien non lu est
signale comme non verifie.
"""
import json
import logging
import re
import unicodedata
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CompanyAsset, CountryOfficialSource, CountryRegulatoryProfile, DCEDocument, DCEEmbedding, Project, Tenant,
)

logger = logging.getLogger(__name__)

FRANCOPHONES = ("FR", "BE", "LU", "MC", "CH")
# Formulaires que l'application genere elle-meme (voir admin_dossiers.py).
GENERABLES = {"FR": {"dc1": "DC1", "dc2": "DC2", "dume": "DUME"}}
_MOTS_DCE = ("pièces à fournir", "pieces a fournir", "dossier de candidature", "contenu de l'offre",
             "contenu du dossier", "dc1", "dc2", "dume", "attestation", "kbis", "documents to be submitted",
             "submission documents", "prequalification", "required documents", "pièces justificatives")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _cle(t: str) -> set:
    vides = {"de", "des", "du", "la", "le", "les", "et", "d", "l", "a", "en", "of", "the", "and", "or", "ou", "pour"}
    return {m for m in re.findall(r"[a-z0-9]{2,}", _norm(t)) if m not in vides}


async def _llm_json(db, tenant_uuid, prompt: str, max_tokens: int = 1500) -> Optional[Dict[str, Any]]:
    try:
        import litellm
        from app.services.model_routing_service import model_routing_service
        res = await model_routing_service.resolve_model_for_tenant(db=db, tenant_id=tenant_uuid, task_type="extraction_gonogo")
        cred = await model_routing_service.get_credentials_for_model(db=db, model_string=res["model_string"])
        if not cred.get("api_key"):
            return None
        kw = {"model": res["model_string"], "api_key": cred["api_key"], "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
        if cred.get("api_base"):
            kw["api_base"] = cred["api_base"]
        r = await litellm.acompletion(**kw)
        brut = re.sub(r"^```(?:json)?\s*|\s*```$", "", (r.choices[0].message.content or "").strip())
        m = re.search(r"\{.*\}", brut, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as exc:
        logger.warning("[Pieces] Appel modele impossible : %s", exc)
        return None


async def _traduire(db, tenant_uuid, texte: str) -> str:
    out = await _llm_json(db, tenant_uuid,
                          'Translate into English search keywords. Answer as JSON {"q": "..."} only: ' + texte, 80)
    return (out or {}).get("q") or texte


async def analyser_pieces(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project, chercher: bool = True) -> Dict[str, Any]:
    tenant = await db.get(Tenant, tenant_uuid)
    pays = (project.country_code or (tenant.country_code if tenant else None) or "FR").upper()
    profil = await db.get(CountryRegulatoryProfile, pays)

    # 1. Exigences
    exigences: List[Dict[str, Any]] = []
    for p in (profil.standard_requirements or []) if profil else []:
        exigences.append({"piece": str(p), "origine": f"Profil réglementaire {profil.country_name}", "citation": None})
    for p in (profil.mandatory_certifications or []) if profil else []:
        exigences.append({"piece": str(p), "origine": f"Certification courante ({profil.country_name}) — à confirmer avec le RC",
                          "citation": None, "certification": True})

    filtres = [DCEEmbedding.content.ilike(f"%{m}%") for m in _MOTS_DCE]
    passages = (await db.execute(
        select(DCEEmbedding.content, DCEEmbedding.page_number, DCEDocument.filename)
        .join(DCEDocument, DCEDocument.id == DCEEmbedding.document_id)
        .where(DCEEmbedding.project_id == project.id, DCEEmbedding.tenant_id == tenant_uuid, or_(*filtres))
        .limit(12)
    )).all()
    dce_lu = bool(passages)
    nb_dce = 0
    if passages:
        extraits = "\n\n".join(f"[{f}, p.{int(pg or 1)}] {c[:1800]}" for c, pg, f in passages)
        out = await _llm_json(db, tenant_uuid, f"""Extrais du dossier de consultation ci-dessous la liste des PIÈCES
ADMINISTRATIVES ET FORMULAIRES que le candidat doit fournir (candidature et offre).
Uniquement ce qui est EXPLICITEMENT exigé ; cite le passage exact (moins de 25 mots) et sa référence [fichier, p.].
Réponds en JSON : {{"pieces": [{{"piece": "...", "citation": "...", "reference": "..."}}]}}. Liste vide si rien.

{extraits}""", 1800)
        for it in (out or {}).get("pieces", []) or []:
            if isinstance(it, dict) and it.get("piece") and it.get("citation"):
                exigences.append({"piece": str(it["piece"])[:120], "origine": f"DCE {it.get('reference') or ''}".strip(),
                                  "citation": str(it["citation"])[:240]})
                nb_dce += 1
    # Dedoublonnage (meme piece citee par le profil pays et par le DCE)
    uniques: List[Dict[str, Any]] = []
    for e in exigences:
        k = _cle(e["piece"])
        doublon = next((u for u in uniques if k and (k <= _cle(u["piece"]) or _cle(u["piece"]) <= k)), None)
        if doublon:
            if e.get("citation") and not doublon.get("citation"):
                doublon.update(citation=e["citation"], origine=doublon["origine"] + " + " + e["origine"])
            continue
        uniques.append(e)

    # 2. Disponible
    docs = (await db.execute(select(DCEDocument.filename, DCEDocument.doc_type)
                             .where(DCEDocument.project_id == project.id, DCEDocument.tenant_id == tenant_uuid))).all()
    assets = (await db.execute(select(CompanyAsset.title, CompanyAsset.category)
                               .where(CompanyAsset.tenant_id == tenant_uuid, CompanyAsset.obsolete_at.is_(None)))).all()
    dispo_dossier = [(f"{f} {t}", f"Pièce du dossier : {f}") for f, t in docs]
    dispo_entreprise = [(f"{t} {c}", f"Document entreprise : {t}") for t, c in assets]
    from app.models.entities import GeneratedSection
    nb_sections = len((await db.execute(select(GeneratedSection.id).where(
        GeneratedSection.project_id == project.id, GeneratedSection.tenant_id == tenant_uuid,
        GeneratedSection.status != "failed"))).all())
    generables = GENERABLES.get(pays, {})

    # 3. Statut + recherche du formulaire officiel
    sources = (await db.execute(select(CountryOfficialSource.portal_url).where(
        CountryOfficialSource.country_code == pays, CountryOfficialSource.status == "active"))).scalars().all()
    domaines = sorted({urlparse(u).netloc for u in sources if u})
    from app.services.web_search_service import web_search_service
    from app.services.official_page_reader import lire_pages

    resultat = []
    for e in uniques:
        k = _cle(e["piece"])
        trouve = None
        # Une piece PROPRE A CETTE OFFRE (memoire technique, acte d'engagement, DPGF...)
        # ne peut pas etre « fournie » par un document d'un autre chantier.
        propre_offre = bool(k & {"memoire", "engagement", "dpgf", "bpu", "dqe", "offre", "planning", "ae"})
        if propre_offre and "memoire" in k and nb_sections:
            trouve = f"Mémoire technique rédigé dans l'application ({nb_sections} section(s))"
        for texte, libelle in (dispo_dossier if propre_offre else dispo_dossier + dispo_entreprise):
            if trouve:
                break
            kd = _cle(texte)
            if k and len(k & kd) >= max(1, min(2, len(k))):
                trouve = libelle
                break
        gen = ", ".join(v for c, v in generables.items() if c in k) or None
        statut = "fourni" if trouve else ("generable" if gen else "manquant")
        telechargeables = [{"code": c, "libelle": v, "chemin": f"/dossiers/{project.id}/{c}"}
                           for c, v in generables.items() if c in k and c in ("dc1", "dc2")]
        ligne = {**e, "statut": statut, "fourni_par": trouve, "telechargements": telechargeables,
                 "generable": f"Formulaire {gen} pré-rempli par l'application avec vos données — à vérifier et signer" if gen else None,
                 "liens": [], "recherche": None}
        if e.get("certification") and statut == "manquant":
            ligne["recherche"] = ("Certificat délivré par un organisme certificateur : à joindre s'il est détenu, "
                                  "pas de formulaire officiel à télécharger.")
        elif chercher and statut != "fourni" and domaines:
            requete = f"{e['piece']} formulaire" if pays in FRANCOPHONES else await _traduire(db, tenant_uuid, f"{e['piece']} form download")
            try:
                res = await web_search_service.search(tenant_id=str(tenant_uuid), query=requete, num_results=5,
                                                      project_id=str(project.id), allowed_sites=domaines)
            except Exception as exc:
                res = []
                ligne["recherche"] = f"recherche indisponible ({type(exc).__name__})"
            if res:
                lues = {p["url"]: p for p in await lire_pages([r.url for r in res], e["piece"], 600, maximum=5)}
                liens = []
                for r in res:
                    p = lues.get(r.url) or {}
                    # Pertinence minimale : un mot de la piece dans le titre, l'adresse ou le contenu.
                    temoin = _cle(f"{r.title} {r.url} {(p.get('texte') or '')[:2000]} {r.snippet}")
                    if k and not (k & temoin):
                        continue
                    erreur = p.get("erreur")
                    if erreur in ("code 403", "code 401"):
                        erreur = "site protégé contre les robots : lien trouvé par le moteur, à ouvrir vous-même"
                    liens.append({"titre": r.title, "url": r.url, "format": p.get("type") or "page",
                                  "verifie": bool(p.get("texte")), "extrait": (p.get("texte") or r.snippet or "")[:300],
                                  "erreur": erreur})
                # Formulaires telechargeables d'abord, puis pages lues, puis le reste.
                liens.sort(key=lambda l: (l["format"] not in ("pdf", "docx"), not l["verifie"]))
                ligne["liens"] = liens[:3]
                ligne["recherche"] = f"« {requete} » sur {len(domaines)} portail(s) officiel(s) {pays}"
            elif not ligne["recherche"]:
                ligne["recherche"] = f"aucun résultat pour « {requete} » sur les portails officiels {pays}"
        resultat.append(ligne)

    return {
        "pays": pays,
        "pays_nom": profil.country_name if profil else pays,
        "portails": domaines,
        "dce_analyse": dce_lu,
        "pieces": resultat,
        "resume": {s: sum(1 for r in resultat if r["statut"] == s) for s in ("fourni", "generable", "manquant")},
        "pieces_du_dce": nb_dce,
        "avertissement": None if nb_dce else
            "Aucune pièce à fournir n'a été trouvée dans le dossier de consultation déposé (règlement de consultation "
            "absent ?) : seules les exigences standard du pays sont vérifiées. Déposez le RC pour une liste complète.",
    }
