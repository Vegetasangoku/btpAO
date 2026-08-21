"""
Integration Tests for Asynchronous Celery Dispatch from API Endpoints.
Proves that:
1. HTTP POST /api/dce/upload returns status='processing' immediately without blocking on OCR.
2. Background Celery worker parse_dce_task transitions document from 'processing' to 'completed'.
3. HTTP POST /api/export/compile returns status='processing' immediately without blocking on docx assembly.
4. Background Celery worker build_export_doc_task transitions export job to 'completed'.
5. HTTP POST /api/generate/section returns status='processing' immediately and worker updates to 'generated'.
"""
import io
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.core.storage import storage_service
from app.main import app
from app.workers.tasks import (
    build_export_doc_task,
    generate_section_task,
    parse_dce_task,
)

TENANT_A_ID = "11111111-1111-1111-1111-111111111111"
USER_A_ID = "22222222-2222-2222-2222-222222222222"
PROJ_A_ID = "33333333-3333-3333-3333-333333333333"

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_jwt(user_id: str, tenant_id: str, email: str) -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": "conducteur_travaux"},
        "user_metadata": {"tenant_id": tenant_id},
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_postgres_async_dispatch():
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # 1. Tenants & Projects
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES (%s, 'EiffaBTP Construction SAS', 'eiffabtp')
            ON CONFLICT (id) DO NOTHING;
        """, (TENANT_A_ID,))

        cur.execute("""
            INSERT INTO public.projects (id, tenant_id, reference_code, title, client_name, location)
            VALUES (%s, %s, 'AO-LYCEE-2026', 'Lycée HQE Paris', 'Région IDF', 'Paris 15')
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
        """, (PROJ_A_ID, TENANT_A_ID))

        # 2. Subscriptions
        cur.execute("""
            INSERT INTO public.tenant_subscriptions (id, tenant_id, plan_id, status, billing_mode, allow_overage)
            VALUES (gen_random_uuid(), %s, 'pro', 'active', 'stripe', true)
            ON CONFLICT (tenant_id) DO UPDATE SET status = 'active';
        """, (TENANT_A_ID,))

        # 3. Clean
        cur.execute("DELETE FROM public.dce_documents WHERE tenant_id = %s;", (TENANT_A_ID,))
        cur.execute("DELETE FROM public.dce_embeddings WHERE tenant_id = %s;", (TENANT_A_ID,))
        cur.execute("DELETE FROM public.generated_sections WHERE tenant_id = %s;", (TENANT_A_ID,))
        cur.execute("DELETE FROM public.export_jobs WHERE tenant_id = %s;", (TENANT_A_ID,))

    finally:
        cur.close()
        conn.close()


def test_http_dce_upload_returns_processing_and_celery_worker_completes():
    """POST /api/dce/upload returns status='processing' immediately; running worker completes OCR and embeddings."""
    client = TestClient(app)
    token = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user@eiffabtp.fr")

    # 1. HTTP Upload request
    fake_pdf = b"%PDF-1.4 Mock Tender CCTP Document Content For BTP"
    files = {"file": ("CCTP_Gros_Oeuvre.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    data = {"project_id": PROJ_A_ID, "doc_type": "cctp"}

    res = client.post("/api/dce/upload", files=files, data=data, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    resp_data = res.json()

    doc_id = resp_data["document_id"]
    s3_key = resp_data["s3_key"]
    assert resp_data["status"] == "processing", f"Expected 'processing' in HTTP response, got {resp_data['status']}"

    # 2. Verify state in PostgreSQL before task execution
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("SELECT status FROM public.dce_documents WHERE id = %s;", (doc_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "processing"

        # 3. Simulate Celery worker picking up task
        task_res = parse_dce_task(
            tenant_id=TENANT_A_ID,
            project_id=PROJ_A_ID,
            document_id=doc_id,
            s3_key=s3_key,
        )
        assert task_res["status"] == "completed"

        # 4. Verify state in PostgreSQL after Celery task completion
        cur.execute("SELECT status, metadata_json FROM public.dce_documents WHERE id = %s;", (doc_id,))
        completed_row = cur.fetchone()
        assert completed_row is not None
        assert completed_row[0] == "completed"
        assert "fragments indexés" in completed_row[1]["summary"]
    finally:
        cur.close()
        conn.close()


def test_http_export_compile_returns_processing_and_celery_worker_completes():
    """POST /api/export/compile returns status='processing' immediately; worker compiles docx."""
    client = TestClient(app)
    token = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user@eiffabtp.fr")

    payload = {
        "project_id": PROJ_A_ID,
        "format": "docx",
        "include_gantt": True,
        "include_organigramme": True,
    }

    res = client.post("/api/export/compile", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    resp_data = res.json()

    job_id = resp_data["id"]
    assert resp_data["status"] == "processing", f"Expected 'processing' in HTTP response, got {resp_data['status']}"

    # 2. Verify state in PostgreSQL before task execution
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("SELECT status FROM public.export_jobs WHERE id = %s;", (job_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "processing"

        # 3. Simulate Celery worker execution
        task_res = build_export_doc_task(
            tenant_id=TENANT_A_ID,
            project_id=PROJ_A_ID,
            export_job_id=job_id,
            doc_format="docx",
        )
        assert task_res["status"] == "completed"

        # 4. Verify state in PostgreSQL after Celery task execution
        cur.execute("SELECT status, s3_docx_url, file_size_bytes FROM public.export_jobs WHERE id = %s;", (job_id,))
        completed_row = cur.fetchone()
        assert completed_row is not None
        assert completed_row[0] == "completed"
        assert completed_row[1] is not None
        assert completed_row[2] > 0
    finally:
        cur.close()
        conn.close()


def test_http_generate_section_returns_processing_and_celery_worker_completes():
    """POST /api/generate/section returns status='processing' immediately; worker generates content."""
    client = TestClient(app)
    token = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user@eiffabtp.fr")

    payload = {
        "project_id": PROJ_A_ID,
        "section_key": "moyens_humains",
        "custom_instructions": "Conducteur principal ESTP 15 ans d'expérience",
    }

    res = client.post("/api/generate/section", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    resp_data = res.json()

    sec_id = resp_data["id"]
    assert resp_data["status"] == "processing", f"Expected 'processing' in HTTP response, got {resp_data['status']}"

    # 2. Verify state in PostgreSQL before task execution
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("SELECT status FROM public.generated_sections WHERE id = %s;", (sec_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "processing"

        # 3. Simulate Celery worker execution
        task_res = generate_section_task(
            tenant_id=TENANT_A_ID,
            project_id=PROJ_A_ID,
            section_key="moyens_humains",
            custom_instructions="Conducteur principal ESTP 15 ans d'expérience",
        )
        assert task_res["status"] == "completed"

        # 4. Verify state in PostgreSQL after Celery task execution
        cur.execute("SELECT status, compliance_score, content_html FROM public.generated_sections WHERE id = %s;", (sec_id,))
        completed_row = cur.fetchone()
        assert completed_row is not None
        assert completed_row[0] == "generated"
        assert completed_row[1] >= 90.0
        assert len(completed_row[2]) > 50
    finally:
        cur.close()
        conn.close()
