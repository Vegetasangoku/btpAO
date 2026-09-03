"""
DCE (Dossier de Consultation des Entreprises) Ingestion & Criteria Extraction Endpoints.
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
"""
import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
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
    raw_text = ocr_result.get("raw_text", "")
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
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes a reasoned Go / Réserves / No-Go recommendation for a tender.
    Cross-references mandatory criteria, company qualifications, deadline vs workload, and past win-rate.
    Strictly isolated per tenant under Postgres RLS.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
    except ValueError:
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

    return GoNoGoAnalysisOut(
        id=str(analysis.id),
        tenant_id=str(analysis.tenant_id),
        project_id=str(analysis.project_id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        factors=analysis.factors,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
        evaluated_by=str(analysis.evaluated_by) if analysis.evaluated_by else None,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.get("/go-no-go/{project_id}", response_model=GoNoGoAnalysisOut)
async def get_tender_go_no_go(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the persisted Go/No-Go analysis for the project without recalculating.
    Strictly isolated per tenant under Postgres RLS.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    stmt = select(ProjectGoNoGoAnalysis).where(
        ProjectGoNoGoAnalysis.project_id == p_uuid,
        ProjectGoNoGoAnalysis.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        try:
            u_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
            analysis = await go_no_go_service.evaluate_project(
                db=db,
                tenant_id=t_uuid,
                project_id=p_uuid,
                user_id=u_uuid,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Erreur lors du calcul Go/No-Go : {str(e)}",
            )

    return GoNoGoAnalysisOut(
        id=str(analysis.id),
        tenant_id=str(analysis.tenant_id),
        project_id=str(analysis.project_id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        factors=analysis.factors,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
        evaluated_by=str(analysis.evaluated_by) if analysis.evaluated_by else None,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )

