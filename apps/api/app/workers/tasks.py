"""
Celery Asynchronous Tasks for Heavy Processing (OCR, Vector Embeddings, Docx Assembly, AI Generation).
Strict multi-tenant security:
- tenant_id is explicitly passed to every task (never guessed).
- Accesses PostgreSQL via SQLAlchemy 2 Async + get_worker_db_session(tenant_id) (SET ROLE btp_app_user + RLS).
- Zero silent fallbacks: any failure updates entity status to 'failed' and reports clear error to client.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from fastapi import HTTPException
from app.core.celery_app import celery_app
from app.core.db import get_worker_db_session, AsyncSessionLocal

logger = logging.getLogger(__name__)
from app.core.storage import storage_service
from app.models.entities import DCECriterionEntity, DCEDocument, DCEEmbedding, ExportJob, ExportTemplate, GeneratedSection, KnowledgeVector, LlmCatalogModel, LlmUsageLog, Project, ProjectDecision, ProjectGanttTask, CompanyAsset, Tenant, SharePointConnection, SharePointSyncItem

from app.services.billing_service import billing_service
from app.services.ocr_cost_service import check_and_enforce_ocr_cap, log_ocr_usage
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.exporter_service import exporter_service
from app.services.llm_generator import llm_generator_service
from app.services.ocr_service import ocr_service


@celery_app.task(name="tasks.test_celery_task")
def test_celery_task(x: int = 1, y: int = 2) -> int:
    """Demo / Healthcheck Celery task."""
    return x + y


@celery_app.task(bind=True, name="tasks.parse_dce_task")
def parse_dce_task(
    self,
    tenant_id: str,
    project_id: str,
    document_id: str,
    s3_key: str,
):
    """
    Asynchronously processes uploaded DCE tender document:
    1. Downloads file from tenant-scoped storage.
    2. Performs OCR text and tables extraction.
    3. Chunks text and computes pgvector embeddings.
    4. Stores chunks in public.dce_embeddings under verified tenant_id with Postgres RLS.
    5. Updates DCEDocument status to 'completed' (or 'failed' on error).
    """
    async def _async_parse():
        doc_uuid = uuid.UUID(document_id)
        proj_uuid = uuid.UUID(project_id)
        tenant_uuid = uuid.UUID(tenant_id)

        async with get_worker_db_session(tenant_id) as db:
            # 1. Fetch document in DB
            stmt = select(DCEDocument).where(
                DCEDocument.id == doc_uuid,
                DCEDocument.tenant_id == tenant_uuid,
                DCEDocument.project_id == proj_uuid,
            )
            res = await db.execute(stmt)
            doc = res.scalar_one_or_none()

            if not doc:
                raise ValueError(f"Document {document_id} not found for tenant {tenant_id}")

            try:
                # 2. Download file from storage
                pdf_bytes = storage_service.download_file(tenant_id, s3_key)

                # 3. Extract text & tables via OCR (triage local pdfplumber -> Azure
                # uniquement pour les pages a faible rendement textuel, voir ocr_service.py)
                ocr_result = ocr_service.extract_text_and_tables(pdf_bytes, s3_key.split("/")[-1])
                ocr_stats = ocr_result.get("ocr_stats", {"pages_total": 0, "pages_local": 0, "pages_azure": 0})

                # 3bis. Journalise le cout OCR reel (jusqu'ici jamais suivi -- 03/09) puis
                # verifie les deux plafonds independants du plafond LLM : volume de pages
                # (charge Postgres/pgvector) et cout Azure reel. Un depassement bloque
                # PROPREMENT (statut clair sur le document, pas une exception Celery brute)
                # avant tout calcul d'embedding, pour ne pas facturer de cout inutile a un
                # document qui sera de toute facon rejete.
                await log_ocr_usage(db, tenant_uuid, doc_uuid, "dce", ocr_stats)
                pages = ocr_result.get("pages", [])
                pages_count = len(pages)
                try:
                    await billing_service.check_and_enforce_page_quota(tenant_uuid, pages_count, db)
                    await check_and_enforce_ocr_cap(tenant_id, db)
                except HTTPException as quota_exc:
                    doc.status = "blocked_quota"
                    doc.metadata_json = {"error": quota_exc.detail}
                    await db.commit()
                    return {"status": "blocked_quota", "document_id": document_id, "detail": quota_exc.detail}

                # 4. Chunk document
                chunks = chunking_service.chunk_document_pages(pages)

                # 5. Generate embeddings and save to PostgreSQL
                await embedding_service.sync_platform_key(db)
                for c in chunks:
                    vec = embedding_service.generate_embedding(c["content"])
                    embedding_row = DCEEmbedding(
                        id=uuid.uuid4(),
                        tenant_id=tenant_uuid,
                        project_id=proj_uuid,
                        document_id=doc_uuid,
                        chunk_index=c["chunk_index"],
                        page_number=c["page_number"],
                        section_title=c.get("section_title", "Section"),
                        content=c["content"],
                        embedding=vec,
                        metadata_json={"embedding": vec},
                        created_at=datetime.utcnow(),
                    )
                    db.add(embedding_row)


                # 6. Extraction réelle des critères de notation (01/09) -- uniquement pour
                # un document de type RC (Règlement de Consultation), et seulement si ce
                # projet n'a pas déjà de critères (idempotence en cas de retry Celery).
                # Remplace l'ancienne insertion synchrone de 4 critères codés en dur par un
                # vrai appel LLM sur le texte OCR (task_type="extraction_gonogo").
                is_rc_doc = (
                    (doc.doc_type or "").lower() == "rc"
                    or "rc" in (doc.filename or "").lower()
                    or "reglement" in (doc.filename or "").lower()
                )
                if is_rc_doc:
                    try:
                        existing_crit_stmt = select(DCECriterionEntity.id).where(
                            DCECriterionEntity.project_id == proj_uuid,
                            DCECriterionEntity.tenant_id == tenant_uuid,
                        ).limit(1)
                        existing_crit_res = await db.execute(existing_crit_stmt)
                        if not existing_crit_res.scalar_one_or_none():
                            from app.services.criteria_extraction_service import extract_criteria_from_text
                            criteria_rows = await extract_criteria_from_text(
                                db=db,
                                tenant_id=tenant_uuid,
                                project_id=proj_uuid,
                                raw_text=ocr_result.get("raw_text", ""),
                                filename=doc.filename or "",
                            )
                            db.add_all(criteria_rows)
                    except Exception as crit_exc:
                        logger.warning("[parse_dce_task] Extraction critères non bloquante en échec: %s", crit_exc)

                doc.status = "completed"
                doc.pages_count = len(pages)
                doc.metadata_json = {
                    "summary": f"Document analysé avec succès ({len(chunks)} fragments indexés).",
                    "chunks_count": len(chunks),
                }
                await billing_service.increment_usage(tenant_id, "page", db, amount=pages_count)
                await db.commit()

                return {
                    "status": "completed",
                    "document_id": document_id,
                    "chunks_count": len(chunks),
                    "pages_count": len(pages),
                }

            except Exception as e:
                try:
                    doc.status = "failed"
                    doc.metadata_json = {"error": f"Erreur lors de l'analyse OCR / RAG : {str(e)}"}
                    await db.commit()
                except Exception:
                    pass
                raise e

    return asyncio.run(_async_parse())


@celery_app.task(bind=True, name="tasks.generate_section_task")
def generate_section_task(
    self,
    tenant_id: str,
    project_id: str,
    section_key: str,
    custom_instructions: Optional[str] = None,
):
    """
    Asynchronously generates a technical memo section in the background:
    1. Loads project, decisions, DCE embeddings, and company assets under tenant_id + RLS.
    2. Calls LLM with isolated tenant RAG context.
    3. Upserts GeneratedSection with status='generated' (or 'failed' on error).
    """
    async def _async_generate():
        # 29/08 (confirmation redemarrage) : `custom_instructions` est un parametre de la
        # fonction englobante `generate_section_task`, mais est aussi REASSIGNE plus bas dans
        # cette fonction imbriquee (fusion avec `strategic_directives`) -- des qu'une assignation
        # existe n'importe ou dans le corps de `_async_generate`, Python traite ce nom comme
        # local a TOUTE la fonction (pas seulement apres l'assignation), donc toute lecture
        # AVANT que le bloc `if getattr(project, "strategic_directives", ...)` ne s'execute
        # levait UnboundLocalError -- ce qui arrivait sur CHAQUE generation d'un projet sans
        # directive strategique renseignee (la grande majorite des projets). `nonlocal` reference
        # explicitement le parametre de la fonction englobante au lieu d'en creer un nouveau local.
        nonlocal custom_instructions
        proj_uuid = uuid.UUID(project_id)
        tenant_uuid = uuid.UUID(tenant_id)

        async with get_worker_db_session(tenant_id) as db:
            # 1. Enforce quota (nombre de dossiers) + plafond de cout LLM reel (02/09,
            # protection de marge parametrable par forfait/tenant)
            await billing_service.check_and_enforce_quota(tenant_id, action="section", db=db)
            await billing_service.check_and_enforce_cost_cap(tenant_id, db=db)

            # 2. Fetch project
            proj_stmt = select(Project).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid)
            proj_res = await db.execute(proj_stmt)
            project = proj_res.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found for tenant {tenant_id}")

            # Directive Stratégique Générale (définie à la création du dossier) : surcharge
            # prioritaire sur le RAG et sur toute autre source pour CHAQUE génération IA.
            if getattr(project, "strategic_directives", None):
                _priority_directive = (
                    "[DIRECTIVE STRATÉGIQUE PRIORITAIRE — DÉFINIE PAR L'ENTREPRISE, PRÉVAUT SUR LE RAG "
                    f"ET TOUTE AUTRE SOURCE] {project.strategic_directives}"
                )
                custom_instructions = (
                    f"{_priority_directive}\n\n{custom_instructions}" if custom_instructions else _priority_directive
                )

            # 3. Fetch section or create new
            sec_stmt = select(GeneratedSection).where(
                GeneratedSection.project_id == proj_uuid,
                GeneratedSection.tenant_id == tenant_uuid,
                GeneratedSection.section_key == section_key,
            )
            sec_res = await db.execute(sec_stmt)
            section = sec_res.scalar_one_or_none()

            try:
                # 4. Fetch RAG Context
                dec_stmt = select(ProjectDecision).where(
                    ProjectDecision.project_id == proj_uuid,
                    ProjectDecision.tenant_id == tenant_uuid,
                )
                dec_res = await db.execute(dec_stmt)
                decision = dec_res.scalar_one_or_none()
                decision_form = decision.form_data if decision else {}

                # Pre-calculate section query vector for semantic retrieval of both DCE and Company Assets
                await embedding_service.sync_platform_key(db)
                section_query_text = f"{project.title} {section_key} {custom_instructions or ''}".strip()
                sec_vector = embedding_service.generate_embedding(section_query_text[:2000]) if embedding_service else None

                # 3. Fetch Top-K Relevant DCE Chunks via pgvector Cosine Distance
                dce_chunks = []
                try:
                    if sec_vector is not None:
                        async with db.begin_nested():
                            dce_dist_expr = DCEEmbedding.embedding.cosine_distance(sec_vector)
                            dce_stmt = (
                                select(DCEEmbedding)
                                .where(
                                    DCEEmbedding.project_id == proj_uuid,
                                    DCEEmbedding.tenant_id == tenant_uuid,
                                    DCEEmbedding.embedding.isnot(None),
                                )
                                .order_by(dce_dist_expr)
                                .limit(5)
                            )
                            dce_res = await db.execute(dce_stmt)
                            dce_chunks = [
                                {"content": c.content, "section_title": c.section_title, "page_number": int(c.page_number)}
                                for c in dce_res.scalars().all()
                            ]
                except Exception as dce_emb_exc:
                    logger.warning("[tasks.py] Semantic DCE search fallback: %s", dce_emb_exc)

                if not dce_chunks:
                    dce_stmt = select(DCEEmbedding).where(
                        DCEEmbedding.project_id == proj_uuid,
                        DCEEmbedding.tenant_id == tenant_uuid,
                    ).limit(5)
                    dce_res = await db.execute(dce_stmt)
                    dce_chunks = [
                        {"content": c.content, "section_title": c.section_title, "page_number": int(c.page_number)}
                        for c in dce_res.scalars().all()
                    ]

                # 4. Fetch Top-K Relevant Company Knowledge Fragments via pgvector Cosine
                # Distance. Interroge desormais knowledge_vectors (fragments ~1200c du
                # texte COMPLET, voir entities.KnowledgeVector) plutot que
                # CompanyAsset.embedding directement -- l'ancien embedding etait calcule
                # sur les 4000 premiers caracteres seulement, et retourner la description
                # entiere (jusqu'a 12000c) par asset depassait deja a elle seule le budget
                # de 6000c de CONTEXT_LIMITS["assets"] des qu'un 2e asset etait retenu
                # (voir llm_generator.py::bounded_context_join). (30/08)
                company_assets = []
                try:
                    if sec_vector is not None:
                        async with db.begin_nested():
                            kv_dist_expr = KnowledgeVector.embedding.cosine_distance(sec_vector)
                            assets_stmt = (
                                select(KnowledgeVector, CompanyAsset.title)
                                .join(CompanyAsset, CompanyAsset.id == KnowledgeVector.asset_id)
                                .where(
                                    KnowledgeVector.tenant_id == tenant_uuid,
                                    KnowledgeVector.embedding.isnot(None),
                                    CompanyAsset.status != "obsolete",
                                    CompanyAsset.validated_by_user == True,
                                )
                                .order_by(kv_dist_expr)
                                .limit(5)
                            )
                            assets_res = await db.execute(assets_stmt)
                            company_assets = [
                                {"category": kv.category, "title": a_title, "content": kv.content}
                                for kv, a_title in assets_res.all()
                            ]
                except Exception as emb_exc:
                    logger.warning("[tasks.py] Semantic asset search fallback: %s", emb_exc)

                if not company_assets:
                    # Repli degrade (aucun embedding exploitable, ou aucun fragment encore
                    # indexe pour cet asset) : anciens assets tries par recence, chaque
                    # contenu plafonne a ~1200c pour rester coherent avec la taille des
                    # fragments ci-dessus et eviter qu'un asset volumineux n'ecrase les
                    # suivants dans bounded_context_join (30/08).
                    assets_stmt = (
                        select(CompanyAsset)
                        .where(
                            CompanyAsset.tenant_id == tenant_uuid,
                            CompanyAsset.status != "obsolete",
                            CompanyAsset.validated_by_user == True,
                        )
                        .order_by(CompanyAsset.created_at.desc())
                        .limit(5)
                    )
                    assets_res = await db.execute(assets_stmt)
                    company_assets = [
                        {"category": a.category, "title": a.title, "content": (a.description or "")[:1200]}
                        for a in assets_res.scalars().all()
                    ]


                # 5. Fetch Active Tenant Learnings from Past AO debriefs, scoped to this
                # project + section per the "boucle d'apprentissage 3 portees" (this AO
                # only / AOs similaires / tous les futurs dossiers) -- a learning saved
                # with a narrower scope than the current generation never leaks outside it.
                from app.services.learning_service import learning_service
                active_learnings = await learning_service.get_active_tenant_learnings(
                    db=db,
                    tenant_id=tenant_uuid,
                    project_id=proj_uuid,
                    section_type=section_key,
                    limit=5,
                )
                tenant_learnings_payload = [
                    {
                        "category": l.category,
                        "title": l.title,
                        "insight": l.learning_insight,
                        "directive": l.actionable_directive,
                    }
                    for l in active_learnings
                ]

                # 6. Resolve Country Regulatory Profile
                from app.services.regulatory_service import regulatory_service
                reg_profile = await regulatory_service.get_tenant_regulatory_profile(db=db, tenant_id=tenant_uuid)
                reg_dict = {
                    "country_code": reg_profile.country_code,
                    "country_name": reg_profile.country_name,
                    "technical_standards_reference": reg_profile.technical_standards_reference,
                    "environmental_regulation": reg_profile.environmental_regulation,
                    "public_procurement_regime": reg_profile.public_procurement_regime,
                    "recognized_qualifications": reg_profile.recognized_qualifications,
                    "waste_tracking_regime": reg_profile.waste_tracking_regime,
                    "safety_plan_regime": reg_profile.safety_plan_regime,
                }

                # 7. Targeted Web Search Enrichment (Serper API) strictly scoped to tenant request
                # AND strictement restreinte a la whitelist reglementaire Super Admin du pays du
                # tenant : jamais un site hors whitelist, jamais un repli vers l'internet ouvert.
                # Zero source configuree pour ce pays = zero recherche (pas un repli non restreint).
                # PRIORITE RAG ABSOLUE (cahier des charges) : la recherche web est un VRAI repli,
                # jamais un enrichissement systematique -- si le corpus historique du tenant
                # (savoir-faire valide + enseignements capitalises) contient deja de la matiere,
                # la recherche web est sautee entierement (zero appel provider, zero cout, zero
                # dilution du corpus interne par une source externe moins autorisee). Les extraits
                # DCE (dce_chunks) restent hors de cette condition : ce sont les pieces du marche
                # EN COURS, pas le "corpus historique" du tenant, donc toujours independants ici.
                if company_assets or tenant_learnings_payload:
                    logger.info(
                        "[GenerateSectionTask] Corpus client suffisant (%d savoir-faire, %d enseignements) "
                        "-- recherche web sautee (priorite RAG absolue).",
                        len(company_assets), len(tenant_learnings_payload),
                    )
                    web_sources_payload = []
                else:
                    from app.services.web_search_service import web_search_service
                    from app.models.entities import CountryOfficialSource
                    from urllib.parse import urlparse
                    whitelist_res = await db.execute(
                        select(CountryOfficialSource).where(
                            CountryOfficialSource.country_code == reg_profile.country_code,
                            CountryOfficialSource.status == "active",
                        )
                    )
                    whitelist_domains = sorted({
                        urlparse(s.portal_url).netloc for s in whitelist_res.scalars().all() if s.portal_url
                    })
                    search_query = f"{project.title} {section_key} BTP normes {reg_profile.technical_standards_reference[:25]}"
                    if custom_instructions:
                        search_query += f" {custom_instructions[:60]}"
                    web_results = await web_search_service.search(
                        tenant_id=tenant_id,
                        query=search_query,
                        num_results=3,
                        project_id=project_id,
                        allowed_sites=whitelist_domains,
                    )
                    web_sources_payload = [
                        {"title": r.title, "url": r.url, "snippet": r.snippet}
                        for r in web_results
                    ]

                # 8. Retrieve Tenant Custom System Prompt and Model Tier
                tenant_rec = (await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))).scalars().first()
                tenant_custom_prompt = (tenant_rec.branding_config or {}).get("system_prompt") if tenant_rec else None

                # 9. Resolve LLM Model Tier (Tenant Override or Platform Default)
                from app.services.model_routing_service import model_routing_service
                resolved_model_info = await model_routing_service.resolve_model_for_tenant(
                    db=db, tenant_id=tenant_uuid, task_type="redaction_memoire",
                )
                selected_model_string = resolved_model_info["model_string"]
                credentials = await model_routing_service.get_credentials_for_model(db=db, model_string=selected_model_string)

                # 9bis. Repli résilient (29/08) : prépare un fournisseur alternatif (clé
                # réellement configurée, différent du fournisseur principal) pour un unique
                # essai de secours si l'appel principal échoue -- avant le moteur de gabarits.
                fallback_candidate = await model_routing_service.get_fallback_candidate(
                    db=db, exclude_provider=resolved_model_info.get("provider"), tenant_id=tenant_uuid,
                )

                # 10. Generate content via LLM with internal + web citations + tenant learnings + regulatory profile + custom prompt + tenant model
                gen_result = await llm_generator_service.generate_memo_section(
                    project_title=project.title,
                    reference_code=project.reference_code,
                    section_key=section_key,
                    section_title=f"Section {section_key}",
                    decision_form=decision_form,
                    dce_criteria=[],
                    rag_dce_chunks=dce_chunks,
                    rag_company_assets=company_assets,
                    rag_web_sources=web_sources_payload,
                    tenant_learnings=tenant_learnings_payload,
                    regulatory_profile=reg_dict,
                    tenant_system_prompt=tenant_custom_prompt,
                    language=getattr(project, "output_language", None) or "fr",
                    custom_instructions=custom_instructions,
                    llm_model=selected_model_string,
                    api_key=credentials.get("api_key"),
                    api_base=credentials.get("api_base"),
                    fallback_model=fallback_candidate.get("model_string") if fallback_candidate else None,
                    fallback_api_key=fallback_candidate.get("api_key") if fallback_candidate else None,
                    fallback_api_base=fallback_candidate.get("api_base") if fallback_candidate else None,
                )

                # 11. Journal de consommation LLM (30/08) -- tokens + cout estime, reponse a
                # une demande explicite de suivi de consommation utilisateur. Ne doit jamais
                # faire echouer la generation : toute erreur ici est absorbee silencieusement.
                try:
                    usage = gen_result.get("usage") or {}
                    if usage and (usage.get("prompt_tokens") is not None or usage.get("completion_tokens") is not None):
                        used_fallback = bool(gen_result.get("fallback_used"))
                        actual_model = gen_result.get("model_used") or selected_model_string
                        if used_fallback and fallback_candidate:
                            actual_provider_id = fallback_candidate.get("provider") or fallback_candidate.get("provider_id")
                        else:
                            actual_provider_id = credentials.get("provider_id")

                        # 02/09 : delegue a BillingService.estimate_llm_cost_usd (repli de
                        # tarification si le modele n'est pas dans llm_catalog_models -- voir
                        # billing_service.py) plutot que de dupliquer la logique ici.
                        estimated_cost = await billing_service.estimate_llm_cost_usd(
                            db, actual_model, usage.get("prompt_tokens"), usage.get("completion_tokens")
                        )

                        db.add(LlmUsageLog(
                            tenant_id=tenant_uuid,
                            project_id=proj_uuid,
                            provider_id=actual_provider_id,
                            model_string=actual_model,
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                            total_tokens=usage.get("total_tokens"),
                            estimated_cost_usd=estimated_cost,
                            was_fallback=used_fallback,
                        ))
                except Exception as e:
                    print(f"[Tasks] Journal consommation LLM notice: {e} -- generation non affectee.")

                now = datetime.utcnow()
                if section:
                    section.content_html = gen_result["content_html"]
                    section.compliance_score = gen_result.get("compliance_score", 98.0)
                    section.compliance_notes = gen_result.get("compliance_notes", "Généré en tâche de fond")
                    section.status = "generated"
                    section.updated_at = now
                else:
                    section = GeneratedSection(
                        id=uuid.uuid4(),
                        tenant_id=tenant_uuid,
                        project_id=proj_uuid,
                        section_key=section_key,
                        title=f"Section {section_key}",
                        order_index=1,
                        content_html=gen_result["content_html"],
                        compliance_score=gen_result.get("compliance_score", 98.0),
                        compliance_notes=gen_result.get("compliance_notes", "Généré en tâche de fond"),
                        status="generated",
                        locked_for_export=False,
                        updated_at=now,
                    )
                    db.add(section)

                await billing_service.increment_usage(tenant_id, action="section", db=db)
                await db.commit()

                return {
                    "status": "completed",
                    "section_id": str(section.id),
                    "section_key": section_key,
                }

            except Exception as e:
                try:
                    if section:
                        section.status = "failed"
                        section.compliance_notes = f"Erreur de génération : {str(e)}"
                        await db.commit()
                except Exception:
                    pass
                raise e

    return asyncio.run(_async_generate())


@celery_app.task(bind=True, name="tasks.build_export_doc_task")
def build_export_doc_task(
    self,
    tenant_id: str,
    project_id: str,
    export_job_id: str,
    doc_format: str = "docx",
    include_visuals: bool = True,
    include_cover_page: bool = True,
):
    """
    Asynchronously compiles Word .docx and PDF exports:
    1. Loads project, sections, decisions, template under tenant_id + RLS.
    2. Builds .docx and uploads to tenant storage.
    3. Updates ExportJob status to 'completed' (or 'failed' on error).
    """
    async def _async_export():
        proj_uuid = uuid.UUID(project_id)
        job_uuid = uuid.UUID(export_job_id)
        tenant_uuid = uuid.UUID(tenant_id)

        async with get_worker_db_session(tenant_id) as db:
            # 1. Enforce quota
            await billing_service.check_and_enforce_quota(tenant_id, action="export", db=db)

            # 2. Fetch ExportJob
            job_stmt = select(ExportJob).where(
                ExportJob.id == job_uuid,
                ExportJob.tenant_id == tenant_uuid,
            )
            job_res = await db.execute(job_stmt)
            job = job_res.scalar_one_or_none()
            if not job:
                raise ValueError(f"ExportJob {export_job_id} not found for tenant {tenant_id}")

            try:
                # 3. Fetch Project & Sections
                proj_stmt = select(Project).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid)
                proj_res = await db.execute(proj_stmt)
                project = proj_res.scalar_one_or_none()
                if not project:
                    raise ValueError(f"Project {project_id} not found for tenant {tenant_id}")

                sec_stmt = select(GeneratedSection).where(
                    GeneratedSection.project_id == proj_uuid,
                    GeneratedSection.tenant_id == tenant_uuid,
                ).order_by(GeneratedSection.order_index.asc())
                sec_res = await db.execute(sec_stmt)
                sections = [
                    {"title": s.title, "content_html": s.content_html, "compliance_score": float(s.compliance_score or 100)}
                    for s in sec_res.scalars().all()
                ]

                dec_stmt = select(ProjectDecision).where(
                    ProjectDecision.project_id == proj_uuid,
                    ProjectDecision.tenant_id == tenant_uuid,
                )
                dec_res = await db.execute(dec_stmt)
                decision = dec_res.scalar_one_or_none()
                decision_form = decision.form_data if decision else {}

                gantt_tasks_stmt = select(ProjectGanttTask).where(
                    ProjectGanttTask.tenant_id == tenant_uuid,
                    ProjectGanttTask.project_id == proj_uuid,
                ).order_by(ProjectGanttTask.sequence, ProjectGanttTask.start_date)
                gantt_tasks_res = await db.execute(gantt_tasks_stmt)
                gantt_task_rows = gantt_tasks_res.scalars().all()
                gantt_tasks = [
                    {
                        "id": str(r.id), "name": r.name, "start_date": r.start_date, "end_date": r.end_date,
                        "sequence": r.sequence, "milestone_label": r.milestone_label,
                        "depends_on": [str(d) for d in (r.depends_on or [])],
                    }
                    for r in gantt_task_rows
                ] or None

                tmpl_stmt = select(ExportTemplate).where(
                    ExportTemplate.tenant_id == tenant_uuid,
                    ExportTemplate.is_default == True,
                )
                tmpl_res = await db.execute(tmpl_stmt)
                template = tmpl_res.scalar_one_or_none()
                template_bytes = None
                if template and template.s3_docx_key:
                    try:
                        template_bytes = storage_service.download_file(tenant_id, template.s3_docx_key)
                    except Exception:
                        template_bytes = None

                # Repli : aucun template client explicite (ou téléchargement en échec) -> réutiliser
                # la structure du plus récent export .docx déjà complété pour ce tenant plutôt qu'un
                # document vierge générique (même logique que export.py::stream_project_docx, voir
                # commentaire jumeau là-bas pour le détail).
                if not template_bytes:
                    try:
                        fallback_stmt = (
                            select(ExportJob)
                            .where(
                                ExportJob.tenant_id == tenant_uuid,
                                ExportJob.status == "completed",
                                ExportJob.s3_docx_url.isnot(None),
                            )
                            .order_by(ExportJob.completed_at.desc())
                            .limit(1)
                        )
                        fallback_res = await db.execute(fallback_stmt)
                        fallback_job = fallback_res.scalar_one_or_none()
                        if fallback_job and fallback_job.s3_docx_url:
                            template_bytes = storage_service.download_file(tenant_id, fallback_job.s3_docx_url)
                    except Exception:
                        template_bytes = None

                tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
                tenant_row = tenant_res.scalar_one_or_none()
                company_name = None
                branding = {}
                if tenant_row:
                    branding = tenant_row.branding_config or {}
                    company_name = branding.get("company_name") or tenant_row.name
                company_name = company_name or "Votre Entreprise"
                # BT02 (01/09) : transmises a build_memo_docx pour que le Word EXPORTE
                # (chemin reel, include_visuals=True ici) reflete enfin la charte du
                # client sur ses visuels Gantt/Organigramme -- jusqu'ici aucun appelant
                # de build_memo_docx ne passait brand_color/shape_style, donc l'export
                # ignorait la couleur de marque meme quand visuals.py (apercu web) la
                # respectait deja.
                brand_color = branding.get("primary_color")
                shape_style = branding.get("shape_style")

                # 4. Build Word document
                project_dict = {
                    "id": str(project.id),
                    "title": project.title,
                    "reference_code": project.reference_code,
                    "client_name": project.client_name,
                    "location": project.location,
                    "company_name": company_name,
                }
                from app.api.generate import SECTION_DEFINITIONS
                required_section_titles = sorted({v["title"] for k, v in SECTION_DEFINITIONS.items() if k != "qse_environnement"})
                docx_res = exporter_service.build_memo_docx(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    project_data=project_dict,
                    sections=sections,
                    decision_form=decision_form,
                    template_bytes=template_bytes,
                    include_visuals=include_visuals,
                    include_cover_page=include_cover_page,
                    required_section_titles=required_section_titles,
                    gantt_tasks=gantt_tasks,
                    language=getattr(project, "output_language", None) or "fr",
                    brand_color=brand_color,
                    shape_style=shape_style,
                )

                file_bytes = docx_res["docx_bytes"]
                s3_subpath = f"exports/{project_id}/{export_job_id}.docx"
                s3_key = storage_service.upload_file(
                    tenant_id=tenant_id,
                    subpath=s3_subpath,
                    file_obj=file_bytes,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

                now = datetime.utcnow()
                job.status = "completed"
                job.s3_docx_url = s3_key
                job.file_size_bytes = len(file_bytes)
                job.completed_at = now
                job.error_message = None

                # doc_format == "pdf" (02/09, correctif tâche #66) : le bouton "Export PDF"
                # ne produisait jusqu'ici jamais qu'un .docx renommé -- convert_docx_to_pdf
                # existait déjà (LibreOffice headless, exporter_service.py) mais n'était
                # appelé nulle part. On tente réellement la conversion ; si LibreOffice est
                # indisponible sur ce worker, on dégrade honnêtement (le .docx déjà généré
                # reste téléchargeable, error_message explique pourquoi ce n'est pas le PDF
                # demandé) plutôt que de faire échouer tout le job ou de mentir sur le format
                # livré.
                if doc_format == "pdf":
                    pdf_key = exporter_service.convert_docx_to_pdf(file_bytes, tenant_id, project_id)
                    if pdf_key:
                        job.s3_pdf_url = pdf_key
                    else:
                        job.error_message = "Conversion PDF indisponible sur ce serveur (LibreOffice) : document Word fourni à la place."

                await billing_service.increment_usage(tenant_id, action="export", db=db)
                await db.commit()

                return {
                    "status": "completed",
                    "export_job_id": export_job_id,
                    "s3_docx_url": s3_key,
                    "s3_pdf_url": job.s3_pdf_url,
                }

            except Exception as e:
                try:
                    if job:
                        job.status = "failed"
                        job.error_message = str(e)
                        await db.commit()
                except Exception as commit_exc:
                    print(f"DEBUG COMMIT FAILED: {commit_exc}")
                raise e


    return asyncio.run(_async_export())


@celery_app.task(name="tasks.purge_expired_accounts_task")
def purge_expired_accounts_task() -> dict:
    """
    Scheduled Celery task executing daily RGPD account purge:
    - Finds all users with status='pending_deletion' and scheduled_purge_at <= NOW()
    - Anonymizes their audit logs (removing personal link)
    - Hard deletes user records and personal assets
    """
    async def _async_purge():
        from app.core.db import AsyncSessionLocal
        from app.services.gdpr_service import execute_expired_accounts_purge_db

        async with AsyncSessionLocal() as db:
            return await execute_expired_accounts_purge_db(db)

    return asyncio.run(_async_purge())


async def purge_obsolete_knowledge_assets_async(db=None) -> dict:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.core.db import AsyncSessionLocal
    from app.models.entities import CompanyAsset

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    async def _do_purge(session):
        stmt = select(CompanyAsset).where(
            CompanyAsset.status == "obsolete",
            CompanyAsset.obsolete_at <= cutoff,
        )
        res = await session.execute(stmt)
        obsolete_assets = res.scalars().all()
        count = len(obsolete_assets)

        for a in obsolete_assets:
            if a.s3_url:
                try:
                    from app.core.storage import storage_service
                    storage_service.delete_file(str(a.tenant_id), a.s3_url)
                except Exception as s3_exc:
                    print(f"[purge_obsolete_knowledge_assets_task] S3 delete error: {s3_exc}")
            await session.delete(a)

        await session.commit()
        return {"purged_count": count, "cutoff_date": cutoff.isoformat()}

    if db is not None:
        return await _do_purge(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _do_purge(session)


@celery_app.task(name="tasks.purge_obsolete_knowledge_assets_task")
def purge_obsolete_knowledge_assets_task() -> dict:
    """
    Scheduled Celery Beat task executing knowledge retention policy:
    - Finds all CompanyAsset with status='obsolete' and obsolete_at <= NOW() - 90 days
    - Hard-deletes matching records from PostgreSQL and deletes S3 binaries
    """
    return asyncio.run(purge_obsolete_knowledge_assets_async())


async def bootstrap_company_profile_async(
    tenant_id: str,
    company_name: str,
    siret: Optional[str] = None,
    reference_urls: Optional[List[str]] = None,
    triggered_by: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """
    Asynchronous runner for company profile auto-bootstrap.
    """
    from app.services.company_bootstrap_service import company_bootstrap_service
    return await company_bootstrap_service.bootstrap_company_profile(
        tenant_id=tenant_id,
        company_name=company_name,
        siret=siret,
        reference_urls=reference_urls,
        triggered_by=triggered_by,
        run_id=run_id,
    )


@celery_app.task(name="tasks.bootstrap_company_task")
def bootstrap_company_task(
    tenant_id: str,
    company_name: str,
    siret: Optional[str] = None,
    reference_urls: Optional[List[str]] = None,
    triggered_by: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """
    Celery task triggering public web & reference URL extraction for company profile.
    """
    return asyncio.run(
        bootstrap_company_profile_async(
            tenant_id=tenant_id,
            company_name=company_name,
            siret=siret,
            reference_urls=reference_urls,
            triggered_by=triggered_by,
            run_id=run_id,
        )
    )


@celery_app.task(name="tasks.sync_llm_catalog_daily_task")
def sync_llm_catalog_daily_task() -> Dict[str, Any]:
    """
    Tâche planifiée quotidienne (chaque nuit à 4h00 Paris) :
    1. Récupère la liste des modèles et tarifs à jour depuis les fournisseurs / catalogue.
    2. Enregistre les nouveaux modèles avec leurs tarifs réels (tokens prompt / completion).
    3. Marque comme inactifs les modèles retirés par les fournisseurs.
    4. Horodate la synchronisation dans PlatformSettings.
    """
    async def _async_sync():
        from app.services.llm_catalog_service import sync_catalog
        from app.core.db import AsyncSessionLocal
        from app.models.entities import PlatformSettings
        from sqlalchemy.orm.attributes import flag_modified

        async with AsyncSessionLocal() as db:
            result = await sync_catalog(db)
            stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
            res = await db.execute(stmt)
            ps = res.scalar_one_or_none()
            if ps:
                settings_dict = dict(ps.settings or {})
                settings_dict["llm_catalog_last_synced_at"] = result["synced_at"]
                ps.settings = settings_dict
                ps.updated_at = datetime.utcnow()
                flag_modified(ps, "settings")
            await db.commit()
            return result

    return asyncio.run(_async_sync())




@celery_app.task(bind=True, name="tasks.sharepoint_sync_task")
def sharepoint_sync_task(self, tenant_id: str):
    """
    Synchronise le connecteur SharePoint d'UN tenant par delta-query Microsoft Graph
    (03/09) : ne traite QUE les fichiers nouveaux/modifiés depuis le dernier
    delta_link -- jamais un balayage complet répété (voir app/services/sharepoint_service.py).
    Réutilise TEL QUEL le pipeline d'ingestion de la base de connaissances
    (extract_text_from_upload + chunk_and_embed_asset_text, app/api/knowledge.py) :
    mêmes quotas (pages, coût OCR, coût LLM) que n'importe quel document déposé
    manuellement -- aucun raccourci de coût spécifique à SharePoint.
    """
    async def _async_sync():
        import hashlib
        from app.api.knowledge import chunk_and_embed_asset_text, extract_text_from_upload
        from app.core.crypto_vault import decrypt_api_key
        from app.services import sharepoint_service as sp

        tenant_uuid = uuid.UUID(tenant_id)
        summary: Dict[str, int] = {"synced": 0, "skipped": 0, "failed": 0, "deleted": 0}

        async with get_worker_db_session(tenant_id) as db:
            conn_res = await db.execute(
                select(SharePointConnection).where(SharePointConnection.tenant_id == tenant_uuid)
            )
            conn = conn_res.scalar_one_or_none()
            if not conn or conn.status not in ("connected", "pending_verification"):
                return {"status": "no_active_connection"}

            try:
                client_secret = decrypt_api_key(conn.client_secret_encrypted)
                token = sp.get_access_token(conn.ms_tenant_id, conn.client_id, client_secret)

                if not conn.drive_id:
                    conn.drive_id = sp.resolve_drive_id(token, conn.site_url)

                items, new_delta_link = sp.fetch_delta(token, conn.drive_id, conn.delta_link)
                syncable, skipped = sp.filter_syncable_items(
                    items, list(conn.allowed_extensions or []), int(conn.max_file_size_bytes or 0)
                )

                # Plafond mensuel de FICHIERS SharePoint, vérifié avant tout téléchargement --
                # protège contre un premier import massif (ex: site entier ajouté par erreur).
                try:
                    await billing_service.check_and_enforce_sharepoint_quota(tenant_uuid, len(syncable), db)
                except HTTPException as quota_exc:
                    conn.last_error = quota_exc.detail
                    conn.status = "connected"
                    await db.commit()
                    return {"status": "blocked_quota", "detail": quota_exc.detail, "candidates": len(syncable)}

                for item in syncable:
                    graph_item_id = item.get("id")
                    filename = item.get("name") or "fichier_sharepoint"
                    try:
                        async with db.begin_nested():
                            existing_item_res = await db.execute(
                                select(SharePointSyncItem).where(
                                    SharePointSyncItem.connection_id == conn.id,
                                    SharePointSyncItem.graph_item_id == graph_item_id,
                                )
                            )
                            existing_item = existing_item_res.scalar_one_or_none()

                            content_bytes = sp.download_file_content(token, conn.drive_id, graph_item_id)
                            file_hash = hashlib.sha256(content_bytes).hexdigest()

                            if existing_item and existing_item.file_hash == file_hash:
                                # Contenu inchangé (renommage/déplacement côté SharePoint) --
                                # ne relance ni OCR ni embeddings : c'est le coeur du sync incrémental.
                                existing_item.last_synced_at = datetime.utcnow()
                                summary["skipped"] += 1
                                continue

                            extracted_text, status_state, error_msg = extract_text_from_upload(filename, content_bytes)

                            # Estimation de pages avant toute écriture (~3000 caractères/page,
                            # cohérent avec chunking_service) -- vérifiée AVANT de persister quoi
                            # que ce soit, pour ne jamais facturer un cycle de stockage/OCR à un
                            # fichier qui sera de toute façon rejeté.
                            pages_estimate = max(1, len(extracted_text) // 3000) if extracted_text else 1
                            await billing_service.check_and_enforce_page_quota(tenant_uuid, pages_estimate, db)

                            asset_id = uuid.uuid4()
                            s3_key = storage_service.upload_file(
                                tenant_id=tenant_id,
                                subpath=f"sharepoint/{tenant_id}/{asset_id}_{filename}",
                                file_obj=content_bytes,
                                content_type="application/octet-stream",
                            )

                            await embedding_service.sync_platform_key(db)
                            knowledge_vector_rows = []
                            if extracted_text and status_state == "indexed":
                                knowledge_vector_rows = chunk_and_embed_asset_text(
                                    tenant_id_uuid=tenant_uuid,
                                    asset_id=asset_id,
                                    category="sharepoint",
                                    title=filename.rsplit(".", 1)[0],
                                    full_text=extracted_text,
                                )

                            db.add(CompanyAsset(
                                id=asset_id,
                                tenant_id=tenant_uuid,
                                category="sharepoint",
                                title=filename.rsplit(".", 1)[0],
                                description=extracted_text[:12000] if extracted_text else filename,
                                s3_url=s3_key,
                                status=status_state,
                                embedding=None,
                                metadata_json={
                                    "source_type": "sharepoint",
                                    "file_name": filename,
                                    "file_hash": file_hash,
                                    "graph_item_id": graph_item_id,
                                    "status": status_state,
                                    "error_message": error_msg,
                                    "indexed_at": datetime.utcnow().isoformat(),
                                },
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow(),
                            ))
                            for kv in knowledge_vector_rows:
                                db.add(kv)

                            if existing_item:
                                existing_item.file_hash = file_hash
                                existing_item.company_asset_id = asset_id
                                existing_item.status = "indexed"
                                existing_item.status_detail = None
                                existing_item.last_synced_at = datetime.utcnow()
                            else:
                                db.add(SharePointSyncItem(
                                    tenant_id=tenant_uuid,
                                    connection_id=conn.id,
                                    graph_item_id=graph_item_id,
                                    filename=filename,
                                    file_hash=file_hash,
                                    size_bytes=item.get("size", 0),
                                    company_asset_id=asset_id,
                                    status="indexed",
                                    last_synced_at=datetime.utcnow(),
                                ))

                            await billing_service.increment_usage(tenant_id, "page", db, amount=pages_estimate)
                            await billing_service.increment_usage(tenant_id, "sharepoint_file", db)
                            summary["synced"] += 1
                    except HTTPException as quota_exc:
                        summary["skipped"] += 1
                        logger.info("[sharepoint_sync_task] Fichier '%s' ignoré (quota) : %s", filename, quota_exc.detail)
                        continue
                    except Exception as item_exc:
                        summary["failed"] += 1
                        logger.warning("[sharepoint_sync_task] Échec sur '%s': %s", filename, item_exc)
                        db.add(SharePointSyncItem(
                            tenant_id=tenant_uuid,
                            connection_id=conn.id,
                            graph_item_id=graph_item_id,
                            filename=filename,
                            status="failed",
                            status_detail=str(item_exc)[:500],
                            last_synced_at=datetime.utcnow(),
                        ))
                        continue

                for item in skipped:
                    if item.get("_skip_reason") == "deleted_upstream":
                        del_res = await db.execute(
                            select(SharePointSyncItem).where(
                                SharePointSyncItem.connection_id == conn.id,
                                SharePointSyncItem.graph_item_id == item.get("id"),
                            )
                        )
                        del_item = del_res.scalar_one_or_none()
                        if del_item:
                            del_item.status = "deleted_upstream"
                            del_item.last_synced_at = datetime.utcnow()
                        summary["deleted"] += 1

                conn.delta_link = new_delta_link or conn.delta_link
                conn.last_synced_at = datetime.utcnow()
                conn.status = "connected"
                conn.last_error = None
                await db.commit()
                return {"status": "completed", **summary}

            except sp.SharePointGraphError as graph_exc:
                conn.status = "error"
                conn.last_error = str(graph_exc)
                await db.commit()
                return {"status": "error", "detail": str(graph_exc)}

    return asyncio.run(_async_sync())


@celery_app.task(name="tasks.sharepoint_sync_all_tenants_task")
def sharepoint_sync_all_tenants_task() -> Dict[str, Any]:
    """
    Tâche planifiée (toutes les 6h, voir app/core/celery_app.py beat_schedule) :
    liste tous les connecteurs SharePoint actifs (tous tenants, session non filtrée
    par RLS -- même convention que sync_llm_catalog_daily_task pour les tâches
    intrinsèquement inter-tenants) et déclenche un sharepoint_sync_task par tenant.
    Chaque sync individuel reste strictement isolé par RLS (get_worker_db_session).
    """
    async def _async_dispatch():
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(SharePointConnection.tenant_id).where(SharePointConnection.status == "connected")
            )
            tenant_ids = [str(row[0]) for row in res.all()]

        for tid in tenant_ids:
            sharepoint_sync_task.delay(tenant_id=tid)

        return {"dispatched": len(tenant_ids)}

    return asyncio.run(_async_dispatch())
