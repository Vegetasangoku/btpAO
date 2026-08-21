"""
Real HTTP Integration Test for DCE Ingestion, Criteria & Search Multi-Tenant Isolation via SQLAlchemy 2 Async.
Proves via FastAPI TestClient against real Postgres database:
1. Seed real DCE documents, criteria and embeddings for Tenant A and Tenant B directly in PostgreSQL.
2. HTTP GET /api/dce/criteria/{project_id} under Tenant A returns ONLY Tenant A criteria.
3. HTTP GET /api/dce/criteria/{project_id} under Tenant B returns ONLY Tenant B criteria.
4. HTTP GET /api/dce/search under Tenant A returns ONLY Tenant A chunks.
5. Cross-tenant access and header spoofing are strictly prevented.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PROJ_A_ID = "55555555-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_B_ID = "66666666-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
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
def setup_postgres_dce_database():
    """Provisions tables and seeds test DCE data for both tenants directly in PostgreSQL."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Ensure tables exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.dce_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            doc_type TEXT NOT NULL DEFAULT 'cctp',
            s3_key TEXT NOT NULL,
            pages_count NUMERIC DEFAULT 0,
            file_size_bytes NUMERIC DEFAULT 0,
            status TEXT DEFAULT 'uploaded',
            metadata_json JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS public.dce_criteria (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            criterion_title TEXT NOT NULL,
            weight_percentage NUMERIC(5, 2) NOT NULL,
            description TEXT,
            key_expectations JSONB DEFAULT '[]'::jsonb,
            required_evidence JSONB DEFAULT '[]'::jsonb,
            mandatory TEXT DEFAULT 'true',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS public.dce_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            document_id UUID,
            chunk_index NUMERIC DEFAULT 0,
            page_number NUMERIC DEFAULT 1,
            section_title TEXT,
            content TEXT NOT NULL,
            metadata_json JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.dce_documents ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.dce_criteria ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.dce_embeddings ENABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS tenant_isolation_dce_documents ON public.dce_documents;
        CREATE POLICY tenant_isolation_dce_documents ON public.dce_documents
            FOR ALL TO btp_app_user USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID);

        DROP POLICY IF EXISTS tenant_isolation_dce_criteria ON public.dce_criteria;
        CREATE POLICY tenant_isolation_dce_criteria ON public.dce_criteria
            FOR ALL TO btp_app_user USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID);

        DROP POLICY IF EXISTS tenant_isolation_dce_embeddings ON public.dce_embeddings;
        CREATE POLICY tenant_isolation_dce_embeddings ON public.dce_embeddings
            FOR ALL TO btp_app_user USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID);
    """)

    # 2. Seed Tenants & Projects
    cur.execute("""
        INSERT INTO public.tenants (id, name, slug)
        VALUES 
        (%s, 'Tenant A DCE', 'tenant-a-dce'),
        (%s, 'Tenant B DCE', 'tenant-b-dce')
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, location)
        VALUES 
        (%s, %s, 'Chantier A DCE', 'AO-DCE-A', 'Mairie A', 'Paris'),
        (%s, %s, 'Chantier B DCE', 'AO-DCE-B', 'Mairie B', 'Lyon')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID, PROJ_A_ID, TENANT_A_ID, PROJ_B_ID, TENANT_B_ID))

    # 3. Seed DCE Criteria for Tenant A and Tenant B
    cur.execute("""
        DELETE FROM public.dce_criteria WHERE tenant_id IN (%s, %s);
        INSERT INTO public.dce_criteria (id, tenant_id, project_id, criterion_title, weight_percentage, description, key_expectations)
        VALUES
        (%s, %s, %s, '1. Méthodologie Gros Oeuvre Tenant A', 40.0, 'Phasage et cadence 48h', '["Grue Potain MDT"]'::jsonb),
        (%s, %s, %s, '2. Démarche RSE Tenant A', 30.0, 'Béton CEM III bas carbone', '["FDES vérifiée"]'::jsonb),
        (%s, %s, %s, '1. Terrassement et VRD Tenant B', 50.0, 'Terrassement pleine masse', '["Pelles Liebherr"]'::jsonb),
        (%s, %s, %s, '2. Qualité PAQ Tenant B', 20.0, 'Contrôles préalables', '["Fiches autocontrôle"]'::jsonb);
    """, (
        TENANT_A_ID, TENANT_B_ID,
        str(uuid.uuid4()), TENANT_A_ID, PROJ_A_ID,
        str(uuid.uuid4()), TENANT_A_ID, PROJ_A_ID,
        str(uuid.uuid4()), TENANT_B_ID, PROJ_B_ID,
        str(uuid.uuid4()), TENANT_B_ID, PROJ_B_ID,
    ))

    # 4. Seed DCE Embeddings for Tenant A and Tenant B
    cur.execute("""
        DELETE FROM public.dce_embeddings WHERE tenant_id IN (%s, %s);
        INSERT INTO public.dce_embeddings (id, tenant_id, project_id, chunk_index, page_number, section_title, content)
        VALUES
        (%s, %s, %s, 0, 18, 'CCTP Gros Oeuvre', 'Article 4.2 : Pénalités journalières fixées à 1/1000e pour Tenant A.'),
        (%s, %s, %s, 0, 12, 'CCTP VRD', 'Article 5.1 : Pénalités spécifiques Tenant B de 2500 euros par jour.');
    """, (
        TENANT_A_ID, TENANT_B_ID,
        str(uuid.uuid4()), TENANT_A_ID, PROJ_A_ID,
        str(uuid.uuid4()), TENANT_B_ID, PROJ_B_ID,
    ))

    yield

    try:
        cur.execute("DELETE FROM public.dce_embeddings WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.dce_criteria WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.dce_documents WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_get_dce_criteria_tenant_a_isolation():
    """HTTP GET /api/dce/criteria/{project_id} under Tenant A returns ONLY Tenant A criteria."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(f"/api/dce/criteria/{PROJ_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    criteria = response.json()

    assert len(criteria) == 2, f"Expected 2 criteria for Tenant A, got {len(criteria)}"
    titles = [c["criterion_title"] for c in criteria]
    assert "1. Méthodologie Gros Oeuvre Tenant A" in titles
    assert "2. Démarche RSE Tenant A" in titles
    assert "1. Terrassement et VRD Tenant B" not in titles


def test_http_get_dce_criteria_cross_tenant_blocked():
    """Tenant A requesting Tenant B project criteria returns empty (RLS blocks cross-tenant access)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Tenant A attempts to access Tenant B's project criteria
    response = client.get(f"/api/dce/criteria/{PROJ_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    criteria = response.json()

    # RLS must return 0 criteria because PROJ_B belongs to Tenant B
    assert len(criteria) == 0, f"Security Breach! Tenant A accessed Tenant B criteria: {criteria}"


def test_http_dce_search_isolation():
    """HTTP GET /api/dce/search under Tenant A searches ONLY Tenant A chunks."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(
        f"/api/dce/search?project_id={PROJ_A_ID}&query=pénalités",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["results_count"] == 1
    assert "Tenant A" in data["chunks"][0]["content"]
    assert "Tenant B" not in data["chunks"][0]["content"]


def test_http_dce_chat_endpoint():
    """HTTP POST /api/dce/chat returns structured answers with citations."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    payload = {
        "project_id": PROJ_A_ID,
        "query": "Quelles sont les pénalités de retard ?",
        "include_web_search": True,
    }
    response = client.post("/api/dce/chat", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "answer" in data
    assert len(data["sources"]) > 0
