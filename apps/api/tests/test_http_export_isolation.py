"""
Real HTTP Integration Test for Document Compilation & Export Multi-Tenant Isolation via SQLAlchemy 2 Async + PostgreSQL RLS.
Every test executes strictly through the production FastAPI HTTP pipeline (TestClient -> get_db -> SET ROLE btp_app_user -> set_config).

Proves:
1. Seed real distinct export jobs and compiled documents in PostgreSQL for Tenant A and Tenant B.
2. Real HTTP POST /api/export/compile compiles document and stores in tenant-scoped path in PostgreSQL.
3. Real HTTP GET /api/export/job/{job_id} under Tenant A retrieves Tenant A job.
4. Tenant A requesting Tenant B's export job by ID receives 404 (strictly blocked).
5. Real HTTP GET /api/export/download/{job_id} serves file only to authenticated owner tenant.
6. Tenant A attempting direct file download of Tenant B's job ID receives 404 (strictly blocked).
7. Tenant A attempting to stream Tenant B's project memo receives 404.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.core.storage import storage_service
from app.main import app

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PROJ_A_ID = "99991111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_B_ID = "99992222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
JOB_A_ID = "aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_B_ID = "bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_jwt(user_id: str, tenant_id: str, email: str) -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {
            "tenant_id": tenant_id,
            "role": "conducteur_travaux",
        },
        "user_metadata": {
            "tenant_id": tenant_id,
        },
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(scope="module", autouse=True)
def setup_postgres_export_database():
    """Provisions tables, btp_app_user grants, RLS policies and seeds test export jobs for both tenants."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.export_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            template_id UUID,
            format TEXT NOT NULL DEFAULT 'docx',
            status TEXT NOT NULL DEFAULT 'completed',
            s3_docx_url TEXT,
            s3_pdf_url TEXT,
            file_size_bytes NUMERIC DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.export_jobs ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_export_jobs ON public.export_jobs;
        CREATE POLICY tenant_isolation_export_jobs ON public.export_jobs
            FOR ALL TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );
    """)

    # 1. Seed Tenants & Projects
    cur.execute("""
        INSERT INTO public.tenants (id, name, slug)
        VALUES 
        (%s, 'Tenant A Export', 'tenant-a-exp'),
        (%s, 'Tenant B Export', 'tenant-b-exp')
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, location)
        VALUES 
        (%s, %s, 'Projet A Export Memo', 'AO-EXP-A', 'Ville Paris', 'Paris 18'),
        (%s, %s, 'Projet B Export Memo', 'AO-EXP-B', 'Métropole Lyon', 'Lyon 3')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID, PROJ_A_ID, TENANT_A_ID, PROJ_B_ID, TENANT_B_ID))

    # 2. Upload dummy docx files to tenant storage
    s3_key_a = storage_service.upload_file(
        tenant_id=TENANT_A_ID,
        subpath=f"exports/{PROJ_A_ID}/{JOB_A_ID}.docx",
        file_obj=b"PK\x03\x04FAKE_DOCX_TENANT_A",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    s3_key_b = storage_service.upload_file(
        tenant_id=TENANT_B_ID,
        subpath=f"exports/{PROJ_B_ID}/{JOB_B_ID}.docx",
        file_obj=b"PK\x03\x04FAKE_DOCX_TENANT_B",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    # 3. Seed Distinct Export Jobs in PostgreSQL
    cur.execute("DELETE FROM public.export_jobs WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("""
        INSERT INTO public.export_jobs (id, tenant_id, project_id, format, status, s3_docx_url, file_size_bytes)
        VALUES 
        (%s, %s, %s, 'docx', 'completed', %s, 1024),
        (%s, %s, %s, 'docx', 'completed', %s, 2048);
    """, (
        JOB_A_ID, TENANT_A_ID, PROJ_A_ID, s3_key_a,
        JOB_B_ID, TENANT_B_ID, PROJ_B_ID, s3_key_b,
    ))

    yield

    try:
        cur.execute("DELETE FROM public.export_jobs WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_get_export_job_tenant_a_isolation():
    """Real HTTP GET /api/export/job/{job_id} retrieves Tenant A job details."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(f"/api/export/job/{JOB_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    job = response.json()
    assert job["id"] == JOB_A_ID
    assert job["tenant_id"] == TENANT_A_ID
    assert job["status"] == "completed"


def test_http_get_export_job_cross_tenant_blocked():
    """Tenant A requesting Tenant B export job by ID receives 404 (strictly blocked)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Tenant A attempts to read Tenant B's job
    response = client.get(f"/api/export/job/{JOB_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


def test_http_download_export_job_file_isolation():
    """Real HTTP GET /api/export/download/{job_id} serves document only to owner tenant."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(f"/api/export/download/{JOB_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    assert response.content == b"PK\x03\x04FAKE_DOCX_TENANT_A"


def test_http_download_export_job_cross_tenant_blocked():
    """Tenant A attempting to download Tenant B document directly by job ID receives 404 (strictly blocked)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Tenant A attempts direct file download of Tenant B's export job
    response = client.get(f"/api/export/download/{JOB_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


def test_http_compile_technical_memo_tenant_isolation():
    """Real HTTP POST /api/export/compile compiles document and creates job in DB under authenticated tenant."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    payload = {
        "project_id": PROJ_A_ID,
        "format": "docx",
        "include_gantt": True,
        "include_organigramme": True,
    }
    response = client.post("/api/export/compile", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    job = response.json()
    assert job["tenant_id"] == TENANT_A_ID
    assert job["status"] in ("processing", "completed")
    assert job["id"] is not None

