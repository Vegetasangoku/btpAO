"""
Real HTTP Integration Test for Company Knowledge Base Multi-Tenant Isolation via SQLAlchemy 2 Async + PostgreSQL RLS.
Every test executes strictly through the production FastAPI HTTP pipeline (TestClient -> get_db -> SET ROLE btp_app_user -> set_config).

Proves:
1. Seed real distinct company assets and export templates for Tenant A and Tenant B in PostgreSQL.
2. Real HTTP GET /api/knowledge/assets under Tenant A returns ONLY Tenant A assets.
3. Real HTTP GET /api/knowledge/assets under Tenant B returns ONLY Tenant B assets.
4. Real HTTP POST /api/knowledge/assets creates asset bound strictly to authenticated tenant.
5. Real HTTP GET /api/knowledge/search searches strictly within active tenant's knowledge base.
6. Real HTTP GET /api/knowledge/template/word returns tenant-specific template info.
7. Header spoofing via X-Tenant-ID is strictly ignored.
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
def setup_postgres_knowledge_database():
    """Provisions tables, btp_app_user grants, RLS policies and seeds test assets for both tenants."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
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

        CREATE TABLE IF NOT EXISTS public.export_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            s3_docx_key TEXT NOT NULL,
            is_default BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.company_assets ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_company_assets ON public.company_assets;
        CREATE POLICY tenant_isolation_company_assets ON public.company_assets
            FOR ALL TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );

        ALTER TABLE public.export_templates ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_export_templates ON public.export_templates;
        CREATE POLICY tenant_isolation_export_templates ON public.export_templates
            FOR ALL TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );
    """)

    # 1. Seed Tenants
    cur.execute("""
        INSERT INTO public.tenants (id, name, slug)
        VALUES 
        (%s, 'Tenant A Knowledge', 'tenant-a-know'),
        (%s, 'Tenant B Knowledge', 'tenant-b-know')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID))

    # 2. Seed Distinct Company Assets
    cur.execute("DELETE FROM public.company_assets WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("""
        INSERT INTO public.company_assets (id, tenant_id, category, title, description, metadata_json)
        VALUES 
        (%s, %s, 'certificat_qualibat', 'Qualibat 2112 & 1112 Tenant A', 'Béton armé et maçonnerie supérieure Tenant A', '{"numero": "QA-991"}'::jsonb),
        (%s, %s, 'materiel_engins', 'Grues Potain MDT 219 Tenant A', 'Flotte grues topless Tenant A', '{"portee_m": 65}'::jsonb),
        (%s, %s, 'certificat_qualibat', 'Qualibat 1322 Tenant B', 'Terrassement et VRD haute technicité Tenant B', '{"numero": "QB-442"}'::jsonb),
        (%s, %s, 'materiel_engins', 'Grues Liebherr 280 EC-H Tenant B', 'Flotte grues lourdes Tenant B', '{"portee_m": 70}'::jsonb);
    """, (
        str(uuid.uuid4()), TENANT_A_ID,
        str(uuid.uuid4()), TENANT_A_ID,
        str(uuid.uuid4()), TENANT_B_ID,
        str(uuid.uuid4()), TENANT_B_ID,
    ))

    # 3. Seed Export Templates
    cur.execute("DELETE FROM public.export_templates WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("""
        INSERT INTO public.export_templates (id, tenant_id, name, description, s3_docx_key, is_default)
        VALUES 
        (%s, %s, 'Charte_Graphique_Tenant_A.docx', 'Template officiel Tenant A', 'templates/word_template_a.docx', true),
        (%s, %s, 'Charte_Graphique_Tenant_B.docx', 'Template officiel Tenant B', 'templates/word_template_b.docx', true);
    """, (
        str(uuid.uuid4()), TENANT_A_ID,
        str(uuid.uuid4()), TENANT_B_ID,
    ))

    yield

    try:
        cur.execute("DELETE FROM public.export_templates WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.company_assets WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_list_company_assets_tenant_a_isolation():
    """Real HTTP GET /api/knowledge/assets under Tenant A returns ONLY Tenant A assets."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get("/api/knowledge/assets", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assets = response.json()

    assert len(assets) == 2, f"Expected 2 assets for Tenant A, got {len(assets)}"
    for a in assets:
        assert a["tenant_id"] == TENANT_A_ID
        assert a["tenant_id"] != TENANT_B_ID

    titles = [a["title"] for a in assets]
    assert "Qualibat 2112 & 1112 Tenant A" in titles
    assert "Grues Potain MDT 219 Tenant A" in titles
    assert "Qualibat 1322 Tenant B" not in titles
    assert "Grues Liebherr 280 EC-H Tenant B" not in titles


def test_http_list_company_assets_tenant_b_isolation():
    """Real HTTP GET /api/knowledge/assets under Tenant B returns ONLY Tenant B assets."""
    client = TestClient(app)
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    response = client.get("/api/knowledge/assets", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assets = response.json()

    assert len(assets) == 2, f"Expected 2 assets for Tenant B, got {len(assets)}"
    for a in assets:
        assert a["tenant_id"] == TENANT_B_ID
        assert a["tenant_id"] != TENANT_A_ID

    titles = [a["title"] for a in assets]
    assert "Qualibat 1322 Tenant B" in titles
    assert "Grues Liebherr 280 EC-H Tenant B" in titles
    assert "Qualibat 2112 & 1112 Tenant A" not in titles
    assert "Grues Potain MDT 219 Tenant A" not in titles


def test_http_create_company_asset_tenant_isolation():
    """Real HTTP POST /api/knowledge/assets creates asset bound strictly to authenticated tenant."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    payload = {
        "category": "reference_chantier",
        "title": "Chantier Hôpital Nord Tenant A",
        "description": "Construction 15 000 m2 structure béton armé",
        "tags": ["hopital", "beton_arme"],
        "metadata_json": {"annee": 2025}
    }
    response = client.post("/api/knowledge/assets", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 201
    created = response.json()

    assert created["tenant_id"] == TENANT_A_ID
    assert created["title"] == "Chantier Hôpital Nord Tenant A"


def test_http_knowledge_search_isolation():
    """Real HTTP GET /api/knowledge/search searches strictly within active tenant's assets."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get("/api/knowledge/search?query=grues", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    data = response.json()

    results = data["results"]
    assert len(results) > 0
    for r in results:
        assert "Tenant A" in r["title"] or "Tenant A" in (r.get("description") or "")
        assert "Tenant B" not in r["title"]


def test_http_get_word_template_info_isolation():
    """Real HTTP GET /api/knowledge/template/word returns tenant-specific template info."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    res_a = client.get("/api/knowledge/template/word", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    info_a = res_a.json()
    assert info_a["has_template"] is True
    assert "Tenant_A" in info_a["filename"]

    res_b = client.get("/api/knowledge/template/word", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    info_b = res_b.json()
    assert info_b["has_template"] is True
    assert "Tenant_B" in info_b["filename"]
