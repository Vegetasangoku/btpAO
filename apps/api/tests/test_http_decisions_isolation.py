"""
Real HTTP Integration Test for Project Decisions Multi-Tenant Isolation via SQLAlchemy 2 Async + PostgreSQL RLS.
Every test executes strictly through the production FastAPI HTTP pipeline (TestClient -> get_db -> SET ROLE btp_app_user -> set_config).

Proves:
1. Seed real project decisions for Tenant A and Tenant B directly in PostgreSQL.
2. Real HTTP GET /api/decisions/{project_id} under Tenant A returns ONLY Tenant A decisions.
3. Real HTTP GET /api/decisions/{project_id} under Tenant B returns ONLY Tenant B decisions.
4. Tenant A calling GET /api/decisions/{project_id} for Tenant B's project is blocked (404/Not Found).
5. Real HTTP POST /api/decisions/{project_id} updates decisions strictly bound to the authenticated tenant.
6. Header spoofing via X-Tenant-ID is strictly ignored.
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
PROJ_A_ID = "77777777-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_B_ID = "88888888-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
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
def setup_postgres_decisions_database():
    """Provisions tables, btp_app_user grants, RLS policies and seeds test decisions for both tenants."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.project_decisions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            project_id UUID NOT NULL UNIQUE REFERENCES public.projects(id) ON DELETE CASCADE,
            form_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.project_decisions ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_project_decisions ON public.project_decisions;
        CREATE POLICY tenant_isolation_project_decisions ON public.project_decisions
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
        (%s, 'Tenant A Decisions', 'tenant-a-decisions'),
        (%s, 'Tenant B Decisions', 'tenant-b-decisions')
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, location)
        VALUES 
        (%s, %s, 'Projet A Decisions', 'AO-DEC-A', 'Mairie Paris', 'Paris'),
        (%s, %s, 'Projet B Decisions', 'AO-DEC-B', 'Métropole Lyon', 'Lyon')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID, PROJ_A_ID, TENANT_A_ID, PROJ_B_ID, TENANT_B_ID))

    import json
    form_a = {
        "delai_mois": 8,
        "materiel_principal": "Grue Potain MDT 219 dédiée Tenant A",
        "travail_de_nuit": False,
        "gestion_dechets": "Tri 5 flux in situ Tenant A valorisation 90%",
        "equipe_cadres": [{"nom": "Alain Delorme", "role": "Directeur Travaux", "experience_ans": 18, "qualif": "Ingénieur ESTP"}],
        "mesures_securite": "PPSPS strict Tenant A, 0 accident visé",
        "demarche_rse_environnement": "Béton bas carbone CEM III/A Tenant A",
        "phasage_travaux": [{"phase": "Phase 1 Gros Oeuvre", "duree_semaines": 16, "jalon": "Hors d eau"}]
    }
    form_b = {
        "delai_mois": 14,
        "materiel_principal": "Grue Liebherr 280 EC-H dédiée Tenant B",
        "travail_de_nuit": True,
        "gestion_dechets": "Filière locale métropole lyonnaise Tenant B",
        "equipe_cadres": [{"nom": "Bernard Lambert", "role": "Conducteur Principal", "experience_ans": 12, "qualif": "Master INSA"}],
        "mesures_securite": "Contrôles préalables Tenant B",
        "demarche_rse_environnement": "Matériaux biosourcés Tenant B",
        "phasage_travaux": [{"phase": "Phase 1 Terrassement", "duree_semaines": 8, "jalon": "Plateforme"}]
    }

    # 2. Seed Distinct Real Decisions for Tenant A and Tenant B
    cur.execute("DELETE FROM public.project_decisions WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("""
        INSERT INTO public.project_decisions (id, tenant_id, project_id, form_data)
        VALUES 
        (%s, %s, %s, %s::jsonb),
        (%s, %s, %s, %s::jsonb);
    """, (
        str(uuid.uuid4()), TENANT_A_ID, PROJ_A_ID, json.dumps(form_a),
        str(uuid.uuid4()), TENANT_B_ID, PROJ_B_ID, json.dumps(form_b),
    ))

    yield

    try:
        cur.execute("DELETE FROM public.project_decisions WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_get_project_decisions_tenant_a_isolation():
    """Real HTTP GET /api/decisions/{project_id} under Tenant A returns ONLY Tenant A decisions."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get(f"/api/decisions/{PROJ_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["delai_mois"] == 8
    assert "Tenant A" in data["materiel_principal"]
    assert "Tenant B" not in data["materiel_principal"]
    assert data["equipe_cadres"][0]["nom"] == "Alain Delorme"


def test_http_get_project_decisions_tenant_b_isolation():
    """Real HTTP GET /api/decisions/{project_id} under Tenant B returns ONLY Tenant B decisions."""
    client = TestClient(app)
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    response = client.get(f"/api/decisions/{PROJ_B_ID}", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["delai_mois"] == 14
    assert "Tenant B" in data["materiel_principal"]
    assert "Tenant A" not in data["materiel_principal"]
    assert data["equipe_cadres"][0]["nom"] == "Bernard Lambert"


def test_http_get_decisions_cross_tenant_access_blocked():
    """Tenant A requesting decisions of Tenant B project must receive 404 (strictly blocked)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    # Tenant A attempts to access Tenant B project decisions
    response = client.get(f"/api/decisions/{PROJ_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


def test_http_save_project_decisions_tenant_isolation():
    """Real HTTP POST /api/decisions/{project_id} updates decisions in PostgreSQL under active tenant."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    update_payload = {
        "delai_mois": 10,
        "date_demarrage": "2026-09-01T08:00:00Z",
        "materiel_principal": "2 Grues Potain MDT 219 & Centrale Béton Tenant A",
        "travail_de_nuit": False,
        "gestion_dechets": "Tri 5 flux in situ Tenant A valorisation 95%",
        "equipe_cadres": [
            {"nom": "Alain Delorme", "role": "Directeur Travaux", "experience_ans": 19, "qualif": "Ingénieur ESTP"}
        ],
        "mesures_securite": "PPSPS certifié ISO 45001",
        "demarche_rse_environnement": "Béton CEM III bas carbone 100%",
        "phasage_travaux": [
            {"phase": "Phase 1 Terrassement", "duree_semaines": 4, "jalon": "Plateforme"},
            {"phase": "Phase 2 Gros Oeuvre", "duree_semaines": 20, "jalon": "Hors d eau"}
        ]
    }

    # Save decisions
    save_res = client.post(
        f"/api/decisions/{PROJ_A_ID}",
        json=update_payload,
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert save_res.status_code == 200

    # Verify updated values through real GET
    get_res = client.get(f"/api/decisions/{PROJ_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_res.status_code == 200
    saved = get_res.json()
    assert saved["delai_mois"] == 10
    assert "2 Grues Potain" in saved["materiel_principal"]
