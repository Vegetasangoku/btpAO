#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 3 — addresses two more explicit user requirements:

1. "pourquoi la question sur le corpus est la elle devrait etre sous mon entreprise" --
   the corpus Q&A chat must live under "Mon Entreprise", not (only) the project editor.
   Adds a genuinely tenant-scoped POST /api/company/ask endpoint (searches CompanyAsset,
   NOT any single project's DCE -- reusing the project-scoped /projects/{id}/ask here would
   have silently mixed in one arbitrary project's DCE documents, which is wrong for a
   company-wide assistant) and mounts the existing DCEChatSidebar (generalized with a new
   `mode` prop, default 'project' so the editor's existing usage is byte-for-byte unchanged)
   on the "Mon Entreprise" page via a new "Assistant Q&A" button, styled with this page's own
   amber/slate light+dark charte instead of the editor's dark-only sky-blue button.

2. "jespere que recherche web ne concerne que les sites renseigne et ya bien des garde fou
   que ca me coute pas une blinde en token" -- web search from this new company assistant is
   STRICTLY restricted to the tenant's own configured Sites de Reference
   (tenant_reference_urls, already editable in the "Sites de Reference" tab): zero URLs
   configured means zero web search (never a silent fallback to the open internet), a
   `site:` filter plus a hard post-filter enforce the allowlist even if a provider ignores
   `site:`, and a real persistent monthly quota (COMPANY_CHAT_WEB_SEARCH_MONTHLY_CAP,
   tracked via a new tenant_usage_counters.web_searches_count column reusing the existing
   billing_service counter machinery) caps actual Serper/Brave spend. The 3 pre-existing
   web_search_service.search() call sites (project assistant, section generation, company
   bootstrap scan) are untouched -- they simply don't pass allowed_sites, so they keep their
   current unrestricted behavior exactly as before (zero regression risk).

Exact-match-count-of-1 verified before writing; aborts per-file with zero writes on mismatch.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected 1). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_batch3_company_chat_websearch.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
ENTITIES_PY = f"{REPO_ROOT}/apps/api/app/models/entities.py"
BILLING_SVC_PY = f"{REPO_ROOT}/apps/api/app/services/billing_service.py"
WEB_SEARCH_PY = f"{REPO_ROOT}/apps/api/app/services/web_search_service.py"
COMPANY_BOOTSTRAP_PY = f"{REPO_ROOT}/apps/api/app/api/company_bootstrap.py"
API_TS = f"{REPO_ROOT}/apps/web/src/lib/api.ts"
CHAT_SIDEBAR_TSX = f"{REPO_ROOT}/apps/web/src/components/chat/dce-chat-sidebar.tsx"
COMPANY_PAGE_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/company/page.tsx"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. entities.py — new counter column
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(ENTITIES_PY, [
    (
        "add web_searches_count column to TenantUsageCounter",
        '''class TenantUsageCounter(Base):
    __tablename__ = "tenant_usage_counters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    dossiers_generated = Column(Integer, default=0, nullable=False)
    sections_generated = Column(Integer, default=0, nullable=False)
    exports_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)''',
        '''class TenantUsageCounter(Base):
    __tablename__ = "tenant_usage_counters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    dossiers_generated = Column(Integer, default=0, nullable=False)
    sections_generated = Column(Integer, default=0, nullable=False)
    exports_count = Column(Integer, default=0, nullable=False)
    web_searches_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. billing_service.py — initialize the new column on period creation
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(BILLING_SVC_PY, [
    (
        "init web_searches_count=0 in get_or_create_usage",
        '''            usage = TenantUsageCounter(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                period_start=start,
                period_end=end,
                dossiers_generated=0,
                sections_generated=0,
                exports_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )''',
        '''            usage = TenantUsageCounter(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                period_start=start,
                period_end=end,
                dossiers_generated=0,
                sections_generated=0,
                exports_count=0,
                web_searches_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. web_search_service.py — allowed_sites restriction (backward-compatible: None = unrestricted)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(WEB_SEARCH_PY, [
    (
        "search(): add allowed_sites param + site: filter + post-filter",
        '''    async def search(
        self,
        tenant_id: str,
        query: str,
        num_results: int = 4,
        project_id: Optional[str] = None,
        prefer_provider: Optional[str] = None,
    ) -> List[WebSearchResult]:
        """
        Executes a targeted web search strictly scoped to the tenant's request.
        Supports automatic provider failover (Brave Search <-> Serper).
        Adheres to GDPR data minimization for company and public procurement lookups.
        """
        logger.info(
            f"[WebSearch] Tenant {tenant_id} | Project {project_id} | Query: '{query}' | "
            f"Provider Config: {self.provider} (prefer: {prefer_provider})"
        )

        is_test_env = settings.APP_ENV in ("test", "testing")
        if is_test_env:
            return self._generate_mock_results(query, num_results)

        # Provider determination
        active_provider = prefer_provider or self.provider

        # 1. Try Brave Search if requested/configured
        if active_provider == "brave" or (active_provider == "auto" and self.brave_api_key):
            brave_res = await self._search_brave(query, num_results)
            if brave_res:
                return brave_res
            logger.info("[WebSearch] Brave search returned 0 results or failed, attempting Serper fallback.")

        # 2. Try Serper (Google Search API)
        if self.serper_api_key:
            serper_res = await self._search_serper(query, num_results)
            if serper_res:
                return serper_res

        # 3. If primary was Serper and failed, try Brave as fallback
        if self.brave_api_key and active_provider != "brave":
            brave_res = await self._search_brave(query, num_results)
            if brave_res:
                return brave_res

        logger.warning(
            f"[WebSearch] No active search provider API keys configured or queries failed. "
            f"Returning 0 results to prevent fake citations."
        )
        return []''',
        '''    async def search(
        self,
        tenant_id: str,
        query: str,
        num_results: int = 4,
        project_id: Optional[str] = None,
        prefer_provider: Optional[str] = None,
        allowed_sites: Optional[List[str]] = None,
    ) -> List[WebSearchResult]:
        """
        Executes a targeted web search strictly scoped to the tenant's request.
        Supports automatic provider failover (Brave Search <-> Serper).
        Adheres to GDPR data minimization for company and public procurement lookups.

        allowed_sites: when provided (non-empty), the search is STRICTLY restricted to these
        domains -- via a `site:` filter added to the provider query AND a hard post-filter on
        returned URLs (defense in depth: a provider ignoring/mishandling `site:` must never
        leak an off-allowlist result to the caller). An explicit empty list means "tenant has
        configured zero reference sites" and short-circuits to zero results without ever
        calling a provider -- this must never be mistaken for "unrestricted". Passing None
        (the default) preserves the original unrestricted behavior for existing callers
        (project DCE assistant, section generation, company bootstrap scan).
        """
        logger.info(
            f"[WebSearch] Tenant {tenant_id} | Project {project_id} | Query: '{query}' | "
            f"Provider Config: {self.provider} (prefer: {prefer_provider}) | "
            f"Allowed sites: {allowed_sites if allowed_sites is not None else 'unrestricted'}"
        )

        if allowed_sites is not None and len(allowed_sites) == 0:
            logger.info("[WebSearch] allowed_sites explicitly empty -- skipping search entirely (no provider call).")
            return []

        is_test_env = settings.APP_ENV in ("test", "testing")
        if is_test_env:
            return self._filter_by_allowed_sites(self._generate_mock_results(query, num_results), allowed_sites)

        effective_query = query
        if allowed_sites:
            site_filter = " OR ".join(f"site:{d}" for d in allowed_sites)
            effective_query = f"{query} ({site_filter})"

        # Provider determination
        active_provider = prefer_provider or self.provider

        # 1. Try Brave Search if requested/configured
        if active_provider == "brave" or (active_provider == "auto" and self.brave_api_key):
            brave_res = await self._search_brave(effective_query, num_results)
            if brave_res:
                return self._filter_by_allowed_sites(brave_res, allowed_sites)
            logger.info("[WebSearch] Brave search returned 0 results or failed, attempting Serper fallback.")

        # 2. Try Serper (Google Search API)
        if self.serper_api_key:
            serper_res = await self._search_serper(effective_query, num_results)
            if serper_res:
                return self._filter_by_allowed_sites(serper_res, allowed_sites)

        # 3. If primary was Serper and failed, try Brave as fallback
        if self.brave_api_key and active_provider != "brave":
            brave_res = await self._search_brave(effective_query, num_results)
            if brave_res:
                return self._filter_by_allowed_sites(brave_res, allowed_sites)

        logger.warning(
            f"[WebSearch] No active search provider API keys configured or queries failed. "
            f"Returning 0 results to prevent fake citations."
        )
        return []

    @staticmethod
    def _filter_by_allowed_sites(
        results: List[WebSearchResult], allowed_sites: Optional[List[str]]
    ) -> List[WebSearchResult]:
        """Defense-in-depth post-filter: drops any result whose URL domain isn't in
        allowed_sites, in case a provider ignored the `site:` filter. No-op (returns results
        unchanged) when allowed_sites is None, i.e. unrestricted mode."""
        if not allowed_sites:
            return results
        from urllib.parse import urlparse
        allowed_set = set(allowed_sites)
        kept = []
        for r in results:
            domain = urlparse(r.url).netloc
            if any(domain == d or domain.endswith(f".{d}") for d in allowed_set):
                kept.append(r)
        return kept''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 4. company_bootstrap.py — new POST /company/ask endpoint
# ─────────────────────────────────────────────────────────────────────────
COMPANY_ASK_ENDPOINT = '''


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
            corpus_text_parts.append(f"--- {citation_tag} ---\\n{a.description or a.title}")

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
                    web_text_parts.append(f"--- {citation_tag} ---\\n{r.snippet}")

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

            context_block = "\\n\\n".join(corpus_text_parts + web_text_parts)
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
                        "content": f"Question : {clean_question}\\n\\nSources disponibles :\\n{context_block}",
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
                "Voici les extraits pertinents :\\n\\n"
                + "\\n\\n".join((corpus_text_parts + web_text_parts)[:3])
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
'''

results.append(apply_patch(COMPANY_BOOTSTRAP_PY, [
    (
        "imports + payload/response schemas + quota constant",
        '''import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
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
from app.services.embedding_service import embedding_service

router = APIRouter(prefix="/company", tags=["Company Profile Bootstrap & Reference URLs"])''',
        '''import logging
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
    timestamp: str''',
    ),
    (
        "append POST /company/ask endpoint at end of file",
        '''    if page_data:
        ref_url.last_fetched_at = datetime.now(timezone.utc)
        ref_url.status = "active"
        await db.commit()
        return {"success": True, "message": f"URL '{ref_url.url}' actualisée avec succès.", "title": page_data["title"]}
    else:
        ref_url.status = "broken"
        await db.commit()
        return {"success": False, "message": f"Impossible de joindre l'URL '{ref_url.url}'.", "status": "broken"}''',
        '''    if page_data:
        ref_url.last_fetched_at = datetime.now(timezone.utc)
        ref_url.status = "active"
        await db.commit()
        return {"success": True, "message": f"URL '{ref_url.url}' actualisée avec succès.", "title": page_data["title"]}
    else:
        ref_url.status = "broken"
        await db.commit()
        return {"success": False, "message": f"Impossible de joindre l'URL '{ref_url.url}'.", "status": "broken"}'''
        + COMPANY_ASK_ENDPOINT,
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 5. api.ts — askCompany()
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(API_TS, [
    (
        "add askCompany after askProject",
        '''    }>(`/projects/${projectId}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, source_mode: sourceMode }),
    }),''',
        '''    }>(`/projects/${projectId}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, source_mode: sourceMode }),
    }),

  // Company-wide Q&A Assistant ("Mon Entreprise") -- searches CompanyAsset knowledge +
  // optionally web search strictly restricted to configured Sites de Référence. Distinct
  // endpoint from askProject: never scoped to (or mixed in with) any single project's DCE.
  askCompany: (question: string, sourceMode: 'corpus' | 'corpus_web' | 'web' = 'corpus') =>
    fetcher<{
      question: string;
      source_mode: 'corpus' | 'corpus_web' | 'web';
      answer_markdown: string;
      sources: Array<{
        type: string;
        title?: string;
        category?: string;
        url?: string;
        citation: string;
        snippet: string;
      }>;
      total_sources_found: number;
      is_degraded?: boolean;
      degraded_reason?: string;
      timestamp: string;
    }>('/company/ask', {
      method: 'POST',
      body: JSON.stringify({ question, source_mode: sourceMode }),
    }),''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 6. dce-chat-sidebar.tsx — generalize with an optional mode prop ('project' default,
#    byte-identical behavior to before; 'company' for the new Mon Entreprise usage).
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(CHAT_SIDEBAR_TSX, [
    (
        "props interface + function signature: add mode",
        '''interface DCEChatSidebarProps {
  projectId: string;
  projectTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

export function DCEChatSidebar({ projectId, projectTitle, isOpen, onClose }: DCEChatSidebarProps) {''',
        '''interface DCEChatSidebarProps {
  projectId?: string;
  projectTitle?: string;
  isOpen: boolean;
  onClose: () => void;
  // 'project' (défaut) interroge le DCE + corpus du projet en cours (nécessite projectId).
  // 'company' interroge le savoir-faire entreprise (Mon Entreprise), sans projet particulier.
  mode?: 'project' | 'company';
}

export function DCEChatSidebar({ projectId, projectTitle, isOpen, onClose, mode = 'project' }: DCEChatSidebarProps) {''',
    ),
    (
        "welcome message + initial source, mode-aware",
        '''    {
      id: 'm-1',
      sender: 'assistant',
      text: `Bonjour ! Je suis votre **Assistant Technique BTP** pour le projet **${projectTitle || 'en cours'}**.\\n\\nPosez une question technique et sélectionnez votre source :\\n- **Corpus** : Pièces du DCE et base de savoir-faire entreprise\\n- **Corpus + Web** : Synthèse enrichie avec veille normative externe\\n- **Web** : Recherche externe temps réel (DTU, normes, données marché)`,
      source_mode: 'corpus',
      sources: [
        { title: 'Pièces de Marché DCE', page: 1, citation: '[Source : DCE]', snippet: 'CCTP, RC, DPGF et savoir-faire entreprise indexés pour votre projet' },
      ],
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);''',
        '''    {
      id: 'm-1',
      sender: 'assistant',
      text: mode === 'company'
        ? `Bonjour ! Je suis votre **Assistant Savoir-Faire Entreprise**.\\n\\nPosez une question sur vos fiches techniques, moyens, références ou certifications, et sélectionnez votre source :\\n- **Corpus** : Documents et savoir-faire de votre entreprise (onglet Savoir-Faire)\\n- **Corpus + Web** : Corpus enrichi de vos sites de référence configurés\\n- **Web** : Recherche limitée strictement à vos sites de référence configurés (onglet Sites de Référence)`
        : `Bonjour ! Je suis votre **Assistant Technique BTP** pour le projet **${projectTitle || 'en cours'}**.\\n\\nPosez une question technique et sélectionnez votre source :\\n- **Corpus** : Pièces du DCE et base de savoir-faire entreprise\\n- **Corpus + Web** : Synthèse enrichie avec veille normative externe\\n- **Web** : Recherche externe temps réel (DTU, normes, données marché)`,
      source_mode: 'corpus',
      sources: mode === 'company'
        ? [{ title: 'Savoir-Faire Entreprise', citation: '[Source : Mon Entreprise]', snippet: 'Fiches techniques, moyens matériels et références indexés pour votre entreprise' }]
        : [{ title: 'Pièces de Marché DCE', page: 1, citation: '[Source : DCE]', snippet: 'CCTP, RC, DPGF et savoir-faire entreprise indexés pour votre projet' }],
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);''',
    ),
    (
        "suggested prompts, mode-aware",
        '''  const SUGGESTED_PROMPTS = [
    'Quelles sont les pénalités de retard et le délai d\\'exécution ?',
    'Quelles sont les exigences béton bas-carbone (RE2020) ?',
    'Quels sont les critères de notation et pondérations du RC ?',
    'Quelles normes DTU s\\'appliquent au gros œuvre ?',
  ];''',
        '''  const SUGGESTED_PROMPTS = mode === 'company'
    ? [
        'Quelles sont nos certifications et qualifications professionnelles ?',
        'Quels engins et matériels avons-nous dans notre parc ?',
        'Quelles sont nos références de chantiers similaires ?',
        'Quelle est notre politique QSE / RSE ?',
      ]
    : [
        'Quelles sont les pénalités de retard et le délai d\\'exécution ?',
        'Quelles sont les exigences béton bas-carbone (RE2020) ?',
        'Quels sont les critères de notation et pondérations du RC ?',
        'Quelles normes DTU s\\'appliquent au gros œuvre ?',
      ];''',
    ),
    (
        "handleSendMessage: route to askCompany or askProject",
        '''    try {
      const res = await api.askProject(projectId, q, sourceMode);''',
        '''    try {
      const res = mode === 'company'
        ? await api.askCompany(q, sourceMode)
        : await api.askProject(projectId as string, q, sourceMode);''',
    ),
    (
        "header title/subtitle, mode-aware",
        '''              <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                <span>Assistant Q&A DCE & Normes</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </h3>
              <p className="text-[10px] text-slate-400 truncate max-w-[260px]">
                {projectTitle || 'Projet en cours'}
              </p>''',
        '''              <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                <span>{mode === 'company' ? 'Assistant Q&A Savoir-Faire Entreprise' : 'Assistant Q&A DCE & Normes'}</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </h3>
              <p className="text-[10px] text-slate-400 truncate max-w-[260px]">
                {mode === 'company' ? 'Mon Entreprise' : (projectTitle || 'Projet en cours')}
              </p>''',
    ),
    (
        "source selector label, mode-aware",
        '''              {sourceMode === 'corpus' && 'Documents Projet & Entreprise'}
              {sourceMode === 'corpus_web' && 'Corpus + Recherche Web'}
              {sourceMode === 'web' && 'Recherche Web Externe Seule'}''',
        '''              {sourceMode === 'corpus' && (mode === 'company' ? 'Documents Entreprise' : 'Documents Projet & Entreprise')}
              {sourceMode === 'corpus_web' && 'Corpus + Recherche Web'}
              {sourceMode === 'web' && (mode === 'company' ? 'Sites de Référence Configurés Uniquement' : 'Recherche Web Externe Seule')}''',
    ),
    (
        "input placeholder, mode-aware",
        '''            placeholder={`Poser une question sur le projet (${sourceMode})...`}''',
        '''            placeholder={mode === 'company' ? `Poser une question sur votre entreprise (${sourceMode})...` : `Poser une question sur le projet (${sourceMode})...`}''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 7. company/page.tsx — mount the chat (button styled with THIS page's amber/slate charte)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(COMPANY_PAGE_TSX, [
    (
        "imports: add MessageSquare + DCEChatSidebar",
        '''import {
  Building2,
  Users,
  Globe,
  Upload,
  Trash2,
  Plus,
  Mail,
  ExternalLink,
  Loader2,
  CheckCircle2,
  Copy,
} from 'lucide-react';
import { api } from '@/lib/api';
import { CompanyAsset, TeamMember, TeamInvitation, TeamRole } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

export default function CompanyUnifiedPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'knowledge' | 'team' | 'web'>('knowledge');''',
        '''import {
  Building2,
  Users,
  Globe,
  Upload,
  Trash2,
  Plus,
  Mail,
  ExternalLink,
  Loader2,
  CheckCircle2,
  Copy,
  MessageSquare,
} from 'lucide-react';
import { api } from '@/lib/api';
import { CompanyAsset, TeamMember, TeamInvitation, TeamRole } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';
import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';

export default function CompanyUnifiedPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'knowledge' | 'team' | 'web'>('knowledge');
  const [chatOpen, setChatOpen] = useState(false);''',
    ),
    (
        "header: add Assistant Q&A trigger button next to the title block",
        '''        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              {t('company.badge')}
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white font-heading">
            {t('company.title')}
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            {t('company.desc')}
          </p>
        </div>

        {/* 3 Sub-Tabs Header */}''',
        '''        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                {t('company.badge')}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white font-heading">
              {t('company.title')}
            </h1>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('company.desc')}
            </p>
          </div>

          <button
            onClick={() => setChatOpen(true)}
            className="shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold font-heading border bg-amber-500/15 border-amber-500 text-slate-900 dark:text-white hover:bg-amber-500/25 transition-all shadow-subtle"
          >
            <MessageSquare className="w-4 h-4 text-amber-500" />
            <span>Assistant Q&A</span>
          </button>
        </div>

        {/* 3 Sub-Tabs Header */}''',
    ),
    (
        "mount DCEChatSidebar in company mode at the end of the page",
        '''    </div>
  );
}''',
        '''
      <DCEChatSidebar
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        mode="company"
      />
    </div>
  );
}''',
    ),
]))

if not all(results):
    print("\\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\\nALL BATCH-3 PATCHES APPLIED SUCCESSFULLY.")
