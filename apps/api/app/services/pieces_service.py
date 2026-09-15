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
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CompanyAsset, CountryOfficialSource, CountryRegulatoryProfile, DCEDocument, DCEEmbedding, Project, Tenant,
    TenantPieceHistory,
)

logger = logging.getLogger(__name__)

FRANCOPHONES = ("FR", "BE", "LU", "MC", "CH")
MOT_FORMULAIRE = {"FR": "formulaire", "BE": "formulaire", "LU": "formulaire", "MC": "formulaire", "CH": "formulaire",
                  "DE": "Formular", "ES": "formulario", "IT": "modulo", "NL": "formulier"}
# Formulaires que l'application genere elle-meme (voir admin_dossiers.py).
# 11/09 : le DUME est le formulaire europeen (ESPD) ; notre modele est en francais,
# il sert donc aussi en Belgique et au Luxembourg.
GENERABLES = {"FR": {"dc1": "DC1", "dc2": "DC2", "dume": "DUME"},
              "BE": {"dume": "DUME"}, "LU": {"dume": "DUME"}}
_MOTS_DCE = ("pièces à fournir", "pieces a fournir", "dossier de candidature", "contenu de l'offre",
             "contenu du dossier", "dc1", "dc2", "dume", "attestation", "kbis", "documents to be submitted",
             "submission documents", "prequalification", "required documents", "pièces justificatives")


# Textes rediges par ce service, dans la langue de l'interface (en-tete X-UI-Language).
TXT = {
    "profil": {"fr": "Profil réglementaire {pays}", "en": "Regulatory profile — {pays}", "ar": "الملف التنظيمي — {pays}"},
    "certif": {"fr": "Certification courante ({pays}) — à confirmer avec le RC", "en": "Usual certification ({pays}) — to confirm with the RC",
               "ar": "شهادة معتادة ({pays}) — يُتحقق منها في نظام المناقصة"},
    "dume_origine": {"fr": "Accepté par tout acheteur public en France à la place du DC1 / DC2",
                     "en": "Accepted by any French public buyer instead of DC1 / DC2", "ar": "مقبول لدى أي مشترٍ عام في فرنسا بدلاً من DC1 / DC2"},
    "piece_dossier": {"fr": "Pièce du dossier : {x}", "en": "Tender document: {x}", "ar": "وثيقة من الملف: {x}"},
    "doc_entreprise": {"fr": "Document entreprise : {x}", "en": "Company document: {x}", "ar": "وثيقة الشركة: {x}"},
    "memoire_app": {"fr": "Mémoire technique rédigé dans l'application ({n} section(s))", "en": "Technical bid written in the app ({n} section(s))",
                    "ar": "مذكرة فنية محررة في التطبيق ({n} قسم)"},
    "generable": {"fr": "Formulaire {x} pré-rempli par l'application avec vos données — à vérifier et signer",
                  "en": "{x} form pre-filled by the app with your data — to check and sign", "ar": "نموذج {x} معبأ مسبقاً ببياناتك — للتحقق والتوقيع"},
    "redigeable": {"fr": "Brouillon rédigé par l'application à partir du dossier de consultation — à vérifier, compléter et signer",
                   "en": "Draft written by the app from the tender documents — to check, complete and sign",
                   "ar": "مسودة أعدها التطبيق استناداً إلى ملف المناقصة — للتحقق والإكمال والتوقيع"},
    "historique": {"fr": "Vu dans un dossier précédent ({pays}) — confirmé par vous pour celui-ci",
                   "en": "Seen in a previous tender ({pays}) — confirmed by you for this one",
                   "ar": "ظهرت في ملف سابق ({pays}) — أكدتها لهذا الملف"},
    "certificat": {"fr": "Certificat délivré par un organisme certificateur : à joindre s'il est détenu, pas de formulaire officiel à télécharger.",
                   "en": "Certificate issued by a certification body: attach it if held; there is no official form to download.",
                   "ar": "شهادة تصدرها جهة اعتماد: تُرفق إن وُجدت، ولا يوجد نموذج رسمي للتنزيل."},
    "robots": {"fr": "site protégé contre les robots : lien trouvé par le moteur, à ouvrir vous-même",
               "en": "site blocks automated reading: link found by the search engine, open it yourself",
               "ar": "الموقع يمنع القراءة الآلية: رابط وجده محرك البحث، افتحه بنفسك"},
    "recherche": {"fr": "« {q} » sur {n} portail(s) officiel(s) {pays}", "en": "“{q}” on {n} official portal(s) — {pays}",
                  "ar": "«{q}» على {n} بوابة رسمية — {pays}"},
    "aucun": {"fr": "aucun résultat pour « {q} » sur les portails officiels {pays}", "en": "no result for “{q}” on official portals — {pays}",
              "ar": "لا نتائج لـ «{q}» على البوابات الرسمية — {pays}"},
    "indispo": {"fr": "recherche indisponible ({x})", "en": "search unavailable ({x})", "ar": "البحث غير متاح ({x})"},
    "rc_illisible": {"fr": "Le règlement de consultation est déposé, mais la liste des pièces n'a pas pu y être lue automatiquement. Vérifiez-la dans le RC ; la liste ci-dessous suit les usages du pays.",
                     "en": "The tender regulations (RC) are uploaded, but the list of required documents could not be read automatically. Check it in the RC; the list below follows the country's usual practice.",
                     "ar": "نظام المناقصة مرفوع، لكن تعذرت قراءة قائمة الوثائق المطلوبة تلقائيًا. تحقق منها في النظام؛ القائمة أدناه تتبع الأعراف المعتادة في البلد."},
    "rc_absent": {"fr": "La liste exacte des pièces demandées est écrite par l'acheteur dans le « règlement de consultation » (RC), un PDF fourni avec le CCTP dans le dossier de l'appel d'offres. Il n'a pas été ajouté à ce projet : la vérification ci-dessous porte donc sur les pièces demandées habituellement ({pays}).",
                  "en": "The exact list of required documents is written by the buyer in the tender regulations (“règlement de consultation”, RC), a PDF provided with the specifications in the tender file. It has not been added to this project, so the check below covers the documents usually required ({pays}).",
                  "ar": "يحدد المشتري القائمة الدقيقة للوثائق المطلوبة في «نظام المناقصة» (RC)، وهو ملف PDF مرفق مع دفتر الشروط في ملف المناقصة. لم يُضف إلى هذا المشروع، لذا يشمل التحقق أدناه الوثائق المطلوبة عادةً ({pays})."},
}


# 11/09 : le nom du pays apparaissait en francais dans les textes anglais et arabes.
NOMS_PAYS = {
    "AE": {"fr": "Émirats arabes unis", "en": "United Arab Emirates", "ar": "الإمارات العربية المتحدة"},
    "BE": {"fr": "Belgique", "en": "Belgium", "ar": "بلجيكا"},
    "DE": {"fr": "Allemagne", "en": "Germany", "ar": "ألمانيا"},
    "ES": {"fr": "Espagne", "en": "Spain", "ar": "إسبانيا"},
    "FR": {"fr": "France", "en": "France", "ar": "فرنسا"},
    "IT": {"fr": "Italie", "en": "Italy", "ar": "إيطاليا"},
    "LB": {"fr": "Liban", "en": "Lebanon", "ar": "لبنان"},
    "LU": {"fr": "Luxembourg", "en": "Luxembourg", "ar": "لوكسمبورغ"},
    "NL": {"fr": "Pays-Bas", "en": "Netherlands", "ar": "هولندا"},
    "QA": {"fr": "Qatar", "en": "Qatar", "ar": "قطر"},
    "SA": {"fr": "Arabie saoudite", "en": "Saudi Arabia", "ar": "المملكة العربية السعودية"},
}


def nom_pays(code: str, langue: str, defaut: str = None) -> str:
    return NOMS_PAYS.get((code or "").upper(), {}).get(langue) or defaut or code


def _t(cle: str, langue: str, **kw) -> str:
    return TXT[cle].get(langue, TXT[cle]["fr"]).format(**kw)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _cle(t: str) -> set:
    vides = {"de", "des", "du", "la", "le", "les", "et", "d", "l", "a", "en", "of", "the", "and", "or", "ou", "pour"}
    return {m for m in re.findall(r"[a-z0-9]{2,}", _norm(t)) if m not in vides}


def _cle_historique(piece: str) -> str:
    """Cle stable pour tenant_piece_history (UNIQUE tenant_id+country_code+piece_key) -- derivee
    du meme decoupage que _cle() (mots significatifs, ordre indifferent) pour que deux libelles
    proches du meme document ("attestation fiscale" / "attestation fiscale a jour") retombent
    sur la meme ligne d'historique plutot que d'en creer une par variante de formulation."""
    return " ".join(sorted(_cle(piece)))[:180] or _norm(piece)[:180]


async def _upsert_piece_history(db: AsyncSession, tenant_uuid: uuid.UUID, pays: str, piece_label: str,
                                piece_type: Optional[str], citation: Optional[str], project_id) -> None:
    """Enregistre/renforce qu'une piece a ete reellement vue (citee dans un vrai RC/DCE) pour ce
    tenant+pays -- alimente la recommandation "dossier similaire, meme pays" (15/09). N'ecrit
    jamais pour une piece sans citation reelle (heuristique de profil pays) : seul ce qui a
    vraiment ete demande une fois entre dans l'historique."""
    cle = _cle_historique(piece_label)
    if not cle:
        return
    existant = (await db.execute(select(TenantPieceHistory).where(
        TenantPieceHistory.tenant_id == tenant_uuid, TenantPieceHistory.country_code == pays,
        TenantPieceHistory.piece_key == cle,
    ))).scalar_one_or_none()
    maintenant = datetime.utcnow()
    if existant:
        existant.seen_count = (existant.seen_count or 0) + 1
        existant.last_seen_project_id = project_id
        existant.last_seen_at = maintenant
        existant.piece_label = piece_label[:250]
        if citation and not existant.piece_citation:
            existant.piece_citation = citation[:400]
        if piece_type and not existant.piece_type:
            existant.piece_type = piece_type
    else:
        db.add(TenantPieceHistory(
            id=uuid.uuid4(), tenant_id=tenant_uuid, country_code=pays, piece_key=cle,
            piece_label=piece_label[:250], piece_type=piece_type,
            piece_citation=(citation[:400] if citation else None),
            seen_count=1, last_seen_project_id=project_id, last_seen_at=maintenant,
        ))


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
        # 11/09 : sans delai, un appel pouvait pendre plusieurs minutes et bloquer la carte.
        import asyncio
        kw["timeout"] = 55
        r = await asyncio.wait_for(litellm.acompletion(**kw), timeout=60)
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


_DECLENCHEURS = ("comprendra", "pieces suivantes", "pièces suivantes", "a fournir", "à fournir",
                 "shall include", "following documents", "must submit")


def _pieces_par_lecture_simple(passages) -> List[Dict[str, str]]:
    """Lecture sans modele : les listes a puces et les enumerations « comprendra : a ; b ; c »."""
    trouves: List[Dict[str, str]] = []
    vus = set()
    for contenu, page, fichier in passages:
        ref = f"[{fichier}, p.{int(page or 1)}]"
        lignes = (contenu or "").replace("\r", "").split("\n")
        # Recoller les lignes coupees par la mise en page du PDF.
        blocs, courant = [], ""
        for l in lignes:
            l = l.strip()
            if not l:
                continue
            if re.match(r"^[-•▪●–*]\s+", l) or re.match(r"^(article|art\.)\s", l, re.I) or not courant:
                if courant:
                    blocs.append(courant)
                courant = l
            else:
                courant += " " + l
        if courant:
            blocs.append(courant)
        candidats = []
        for b in blocs:
            if re.match(r"^[-•▪●–*]\s+", b):
                candidats.append(re.sub(r"^[-•▪●–*]\s+", "", b))
            elif any(d in _norm(b) for d in _DECLENCHEURS) and ":" in b:
                candidats += [x for x in re.split(r"\s*;\s*", b.split(":", 1)[1]) if x]
        for c in candidats:
            c = c.strip(" .;")
            if not (4 <= len(c) <= 200):
                continue
            cle = _norm(c)[:60]
            if cle in vus:
                continue
            vus.add(cle)
            nom = re.sub(r"^(?:(?:les|la|le|une|un|des)\s+|l['’]\s*)", "", c, flags=re.I)
            trouves.append({"piece": nom[:1].upper() + nom[1:120], "citation": c[:240], "reference": ref})
    return trouves[:20]


async def analyser_pieces(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project, chercher: bool = True,
                          langue: str = "fr", pieces_confirmees: Optional[List[str]] = None) -> Dict[str, Any]:
    L = (langue or "fr").lower()[:2]
    L = L if L in ("fr", "en", "ar") else "fr"
    tenant = await db.get(Tenant, tenant_uuid)
    pays = (project.country_code or (tenant.country_code if tenant else None) or "FR").upper()
    profil = await db.get(CountryRegulatoryProfile, pays)
    # 15/09 : pieces deja vues (citees dans un vrai RC/DCE) pour ce tenant, dans ce pays --
    # alimente a la fois l'injection des pieces confirmees ci-dessous et les recommandations.
    historique = (await db.execute(select(TenantPieceHistory).where(
        TenantPieceHistory.tenant_id == tenant_uuid, TenantPieceHistory.country_code == pays,
    ))).scalars().all()

    # 1. Exigences
    exigences: List[Dict[str, Any]] = []
    for p in (profil.standard_requirements or []) if profil else []:
        exigences.append({"piece": str(p), "origine": _t("profil", L, pays=nom_pays(pays, L, profil.country_name)), "citation": None})
    for p in (profil.mandatory_certifications or []) if profil else []:
        exigences.append({"piece": str(p), "origine": _t("certif", L, pays=nom_pays(pays, L, profil.country_name)),
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
    lecture_simple = False
    if passages:
        extraits = "\n\n".join(f"[{f}, p.{int(pg or 1)}] {c[:1800]}" for c, pg, f in passages)
        consigne = f"""Extrais du dossier de consultation ci-dessous la liste des PIÈCES
ADMINISTRATIVES ET FORMULAIRES que le candidat doit fournir (candidature et offre).
Uniquement ce qui est EXPLICITEMENT exigé ; cite le passage exact (moins de 25 mots) et sa référence [fichier, p.].
Pour chaque pièce, classe aussi son "type" :
- "declaration_candidat" si c'est une lettre/déclaration que LE CANDIDAT rédige et signe lui-même (lettre de candidature, déclaration sur l'honneur, note de présentation, attestation de moyens propres...).
- "document_tiers" si c'est un document DÉLIVRÉ PAR UN TIERS que le candidat ne fait qu'obtenir et joindre (attestation fiscale, extrait de registre du commerce, garantie bancaire, certificat d'assurance, certification qualité...).
Réponds en JSON : {{"pieces": [{{"piece": "...", "citation": "...", "reference": "...", "type": "declaration_candidat|document_tiers"}}]}}. Liste vide si rien.

{extraits}"""
        out = await _llm_json(db, tenant_uuid, consigne, 1800)
        # 11/09 : un appel modele en echec (ou vide) faisait disparaitre TOUTES les
        # pieces du RC -- et la carte annoncait « RC absent » alors qu'il etait
        # depose. On lit alors simplement les listes du texte.
        if not (out or {}).get("pieces"):
            out = {"pieces": _pieces_par_lecture_simple(passages)}
            lecture_simple = bool(out["pieces"])
        for it in (out or {}).get("pieces", []) or []:
            if isinstance(it, dict) and it.get("piece") and it.get("citation"):
                type_piece = it.get("type") if it.get("type") in ("declaration_candidat", "document_tiers") else None
                exigences.append({"piece": str(it["piece"])[:120], "origine": f"DCE {it.get('reference') or ''}".strip(),
                                  "citation": str(it["citation"])[:240], "type": type_piece})
                nb_dce += 1
    if pays == "FR" and not any("dume" in _norm(e["piece"]) for e in exigences):
        exigences.append({"piece": "DUME", "citation": None,
                          "origine": _t("dume_origine", L)})
    # 15/09 : pieces recommandees (vues dans un dossier precedent, meme tenant/pays) que
    # l'utilisateur vient de confirmer pour CE dossier -- rejoignent les exigences, avec la
    # citation/le type retrouves dans l'historique ; renforcees comme les autres plus bas.
    for _label in (pieces_confirmees or []):
        _lbl = str(_label)[:250]
        _h = next((h for h in historique if h.piece_key == _cle_historique(_lbl)), None)
        if not _h:
            _kl = _cle(_lbl)
            _h = next((h for h in historique if _kl and (_kl <= _cle(h.piece_label) or _cle(h.piece_label) <= _kl)), None)
        if _h:
            exigences.append({
                "piece": _h.piece_label, "citation": _h.piece_citation,
                "origine": _t("historique", L, pays=nom_pays(pays, L, profil.country_name if profil else pays)),
                "type": _h.piece_type, "historique": True,
            })
    # Dedoublonnage (meme piece citee par le profil pays et par le DCE)
    uniques: List[Dict[str, Any]] = []
    for e in exigences:
        k = _cle(e["piece"])
        doublon = next((u for u in uniques if k and (k <= _cle(u["piece"]) or _cle(u["piece"]) <= k)), None)
        if doublon:
            if e.get("citation") and not doublon.get("citation"):
                doublon.update(citation=e["citation"], origine=doublon["origine"] + " + " + e["origine"])
                if e.get("historique"):
                    doublon["historique"] = True
            continue
        uniques.append(e)

    # 15/09 : recommandations -- pieces vues dans un dossier precedent (meme tenant, meme pays)
    # mais absentes de celui-ci ; jamais ajoutees d'office, seulement proposees (pieces_confirmees
    # au prochain appel les fait rejoindre les exigences ci-dessus, cf. bloc precedent).
    recommandations: List[Dict[str, Any]] = []
    for h in sorted(historique, key=lambda h: h.seen_count or 0, reverse=True):
        kh = _cle(h.piece_label)
        if not kh or any(kh <= _cle(u["piece"]) or _cle(u["piece"]) <= kh for u in uniques):
            continue
        recommandations.append({
            "piece": h.piece_label, "type": h.piece_type, "vu_fois": h.seen_count or 1,
            "dernier_dossier_le": h.last_seen_at.isoformat() if h.last_seen_at else None,
        })

    # 2. Disponible
    docs = (await db.execute(select(DCEDocument.filename, DCEDocument.doc_type)
                             .where(DCEDocument.project_id == project.id, DCEDocument.tenant_id == tenant_uuid))).all()
    assets = (await db.execute(select(CompanyAsset.title, CompanyAsset.category)
                               .where(CompanyAsset.tenant_id == tenant_uuid, CompanyAsset.obsolete_at.is_(None)))).all()
    rc_depose = any((t or "").lower() == "rc" for _f, t in docs)
    dispo_dossier = [(f"{f} {t}", _t("piece_dossier", L, x=f)) for f, t in docs]
    dispo_entreprise = [(f"{t} {c}", _t("doc_entreprise", L, x=t)) for t, c in assets]
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
            trouve = _t("memoire_app", L, n=nb_sections)
        for texte, libelle in (dispo_dossier if propre_offre else dispo_dossier + dispo_entreprise):
            if trouve:
                break
            kd = _cle(texte)
            if k and len(k & kd) >= max(1, min(2, len(k))):
                trouve = libelle
                break
        gen = ", ".join(v for c, v in generables.items() if c in k) or None
        # 15/09 : pour un pays sans formulaire national fixe (gen=None), une piece que le
        # DCE exige explicitement (citation reelle, pas une heuristique de profil pays) ET
        # que le modele a classee comme redigee par le candidat lui-meme (pas un document
        # tiers comme une attestation fiscale ou une garantie bancaire) peut etre PROPOSEE
        # EN BROUILLON plutot que seulement recherchee -- voir generate_declaration_docx.
        redigeable = bool(
            not trouve and not gen and not e.get("certification")
            and e.get("type") == "declaration_candidat" and e.get("citation")
        )
        statut = "fourni" if trouve else ("generable" if gen else ("redigeable" if redigeable else "manquant"))
        telechargeables = [{"code": c, "libelle": v, "type": "template",
                            "chemin": f"/dossiers/{project.id}/{'dume.docx' if c == 'dume' else c}"}
                           for c, v in generables.items() if c in k]
        if redigeable:
            telechargeables.append({
                "code": "declaration", "libelle": e["piece"], "type": "draft",
                "chemin": f"/dossiers/{project.id}/piece-declaration?piece={quote(e['piece'])}&citation={quote(e['citation'])}",
            })
        ligne = {**e, "statut": statut, "fourni_par": trouve, "telechargements": telechargeables,
                 "generable": _t("generable", L, x=gen) if gen else None,
                 "redigeable": _t("redigeable", L) if redigeable else None,
                 "liens": [], "recherche": None}
        if e.get("certification") and statut == "manquant":
            ligne["recherche"] = _t("certificat", L)
        elif chercher and statut != "fourni" and domaines:
            # 11/09 : les pieces allemandes, espagnoles, italiennes et neerlandaises
            # sont deja nommees dans la langue du pays ; les traduire en anglais ne
            # trouvait plus rien sur leurs portails (0 lien pour l'Allemagne).
            mot = MOT_FORMULAIRE.get(pays)
            requete = f"{e['piece']} {mot}" if mot else await _traduire(db, tenant_uuid, f"{e['piece']} form download")
            try:
                res = await web_search_service.search(tenant_id=str(tenant_uuid), query=requete, num_results=5,
                                                      project_id=str(project.id), allowed_sites=domaines)
            except Exception as exc:
                res = []
                ligne["recherche"] = _t("indispo", L, x=type(exc).__name__)
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
                        erreur = _t("robots", L)
                    liens.append({"titre": r.title, "url": r.url, "format": p.get("type") or "page",
                                  "verifie": bool(p.get("texte")), "extrait": (p.get("texte") or r.snippet or "")[:300],
                                  "erreur": erreur})
                # Formulaires telechargeables d'abord, puis pages lues, puis le reste.
                liens.sort(key=lambda l: (l["format"] not in ("pdf", "docx"), not l["verifie"]))
                ligne["liens"] = liens[:3]
                ligne["recherche"] = _t("recherche", L, q=requete, n=len(domaines), pays=nom_pays(pays, L))
            elif not ligne["recherche"]:
                ligne["recherche"] = _t("aucun", L, q=requete, pays=nom_pays(pays, L))
        resultat.append(ligne)

    # 15/09 : renforce l'historique tenant+pays avec tout ce qui a une citation reelle (DCE
    # de ce dossier, ou confirme depuis une recommandation) -- alimente les recommandations
    # des PROCHAINS dossiers similaires ("on fait les reco et on apprend").
    for e in uniques:
        if e.get("citation"):
            await _upsert_piece_history(db, tenant_uuid, pays, e["piece"], e.get("type"), e["citation"], project.id)

    return {
        "pays": pays,
        "pays_nom": nom_pays(pays, L, profil.country_name if profil else pays),
        "portails": domaines,
        "dce_analyse": dce_lu,
        "pieces": resultat,
        "resume": {s: sum(1 for r in resultat if r["statut"] == s) for s in ("fourni", "generable", "redigeable", "manquant")},
        "pieces_du_dce": nb_dce,
        "rc_absent": not nb_dce and not rc_depose,
        "lecture_simple": lecture_simple,
        "recommandations": recommandations,
        "avertissement": (None if nb_dce else
                          _t("rc_illisible", L) if rc_depose else
                          _t("rc_absent", L, pays=nom_pays(pays, L, profil.country_name if profil else pays))),
    }
