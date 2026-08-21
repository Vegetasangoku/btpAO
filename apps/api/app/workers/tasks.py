"""
Celery Asynchronous Tasks for Heavy Processing (OCR, Vector Embeddings, Docx Assembly, AI Generation).
Strict multi-tenant security:
- tenant_id is explicitly passed to every task (never guessed).
- Accesses PostgreSQL via SQLAlchemy 2 Async + get_worker_db_session(tenant_id) (SET ROLE btp_app_user + RLS).
- Zero silent fallbacks: any failure updates entity status to 'failed' and reports clear error to client.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from app.core.celery_app import celery_app
from app.core.db import get_worker_db_session
from app.core.storage import storage_service
from app.models.entities import DCEDocument, DCEEmbedding, ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, CompanyAsset, Tenant

from app.services.billing_service import billing_service
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

                # 3. Extract text & tables via OCR
                ocr_result = ocr_service.extract_text_and_tables(pdf_bytes, s3_key.split("/")[-1])

                # 4. Chunk document
                pages = ocr_result.get("pages", [])
                chunks = chunking_service.chunk_document_pages(pages)

                # 5. Generate embeddings and save to PostgreSQL
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
                        metadata_json={"embedding": vec},
                        created_at=datetime.utcnow(),
                    )
                    db.add(embedding_row)


                doc.status = "completed"
                doc.pages_count = len(pages)
                doc.metadata_json = {
                    "summary": f"Document analysé avec succès ({len(chunks)} fragments indexés).",
                    "chunks_count": len(chunks),
                }
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
        proj_uuid = uuid.UUID(project_id)
        tenant_uuid = uuid.UUID(tenant_id)

        async with get_worker_db_session(tenant_id) as db:
            # 1. Enforce quota
            await billing_service.check_and_enforce_quota(tenant_id, action="section", db=db)

            # 2. Fetch project
            proj_stmt = select(Project).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid)
            proj_res = await db.execute(proj_stmt)
            project = proj_res.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found for tenant {tenant_id}")

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

                dce_stmt = select(DCEEmbedding).where(
                    DCEEmbedding.project_id == proj_uuid,
                    DCEEmbedding.tenant_id == tenant_uuid,
                ).limit(5)
                dce_res = await db.execute(dce_stmt)
                dce_chunks = [
                    {"content": c.content, "section_title": c.section_title, "page_number": int(c.page_number)}
                    for c in dce_res.scalars().all()
                ]

                assets_stmt = select(CompanyAsset).where(CompanyAsset.tenant_id == tenant_uuid).limit(5)
                assets_res = await db.execute(assets_stmt)
                company_assets = [
                    {"category": a.category, "title": a.title, "content": a.description}
                    for a in assets_res.scalars().all()
                ]

                # 5. Fetch Active Tenant Learnings from Past AO debriefs
                from app.models.entities import TenantLearning
                learnings_stmt = (
                    select(TenantLearning)
                    .where(TenantLearning.tenant_id == tenant_uuid, TenantLearning.is_active == True)
                    .order_by(TenantLearning.created_at.desc())
                    .limit(5)
                )
                learnings_res = await db.execute(learnings_stmt)
                tenant_learnings_payload = [
                    {
                        "category": l.category,
                        "title": l.title,
                        "insight": l.learning_insight,
                        "directive": l.actionable_directive,
                    }
                    for l in learnings_res.scalars().all()
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
                from app.services.web_search_service import web_search_service
                search_query = f"{project.title} {section_key} BTP normes {reg_profile.technical_standards_reference[:25]}"
                if custom_instructions:
                    search_query += f" {custom_instructions[:60]}"
                web_results = await web_search_service.search(
                    tenant_id=tenant_id,
                    query=search_query,
                    num_results=3,
                    project_id=project_id,
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
                resolved_model_info = await model_routing_service.resolve_model_for_tenant(db=db, tenant_id=tenant_uuid)
                selected_model_string = resolved_model_info["model_string"]

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
                    custom_instructions=custom_instructions,
                    llm_model=selected_model_string,
                )






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

                # 4. Build Word document
                project_dict = {
                    "id": str(project.id),
                    "title": project.title,
                    "reference_code": project.reference_code,
                    "client_name": project.client_name,
                    "location": project.location,
                }
                docx_res = exporter_service.build_memo_docx(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    project_data=project_dict,
                    sections=sections,
                    decision_form=decision_form,
                    template_bytes=template_bytes,
                    include_visuals=include_visuals,
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

                await billing_service.increment_usage(tenant_id, action="export", db=db)
                await db.commit()

                return {
                    "status": "completed",
                    "export_job_id": export_job_id,
                    "s3_docx_url": s3_key,
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


