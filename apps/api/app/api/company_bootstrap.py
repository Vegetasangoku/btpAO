"""
Company Profile Bootstrap & Tenant Reference URLs API Router.
Provides endpoints for:
1. Triggering company profile web scanning (POST /api/company/bootstrap)
2. Checking bootstrap status & reviewing extracted suggestions (GET /api/company/bootstrap/{run_id})
3. Human validation / correction of extracted assets (POST /api/company/assets/{asset_id}/validate)
4. Managing client trusted reference URLs (GET/POST/DELETE /api/company/reference-urls)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import CompanyAsset, CompanyBootstrapRun, TenantReferenceUrl
from app.models.schemas import (
    CompanyAssetOut,
    CompanyAssetValidationRequest,
    CompanyBootstrapRunOut,
    CompanyBootstrapTriggerRequest,
    TenantReferenceUrlCreate,
    TenantReferenceUrlOut,
)
from app.services.billing_service import billing_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger("company_bootstrap")

router = APIRouter(prefix="/company", tags=["Company Profile Bootstrap & Reference URLs"])

# Garde-fou de coût : nombre max de requêtes de recherche web (Assistant Q&A "Mon Entreprise")
# autorisées par tenant et par mois. Première version simple et non liée à un plan spécifique --
# facilement déplaçable vers subscription_plans si un palier par plan est nécessaire plus tard.
COMPANY_CHAT_WEB_SEARCH_MONTHLY_CAP = 50


class CompanyAskPayload(BaseModel):
    question: str
    source_mode: str = "corpus"  # "corpus", "corpus_web", "web"


class CompanyAskResponse(BaseModel):
    question: str
    source_mode: str
    answer_markdown: str
    sources: List[Dict[str, Any]]
    total_sources_found: int
    is_degraded: bool = False
    degraded_reason: Optional[str] = None
    timestamp: str


@router.post("/bootstrap", status_code=status.HTTP_202_ACCEPTED)
async def trigger_company_bootstrap(
    payload: CompanyBootstrapTriggerRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually triggers an asynchronous web scan to pre-fill company profile assets.
    Returns a run_id immediately to track progress.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        user_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    if not payload.company_name or not payload.company_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nom de l'entreprise est obligatoire pour lancer le scan.",
        )

    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Create run record
    run = CompanyBootstrapRun(
        id=run_id,
        tenant_id=t_uuid,
        status="pending",
        triggered_by=user_uuid,
        started_at=now,
        sources_found=[],
    )
    db.add(run)
    await db.commit()

    # 2. Dispatch Celery Task (or fallback to direct async execution in test)
    try:
        from app.workers.tasks import bootstrap_company_task
        bootstrap_company_task.delay(
            tenant_id=str(t_uuid),
            company_name=payload.company_name.strip(),
            siret=payload.siret.strip() if payload.siret else None,
            reference_urls=[u.strip() for u in payload.reference_urls if u.strip()],
            triggered_by=str(user_uuid) if user_uuid else None,
            run_id=str(run_id),
        )
    except Exception as celery_exc:
        # Direct fallback execution if Celery broker is offline in local dev
        from app.services.company_bootstrap_service import company_bootstrap_service
        import asyncio
        asyncio.create_task(
            company_bootstrap_service.bootstrap_company_profile(
                tenant_id=str(t_uuid),
                company_name=payload.company_name.strip(),
                siret=payload.siret.strip() if payload.siret else None,
                reference_urls=[u.strip() for u in payload.reference_urls if u.strip()],
                triggered_by=str(user_uuid) if user_uuid else None,
                run_id=str(run_id),
            )
        )

    return {
        "success": True,
        "run_id": str(run_id),
        "status": "pending",
        "message": "Scan de pré-remplissage du profil entreprise lancé avec succès.",
    }


@router.get("/bootstrap/{run_id}", response_model=CompanyBootstrapRunOut)
async def get_company_bootstrap_status(
    run_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns status and extracted suggestions for a bootstrap run.
    Strictly scoped to authenticated tenant.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        r_uuid = uuid.UUID(run_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(CompanyBootstrapRun).where(
        CompanyBootstrapRun.id == r_uuid,
        CompanyBootstrapRun.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable ou accès refusé")

    # Fetch associated extracted assets
    assets_stmt = select(CompanyAsset).where(
        CompanyAsset.tenant_id == t_uuid,
    ).order_by(CompanyAsset.created_at.desc())
    assets_res = await db.execute(assets_stmt)
    all_tenant_assets = assets_res.scalars().all()

    # Filter assets created by this run or matching unvalidated web suggestions
    run_assets = [
        a for a in all_tenant_assets
        if isinstance(a.metadata_json, dict) and a.metadata_json.get("bootstrap_run_id") == str(r_uuid)
    ]

    return CompanyBootstrapRunOut(
        id=str(run.id),
        tenant_id=str(run.tenant_id),
        status=run.status,
        triggered_by=str(run.triggered_by) if run.triggered_by else None,
        started_at=run.started_at,
        completed_at=run.completed_at,
        sources_found=run.sources_found or [],
        error_message=run.error_message,
        created_at=run.created_at,
        extracted_assets=[
            CompanyAssetOut(
                id=str(a.id),
                tenant_id=str(a.tenant_id),
                category=a.category,
                title=a.title,
                description=a.description or "",
                s3_url=a.s3_url,
                source_type=a.source_type or "web_auto_bootstrap",
                collected_at=a.collected_at or a.created_at,
                validated_by_user=bool(a.validated_by_user),
                tags=a.metadata_json.get("tags", []) if isinstance(a.metadata_json, dict) else [],
                metadata_json=a.metadata_json or {},
                created_at=a.created_at,
            )
            for a in run_assets
        ],
    )


@router.post("/assets/{asset_id}/validate", response_model=CompanyAssetOut)
async def validate_company_asset(
    asset_id: str,
    payload: CompanyAssetValidationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates or corrects an extracted suggestion.
    Only when validated_by_user = True can this asset be used in memo generation.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        a_uuid = uuid.UUID(asset_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(CompanyAsset).where(
        CompanyAsset.id == a_uuid,
        CompanyAsset.tenant_id == t_uuid,
    )
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset introuvable ou accès refusé")

    # Update validation status
    asset.validated_by_user = payload.validated

    # Update contents if user modified them
    if payload.title is not None:
        asset.title = payload.title.strip()
    if payload.description is not None:
        asset.description = payload.description.strip()
    if payload.category is not None:
        asset.category = payload.category.strip()

    # Recompute embedding if description was updated
    if payload.description is not None and embedding_service:
        try:
            asset.embedding = embedding_service.generate_embedding(
                f"{asset.title}\n{asset.description}"[:2000]
            )
        except Exception:
            pass

    asset.updated_at = datetime.now(timezone.utc)
    if isinstance(asset.metadata_json, dict):
        asset.metadata_json["validated_at"] = datetime.now(timezone.utc).isoformat()
        asset.metadata_json["validated_by"] = current_user.user_id

    await db.commit()

    return CompanyAssetOut(
        id=str(asset.id),
        tenant_id=str(asset.tenant_id),
        category=asset.category,
        title=asset.title,
        description=asset.description or "",
        s3_url=asset.s3_url,
        source_type=asset.source_type or "web_auto_bootstrap",
        collected_at=asset.collected_at or asset.created_at,
        validated_by_user=bool(asset.validated_by_user),
        tags=asset.metadata_json.get("tags", []) if isinstance(asset.metadata_json, dict) else [],
        metadata_json=asset.metadata_json or {},
        created_at=asset.created_at,
    )


# -----------------------------------------------------------------------------
# Tenant Reference URLs Management
# -----------------------------------------------------------------------------
@router.get("/reference-urls", response_model=List[TenantReferenceUrlOut])
async def list_reference_urls(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all trusted reference URLs configured by the tenant."""
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(TenantReferenceUrl).where(
        TenantReferenceUrl.tenant_id == t_uuid,
    ).order_by(TenantReferenceUrl.added_at.desc())
    res = await db.execute(stmt)
    urls = res.scalars().all()

    return [
        TenantReferenceUrlOut(
            id=str(u.id),
            tenant_id=str(u.tenant_id),
            url=u.url,
            label=u.label,
            added_by=str(u.added_by) if u.added_by else None,
            added_at=u.added_at,
            last_fetched_at=u.last_fetched_at,
            status=u.status,
        )
        for u in urls
    ]


@router.post("/reference-urls", response_model=TenantReferenceUrlOut, status_code=status.HTTP_201_CREATED)
async def add_reference_url(
    payload: TenantReferenceUrlCreate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Adds a new trusted reference URL for the tenant."""
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        user_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL invalide. Veuillez fournir une URL commençant par http:// ou https://.",
        )

    ref_url = TenantReferenceUrl(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        url=url,
        label=payload.label.strip() if payload.label else None,
        added_by=user_uuid,
        added_at=datetime.now(timezone.utc),
        status="active",
    )
    db.add(ref_url)
    await db.commit()

    return TenantReferenceUrlOut(
        id=str(ref_url.id),
        tenant_id=str(ref_url.tenant_id),
        url=ref_url.url,
        label=ref_url.label,
        added_by=str(ref_url.added_by) if ref_url.added_by else None,
        added_at=ref_url.added_at,
        last_fetched_at=ref_url.last_fetched_at,
        status=ref_url.status,
    )


@router.delete("/reference-urls/{url_id}")
async def delete_reference_url(
    url_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a trusted reference URL."""
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(url_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(TenantReferenceUrl).where(
        TenantReferenceUrl.id == u_uuid,
        TenantReferenceUrl.tenant_id == t_uuid,
    )
    res = await db.execute(stmt)
    ref_url = res.scalar_one_or_none()

    if not ref_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL de référence introuvable ou accès refusé")

    await db.delete(ref_url)
    await db.commit()

    return {"success": True, "message": "URL de référence supprimée avec succès."}


@router.post("/reference-urls/{url_id}/refresh")
async def refresh_reference_url(
    url_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Refreshes content from the reference URL and updates its last_fetched_at."""
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(url_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(TenantReferenceUrl).where(
        TenantReferenceUrl.id == u_uuid,
        TenantReferenceUrl.tenant_id == t_uuid,
    )
    res = await db.execute(stmt)
    ref_url = res.scalar_one_or_none()

    if not ref_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL de référence introuvable ou accès refusé")

    from app.services.company_bootstrap_service import company_bootstrap_service
    page_data = await company_bootstrap_service.fetch_page_content(ref_url.url)

    if page_data:
        ref_url.last_fetched_at = datetime.now(timezone.utc)
        ref_url.status = "active"
        await db.commit()
        return {"success": True, "message": f"URL '{ref_url.url}' actualisée avec succès.", "title": page_data["title"]}
    else:
        ref_url.status = "broken"
        await db.commit()
        return {"success": False, "message": f"Impossible de joindre l'URL '{ref_url.url}'.", "status": "broken"}


@router.post("/ask", response_model=CompanyAskResponse)
async def ask_company_assistant(
    payload: CompanyAskPayload,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assistant Q&A sur le savoir-faire de l'entreprise (page "Mon Entreprise"), distinct de
    l'assistant DCE d'un projet (POST /projects/{id}/ask) : interroge le corpus CompanyAsset
    validé du tenant (fiches techniques, moyens, références...) et/ou une recherche web
    STRICTEMENT restreinte aux "Sites de Référence" explicitement configurés par le tenant --
    jamais un fallback vers Internet ouvert. Un garde-fou de quota mensuel protège le coût des
    requêtes de recherche web réellement exécutées. Règle zéro hallucination : indique
    explicitement quand aucune source n'est trouvée au lieu d'inventer une réponse.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant UUID invalide")

    clean_question = payload.question.strip()
    if not clean_question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La question ne peut pas être vide.")

    source_mode = payload.source_mode.strip().lower()
    if source_mode not in ("corpus", "web", "corpus_web"):
        source_mode = "corpus"
    want_corpus = source_mode in ("corpus", "corpus_web")
    want_web = source_mode in ("web", "corpus_web")

    sources: List[Dict[str, Any]] = []
    corpus_text_parts: List[str] = []
    web_text_parts: List[str] = []
    is_degraded = False
    degraded_reason: Optional[str] = None

    # 1. Corpus : recherche vectorielle sur les CompanyAsset validés et non-obsolètes du tenant.
    if want_corpus:
        query_vector = embedding_service.generate_embedding(clean_question[:2000]) if embedding_service else None

        asset_rows = []
        try:
            if query_vector is not None:
                async with db.begin_nested():
                    dist_expr = CompanyAsset.embedding.cosine_distance(query_vector)
                    stmt = (
                        select(CompanyAsset)
                        .where(
                            CompanyAsset.tenant_id == t_uuid,
                            CompanyAsset.embedding.isnot(None),
                            CompanyAsset.validated_by_user.is_(True),
                            CompanyAsset.obsolete_at.is_(None),
                        )
                        .order_by(dist_expr)
                        .limit(6)
                    )
                    res = await db.execute(stmt)
                    asset_rows = res.scalars().all()
        except Exception as vec_exc:
            logger.warning("[company_bootstrap.py] CompanyAsset semantic search fallback: %s", vec_exc)
            asset_rows = []

        if not asset_rows:
            stmt = (
                select(CompanyAsset)
                .where(
                    CompanyAsset.tenant_id == t_uuid,
                    CompanyAsset.validated_by_user.is_(True),
                    CompanyAsset.obsolete_at.is_(None),
                )
                .order_by(CompanyAsset.updated_at.desc())
                .limit(6)
            )
            res = await db.execute(stmt)
            asset_rows = res.scalars().all()

        for a in asset_rows:
            snippet_src = a.description or a.title
            snippet = snippet_src[:220] + "..." if len(snippet_src) > 220 else snippet_src
            citation_tag = f"[Source : {a.category} — {a.title}]"
            sources.append({
                "type": "company_asset",
                "id": str(a.id),
                "title": a.title,
                "category": a.category,
                "citation": citation_tag,
                "snippet": snippet,
            })
            corpus_text_parts.append(f"--- {citation_tag} ---\n{a.description or a.title}")

    # 2. Web : STRICTEMENT restreint aux tenant_reference_urls actives configurées par le
    #    tenant. Aucune config = aucune recherche web (jamais un fallback vers Internet ouvert),
    #    et un garde-fou de quota mensuel protège le coût des requêtes réellement exécutées.
    if want_web:
        ref_stmt = select(TenantReferenceUrl).where(
            TenantReferenceUrl.tenant_id == t_uuid,
            TenantReferenceUrl.status == "active",
        )
        ref_res = await db.execute(ref_stmt)
        ref_urls = ref_res.scalars().all()
        allowed_domains = sorted({urlparse(u.url).netloc for u in ref_urls if u.url and urlparse(u.url).netloc})

        if not allowed_domains:
            is_degraded = True
            degraded_reason = (
                "Aucun site de référence n'est configuré. Ajoutez des sites de confiance dans "
                "l'onglet « Sites de Référence » de Mon Entreprise pour activer la recherche web."
            )
        else:
            usage = await billing_service.get_or_create_usage(t_uuid, db)
            if (usage.web_searches_count or 0) >= COMPANY_CHAT_WEB_SEARCH_MONTHLY_CAP:
                is_degraded = True
                degraded_reason = (
                    f"Quota mensuel de recherche web atteint ({COMPANY_CHAT_WEB_SEARCH_MONTHLY_CAP} "
                    "requêtes/mois) pour garder les coûts sous contrôle. Réessayez le mois prochain "
                    "ou utilisez le mode Corpus."
                )
            else:
                from app.services.web_search_service import web_search_service
                try:
                    web_results = await web_search_service.search(
                        tenant_id=str(t_uuid),
                        query=clean_question,
                        num_results=4,
                        allowed_sites=allowed_domains,
                    )
                except Exception as web_exc:
                    logger.warning("[company_bootstrap.py] Web search failed: %s", web_exc)
                    web_results = []

                usage.web_searches_count = (usage.web_searches_count or 0) + 1
                usage.updated_at = datetime.now(timezone.utc)
                await db.commit()

                if not web_results and not corpus_text_parts:
                    is_degraded = True
                    degraded_reason = "Aucun résultat trouvé sur les sites de référence configurés pour cette question."

                for r in web_results:
                    citation_tag = f"[Source web : {r.title} — {r.url}]"
                    sources.append({
                        "type": "web",
                        "title": r.title,
                        "url": r.url,
                        "citation": citation_tag,
                        "snippet": r.snippet,
                    })
                    web_text_parts.append(f"--- {citation_tag} ---\n{r.snippet}")

    # 3. Synthèse : jamais d'invention hors-corpus. Sans aucune source, réponse honnête directe
    #    sans appel LLM ; avec des sources, un LLM les synthétise en citant strictement les tags.
    if not corpus_text_parts and not web_text_parts:
        if want_corpus and want_web:
            scope_desc = "votre corpus entreprise ou vos sites de référence configurés"
        elif want_web:
            scope_desc = "vos sites de référence configurés"
        else:
            scope_desc = "votre corpus entreprise"
        answer = (
            f"Je n'ai trouvé aucune information sur ce sujet dans {scope_desc}. "
            "Ajoutez un document dans « Mon Entreprise › Savoir-Faire » ou reformulez votre question."
        )
        is_degraded = True
        if not degraded_reason:
            degraded_reason = "Aucune source correspondante trouvée dans le mode sélectionné."
    else:
        try:
            import asyncio
            import litellm
            from app.services.model_routing_service import model_routing_service

            resolved_model_info = await model_routing_service.resolve_model_for_tenant(db=db, tenant_id=t_uuid)
            selected_model_string = resolved_model_info["model_string"]
            credentials = await model_routing_service.get_credentials_for_model(db=db, model_string=selected_model_string)

            context_block = "\n\n".join(corpus_text_parts + web_text_parts)
            kwargs: Dict[str, Any] = {
                "model": selected_model_string,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es l'assistant documentaire de l'entreprise BTP sur btpAO. Réponds "
                            "UNIQUEMENT à partir des extraits de sources fournis ci-dessous. Si "
                            "l'information n'y figure pas explicitement, dis clairement que tu ne "
                            "l'as pas trouvée -- n'invente jamais. Cite les sources par leur tag "
                            "[Source : ...] entre crochets à la fin des phrases concernées."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question : {clean_question}\n\nSources disponibles :\n{context_block}",
                    },
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            }
            if credentials.get("api_key"):
                kwargs["api_key"] = credentials["api_key"]
            if credentials.get("api_base"):
                kwargs["api_base"] = credentials["api_base"]

            completion = await asyncio.to_thread(litellm.completion, **kwargs)
            answer = completion.choices[0].message.content or ""
        except Exception as llm_exc:
            logger.warning("[company_bootstrap.py] LLM synthesis failed: %s", llm_exc)
            answer = (
                "Sources trouvées mais la synthèse automatique a échoué techniquement. "
                "Voici les extraits pertinents :\n\n"
                + "\n\n".join((corpus_text_parts + web_text_parts)[:3])
            )
            is_degraded = True
            degraded_reason = degraded_reason or "Échec de la synthèse LLM -- extraits bruts affichés."

    return CompanyAskResponse(
        question=clean_question,
        source_mode=source_mode,
        answer_markdown=answer,
        sources=sources,
        total_sources_found=len(sources),
        is_degraded=is_degraded,
        degraded_reason=degraded_reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

