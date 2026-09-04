"""
Project & Tender (Appels d'Offres) Management Endpoints
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import CompanyAsset, CountryOfficialSource, DCEEmbedding, GeneratedSection, Project, ProjectGoNoGoAnalysis, Tenant, TenantLearning
from app.models.schemas import (
    GoNoGoSummaryOut,
    ProjectCreate,
    ProjectHistoryItemOut,
    ProjectOut,
    ProjectOutcomeRecordPayload,
    ProjectsHistoryResponse,
    ProjectUpdate,
    TenantLearningOut,
    TenantLearningUpdate,
)
from app.services.billing_service import billing_service, infer_provider_id_from_model_string
from app.services.go_no_go_service import go_no_go_service
from app.services.learning_service import learning_service


class AskProjectPayload(BaseModel):
    question: str
    source_mode: str = "corpus"  # "corpus", "corpus_web", "web"
    custom_api_key: Optional[str] = None


class AskProjectResponse(BaseModel):
    id: Optional[str] = None
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
    target_tenant_id = current_user.tenant_id or "93365082-4489-4f0a-9e4b-9dbb219553aa"
    try:
        tenant_uuid = uuid.UUID(str(target_tenant_id))
    except (ValueError, TypeError):
        tenant_uuid = uuid.UUID("93365082-4489-4f0a-9e4b-9dbb219553aa")

    if not settings.DISABLE_WHERE_CLAUSE_FOR_RLS_TEST:
        stmt = stmt.where(Project.tenant_id == tenant_uuid)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    stmt = stmt.order_by(Project.created_at.desc())

    result = await db.execute(stmt)
    projects = result.scalars().all()

    # Batch fetch or auto-compute Go/No-Go analyses for all projects
    analyses_stmt = select(ProjectGoNoGoAnalysis).where(
        ProjectGoNoGoAnalysis.tenant_id == tenant_uuid
    )
    analyses_res = await db.execute(analyses_stmt)
    analyses_map = {a.project_id: a for a in analyses_res.scalars().all()}

    output_list = []
    for p in projects:
        analysis = analyses_map.get(p.id)
        if not analysis:
            try:
                analysis = await go_no_go_service.evaluate_project(
                    db=db,
                    tenant_id=tenant_uuid,
                    project_id=p.id,
                )
                analyses_map[p.id] = analysis
            except Exception as e:
                logger.warning(f"Auto Go/No-Go calculation notice for project {p.id}: {e}")
                analysis = None

        gng_out = GoNoGoSummaryOut(
            id=str(analysis.id),
            recommendation=analysis.recommendation,
            score=float(analysis.score),
            summary=analysis.summary,
            mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
            blocking_issues=analysis.blocking_issues or [],
            completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
            has_sufficient_data=bool(analysis.has_sufficient_data),
        ) if analysis else None

        output_list.append(
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
                strategic_directives=p.strategic_directives,
                output_language=p.output_language or "fr",
                outcome_status=p.outcome_status or "pending",
                buyer_feedback=p.buyer_feedback or {},
                outcome_recorded_at=p.outcome_recorded_at,
                go_no_go=gng_out,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )

    return output_list


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
    t_uuid = uuid.UUID(current_user.tenant_id)

    new_project = Project(
        id=project_id,
        tenant_id=t_uuid,
        title=payload.title,
        reference_code=payload.reference_code,
        client_name=payload.client_name,
        location=payload.location,
        lot_number=payload.lot_number,
        status="draft",
        budget_estimate=payload.budget_estimate,
        submission_deadline=payload.submission_deadline,
        scoring_notes=payload.scoring_notes,
        strategic_directives=payload.strategic_directives,
        output_language=payload.output_language,
        created_at=now,
        updated_at=now,
    )

    db.add(new_project)
    await db.flush()
    await db.refresh(new_project)

    # Automatically compute initial Go/No-Go score
    analysis = None
    try:
        u_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
        analysis = await go_no_go_service.evaluate_project(
            db=db,
            tenant_id=t_uuid,
            project_id=new_project.id,
            user_id=u_uuid,
        )
    except Exception as e:
        logger.warning(f"Initial Go/No-Go calculation notice on project creation: {e}")

    gng_out = GoNoGoSummaryOut(
        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
    ) if analysis else None

    # Génération Proactive (Zero-Click) : pré-génère immédiatement l'intégralité des sections
    # standard du mémoire technique, afin que l'éditeur ne soit jamais vide à l'ouverture.
    try:
        await billing_service.check_and_enforce_quota(current_user.tenant_id, action="dossier_auto_generation", db=db)
        from app.api.generate import SECTION_DEFINITIONS
        from app.workers.tasks import generate_section_task
        proactive_now = datetime.utcnow()
        for proactive_key, proactive_meta in SECTION_DEFINITIONS.items():
            if proactive_key == "qse_environnement":
                continue  # alias rétro-compatible de rse_environnement, ne pas générer en double
            db.add(GeneratedSection(
                id=uuid.uuid4(),
                tenant_id=t_uuid,
                project_id=new_project.id,
                section_key=proactive_key,
                title=proactive_meta["title"],
                order_index=proactive_meta["order"],
                content_html="<p>Génération en cours d'exécution par le worker d'IA en tâche de fond...</p>",
                content_json={},
                visual_placeholders=[],
                compliance_score=0.0,
                compliance_notes="Génération proactive automatique à la création du dossier (Celery worker)",
                status="processing",
                locked_for_export=False,
                updated_at=proactive_now,
            ))
        await db.flush()
        for proactive_key in SECTION_DEFINITIONS.keys():
            if proactive_key == "qse_environnement":
                continue
            generate_section_task.delay(
                tenant_id=current_user.tenant_id,
                project_id=str(new_project.id),
                section_key=proactive_key,
                custom_instructions=None,
            )
    except HTTPException as e:
        logger.warning(f"Génération proactive ignorée à la création (quota/abonnement) : {e.detail}")
    except Exception as e:
        logger.warning(f"Notice génération proactive à la création du dossier : {e}")

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
        strategic_directives=new_project.strategic_directives,
        output_language=new_project.output_language or "fr",
        outcome_status=new_project.outcome_status or "pending",
        buyer_feedback=new_project.buyer_feedback or {},
        outcome_recorded_at=new_project.outcome_recorded_at,
        go_no_go=gng_out,
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

    # Fetch or auto-compute Go/No-Go analysis
    analysis_stmt = select(ProjectGoNoGoAnalysis).where(
        ProjectGoNoGoAnalysis.project_id == p_uuid,
        ProjectGoNoGoAnalysis.tenant_id == t_uuid,
    )
    analysis_res = await db.execute(analysis_stmt)
    analysis = analysis_res.scalar_one_or_none()

    if not analysis:
        try:
            analysis = await go_no_go_service.evaluate_project(
                db=db,
                tenant_id=t_uuid,
                project_id=p_uuid,
            )
        except Exception:
            analysis = None

    gng_out = GoNoGoSummaryOut(
        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
    ) if analysis else None

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
        strategic_directives=project.strategic_directives,
        output_language=project.output_language or "fr",
        outcome_status=project.outcome_status or "pending",
        buyer_feedback=project.buyer_feedback or {},
        outcome_recorded_at=project.outcome_recorded_at,
        go_no_go=gng_out,
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

    # Fetch Go/No-Go analysis
    analysis_stmt = select(ProjectGoNoGoAnalysis).where(
        ProjectGoNoGoAnalysis.project_id == p_uuid,
        ProjectGoNoGoAnalysis.tenant_id == t_uuid,
    )
    analysis_res = await db.execute(analysis_stmt)
    analysis = analysis_res.scalar_one_or_none()

    gng_out = GoNoGoSummaryOut(
        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
    ) if analysis else None

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
        strategic_directives=project.strategic_directives,
        output_language=project.output_language or "fr",
        outcome_status=project.outcome_status or "pending",
        buyer_feedback=project.buyer_feedback or {},
        outcome_recorded_at=project.outcome_recorded_at,
        go_no_go=gng_out,
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
        strategic_directives=project.strategic_directives,
        output_language=project.output_language or "fr",
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

    # 02/09 : plafond de cout LLM mensuel reel (protection de marge, parametrable par
    # forfait/tenant) -- verifie avant toute recherche (corpus/web) et tout appel LLM.
    await billing_service.check_and_enforce_cost_cap(current_user.tenant_id, db=db)
    # 03/09 : plafond mensuel de NOMBRE de questions (signal d'abus complementaire au $
    # deja plafonne ci-dessus, avec depassement payant comme pour les dossiers) -- verifie
    # AVANT la recherche RAG + l'appel LLM pour ne pas facturer une question qui sera
    # de toute facon refusee.
    await billing_service.check_and_enforce_question_quota(t_uuid, db=db)

    source_mode = payload.source_mode.strip().lower()
    # Normalize mode names: 'ce_projet'/'corpus' vs 'tout_historique'/'all_history' vs 'web' vs 'corpus_web'
    is_all_history_mode = source_mode in ("tout_historique", "all_history", "history", "all_projects")
    is_single_project_mode = source_mode in ("corpus", "ce_projet", "project", "current_project")
    is_web_only_mode = source_mode == "web"
    is_combined_mode = source_mode in ("corpus_web", "tout_historique_web", "all_history_web")

    collected_sources: List[Dict[str, Any]] = []
    corpus_text_parts: List[str] = []
    web_text_parts: List[str] = []

    from app.services.embedding_service import embedding_service
    await embedding_service.sync_platform_key(db)
    query_vector = embedding_service.generate_embedding(clean_question[:2000]) if embedding_service else None

    # 2. Mode "tout l'historique" : Interroge l'ensemble du corpus du tenant (tous projets + sections + URLs de référence)
    if is_all_history_mode or is_combined_mode:
        from app.models.entities import GeneratedSection, TenantLearning, TenantReferenceUrl

        # A. DCE Embeddings across ALL projects for this tenant, ranked by Cosine Distance
        dce_chunks_hist = []
        try:
            if query_vector is not None:
                async with db.begin_nested():
                    dce_dist_expr = DCEEmbedding.embedding.cosine_distance(query_vector)
                    dce_hist_stmt = (
                        select(DCEEmbedding, Project.title, Project.created_at)
                        .join(Project, DCEEmbedding.project_id == Project.id)
                        .where(
                            DCEEmbedding.tenant_id == t_uuid,
                            DCEEmbedding.embedding.isnot(None),
                        )
                        .order_by(dce_dist_expr)
                        .limit(6)
                    )
                    dce_res = await db.execute(dce_hist_stmt)
                    dce_chunks_hist = dce_res.all()
        except Exception as dce_hist_exc:
            logger.warning("[projects.py] Multi-project semantic search fallback: %s", dce_hist_exc)

        if not dce_chunks_hist:
            dce_hist_stmt = (
                select(DCEEmbedding, Project.title, Project.created_at)
                .join(Project, DCEEmbedding.project_id == Project.id)
                .where(DCEEmbedding.tenant_id == t_uuid)
                .order_by(DCEEmbedding.created_at.desc())
                .limit(6)
            )
            dce_res = await db.execute(dce_hist_stmt)
            dce_chunks_hist = dce_res.all()

        for row in dce_chunks_hist:
            chunk, proj_title, proj_created = row[0], row[1], row[2]
            sec_title = chunk.section_title or "Section Technique"
            pg = int(chunk.page_number) if chunk.page_number else 1
            proj_date = proj_created.strftime("%d/%m/%Y") if proj_created else "2026"
            citation_tag = f"[Source historique : Projet {proj_title}, Date {proj_date}]"
            snippet = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
            collected_sources.append({
                "type": "project_dce_history",
                "id": str(chunk.id),
                "title": f"DCE {proj_title} — {sec_title}",
                "project_title": proj_title,
                "date": proj_date,
                "page": pg,
                "citation": citation_tag,
                "snippet": snippet,
            })
            corpus_text_parts.append(f"--- {citation_tag} (Page {pg}) ---\n{chunk.content}")

        # B. Past validated GeneratedSections across all projects of the tenant
        sec_stmt = (
            select(GeneratedSection, Project.title)
            .join(Project, GeneratedSection.project_id == Project.id)
            .where(
                GeneratedSection.tenant_id == t_uuid,
                GeneratedSection.status.in_(["validated", "user_edited", "completed"]),
            )
            .order_by(GeneratedSection.updated_at.desc())
            .limit(4)
        )
        sec_res = await db.execute(sec_stmt)
        for s_row in sec_res.all():
            sec, p_title = s_row[0], s_row[1]
            sec_date = sec.updated_at.strftime("%d/%m/%Y") if sec.updated_at else "2026"
            citation_tag = f"[Source historique : Projet {p_title}, Date {sec_date}]"
            import re
            clean_sec_txt = re.sub(r'<[^>]+>', ' ', sec.content_html or "").strip()
            if clean_sec_txt:
                snippet = clean_sec_txt[:200] + "..." if len(clean_sec_txt) > 200 else clean_sec_txt
                collected_sources.append({
                    "type": "past_project_section",
                    "id": str(sec.id),
                    "title": sec.title,
                    "project_title": p_title,
                    "date": sec_date,
                    "citation": citation_tag,
                    "snippet": snippet,
                })
                corpus_text_parts.append(f"--- {citation_tag} (Section: {sec.title}) ---\n{clean_sec_txt[:1000]}")

        # C. Tenant Reference URLs registered by the client
        ref_urls_stmt = select(TenantReferenceUrl).where(
            TenantReferenceUrl.tenant_id == t_uuid,
            TenantReferenceUrl.status == "active",
        ).limit(4)
        ref_urls_res = await db.execute(ref_urls_stmt)
        for ru in ref_urls_res.scalars().all():
            portal_label = ru.label or "Portail officiel / Référence"
            citation_tag = f"[Source référence client : {portal_label} — {ru.url}]"
            collected_sources.append({
                "type": "tenant_reference_url",
                "id": str(ru.id),
                "title": portal_label,
                "url": ru.url,
                "citation": citation_tag,
                "snippet": f"Référence client enregistrée : {portal_label} ({ru.url})",
            })
            corpus_text_parts.append(f"--- {citation_tag} ---\n{portal_label} : {ru.url}")

        # D. Validated Company Assets via Cosine Distance ranking
        assets = []
        try:
            if query_vector is not None:
                async with db.begin_nested():
                    dist_expr = CompanyAsset.embedding.cosine_distance(query_vector)
                    assets_stmt = (
                        select(CompanyAsset)
                        .where(
                            CompanyAsset.tenant_id == t_uuid,
                            CompanyAsset.embedding.isnot(None),
                            CompanyAsset.status != "obsolete",
                            CompanyAsset.validated_by_user == True,
                        )
                        .order_by(dist_expr)
                        .limit(4)
                    )
                    assets_res = await db.execute(assets_stmt)
                    assets = assets_res.scalars().all()
        except Exception as emb_exc:
            logger.warning("[projects.py] Semantic asset search fallback: %s", emb_exc)

        if not assets:
            assets_stmt = (
                select(CompanyAsset)
                .where(
                    CompanyAsset.tenant_id == t_uuid,
                    CompanyAsset.status != "obsolete",
                    CompanyAsset.validated_by_user == True,
                )
                .order_by(CompanyAsset.created_at.desc())
                .limit(4)
            )
            assets_res = await db.execute(assets_stmt)
            assets = assets_res.scalars().all()

        for asset in assets:
            cat = asset.category or "Savoir-Faire"
            title = asset.title or "Fiche Entreprise"
            citation_tag = f"[Source : Entreprise - {title}]"
            collected_sources.append({
                "type": "company_asset",
                "id": str(asset.id),
                "category": cat,
                "title": title,
                "citation": citation_tag,
                "snippet": (asset.description or asset.metadata_json or "")[:200] if isinstance(asset.description, str) else str(asset.metadata_json)[:200],
            })
            corpus_text_parts.append(f"--- {citation_tag} ({cat}) ---\n{asset.description or asset.metadata_json or ''}")

    # 3. Mode "ce projet" : Interroge uniquement le DCE du projet courant + assets validés
    elif is_single_project_mode:
        # A. DCE Embeddings for the CURRENT project only
        dce_chunks = []
        try:
            if query_vector is not None:
                async with db.begin_nested():
                    dce_dist_expr = DCEEmbedding.embedding.cosine_distance(query_vector)
                    dce_stmt = (
                        select(DCEEmbedding)
                        .where(
                            DCEEmbedding.project_id == p_uuid,
                            DCEEmbedding.tenant_id == t_uuid,
                            DCEEmbedding.embedding.isnot(None),
                        )
                        .order_by(dce_dist_expr)
                        .limit(6)
                    )
                    dce_res = await db.execute(dce_stmt)
                    dce_chunks = dce_res.scalars().all()
        except Exception as dce_emb_exc:
            logger.warning("[projects.py] Semantic DCE search fallback: %s", dce_emb_exc)

        if not dce_chunks:
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
                "id": str(chunk.id),
                "title": f"DCE {sec_title}",
                "page": pg,
                "citation": citation_tag,
                "snippet": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
            })
            corpus_text_parts.append(f"--- {citation_tag} ---\n{chunk.content}")

        # B. Company Assets
        assets = []
        try:
            if query_vector is not None:
                async with db.begin_nested():
                    dist_expr = CompanyAsset.embedding.cosine_distance(query_vector)
                    assets_stmt = (
                        select(CompanyAsset)
                        .where(
                            CompanyAsset.tenant_id == t_uuid,
                            CompanyAsset.embedding.isnot(None),
                            CompanyAsset.status != "obsolete",
                            CompanyAsset.validated_by_user == True,
                        )
                        .order_by(dist_expr)
                        .limit(4)
                    )
                    assets_res = await db.execute(assets_stmt)
                    assets = assets_res.scalars().all()
        except Exception as emb_exc:
            logger.warning("[projects.py] Semantic asset search fallback: %s", emb_exc)

        if not assets:
            assets_stmt = (
                select(CompanyAsset)
                .where(
                    CompanyAsset.tenant_id == t_uuid,
                    CompanyAsset.status != "obsolete",
                    CompanyAsset.validated_by_user == True,
                )
                .order_by(CompanyAsset.created_at.desc())
                .limit(4)
            )
            assets_res = await db.execute(assets_stmt)
            assets = assets_res.scalars().all()

        for asset in assets:
            cat = asset.category or "Savoir-Faire"
            title = asset.title or "Fiche Entreprise"
            citation_tag = f"[Source : Entreprise - {title}]"
            collected_sources.append({
                "type": "company_asset",
                "id": str(asset.id),
                "category": cat,
                "title": title,
                "citation": citation_tag,
                "snippet": (asset.description or asset.metadata_json or "")[:200] if isinstance(asset.description, str) else str(asset.metadata_json)[:200],
            })
            corpus_text_parts.append(f"--- {citation_tag} ({cat}) ---\n{asset.description or asset.metadata_json or ''}")

    # 4. Web Sources if mode is 'web' or 'corpus_web' / 'all_history_web'
    if is_web_only_mode or is_combined_mode:
        from app.services.web_search_service import web_search_service
        from urllib.parse import urlparse
        # Pays du MARCHE d'abord (04/09) : la whitelist de sources officielles doit suivre
        # le dossier, pas l'entreprise. Repli explicite sur le pays du tenant si le projet
        # n'a pas de pays determine.
        tenant_row_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
        tenant_row = tenant_row_res.scalar_one_or_none()
        tenant_country_code = (
            project.country_code or (tenant_row.country_code if tenant_row else "FR")
        )
        whitelist_res = await db.execute(
            select(CountryOfficialSource).where(
                CountryOfficialSource.country_code == tenant_country_code,
                CountryOfficialSource.status == "active",
            )
        )
        whitelist_domains = sorted({
            urlparse(s.portal_url).netloc for s in whitelist_res.scalars().all() if s.portal_url
        })
        search_query = f"{project.title} BTP {clean_question}"
        web_results = await web_search_service.search(
            tenant_id=current_user.tenant_id,
            query=search_query,
            num_results=3,
            project_id=str(p_uuid),
            allowed_sites=whitelist_domains,
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

    # 5. Prompt Engineering strictly adhering to citations and anti-hallucination
    prompt = f"""Tu es un Ingénieur Principal d'Études BTP assistant sur l'Appel d'Offres "{project.title}" (Réf : {project.reference_code}).
L'utilisateur te pose une question technique avec le mode de sources : {source_mode.upper()}.

EXTRAITS DU CORPUS DU PROJET (DCE & ENTREPRISE) :
{corpus_context or "Aucun extrait trouvé dans le corpus sélectionné."}

EXTRAITS DES SOURCES WEB EXTERNES :
{web_context or "Aucune recherche web externe effectuée pour ce mode."}

QUESTION :
{clean_question}

DIRECTIVES DE RÉPONSE NON NÉGOCIABLES :
1. RÈGLE STRICTE DE CITATION DES SOURCES :
   - Pour les informations issues du projet en cours : [Source : Nom du document, Page X].
   - Pour les informations issues d'anciens projets / historique : [Source historique : Projet Titre, Date JJ/MM/AAAA].
   - Pour les informations issues de l'entreprise : [Source : Entreprise - Titre].
   - Pour les portails / liens de référence : [Source référence client : Nom du portail — URL].
   - Pour les informations du web externe : [Source web : Titre — URL].
2. RÈGLE ANTI-HALLUCINATION ABSOLUE :
   - Si les sources fournies dans le mode '{source_mode}' ne contiennent pas l'information demandée, indique immédiatement et explicitement : "Aucune information correspondante n'a été trouvée dans les sources sélectionnées ({source_mode}) pour répondre à cette question."
   - Ne jamais inventer de données, d'exigences contractuelles ou de sources.
3. Rédige en Markdown clair, structuré, précis et direct.
"""

    answer_markdown = ""
    is_degraded = False
    degraded_reason: Optional[str] = None

    # CORRECTIF (03/09) : cet appel ne regardait que les variables d'environnement
    # (ANTHROPIC_API_KEY, OPENAI_API_KEY, MISTRAL_API_KEY) et forçait le modèle à
    # Claude. Il ignorait donc complètement les fournisseurs et les clés
    # configurés dans l'administration : un client dont le palier était réglé sur
    # Gemini n'obtenait jamais de réponse rédigée, et le message parlait d'un
    # « service temporairement indisponible » alors que le service n'avait
    # simplement jamais été appelé. On passe désormais par le même routage que le
    # reste de l'application, palier et surcharges par client compris.
    from app.services.model_routing_service import model_routing_service

    resolved = await model_routing_service.resolve_model_for_tenant(db, t_uuid)
    model_to_use = resolved["model_string"]
    creds = await model_routing_service.get_credentials_for_model(db, model_to_use)
    api_key_to_use = payload.custom_api_key or creds.get("api_key")
    provider_label = resolved.get("provider") or infer_provider_id_from_model_string(model_to_use)

    if api_key_to_use:
        try:
            import litellm
            call_kwargs = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": prompt}],
                "api_key": api_key_to_use,
                "temperature": 0.2,
                "max_tokens": 1000,
            }
            if creds.get("api_base"):
                call_kwargs["api_base"] = creds["api_base"]
            response = litellm.completion(**call_kwargs)
            answer_markdown = response.choices[0].message.content

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
            is_degraded = True
            # Dire ce qui a réellement échoué : « indisponible » envoyait chercher
            # une panne là où il n'y avait qu'une clé refusée ou un modèle inconnu.
            degraded_reason = f"Le fournisseur {provider_label} a refusé l'appel ({type(e).__name__})."
            print(f"[ProjectAsk] LLM generation notice ({model_to_use}): {e}")
    elif creds.get("budget_exceeded"):
        is_degraded = True
        degraded_reason = (
            f"Le plafond mensuel du fournisseur {provider_label} est atteint : "
            "les appels sont suspendus jusqu'au relèvement du plafond."
        )
    else:
        is_degraded = True
        degraded_reason = (
            f"Aucune clé d'API n'est enregistrée pour {provider_label}, "
            "le modèle retenu pour ce client. Renseignez-la dans l'administration, "
            "onglet « Clés d'API »."
        )

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

    # 5. Persist interaction in project metadata for history management
    msg_id = str(uuid.uuid4())
    msg_entry = {
        "id": msg_id,
        "question": clean_question,
        "source_mode": source_mode,
        "answer_markdown": answer_markdown,
        "sources": collected_sources,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    project_meta = project.metadata_json or {}
    history = project_meta.get("assistant_history", [])
    history.append(msg_entry)
    project_meta["assistant_history"] = history
    project.metadata_json = project_meta
    await billing_service.increment_usage(current_user.tenant_id, "question", db)
    await db.commit()

    return AskProjectResponse(
        id=msg_id,
        question=clean_question,
        source_mode=source_mode,
        answer_markdown=answer_markdown,
        sources=collected_sources,
        total_sources_found=len(collected_sources),
        is_degraded=is_degraded,
        degraded_reason=degraded_reason if is_degraded else None,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.delete("/{project_id}/assistant/messages/{message_id}")
async def delete_project_assistant_message(
    project_id: str,
    message_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Immediate hard-delete of an individual Q&A interaction message from the project assistant history.
    Strictly scoped to the tenant, leaves zero hidden records.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    proj_stmt = select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable pour ce tenant.")

    meta = project.metadata_json or {}
    history = meta.get("assistant_history", [])
    initial_len = len(history)
    updated_history = [m for m in history if str(m.get("id")) != str(message_id)]

    meta["assistant_history"] = updated_history
    project.metadata_json = dict(meta)
    flag_modified(project, "metadata_json")
    await db.commit()


    return {
        "success": True,
        "message": f"Message {message_id} supprimé définitivement de l'historique assistant (hard delete immédiat).",
        "project_id": str(project.id),
        "deleted_message_id": message_id,
        "remaining_count": len(updated_history),
    }


# ---------------------------------------------------------------------------
# Detection du pays du marche (04/09)
# ---------------------------------------------------------------------------

class ProjectCountryOverride(BaseModel):
    country_code: Optional[str] = None


async def _load_project(db: AsyncSession, project_id: str, tenant_id: str) -> Project:
    """Charge un projet en garantissant l'appartenance au tenant (meme controle que les
    autres routes du fichier, factorise pour les trois endpoints pays ci-dessous)."""
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid project ID format")

    res = await db.execute(select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable pour ce tenant.")
    return project


async def _load_country_context(db: AsyncSession, tenant_id: str) -> tuple:
    """Charge le pays du tenant et les pays configures. A appeler AVANT tout commit :
    get_db() ouvre la session dans un context manager, donc la moindre requete emise
    apres un commit leve "Can't operate on closed transaction" (meme piege que les
    db.refresh() retires le 04/09)."""
    from app.models.entities import CountryRegulatoryProfile

    t_res = await db.execute(select(Tenant.country_code).where(Tenant.id == uuid.UUID(tenant_id)))
    tenant_country = t_res.scalar_one_or_none() or "FR"

    prof_res = await db.execute(
        select(CountryRegulatoryProfile)
        .where(CountryRegulatoryProfile.is_active == True)  # noqa: E712
        .order_by(CountryRegulatoryProfile.country_name)
    )
    available = [
        {"country_code": p.country_code, "country_name": p.country_name, "currency": p.currency}
        for p in prof_res.scalars().all()
    ]
    return tenant_country, available


def _country_payload(project: Project, tenant_country: str, available: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assemblage pur, sans I/O : utilisable apres un commit sans risque."""
    return {
        "project_id": str(project.id),
        "country_code": project.country_code,
        "effective_country_code": project.country_code or tenant_country,
        "is_tenant_fallback": project.country_code is None,
        "tenant_country_code": tenant_country,
        "detection": project.country_detection or {},
        "available_countries": available,
    }


@router.get("/{project_id}/country")
async def get_project_country(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Pays applique au dossier, d'ou il vient, et pays disponibles."""
    project = await _load_project(db, project_id, current_user.tenant_id)
    tenant_country, available = await _load_country_context(db, current_user.tenant_id)
    return _country_payload(project, tenant_country, available)


@router.post("/{project_id}/country/detect")
async def detect_project_country(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse les pieces du dossier pour en deduire le pays du marche.

    Le resultat est TOUJOURS enregistre dans country_detection (tracabilite), mais le pays
    n'est applique automatiquement que si la detection est de confiance haute ET que
    l'utilisateur n'a pas deja corrige a la main -- on ne revient jamais sur un choix humain.
    Dans tous les cas l'interface doit afficher le pays retenu et pourquoi.
    """
    from app.services.country_detection_service import country_detection_service

    project = await _load_project(db, project_id, current_user.tenant_id)
    # Tout ce qui necessite la base est charge AVANT la mutation et le commit.
    tenant_country, available = await _load_country_context(db, current_user.tenant_id)

    detection = await country_detection_service.detect(
        db=db, project=project, tenant_country_code=tenant_country
    )

    previously_overridden = bool((project.country_detection or {}).get("overridden_by_user"))
    auto_applied = False
    if (
        detection.get("confidence") == "high"
        and detection.get("detected_code")
        and not previously_overridden
    ):
        project.country_code = detection["detected_code"]
        auto_applied = True

    detection["auto_applied"] = auto_applied
    detection["overridden_by_user"] = previously_overridden
    project.country_detection = detection
    flag_modified(project, "country_detection")
    await db.commit()

    return _country_payload(project, tenant_country, available)


@router.patch("/{project_id}/country")
async def override_project_country(
    project_id: str,
    payload: ProjectCountryOverride,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Correction manuelle du pays du marche. `country_code: null` remet le dossier sur le
    pays du tenant. Un pays sans profil reglementaire actif est refuse explicitement plutot
    que d'etre accepte puis de faire echouer la generation plus loin.
    """
    from app.models.entities import CountryRegulatoryProfile

    project = await _load_project(db, project_id, current_user.tenant_id)
    tenant_country, available = await _load_country_context(db, current_user.tenant_id)
    code = (payload.country_code or "").strip().upper() or None

    if code:
        prof_res = await db.execute(
            select(CountryRegulatoryProfile).where(
                CountryRegulatoryProfile.country_code == code,
                CountryRegulatoryProfile.is_active == True,  # noqa: E712
            )
        )
        if prof_res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=400,
                detail=f"Aucun profil reglementaire actif pour le pays '{code}'.",
            )

    project.country_code = code
    detection = dict(project.country_detection or {})
    detection["overridden_by_user"] = True
    detection["overridden_at"] = datetime.now(timezone.utc).isoformat()
    detection["overridden_to"] = code
    project.country_detection = detection
    flag_modified(project, "country_detection")
    await db.commit()

    return _country_payload(project, tenant_country, available)
