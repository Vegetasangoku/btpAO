"""
Integration Tests for Celery Asynchronous Workers with Postgres RLS & Tenant Isolation.
Verifies:
1. Healthcheck / Demo task execution.
2. Long-running DCE OCR & pgvector embedding generation strictly scoped to tenant.
3. Long-running section generation strictly isolated to tenant.
4. Export compilation task with explicit status 'failed' reporting (zero silent errors).
5. Cross-tenant access blocked by RLS in background worker transactions.
"""
import uuid
import psycopg2
import pytest
from app.workers.tasks import (
    build_export_doc_task,
    generate_section_task,
    parse_dce_task,
    test_celery_task as celery_healthcheck_task,
)

TENANT_A_ID = "11111111-1111-1111-1111-111111111111"
USER_A_ID = "22222222-2222-2222-2222-222222222222"
PROJ_A_ID = "33333333-3333-3333-3333-333333333333"
DOC_A_ID = "55555555-5555-5555-5555-555555555555"
JOB_A_ID = "77777777-7777-7777-7777-777777777777"

TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_B_ID = "bbbbbbbb-3333-3333-3333-333333333333"
PROJ_B_ID = "bbbbbbbb-4444-4444-4444-444444444444"
DOC_B_ID = "bbbbbbbb-5555-5555-5555-555555555555"


@pytest.fixture(autouse=True)
def setup_postgres_celery_database():
    """Initializes schema and seeds realistic test data for both Tenant A and Tenant B."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")


        # 1. Tenants
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES 
            (%s, 'EiffaBTP Construction SAS', 'eiffabtp-celery'),
            (%s, 'BouygBTP Travaux Publics', 'bouygbtp-celery')
            ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug;

        """, (TENANT_A_ID, TENANT_B_ID))

        # 2. Projects
        cur.execute("""
            INSERT INTO public.projects (id, tenant_id, reference_code, title, client_name, location)
            VALUES
            (%s, %s, 'AO-2026-LYCEE', 'Projet Lycée HQE - EiffaBTP', 'Région IDF', 'Paris 15'),
            (%s, %s, 'AO-2026-TRAM', 'Projet Tramway Ligne 4 - BouygBTP', 'Métropole Lyon', 'Lyon Part-Dieu')
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, reference_code = EXCLUDED.reference_code;
        """, (PROJ_A_ID, TENANT_A_ID, PROJ_B_ID, TENANT_B_ID))        # 3. DCE Documents
        from app.core.storage import storage_service
        s3_key_a = storage_service.upload_file(TENANT_A_ID, "dce/cctp.pdf", b"%PDF-1.4 Mock BTP CCTP Document Content")
        s3_key_b = storage_service.upload_file(TENANT_B_ID, "dce/cctp.pdf", b"%PDF-1.4 Mock BTP CCTP Document Content")

        cur.execute("""
            INSERT INTO public.dce_documents (id, tenant_id, project_id, filename, doc_type, s3_key, status)
            VALUES
            (%s, %s, %s, 'CCTP_Lycée.pdf', 'cctp', %s, 'uploaded'),
            (%s, %s, %s, 'CCTP_Tramway.pdf', 'cctp', %s, 'uploaded')
            ON CONFLICT (id) DO UPDATE SET status = 'uploaded', s3_key = EXCLUDED.s3_key;
        """, (DOC_A_ID, TENANT_A_ID, PROJ_A_ID, s3_key_a, DOC_B_ID, TENANT_B_ID, PROJ_B_ID, s3_key_b))

        # 4. Clean previous embeddings, sections, export jobs
        cur.execute("DELETE FROM public.dce_embeddings WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.export_jobs WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))

        # 5. Export Job for Tenant A
        cur.execute("""
            INSERT INTO public.export_jobs (id, tenant_id, project_id, format, status)
            VALUES (%s, %s, %s, 'docx', 'pending')
            ON CONFLICT (id) DO UPDATE SET status = 'pending';
        """, (JOB_A_ID, TENANT_A_ID, PROJ_A_ID))

        # 6. Subscriptions
        cur.execute("""
            INSERT INTO public.tenant_subscriptions (id, tenant_id, plan_id, status, billing_mode, allow_overage)
            VALUES 
            (gen_random_uuid(), %s, 'pro', 'active', 'stripe', true),
            (gen_random_uuid(), %s, 'starter', 'active', 'stripe', true)
            ON CONFLICT (tenant_id) DO UPDATE SET status = 'active';
        """, (TENANT_A_ID, TENANT_B_ID))

    finally:
        cur.close()
        conn.close()


def test_celery_healthcheck_demo_task():
    """Validates basic Celery task execution."""
    res = celery_healthcheck_task(12, 23)
    assert res == 35


def test_celery_parse_dce_task_tenant_isolation_and_embeddings():
    """Background DCE parsing extracts OCR, computes embeddings, and records status in PostgreSQL."""
    result = parse_dce_task(
        tenant_id=TENANT_A_ID,
        project_id=PROJ_A_ID,
        document_id=DOC_A_ID,
        s3_key=f"tenants/{TENANT_A_ID}/dce/cctp.pdf",
    )
    assert result["status"] == "completed"
    assert result["chunks_count"] > 0

    # Verify PostgreSQL state under RLS btp_app_user for Tenant A
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))

        # Check DCEDocument updated
        cur.execute("SELECT status, metadata_json FROM public.dce_documents WHERE id = %s;", (DOC_A_ID,))
        doc_row = cur.fetchone()
        assert doc_row is not None
        assert doc_row[0] == "completed"
        assert "fragments indexés" in doc_row[1]["summary"]

        # Check embeddings count for Tenant A
        cur.execute("SELECT COUNT(*) FROM public.dce_embeddings WHERE tenant_id = %s;", (TENANT_A_ID,))
        a_count = cur.fetchone()[0]
        assert a_count > 0

        # Prove Tenant B document was untouched (still uploaded)
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_B_ID,))
        cur.execute("SELECT status FROM public.dce_documents WHERE id = %s;", (DOC_B_ID,))
        doc_b = cur.fetchone()
        assert doc_b[0] == "uploaded"

        # Prove zero embeddings for Tenant B
        cur.execute("SELECT COUNT(*) FROM public.dce_embeddings WHERE tenant_id = %s;", (TENANT_B_ID,))
        b_count = cur.fetchone()[0]
        assert b_count == 0
    finally:
        cur.close()
        conn.close()


def test_celery_task_cross_tenant_access_blocked_by_rls():
    """A worker running under Tenant A cannot process Tenant B's documents."""
    with pytest.raises(ValueError) as exc_info:
        parse_dce_task(
            tenant_id=TENANT_A_ID,
            project_id=PROJ_B_ID,
            document_id=DOC_B_ID,
            s3_key=f"tenants/{TENANT_B_ID}/dce/cctp.pdf",
        )
    assert "not found" in str(exc_info.value)



def test_celery_generate_section_task_tenant_isolation():
    """Background AI section generator produces content under tenant scope."""
    res = generate_section_task(
        tenant_id=TENANT_A_ID,
        project_id=PROJ_A_ID,
        section_key="methodologie_travaux",
        custom_instructions="Mettre en avant les phasages de nuit",
    )
    assert res["status"] == "completed"
    assert res["section_key"] == "methodologie_travaux"

    # Verify GeneratedSection in PostgreSQL under Tenant A
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("""
            SELECT section_key, status, compliance_score, content_html 
            FROM public.generated_sections 
            WHERE project_id = %s;
        """, (PROJ_A_ID,))
        sec_row = cur.fetchone()
        assert sec_row is not None
        assert sec_row[0] == "methodologie_travaux"
        assert sec_row[1] == "generated"
        assert sec_row[2] >= 90.0
        assert len(sec_row[3]) > 50

        # Tenant B has 0 sections
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_B_ID,))
        cur.execute("SELECT COUNT(*) FROM public.generated_sections WHERE tenant_id = %s;", (TENANT_B_ID,))
        b_count = cur.fetchone()[0]
        assert b_count == 0
    finally:
        cur.close()
        conn.close()


def test_celery_build_export_task_success_and_failure_reporting():
    """Export task updates status to 'completed' on success and 'failed' on error with explicit error message."""
    # 1. Success case
    res = build_export_doc_task(
        tenant_id=TENANT_A_ID,
        project_id=PROJ_A_ID,
        export_job_id=JOB_A_ID,
        doc_format="docx",
    )
    assert res["status"] == "completed"
    assert res["s3_docx_url"] is not None

    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("SELECT status, s3_docx_url, file_size_bytes FROM public.export_jobs WHERE id = %s;", (JOB_A_ID,))
        job_row = cur.fetchone()
        assert job_row is not None
        assert job_row[0] == "completed"
        assert job_row[1] is not None
        assert job_row[2] > 0

        # 2. Failure case: seed a failing job (invalid project)
        bad_job_id = "99999999-9999-9999-9999-999999999999"
        cur.execute("RESET ROLE;")
        cur.execute("""
            INSERT INTO public.export_jobs (id, tenant_id, project_id, format, status)
            VALUES (%s, %s, %s, 'docx', 'pending');
        """, (bad_job_id, TENANT_A_ID, PROJ_A_ID))


        # Intentionally cause an error by passing a non-existent project_id to the task
        with pytest.raises(Exception):
            build_export_doc_task(
                tenant_id=TENANT_A_ID,
                project_id="00000000-0000-0000-0000-000000000000",
                export_job_id=bad_job_id,
            )

        # Verify job is marked 'failed' in DB, NOT silent
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("SELECT status, error_message FROM public.export_jobs WHERE id = %s;", (bad_job_id,))
        failed_row = cur.fetchone()
        assert failed_row is not None
        assert failed_row[0] == "failed"
        assert failed_row[1] is not None
        assert len(failed_row[1]) > 0
    finally:
        cur.close()
        conn.close()
