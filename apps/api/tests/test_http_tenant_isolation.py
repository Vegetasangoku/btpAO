"""
Real HTTP Integration Test for Multi-Tenant Isolation via SQLAlchemy 2 Async + PostgreSQL RLS.
Every test executes strictly through the production FastAPI HTTP pipeline (TestClient -> get_db -> SET ROLE btp_app_user -> set_config).

Proves:
1. Real HTTP GET /api/projects WITHOUT .where() clause (bare select via RLS alone) returns ONLY Tenant A projects.
2. Real HTTP GET /api/projects WITH .where() clause (defense-in-depth) returns ONLY Tenant A projects.
3. Real HTTP GET /api/projects under Tenant B JWT returns ONLY Tenant B projects.
4. Real HTTP GET /api/projects with spoofed X-Tenant-ID header strictly ignores the header.
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
def setup_postgres_database():
    """Provisions tables, btp_app_user role, RLS policies and seeds test projects directly in PostgreSQL."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Ensure extensions, role, and tables exist
    cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'btp_app_user') THEN
                CREATE ROLE btp_app_user NOLOGIN;
            END IF;
        END
        $$;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.tenants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL DEFAULT 'enterprise',
            s3_bucket_prefix TEXT,
            branding_config JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS public.users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'member',
            avatar_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS public.projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            reference_code TEXT NOT NULL,
            client_name TEXT NOT NULL,
            location TEXT,
            lot_number TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            budget_estimate NUMERIC(15, 2),
            submission_deadline TIMESTAMPTZ,
            scoring_notes JSONB DEFAULT '{"technical_weight": 60, "price_weight": 40}'::jsonb,
            metadata_json JSONB DEFAULT '{}'::jsonb,
            created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT USAGE ON SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_projects ON public.projects;
        CREATE POLICY tenant_isolation_projects ON public.projects
            FOR ALL
            TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );
    """)

    # 2. Clean previous test records
    cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("DELETE FROM public.users WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))

    # 3. Seed Tenants
    cur.execute("""
        INSERT INTO public.tenants (id, name, slug)
        VALUES 
        (%s, 'EiffaBTP Construction SAS', 'eiffabtp-test-a'),
        (%s, 'BouygBTP Nord SAS', 'bouygbtp-test-b')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID))

    # 4. Seed Users
    cur.execute("""
        INSERT INTO public.users (id, tenant_id, email, full_name, role)
        VALUES 
        (%s, %s, 'user.a@eiffabtp.fr', 'Jean-Marc Alibert', 'conducteur_travaux'),
        (%s, %s, 'user.b@bouygbtp.fr', 'Thomas Renaud', 'conducteur_travaux')
        ON CONFLICT (id) DO NOTHING;
    """, (USER_A_ID, TENANT_A_ID, USER_B_ID, TENANT_B_ID))

    # 5. Seed Projects for Tenant A and Tenant B
    cur.execute("""
        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, location, lot_number, status, budget_estimate, created_by)
        VALUES 
        (%s, %s, 'Projet A1 : Construction École Maternelle', 'AO-2026-A1', 'Mairie de Saint-Denis', 'Saint-Denis (93)', 'Lot 01 Gros Oeuvre', 'review', 2400000.0, %s),
        (%s, %s, 'Projet A2 : Réhabilitation Gymnase HQE', 'AO-2026-A2', 'Ville de Paris', 'Paris 18e', 'Lot 02 Charpente', 'draft', 1850000.0, %s),
        (%s, %s, 'Projet B1 : Hôpital Régional Grand Lyon', 'AO-2026-B1', 'Métropole de Lyon', 'Lyon (69)', 'Lot 03 VRD', 'review', 4200000.0, %s),
        (%s, %s, 'Projet B2 : Complexe Aquatique Lille', 'AO-2026-B2', 'Métropole Européenne de Lille', 'Lille (59)', 'Lot 01 Gros Oeuvre', 'draft', 3100000.0, %s);
    """, (
        str(uuid.uuid4()), TENANT_A_ID, USER_A_ID,
        str(uuid.uuid4()), TENANT_A_ID, USER_A_ID,
        str(uuid.uuid4()), TENANT_B_ID, USER_B_ID,
        str(uuid.uuid4()), TENANT_B_ID, USER_B_ID,
    ))

    yield

    # Cleanup test data after module execution
    try:
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.users WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_get_projects_bare_select_without_where_clause_proves_rls():
    """
    PROVES POSTGRESQL RLS AS THE REAL GUARDFEUL:
    Calls real HTTP GET /api/projects via TestClient with the application .where() clause DISABLED.
    The real get_db() dependency sets SET ROLE btp_app_user and SET LOCAL app.current_tenant_id.
    Proves that even with NO .where() in Python code, PostgreSQL RLS alone returns ONLY Tenant A projects.
    """
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Disable application-level .where() clause
    settings.DISABLE_WHERE_CLAUSE_FOR_RLS_TEST = True
    try:
        response = client.get("/api/projects", headers={"Authorization": f"Bearer {token_a}"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        projects = response.json()

        # Database RLS alone MUST guarantee 0 leakage
        assert len(projects) == 2, f"Expected exactly 2 projects from RLS, got {len(projects)}"
        for proj in projects:
            assert proj["tenant_id"] == TENANT_A_ID, f"Security Breach! Project {proj['id']} returned under wrong tenant"
            assert proj["tenant_id"] != TENANT_B_ID, "Security Breach! Tenant B project leaked to Tenant A"

        titles = [p["title"] for p in projects]
        assert "Projet A1 : Construction École Maternelle" in titles
        assert "Projet A2 : Réhabilitation Gymnase HQE" in titles
        assert "Projet B1 : Hôpital Régional Grand Lyon" not in titles
        assert "Projet B2 : Complexe Aquatique Lille" not in titles
    finally:
        # Re-enable defense-in-depth .where() clause
        settings.DISABLE_WHERE_CLAUSE_FOR_RLS_TEST = False


def test_http_get_projects_with_where_clause_defense_in_depth():
    """
    PROVES DEFENSE IN DEPTH:
    Calls real HTTP GET /api/projects via TestClient with explicit .where() clause enabled.
    Returns strictly Tenant A projects.
    """
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Application-level .where() clause enabled (production default)
    assert settings.DISABLE_WHERE_CLAUSE_FOR_RLS_TEST is False

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    projects = response.json()

    assert len(projects) == 2, f"Expected exactly 2 projects for Tenant A, got {len(projects)}"
    for proj in projects:
        assert proj["tenant_id"] == TENANT_A_ID
        assert proj["tenant_id"] != TENANT_B_ID

    titles = [p["title"] for p in projects]
    assert "Projet A1 : Construction École Maternelle" in titles
    assert "Projet A2 : Réhabilitation Gymnase HQE" in titles
    assert "Projet B1 : Hôpital Régional Grand Lyon" not in titles
    assert "Projet B2 : Complexe Aquatique Lille" not in titles


def test_http_get_projects_tenant_b_isolation():
    """HTTP GET /api/projects with Tenant B JWT must return ONLY Tenant B projects from PostgreSQL."""
    client = TestClient(app)
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    projects = response.json()

    assert len(projects) == 2, f"Expected exactly 2 projects for Tenant B, got {len(projects)}"
    for proj in projects:
        assert proj["tenant_id"] == TENANT_B_ID, f"Security Breach! Project {proj['id']} returned under wrong tenant"
        assert proj["tenant_id"] != TENANT_A_ID, "Security Breach! Tenant A project leaked to Tenant B"

    titles = [p["title"] for p in projects]
    assert "Projet B1 : Hôpital Régional Grand Lyon" in titles
    assert "Projet B2 : Complexe Aquatique Lille" in titles
    assert "Projet A1 : Construction École Maternelle" not in titles
    assert "Projet A2 : Réhabilitation Gymnase HQE" not in titles


def test_http_get_projects_tenant_spoofing_header_ignored():
    """HTTP GET /api/projects with Tenant A JWT + spoofed X-Tenant-ID: Tenant B must remain strictly bound to Tenant A."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    headers = {
        "Authorization": f"Bearer {token_a}",
        "X-Tenant-ID": TENANT_B_ID,  # Attacker attempts to spoof Tenant B
    }

    response = client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    projects = response.json()

    assert len(projects) == 2, f"Expected exactly 2 projects for Tenant A, got {len(projects)}"
    for proj in projects:
        assert proj["tenant_id"] == TENANT_A_ID
        assert proj["tenant_id"] != TENANT_B_ID
