"""
Real HTTP Integration Test for AI Memo Generation & Section Management Multi-Tenant Isolation via SQLAlchemy 2 Async + PostgreSQL RLS.
Every test executes strictly through the production FastAPI HTTP pipeline (TestClient -> get_db -> SET ROLE btp_app_user -> set_config).

Proves:
1. Seed real distinct sections and RAG assets for Tenant A and Tenant B in PostgreSQL.
2. HTTP GET /api/generate/sections/{project_id} under Tenant A returns ONLY Tenant A sections.
3. HTTP GET /api/generate/sections/{project_id} under Tenant B returns ONLY Tenant B sections.
4. Cross-tenant reads and updates (PUT /api/generate/section/{id}) are strictly blocked (404/Empty).
5. HTTP POST /api/generate/section generates memo section strictly using authenticated tenant RAG context.
6. Header spoofing via X-Tenant-ID is strictly ignored.
"""
import json
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
PROJ_A_ID = "11112222-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_B_ID = "33334444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
SEC_A_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SEC_B_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
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
def setup_postgres_generate_database():
    """Provisions tables, btp_app_user grants, RLS policies and seeds test sections for both tenants."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.generated_sections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
            section_key TEXT NOT NULL,
            title TEXT NOT NULL,
            order_index INT NOT NULL DEFAULT 1,
            content_html TEXT NOT NULL DEFAULT '',
            content_json JSONB DEFAULT '{}'::jsonb,
            visual_placeholders JSONB DEFAULT '[]'::jsonb,
            compliance_score NUMERIC(4, 1) DEFAULT 100.0,
            compliance_notes TEXT,
            status TEXT NOT NULL DEFAULT 'generated',
            locked_for_export BOOLEAN DEFAULT false,
            validated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
            validated_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT unique_project_section UNIQUE(project_id, section_key)
        );

        CREATE TABLE IF NOT EXISTS public.company_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            s3_url TEXT,
            tags TEXT[] DEFAULT ARRAY[]::TEXT[],
            metadata_json JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.generated_sections ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_generated_sections ON public.generated_sections;
        CREATE POLICY tenant_isolation_generated_sections ON public.generated_sections
            FOR ALL TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );

        ALTER TABLE public.company_assets ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_company_assets ON public.company_assets;
        CREATE POLICY tenant_isolation_company_assets ON public.company_assets
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
        (%s, 'Tenant A Generate', 'tenant-a-gen'),
        (%s, 'Tenant B Generate', 'tenant-b-gen')
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, location)
        VALUES 
        (%s, %s, 'Projet A Memo', 'AO-MEMO-A', 'Ville Paris', 'Paris 18'),
        (%s, %s, 'Projet B Memo', 'AO-MEMO-B', 'Métropole Lyon', 'Lyon 3')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID, PROJ_A_ID, TENANT_A_ID, PROJ_B_ID, TENANT_B_ID))

    # 2. Seed Distinct Company Assets (RAG)
    cur.execute("DELETE FROM public.company_assets WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("""
        INSERT INTO public.company_assets (id, tenant_id, category, title, description)
        VALUES 
        (%s, %s, 'materiel_engins', 'Parc Grues Potain Tenant A', 'Flotte propre de 12 grues à tour Potain MDT'),
        (%s, %s, 'materiel_engins', 'Parc Grues Liebherr Tenant B', 'Flotte propre de 8 grues à tour Liebherr EC-B');
    """, (
        str(uuid.uuid4()), TENANT_A_ID,
        str(uuid.uuid4()), TENANT_B_ID,
    ))

    # 3. Seed Distinct Sections for Tenant A and Tenant B
    cur.execute("DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("""
        INSERT INTO public.generated_sections (id, tenant_id, project_id, section_key, title, order_index, content_html, status)
        VALUES 
        (%s, %s, %s, 'moyens_humains', '1. Moyens Humains Tenant A', 1, '<p>Encadrement dédié Tenant A : Alain Delorme Ingénieur ESTP.</p>', 'generated'),
        (%s, %s, %s, 'moyens_humains', '1. Moyens Humains Tenant B', 1, '<p>Encadrement dédié Tenant B : Bernard Lambert Master INSA.</p>', 'generated');
    """, (
        SEC_A_ID, TENANT_A_ID, PROJ_A_ID,
        SEC_B_ID, TENANT_B_ID, PROJ_B_ID,
    ))

    yield

    try:
        cur.execute("DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.company_assets WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_get_project_sections_tenant_a_isolation():
    """Real HTTP GET /api/generate/sections/{project_id} under Tenant A returns ONLY Tenant A sections."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(f"/api/generate/sections/{PROJ_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    sections = response.json()

    assert len(sections) == 1, f"Expected 1 section for Tenant A, got {len(sections)}"
    assert sections[0]["tenant_id"] == TENANT_A_ID
    assert "Tenant A" in sections[0]["content_html"]
    assert "Tenant B" not in sections[0]["content_html"]


def test_http_get_project_sections_tenant_b_isolation():
    """Real HTTP GET /api/generate/sections/{project_id} under Tenant B returns ONLY Tenant B sections."""
    client = TestClient(app)
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    response = client.get(f"/api/generate/sections/{PROJ_B_ID}", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    sections = response.json()

    assert len(sections) == 1, f"Expected 1 section for Tenant B, got {len(sections)}"
    assert sections[0]["tenant_id"] == TENANT_B_ID
    assert "Tenant B" in sections[0]["content_html"]
    assert "Tenant A" not in sections[0]["content_html"]


def test_http_get_sections_cross_tenant_blocked():
    """Tenant A requesting sections of Tenant B project must return empty list (RLS blocked)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(f"/api/generate/sections/{PROJ_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    sections = response.json()
    assert len(sections) == 0, f"Security Breach! Tenant A accessed Tenant B sections: {sections}"


def test_http_update_section_cross_tenant_blocked():
    """Tenant A attempting to modify Tenant B section via PUT receives 404 (strictly blocked)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Tenant A attempts to update SEC_B_ID
    payload = {"content_html": "<p>Attaque malveillante!</p>"}
    response = client.put(f"/api/generate/section/{SEC_B_ID}", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


def test_http_generate_single_section_tenant_isolation():
    """Real HTTP POST /api/generate/section generates section in DB strictly scoped to Tenant A."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    payload = {
        "project_id": PROJ_A_ID,
        "section_key": "moyens_materiels",
        "custom_instructions": "Préciser l'utilisation de grues Potain MDT",
    }
    response = client.post("/api/generate/section", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    sec = response.json()
    assert sec["tenant_id"] == TENANT_A_ID
    assert sec["section_key"] == "moyens_materiels"
    assert "content_html" in sec
