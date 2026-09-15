"""
DCE (Dossier de Consultation des Entreprises) Ingestion & Criteria Extraction Endpoints.
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
"""
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.core.storage import storage_service
from app.models.entities import DCECriterionEntity, DCEDocument, DCEEmbedding, ProjectGoNoGoAnalysis
from app.models.schemas import DCECriterion, DCEUploadResponse, GoNoGoAnalysisOut
from app.services.billing_service import billing_service, infer_provider_id_from_model_string
from app.services.chunking_service import chunking_service
from app.services.go_no_go_service import go_no_go_service
from app.services.ocr_service import ocr_service


router = APIRouter(prefix="/dce", tags=["DCE Ingestion & Criteria"])

# 14/09 : aucune limite de taille n'etait appliquee sur le depot d'un DCE (a la
# difference de la base de connaissance, plafonnee a 50 Mo). Le texte affiche au
# client ("jusqu'a 50 Mo") n'etait donc qu'une indication, jamais verifiee -- ni
# cote navigateur ni cote API. Mesure reelle (14/09) : un CCTP de 300 pages
# scanne en niveaux de gris a 200 DPI pese environ 110 Mo ; ce plafond laisse une
# marge confortable (plus haute resolution, dossier plus volumineux) tout en
# bornant la memoire du service API, qui lit le fichier entierement avant de le
# stocker.
MAX_DCE_FILE_SIZE_BYTES = 250 * 1024 * 1024  # 250 Mo


@router.post("/upload", response_model=DCEUploadResponse)
async def upload_dce_document(
    project_id: str = Form(...),
    doc_type: str = Form("cctp"),
    file: UploadFile = File(...),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Uploads a tender PDF document to tenant storage and records it directly in PostgreSQL.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_DCE_FILE_SIZE_BYTES:
        size_mb = round(len(file_bytes) / (1024 * 1024), 1)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Fichier trop volumineux ({size_mb} Mo). Taille maximale acceptee pour une "
                f"piece de marche : 250 Mo."
            ),
        )

    filename = file.filename or "dce_document.pdf"
    doc_id = uuid.uuid4()

    # 03/09 : rejette un doublon exact deja indexe sur CE projet -- protection anti-abus
    # (un client, volontairement ou par erreur, qui redepose 50 fois le meme CCTP ne doit
    # pas faire consommer 50 fois le quota de pages / le cout OCR-embeddings), miroir du
    # dedup deja en place sur la base de connaissances (app/api/knowledge.py).
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    dedup_stmt = select(DCEDocument).where(
        DCEDocument.tenant_id == t_uuid,
        DCEDocument.project_id == p_uuid,
        DCEDocument.file_hash == file_hash,
    )
    dedup_result = await db.execute(dedup_stmt)
    existing_duplicate = dedup_result.scalar_one_or_none()
    if existing_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Ce fichier est identique à un document déjà déposé sur ce dossier : "
                f"« {existing_duplicate.filename} ». Supprimez-le d'abord si vous voulez le remplacer."
            ),
        )

    subpath = f"dce/{project_id}/{doc_id}_{filename}"
    s3_key = storage_service.upload_file(
        tenant_id=current_user.tenant_id,
        subpath=subpath,
        file_obj=file_bytes,
        content_type=file.content_type or "application/pdf"
    )

    # 1. Save document record in PostgreSQL with status 'processing'
    dce_doc = DCEDocument(
        id=doc_id,
        tenant_id=t_uuid,
        project_id=p_uuid,
        filename=filename,
        doc_type=doc_type,
        s3_key=s3_key,
        file_size_bytes=len(file_bytes),
        file_hash=file_hash,
        ocr_status="processing",
        raw_metadata={"task": "parse_dce_task"},
        created_at=datetime.utcnow(),
    )
    db.add(dce_doc)

    # 2. L'extraction des critères réels se fait maintenant de façon asynchrone dans
    # parse_dce_task (01/09), une fois le texte OCR du document disponible -- un
    # vrai appel LLM (criteria_extraction_service, task_type="extraction_gonogo")
    # remplace l'ancienne insertion synchrone des 4 mêmes critères codés en dur,
    # qui ne lisait jamais le contenu réel du document déposé.

    await db.flush()
    # (La ligne n'est validee qu'a la fin de la requete : parse_dce_task reessaie
    # quelques secondes s'il ne la trouve pas encore -- voir tasks.py, 11/09.)

    # 3. Asynchronously dispatch Celery background worker task for OCR, chunking & vector embeddings
    from app.workers.tasks import parse_dce_task
    parse_dce_task.delay(
        tenant_id=current_user.tenant_id,
        project_id=str(p_uuid),
        document_id=str(doc_id),
        s3_key=s3_key,
    )

    return DCEUploadResponse(
        document_id=str(doc_id),
        project_id=str(p_uuid),
        filename=filename,
        s3_key=s3_key,
        status="processing",
        pages_count=0,
        chunks_count=0,
        message="Document déposé avec succès. Analyse OCR et indexation vectorielle lancées en arrière-plan (Celery).",
    )



MSG_PIECES = {
    "fr": {"abandon": "Analyse jamais terminée (le traitement en arrière-plan s'est arrêté). Cliquez sur « Relancer l'analyse » : elle se fera tout de suite.",
           "vide": "Analyse déclarée terminée mais aucun fragment indexé : cette pièce n'apporte rien à la rédaction. Relancez l'analyse.",
           "ok": "{n} fragment(s) indexé(s) et exploitables par la rédaction.",
           "echec": "Analyse en échec.", "en_cours": "Analyse en cours.",
           "aucune": "Aucune pièce du marché n'est exploitable sur ce dossier : la rédaction se fera sans le CCTP ni le règlement de consultation.",
           "partiel": " {n_illisibles} page(s) sur {n_total} n'ont pas pu être lues (probablement scannées en mauvaise qualité) et ne contribuent pas à la rédaction."},
    "en": {"abandon": "Analysis never finished (the background processing stopped). Click “Rerun analysis”: it will run right away.",
           "vide": "Analysis reported as finished but no passage was indexed: this document adds nothing to the writing. Rerun the analysis.",
           "ok": "{n} passage(s) indexed and usable for writing.",
           "echec": "Analysis failed.", "en_cours": "Analysis in progress.",
           "aucune": "No tender document is usable on this project: writing will proceed without the specifications or the tender regulations.",
           "partiel": " {n_illisibles} page(s) out of {n_total} could not be read (likely a low-quality scan) and do not contribute to the writing."},
    "ar": {"abandon": "لم يكتمل التحليل (توقفت المعالجة في الخلفية). انقر على «إعادة التحليل»: سيتم فورًا.",
           "vide": "أُعلن انتهاء التحليل دون فهرسة أي مقطع: لا تفيد هذه الوثيقة التحرير. أعد التحليل.",
           "ok": "{n} مقطع مفهرس وقابل للاستخدام في التحرير.",
           "echec": "فشل التحليل.", "en_cours": "التحليل جارٍ.",
           "aucune": "لا توجد وثيقة مناقصة قابلة للاستخدام في هذا المشروع: سيتم التحرير دون دفتر الشروط الفنية ولا نظام المناقصة.",
           "partiel": " تعذّرت قراءة {n_illisibles} صفحة من أصل {n_total} (على الأرجح مسح ضوئي رديء الجودة) ولا تُستخدم في التحرير."},
}


@router.get("/documents/{project_id}")
async def list_dce_documents(
    project_id: str,
    request: Request,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    État réel des pièces du marché déposées sur un dossier.

    Pourquoi cette route existe (10/09). Il n'existait AUCUN moyen, dans l'interface,
    de voir si une pièce déposée avait été analysée. Constat sur un vrai dossier :
    un CCTP déposé le 3 septembre était resté bloqué en « processing » pendant une
    semaine, zéro fragment indexé — et toutes les sections avaient été rédigées sans
    une seule ligne du marché, sans que rien ne le signale. L'utilisateur avait
    fini par redéposer le même fichier sur de NOUVEAUX dossiers, sans comprendre.

    On renvoie donc, pour chaque pièce : son statut réel, le nombre de fragments
    réellement indexés (la seule preuve qu'elle est exploitable), et un message en
    clair. Une analyse restée en cours au-delà d'un délai large est requalifiée en
    échec : mieux vaut un échec explicite qu'un sablier éternel.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifiant invalide")

    res = await db.execute(
        select(DCEDocument)
        .where(DCEDocument.tenant_id == t_uuid, DCEDocument.project_id == p_uuid)
        .order_by(DCEDocument.created_at.desc())
    )
    documents = res.scalars().all()

    comptes = {}
    if documents:
        cnt_res = await db.execute(
            select(DCEEmbedding.document_id, func.count())
            .where(DCEEmbedding.project_id == p_uuid, DCEEmbedding.tenant_id == t_uuid)
            .group_by(DCEEmbedding.document_id)
        )
        comptes = {row[0]: row[1] for row in cnt_res.all()}

    DELAI_ABANDON = timedelta(minutes=20)
    # 11/09 : messages dans la langue de l'interface.
    L = (request.headers.get("X-UI-Language") or "fr").lower()[:2]
    L = L if L in MSG_PIECES else "fr"
    M = MSG_PIECES[L]
    maintenant = datetime.utcnow()
    sortie = []
    for d in documents:
        nb = comptes.get(d.id, 0)
        statut = d.ocr_status or "processing"
        message = None
        depuis = d.created_at
        # 11/09 : une piece RELANCEE etait jugee sur sa date de depot et redevenait
        # aussitot « jamais terminee ». On part de la derniere relance.
        relance = (d.raw_metadata or {}).get("relance_le")
        if relance:
            try:
                depuis = datetime.fromisoformat(relance)
            except ValueError:
                pass
        if depuis is not None and depuis.tzinfo is not None:
            depuis = depuis.replace(tzinfo=None)

        if statut == "processing" and depuis is not None and maintenant - depuis > DELAI_ABANDON:
            statut = "failed"
            message = M["abandon"]
        elif statut == "completed" and nb == 0:
            statut = "failed"
            message = M["vide"]
        elif statut == "completed":
            message = M["ok"].format(n=nb)
            # 14/09 : le nombre de pages illisibles (scan de mauvaise qualite, meme
            # apres tentative Azure) etait calcule dans ocr_service.py mais jamais lu
            # nulle part ailleurs -- un document a moitie scanne s'affichait comme un
            # succes plein, sans que rien ne dise que des pages n'avaient rien apporte.
            meta = d.raw_metadata or {}
            n_illisibles = meta.get("pages_illisibles") or 0
            n_total = meta.get("pages_total") or 0
            if n_illisibles > 0 and n_total > 0:
                message += M["partiel"].format(n_illisibles=n_illisibles, n_total=n_total)
        elif statut == "failed":
            message = (d.raw_metadata or {}).get("error") or M["echec"]
        else:
            message = M["en_cours"]

        sortie.append({
            "id": str(d.id),
            "filename": d.filename,
            "doc_type": d.doc_type,
            "statut": statut,
            "statut_brut": d.ocr_status,
            "fragments_indexes": nb,
            "message": message,
            "taille_octets": d.file_size_bytes,
            "created_at": d.created_at,
            "pages_illisibles": (d.raw_metadata or {}).get("pages_illisibles") or 0,
            "pages_total": (d.raw_metadata or {}).get("pages_total") or 0,
        })

    total_fragments = sum(x["fragments_indexes"] for x in sortie)
    return {
        "documents": sortie,
        "total_fragments": total_fragments,
        "exploitable": total_fragments > 0,
        "avertissement": None if total_fragments > 0 else M["aucune"],
    }


@router.post("/documents/{document_id}/reanalyser")
async def relancer_analyse_document(
    document_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Relance l'analyse d'une pièce restée bloquée ou dont l'indexation a échoué."""
    try:
        d_uuid = uuid.UUID(document_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifiant invalide")

    res = await db.execute(
        select(DCEDocument).where(DCEDocument.id == d_uuid, DCEDocument.tenant_id == t_uuid)
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pièce introuvable")
    if not doc.s3_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette pièce n'a pas de fichier stocké : il faut la redéposer.",
        )

    reponse = {"relance": True, "document_id": str(doc.id), "filename": doc.filename}
    tache = dict(
        tenant_id=current_user.tenant_id,
        project_id=str(doc.project_id),
        document_id=str(doc.id),
        s3_key=doc.s3_key,
    )
    # 11/09 : le statut est valide AVANT d'envoyer la tache, dans une session dediee
    # (la session de get_db ne se valide qu'en fin de requete et ne doit pas etre
    # validee a la main). Sinon un echec rapide du worker (« failed ») etait ecrase
    # par le « processing » valide apres coup. L'appartenance vient d'etre verifiee.
    from app.core.db import AsyncSessionLocal
    async with AsyncSessionLocal() as session_statut:
        d_statut = await session_statut.get(DCEDocument, doc.id)
        d_statut.ocr_status = "processing"
        d_statut.raw_metadata = {**(d_statut.raw_metadata or {}), "task": "parse_dce_task",
                                 "relance_le": datetime.utcnow().isoformat()}
        await session_statut.commit()
    db.expunge(doc)

    from app.workers.tasks import parse_dce_task
    parse_dce_task.delay(**tache)
    return reponse


@router.post("/documents/{document_id}/analyser-maintenant")
async def analyser_document_maintenant(
    document_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyse une piece TOUT DE SUITE, dans l'API, sans passer par le worker (11/09).

    Meme raison d'etre que /export/compile/sync : quand le worker est arrete, occupe
    ou sur un code perime, « Relancer l'analyse » partait en file et ne revenait
    jamais (constate avec le RC de test : « en cours » pendant plus d'une heure).
    """
    from starlette.concurrency import run_in_threadpool
    from app.core.db import AsyncSessionLocal
    from app.workers.tasks import parse_dce_task

    try:
        d_uuid = uuid.UUID(document_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifiant invalide")
    doc = (await db.execute(select(DCEDocument).where(DCEDocument.id == d_uuid,
                                                      DCEDocument.tenant_id == t_uuid))).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pièce introuvable")
    if not doc.s3_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette pièce n'a pas de fichier stocké : il faut la redéposer.")
    project_id, s3_key = doc.project_id, doc.s3_key

    async with AsyncSessionLocal() as session_statut:
        d = await session_statut.get(DCEDocument, d_uuid)
        d.ocr_status = "processing"
        d.raw_metadata = {**(d.raw_metadata or {}), "task": "parse_dce_task (api)",
                          "relance_le": datetime.utcnow().isoformat()}
        await session_statut.commit()

    erreur = None
    try:
        await run_in_threadpool(parse_dce_task, tenant_id=current_user.tenant_id, project_id=str(project_id),
                                document_id=document_id, s3_key=s3_key)
    except Exception as exc:  # le statut « failed » et son motif sont ecrits par la tache
        erreur = str(exc)[:300]

    async with AsyncSessionLocal() as session_lecture:
        d = await session_lecture.get(DCEDocument, d_uuid)
        fragments = (await session_lecture.execute(select(func.count()).select_from(DCEEmbedding)
                                                   .where(DCEEmbedding.document_id == d_uuid))).scalar() or 0
        criteres = (await session_lecture.execute(select(func.count()).select_from(DCECriterionEntity)
                                                  .where(DCECriterionEntity.project_id == project_id))).scalar() or 0
        return {"document_id": document_id, "statut": d.ocr_status if d else None, "fragments": fragments,
                "criteres": criteres, "erreur": erreur or ((d.raw_metadata or {}).get("error") if d else None)}


@router.get("/criteria/{project_id}", response_model=List[DCECriterion])
async def get_project_criteria(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the extracted RC scoring criteria and requirements for the tender project.
    Strictly scoped by Postgres RLS and tenant_id.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    stmt = select(DCECriterionEntity).where(
        DCECriterionEntity.project_id == p_uuid,
        DCECriterionEntity.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    criteria = result.scalars().all()

    return [
        DCECriterion(
            id=str(c.id),
            criterion_title=c.criterion_title,
            weight_percentage=float(c.weight_percentage),
            description=c.description or "",
            key_expectations=c.key_expectations or [],
            required_evidence=c.required_evidence or [],
            mandatory=c.mandatory in ("true", "True", True, "1"),
            # 11/09 : on dit d'ou vient le critere (fichier lu, ou bareme generique).
            extracted_from=c.extracted_from or "Règlement de Consultation (RC)",
        )
        for c in criteria
    ]


@router.get("/search")
async def search_dce_chunks(
    project_id: str,
    query: str,
    limit: int = 5,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Searches indexed DCE chunks for a project using PostgreSQL.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    stmt = (
        select(DCEEmbedding)
        .where(
            DCEEmbedding.project_id == p_uuid,
            DCEEmbedding.tenant_id == t_uuid,
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return {
        "project_id": project_id,
        "query": query,
        "results_count": len(chunks),
        "chunks": [
            {
                "id": str(c.id),
                "page_number": int(c.page_number),
                "content": c.content,
                "section_title": c.section_title,
            }
            for c in chunks
        ]
    }


import pydantic
class DCEChatMessage(pydantic.BaseModel):
    project_id: str
    query: str
    include_web_search: bool = True
    custom_api_key: Optional[str] = None


@router.post("/chat")
async def chat_with_dce(
    payload: DCEChatMessage,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Interactive Chat Assistant for DCE Consultation Dossier & BTP Norms.
    Returns answers with mandatory source citations.
    """
    import litellm

    try:
        p_uuid = uuid.UUID(payload.project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project UUID")

    # 02/09 : plafond de cout LLM mensuel reel (protection de marge, parametrable par
    # forfait/tenant) -- verifie avant tout appel LLM.
    await billing_service.check_and_enforce_cost_cap(current_user.tenant_id, db=db)

    query = payload.query.strip()

    # 1. Fetch relevant DCE extracts from PostgreSQL
    stmt = (
        select(DCEEmbedding)
        .where(
            DCEEmbedding.project_id == p_uuid,
            DCEEmbedding.tenant_id == t_uuid,
        )
        .limit(4)
    )
    result = await db.execute(stmt)
    db_chunks = result.scalars().all()

    # Correctif (29/08) : ce endpoint servait avant un contenu générique câblé en
    # dur ("CCTP Lot 01"... "Article 4.2"...) avec des pages inventées dès qu'aucun
    # extrait réel n'existait pour CE dossier précis -- indiscernable pour
    # l'utilisateur d'une vraie réponse sourcée sur SES documents. Corrigé pour
    # respecter la même règle "zéro hallucination" appliquée ailleurs dans
    # l'application (cf. tag "Donnée non trouvée / Manquante") : si rien n'est
    # indexé pour ce dossier, on le dit clairement plutôt que d'inventer un
    # contenu plausible mais faux.
    if not db_chunks:
        return {
            "success": True,
            "query": query,
            "answer": (
                "Aucun extrait indexé pour ce dossier pour le moment — je ne peux pas répondre en "
                "me basant sur votre document réel tant que l'indexation n'est pas terminée. "
                "Le DCE/CCTP n'a peut-être pas encore été uploadé, ou son analyse est encore en "
                "cours (OCR + indexation en tâche de fond). Vérifiez le statut du document dans "
                "l'onglet Documents, puis réessayez dans quelques instants."
            ),
            "sources": [],
            "grounded": False,
            "timestamp": datetime.utcnow().isoformat(),
        }

    sources = [
        {
            "source": f"DCE {c.section_title or 'Section'}",
            "page": int(c.page_number),
            "snippet": c.content[:150] + "..." if len(c.content) > 150 else c.content,
        }
        for c in db_chunks
    ]

    sources_text = "\n".join([f"- [{s['source']}, Page {s['page']}]: {s['snippet']}" for s in sources])
    prompt = f"""Tu es un Ingénieur d'Études BTP expert en marchés publics français.
L'utilisateur te pose une question technique sur le Dossier de Consultation des Entreprises (DCE) du projet ou sur les normes BTP.

EXTRAITS DU DOSSIER DE CONSULTATION (DCE) :
{sources_text}

QUESTION DE L'UTILISATEUR :
{query}

DIRECTIVES :
1. Réponds de façon précise, technique et concise en français.
2. CITE OBLIGATOIREMENT tes sources exactes (ex: "Source : CCTP Lot 01, Page 18", ou "Référence : DTU 21").
3. Donne les valeurs chiffrées précises quand elles s'appliquent.
"""

    answer_text = ""

    # Même correctif que sur l'assistant de projet (03/09) : ce point d'appel
    # lisait uniquement ANTHROPIC_API_KEY et forçait Claude, en ignorant le
    # fournisseur choisi dans l'administration. Il passe désormais par le routage
    # commun, donc par le palier du client et ses éventuelles surcharges.
    from app.services.model_routing_service import model_routing_service

    resolved = await model_routing_service.resolve_model_for_tenant(db, t_uuid)
    model_to_use = resolved["model_string"]
    creds = await model_routing_service.get_credentials_for_model(db, model_to_use)
    api_key_to_use = payload.custom_api_key or creds.get("api_key")

    if api_key_to_use:
        try:
            call_kwargs = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": prompt}],
                "api_key": api_key_to_use,
                "temperature": 0.2,
                "max_tokens": 600,
            }
            if creds.get("api_base"):
                call_kwargs["api_base"] = creds["api_base"]
            response = litellm.completion(**call_kwargs)
            answer_text = response.choices[0].message.content

            _usage = getattr(response, "usage", None)
            await billing_service.log_llm_usage(
                db=db,
                tenant_id=t_uuid,
                project_id=p_uuid,
                provider_id=creds.get("provider_id") or infer_provider_id_from_model_string(model_to_use),
                model_string=model_to_use,
                prompt_tokens=getattr(_usage, "prompt_tokens", None) if _usage else None,
                completion_tokens=getattr(_usage, "completion_tokens", None) if _usage else None,
                total_tokens=getattr(_usage, "total_tokens", None) if _usage else None,
            )
        except Exception as e:
            print(f"[DCEChat] LLM notice ({model_to_use}): {e}")

    if not answer_text:
        # Correctif (29/08) : repli honnête si l'appel LLM échoue -- ne fabrique
        # plus de réponse générique câblée en dur déconnectée du dossier réel.
        # Les VRAIS extraits trouvés (sources ci-dessous) restent affichés même
        # si le résumé automatique par l'IA a échoué.
        answer_text = (
            f"Le moteur IA n'a pas pu générer de résumé pour le moment (voir les journaux serveur). "
            f"{len(sources)} extrait(s) réel(s) de votre dossier ont bien été trouvés et sont listés "
            "ci-dessous en sources -- consultez-les directement, ou réessayez la question dans un instant."
        )

    return {
        "success": True,
        "query": query,
        "answer": answer_text,
        "sources": sources,
        "grounded": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/test-ocr")
async def test_ocr_extraction(
    file: UploadFile = File(...),
    custom_azure_key: Optional[str] = Form(None)
):
    """
    Live Playground Endpoint: runs OCR on uploaded document.
    """
    file_bytes = await file.read()
    filename = file.filename or "test_document.pdf"
    
    ocr_result = ocr_service.extract_text_and_tables(file_bytes, filename)
    pages = ocr_result.get("pages", [])
    raw_text = ocr_result.get("full_text") or ocr_result.get("raw_text", "")
    chunks = chunking_service.chunk_document_pages(pages)

    return {
        "status": "success",
        "filename": filename,
        "file_size_bytes": len(file_bytes),
        "pages_count": len(pages),
        "total_characters": len(raw_text),
        "estimated_tokens": len(raw_text) // 4,
        "ocr_provider": "Azure Document Intelligence" if (settings.AZURE_DOC_INTELLIGENCE_KEY or custom_azure_key) else "pdfplumber (Python Local OCR)",
        "pages": pages[:10],
        "chunks_count": len(chunks),
        "chunks_sample": chunks[:5],
    }


# -----------------------------------------------------------------------------
# Go/No-Go Tender Decision Matrix Endpoints
# -----------------------------------------------------------------------------
@router.post("/go-no-go/{project_id}", response_model=GoNoGoAnalysisOut)
async def evaluate_tender_go_no_go(
    project_id: str,
    request: Request,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes a reasoned Go / Réserves / No-Go recommendation for a tender.
    11/09 : renvoie aussi l'etat (go / no_go / suspendue / reserves), les raisons et les
    actions a mener avec leur lien, dans la langue de l'interface (X-UI-Language).
    """
    return await _go_no_go(project_id, request, current_user, db)


async def _go_no_go(project_id: str, request: Request, current_user: CurrentTenantUser, db: AsyncSession):
    from app.services.go_no_go_i18n import localiser_analyse
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")
    try:
        analysis = await go_no_go_service.evaluate_project(
            db=db,
            tenant_id=t_uuid,
            project_id=p_uuid,
            user_id=u_uuid,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return GoNoGoAnalysisOut(**localiser_analyse(analysis, request.headers.get("X-UI-Language")))


@router.get("/go-no-go/{project_id}", response_model=GoNoGoAnalysisOut)
async def get_tender_go_no_go(
    project_id: str,
    request: Request,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    11/09 : l'analyse enregistree devenait fausse des qu'une donnee changeait (RC depose,
    date limite saisie...) et restait affichee telle quelle. Le calcul ne coute que
    quelques requetes : on le refait a chaque lecture.
    """
    return await _go_no_go(project_id, request, current_user, db)
