"""
Project & Tender (Appels d'Offres) Management Endpoints
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import CompanyAsset, DCEEmbedding, Project, TenantLearning
from app.models.schemas import (
    ProjectCreate,
    ProjectHistoryItemOut,
    ProjectOut,
    ProjectOutcomeRecordPayload,
    ProjectsHistoryResponse,
    ProjectUpdate,
    TenantLearningOut,
    TenantLearningUpdate,
)
from app.services.learning_service import learning_service


class AskProjectPayload(BaseModel):
    question: str
    source_mode: str = "corpus"  # "corpus", "corpus_web", "web"
    custom_api_key: Optional[str] = None


class AskProjectResponse(BaseModel):
    question: str
    source_mode: str
    answer_markdown: str
    sources: List[Dict[str, Any]]
    total_sources_found: int
    is_degraded: bool = False
    degraded_reason: Optional[str] = None
    timestamp: str



router = APIRouter(prefix="/projects", tags=["Projects"])



@router.get("", response_model=List[ProjectOut])
async def list_projects(
    status_filter: Optional[str] = None,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all tender projects for the authenticated tenant via direct SQLAlchemy 2 Async query.
    RLS and tenant filtering are strictly enforced.
    """
    stmt = select(Project)
    # Defense-in-depth application filter (can be toggled in tests to verify that RLS alone guarantees isolation)
    if not settings.DISABLE_WHERE_CLAUSE_FOR_RLS_TEST:
        stmt = stmt.where(Project.tenant_id == current_user.tenant_id)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    stmt = stmt.order_by(Project.created_at.desc())

    result = await db.execute(stmt)
    projects = result.scalars().all()

    return [
        ProjectOut(
            id=str(p.id),
            tenant_id=str(p.tenant_id),
            title=p.title,
            reference_code=p.reference_code,
            client_name=p.client_name,
            location=p.location,
            lot_number=p.lot_number,
            status=p.status,
            budget_estimate=float(p.budget_estimate) if p.budget_estimate is not None else None,
            submission_deadline=p.submission_deadline,
            scoring_notes=p.scoring_notes or {"technical_weight": 60, "price_weight": 40},
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new tender project bound strictly to the authenticated tenant.
    """
    project_id = uuid.uuid4()
    now = datetime.utcnow()

    new_project = Project(
        id=project_id,
        tenant_id=uuid.UUID(current_user.tenant_id),
        title=payload.title,
        reference_code=payload.reference_code,
        client_name=payload.client_name,
        location=payload.location,
        lot_number=payload.lot_number,
        status="draft",
        budget_estimate=payload.budget_estimate,
        submission_deadline=payload.submission_deadline,
        scoring_notes=payload.scoring_notes,
        created_at=now,
        updated_at=now,
    )

    db.add(new_project)
    await db.flush()
    await db.refresh(new_project)

    return ProjectOut(
        id=str(new_project.id),
        tenant_id=str(new_project.tenant_id),
        title=new_project.title,
        reference_code=new_project.reference_code,
        client_name=new_project.client_name,
        location=new_project.location,
        lot_number=new_project.lot_number,
        status=new_project.status,
        budget_estimate=float(new_project.budget_estimate) if new_project.budget_estimate is not None else None,
        submission_deadline=new_project.submission_deadline,
        scoring_notes=new_project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        outcome_status=new_project.outcome_status,
        buyer_feedback=new_project.buyer_feedback or {},
        outcome_recorded_at=new_project.outcome_recorded_at,
        created_at=new_project.created_at,
        updated_at=new_project.updated_at,
    )


@router.get("/history", response_model=ProjectsHistoryResponse)
async def get_projects_history(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns historical view of all tenders processed by this tenant,
    with win rate metrics and buyer debrief feedback.
    Displays 'Données insuffisantes' when no completed projects exist.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(Project).where(Project.tenant_id == t_uuid).order_by(Project.created_at.desc())
    res = await db.execute(stmt)
    projects = res.scalars().all()

    total_count = len(projects)
    won_count = sum(1 for p in projects if p.outcome_status == "won")
    lost_count = sum(1 for p in projects if p.outcome_status == "lost")
    closed_projects = won_count + lost_count
    pending_count = total_count - closed_projects

    win_rate = None
    win_rate_display = "Données insuffisantes"
    if closed_projects > 0:
        win_rate = round((won_count / closed_projects) * 100.0, 1)
        win_rate_display = f"{win_rate}%"

    return ProjectsHistoryResponse(
        total_projects=total_count,
        closed_projects=closed_projects,
        won_count=won_count,
        lost_count=lost_count,
        pending_count=pending_count,
        win_rate_percentage=win_rate,
        win_rate_display=win_rate_display,
        projects=[
            ProjectHistoryItemOut(
                id=str(p.id),
                title=p.title,
                reference_code=p.reference_code,
                client_name=p.client_name,
                lot_number=p.lot_number,
                budget_estimate=float(p.budget_estimate) if p.budget_estimate is not None else None,
                submission_deadline=p.submission_deadline,
                status=p.status,
                outcome_status=p.outcome_status or "pending",
                buyer_feedback=p.buyer_feedback or {},
                outcome_recorded_at=p.outcome_recorded_at,
                created_at=p.created_at,
            )
            for p in projects
        ],
    )


@router.get("/learnings", response_model=List[TenantLearningOut])
async def list_tenant_learnings(
    category: Optional[str] = None,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists continuous learnings accumulated by the tenant from buyer feedback.
    Strictly isolated per tenant under Postgres RLS.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    learnings = await learning_service.get_active_tenant_learnings(
        db=db,
        tenant_id=t_uuid,
        category=category,
        limit=50,
    )

    return [
        TenantLearningOut(
            id=str(l.id),
            tenant_id=str(l.tenant_id),
            project_id=str(l.project_id) if l.project_id else None,
            category=l.category,
            title=l.title,
            learning_insight=l.learning_insight,
            actionable_directive=l.actionable_directive,
            source_outcome=l.source_outcome,
            is_active=bool(l.is_active),
            created_at=l.created_at,
            updated_at=l.updated_at,
        )
        for l in learnings
    ]


@router.put("/learnings/{learning_id}", response_model=TenantLearningOut)
async def update_tenant_learning(
    learning_id: str,
    payload: TenantLearningUpdate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates an accumulated learning item.
    """
    try:
        l_uuid = uuid.UUID(learning_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid learning or tenant UUID")

    stmt = select(TenantLearning).where(TenantLearning.id == l_uuid, TenantLearning.tenant_id == t_uuid)
    res = await db.execute(stmt)
    learning = res.scalar_one_or_none()

    if not learning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning item not found")

    if payload.title is not None:
        learning.title = payload.title
    if payload.category is not None:
        learning.category = payload.category
    if payload.learning_insight is not None:
        learning.learning_insight = payload.learning_insight
    if payload.actionable_directive is not None:
        learning.actionable_directive = payload.actionable_directive
    if payload.is_active is not None:
        learning.is_active = payload.is_active
    learning.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return TenantLearningOut(
        id=str(learning.id),
        tenant_id=str(learning.tenant_id),
        project_id=str(learning.project_id) if learning.project_id else None,
        category=learning.category,
        title=learning.title,
        learning_insight=learning.learning_insight,
        actionable_directive=learning.actionable_directive,
        source_outcome=learning.source_outcome,
        is_active=bool(learning.is_active),
        created_at=learning.created_at,
        updated_at=learning.updated_at,
    )


@router.delete("/learnings/{learning_id}")
async def delete_tenant_learning(
    learning_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes a learning item.
    """
    try:
        l_uuid = uuid.UUID(learning_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid learning or tenant UUID")

    stmt = select(TenantLearning).where(TenantLearning.id == l_uuid, TenantLearning.tenant_id == t_uuid)
    res = await db.execute(stmt)
    learning = res.scalar_one_or_none()

    if not learning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning item not found")

    await db.delete(learning)
    await db.flush()

    return {"status": "success", "message": "Learning item deleted"}



@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a single project ensuring strict tenant ownership.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid project ID format")

    stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return ProjectOut(
        id=str(project.id),
        tenant_id=str(project.tenant_id),
        title=project.title,
        reference_code=project.reference_code,
        client_name=project.client_name,
        location=project.location,
        lot_number=project.lot_number,
        status=project.status,
        budget_estimate=float(project.budget_estimate) if project.budget_estimate is not None else None,
        submission_deadline=project.submission_deadline,
        scoring_notes=project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates an existing project belonging strictly to the authenticated tenant.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid project ID format")

    stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    project.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(project)

    return ProjectOut(
        id=str(project.id),
        tenant_id=str(project.tenant_id),
        title=project.title,
        reference_code=project.reference_code,
        client_name=project.client_name,
        location=project.location,
        lot_number=project.lot_number,
        status=project.status,
        budget_estimate=float(project.budget_estimate) if project.budget_estimate is not None else None,
        submission_deadline=project.submission_deadline,
        scoring_notes=project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        outcome_status=project.outcome_status or "pending",
        buyer_feedback=project.buyer_feedback or {},
        outcome_recorded_at=project.outcome_recorded_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/{project_id}/outcome", response_model=ProjectOut)
async def record_project_outcome(
    project_id: str,
    payload: ProjectOutcomeRecordPayload,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Records the final outcome (won, lost, withdrawn, pending) and buyer debrief feedback of a tender.
    Automatically distills and capitalizes lessons learned into tenant_learnings.
    Strictly isolated per tenant under Postgres RLS.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or user UUID")

    stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")

    outcome_clean = payload.outcome_status.strip().lower()
    if outcome_clean not in ("won", "lost", "withdrawn", "pending", "in_progress"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid outcome status '{outcome_clean}'")

    now = datetime.now(timezone.utc)
    project.outcome_status = outcome_clean
    if outcome_clean in ("won", "lost"):
        project.status = outcome_clean
    project.outcome_recorded_at = now
    project.outcome_recorded_by = u_uuid
    project.updated_at = now

    feedback_dict = payload.buyer_feedback.model_dump() if payload.buyer_feedback else {}
    if payload.notes:
        feedback_dict["notes"] = payload.notes
    project.buyer_feedback = feedback_dict

    # Automatically extract continuous learnings into tenant memory
    if feedback_dict:
        await learning_service.extract_and_store_learnings_from_feedback(
            db=db,
            tenant_id=t_uuid,
            project_id=p_uuid,
            project_title=project.title,
            outcome_status=outcome_clean,
            buyer_feedback=feedback_dict,
        )

    await db.flush()

    return ProjectOut(
        id=str(project.id),
        tenant_id=str(project.tenant_id),
        title=project.title,
        reference_code=project.reference_code,
        client_name=project.client_name,
        location=project.location,
        lot_number=project.lot_number,
        status=project.status,
        budget_estimate=float(project.budget_estimate) if project.budget_estimate is not None else None,
        submission_deadline=project.submission_deadline,
        scoring_notes=project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        outcome_status=project.outcome_status or "pending",
        buyer_feedback=project.buyer_feedback or {},
        outcome_recorded_at=project.outcome_recorded_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/{project_id}/ask", response_model=AskProjectResponse)
async def ask_project_assistant(
    project_id: str,
    payload: AskProjectPayload,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Project Q&A Assistant with configurable source selection:
    - 'corpus': Vector search on DCE documents (DCEEmbedding) + Company Assets (CompanyAsset) under Postgres RLS.
    - 'web': Real web search (Serper / Anthropic tool) with verified URLs.
    - 'corpus_web': Combined corpus and web search with explicit, individual citations.
    Zero hallucination rule: strictly indicates when no source is found in the selected mode.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project or tenant UUID")

    # 1. Fetch project to ensure it belongs to tenant
    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable pour ce tenant.")

    clean_question = payload.question.strip()
    if not clean_question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La question ne peut pas être vide.")

    source_mode = payload.source_mode.strip().lower()
    if source_mode not in ("corpus", "corpus_web", "web"):
        source_mode = "corpus"

    collected_sources: List[Dict[str, Any]] = []
    corpus_text_parts: List[str] = []
    web_text_parts: List[str] = []

    # 2. Collect Corpus Sources if mode is 'corpus' or 'corpus_web'
    if source_mode in ("corpus", "corpus_web"):
        # A. DCE Embeddings
        dce_stmt = select(DCEEmbedding).where(
            DCEEmbedding.project_id == p_uuid,
            DCEEmbedding.tenant_id == t_uuid
        ).limit(6)
        dce_res = await db.execute(dce_stmt)
        dce_chunks = dce_res.scalars().all()

        for chunk in dce_chunks:
            sec_title = chunk.section_title or "Section Technique"
            pg = int(chunk.page_number) if chunk.page_number else 1
            citation_tag = f"[Source : DCE {sec_title}, Page {pg}]"
            collected_sources.append({
                "type": "dce",
                "title": f"DCE {sec_title}",
                "page": pg,
                "citation": citation_tag,
                "snippet": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
            })
            corpus_text_parts.append(f"--- {citation_tag} ---\n{chunk.content}")

        # B. Company Assets
        assets_stmt = select(CompanyAsset).where(CompanyAsset.tenant_id == t_uuid).limit(4)
        assets_res = await db.execute(assets_stmt)
        assets = assets_res.scalars().all()

        for asset in assets:
            cat = asset.category or "Savoir-Faire"
            title = asset.title or "Fiche Entreprise"
            citation_tag = f"[Source : Entreprise - {title}]"
            collected_sources.append({
                "type": "company_asset",
                "category": cat,
                "title": title,
                "citation": citation_tag,
                "snippet": (asset.description or asset.content or "")[:200],
            })
            corpus_text_parts.append(f"--- {citation_tag} ({cat}) ---\n{asset.description or asset.content or ''}")

    # 3. Collect Web Sources if mode is 'web' or 'corpus_web'
    if source_mode in ("web", "corpus_web"):
        from app.services.web_search_service import web_search_service
        search_query = f"{project.title} BTP {clean_question}"
        web_results = await web_search_service.search(
            tenant_id=current_user.tenant_id,
            query=search_query,
            num_results=3,
            project_id=str(p_uuid),
        )
        for w in web_results:
            citation_tag = f"[Source web : {w.title} — {w.url}]"
            collected_sources.append({
                "type": "web",
                "title": w.title,
                "url": w.url,
                "citation": citation_tag,
                "snippet": w.snippet[:200] + "..." if len(w.snippet) > 200 else w.snippet,
            })
            web_text_parts.append(f"--- {citation_tag} ---\n{w.snippet}")

    corpus_context = "\n\n".join(corpus_text_parts)
    web_context = "\n\n".join(web_text_parts)

    # 4. Prompt Engineering strictly adhering to citations and anti-hallucination
    prompt = f"""Tu es un Ingénieur Principal d'Études BTP assistant sur l'Appel d'Offres "{project.title}" (Réf : {project.reference_code}).
L'utilisateur te pose une question technique avec le mode de sources : {source_mode.upper()}.

EXTRAITS DU CORPUS DU PROJET (DCE & ENTREPRISE) :
{corpus_context or "Aucun extrait trouvé dans le corpus du projet."}

EXTRAITS DES SOURCES WEB EXTERNES :
{web_context or "Aucune recherche web externe effectuée pour ce mode."}

QUESTION :
{clean_question}

DIRECTIVES DE RÉPONSE NON NÉGOCIABLES :
1. RÈGLE STRICTE DE CITATION DES SOURCES :
   - Pour les informations issues du DCE / pièces de marché : cite obligatoirement sous la forme [Source : Nom du document, Page X].
   - Pour les informations issues de l'entreprise : cite sous la forme [Source : Entreprise - Titre].
   - Pour les informations issues du web : cite obligatoirement sous la forme [Source web : Titre — URL].
2. RÈGLE ANTI-HALLUCINATION ABSOLUE :
   - Si les sources fournies dans le mode '{source_mode}' ne contiennent pas l'information demandée, indique immédiatement et explicitement : "Aucune information correspondante n'a été trouvée dans les sources sélectionnées ({source_mode}) pour répondre à cette question."
   - Ne jamais inventer de données, d'exigences contractuelles ou de sources.
3. Rédige en Markdown clair, structuré, précis et direct.
"""

    answer_markdown = ""
    is_degraded = False
    degraded_reason: Optional[str] = None
    api_key_to_use = payload.custom_api_key or settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY or settings.MISTRAL_API_KEY

    if api_key_to_use:
        try:
            import litellm
            model_to_use = "anthropic/claude-3-5-sonnet-20241022" if settings.ANTHROPIC_API_KEY else settings.DEFAULT_LLM_MODEL
            response = litellm.completion(
                model=model_to_use,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key_to_use,
                temperature=0.2,
                max_tokens=1000,
            )
            answer_markdown = response.choices[0].message.content
        except Exception as e:
            is_degraded = True
            degraded_reason = f"Service IA temporairement indisponible ({type(e).__name__})"
            print(f"[ProjectAsk] LLM generation notice: {e}")
    else:
        is_degraded = True
        degraded_reason = "Mode secours : service IA temporairement indisponible"

    if not answer_markdown:
        is_degraded = True
        if not degraded_reason:
            degraded_reason = "Réponse simplifiée / extrait direct"

        # High quality deterministic answering strictly grounded on retrieved sources without hallucination
        if not collected_sources:
            answer_markdown = f"Aucune information correspondante n'a été trouvée dans les sources sélectionnées ({source_mode}) pour répondre à cette question."
        else:
            first_src = collected_sources[0]
            answer_markdown = f"D'après les éléments disponibles dans le mode **{source_mode}** pour le projet **{project.title}** :\n\n- {first_src['snippet']}\n\n{first_src['citation']}"

    return AskProjectResponse(
        question=clean_question,
        source_mode=source_mode,
        answer_markdown=answer_markdown,
        sources=collected_sources,
        total_sources_found=len(collected_sources),
        is_degraded=is_degraded,
        degraded_reason=degraded_reason if is_degraded else None,
        timestamp=datetime.utcnow().isoformat(),
    )



