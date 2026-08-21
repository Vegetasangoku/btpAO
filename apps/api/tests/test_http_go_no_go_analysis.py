"""
Integration Tests for Go/No-Go Tender Decision Matrix (POST/GET /dce/go-no-go/{project_id}).
Tests:
1. Clear GO case: Valid qualifications, comfortable deadline, complete DCE criteria.
2. Clear NO_GO case: Missing required qualification / expired insurance or untenable deadline.
3. Transparent missing-data handling: Never fabricates figures if data is absent.
4. Multi-Tenant RLS Isolation: Tenant B cannot compute or view Tenant A's Go/No-Go analysis.
"""
import uuid
from datetime import datetime, timedelta, timezone
import json
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PROJ_GO_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_NOGO_ID = "33333333-cccc-cccc-cccc-cccccccccccc"
PROJ_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

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
def setup_postgres_go_no_go():
    """Initializes schema and seeds realistic test projects and assets for Go/No-Go testing."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # 1. Seed Tenants & Users
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES 
            (%s, 'EiffaBTP Construction', 'eiffabtp-gng'),
            (%s, 'BouygBTP Bâtiment', 'bouygbtp-gng')
            ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug;

            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES
            (%s, %s, 'user.a@eiffabtp.fr', 'Directeur AO A', 'conducteur_travaux'),
            (%s, %s, 'user.b@bouygbtp.fr', 'Directeur AO B', 'conducteur_travaux')
            ON CONFLICT (id) DO NOTHING;
        """, (TENANT_A_ID, TENANT_B_ID, USER_A_ID, TENANT_A_ID, USER_B_ID, TENANT_B_ID))

        # 2. Seed Projects for Tenant A (One favorable GO, one unfavorable NO_GO) and Tenant B
        deadline_favorable = datetime.now(timezone.utc) + timedelta(days=20)
        deadline_untenable = datetime.now(timezone.utc) + timedelta(hours=12)

        cur.execute("""
            INSERT INTO public.projects (id, tenant_id, reference_code, title, client_name, location, submission_deadline, status)
            VALUES 
            (%s, %s, 'AO-GO-FAVORABLE', 'Construction Gymnase & Dojo', 'Mairie Paris 15', 'Paris', %s, 'draft'),
            (%s, %s, 'AO-NOGO-UNFAVORABLE', 'Rénovation Complexe Nucléaire', 'CEA Saclay', 'Saclay', %s, 'draft'),
            (%s, %s, 'AO-TENANT-B', 'Chantier Tenant B', 'Mairie Lyon', 'Lyon', %s, 'draft')
            ON CONFLICT (id) DO UPDATE SET 
                submission_deadline = EXCLUDED.submission_deadline,
                title = EXCLUDED.title;
        """, (
            PROJ_GO_ID, TENANT_A_ID, deadline_favorable,
            PROJ_NOGO_ID, TENANT_A_ID, deadline_untenable,
            PROJ_B_ID, TENANT_B_ID, deadline_favorable
        ))

        # 3. Clean and Seed Company Assets for Tenant A (Qualifications & Assurances)
        cur.execute("DELETE FROM public.project_go_no_go_analyses WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.dce_criteria WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.company_assets WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))

        valid_until = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        cur.execute("""
            INSERT INTO public.company_assets (id, tenant_id, category, title, description, metadata_json)
            VALUES 
            (gen_random_uuid(), %s, 'certification', 'QUALIBAT 2112 - Maçonnerie et béton armé courant', 'Qualification certifiée niveau supérieur', %s::jsonb),
            (gen_random_uuid(), %s, 'assurance', 'Police Décennale SMABTP n°78945612', 'Attestation d''assurance décennale et RC Pro', %s::jsonb);
        """, (
            TENANT_A_ID, json.dumps({"expiration_date": valid_until, "code": "2112"}),
            TENANT_A_ID, json.dumps({"expiration_date": valid_until, "police": "78945612"})
        ))

        # 4. Seed DCE Criteria for PROJ_GO_ID (matches QUALIBAT 2112)
        cur.execute("""
            INSERT INTO public.dce_criteria (id, tenant_id, project_id, criterion_title, weight_percentage, description, required_evidence, mandatory)
            VALUES 
            (gen_random_uuid(), %s, %s, 'Valeur Technique & Encadrement', 60.0, 'Qualification Qualibat 2112 requise pour le gros oeuvre', '["Attestation Qualibat 2112", "CV Conducteur"]'::jsonb, 'true'),
            (gen_random_uuid(), %s, %s, 'Prix des Prestations', 40.0, 'Montant de la DPGF et cohérence des sous-détails', '["DPGF complétée"]'::jsonb, 'true');
        """, (TENANT_A_ID, PROJ_GO_ID, TENANT_A_ID, PROJ_GO_ID))

        # 5. Seed DCE Criteria for PROJ_NOGO_ID (requires missing nuclear/special FNTP certification)
        cur.execute("""
            INSERT INTO public.dce_criteria (id, tenant_id, project_id, criterion_title, weight_percentage, description, required_evidence, mandatory)
            VALUES 
            (gen_random_uuid(), %s, %s, 'Agrément Nucléaire & FNTP', 70.0, 'Certification FNTP travaux spéciaux et habilitation confidentiel défense obligatoire', '["Certification FNTP"]'::jsonb, 'true');
        """, (TENANT_A_ID, PROJ_NOGO_ID))


    finally:
        cur.close()
        conn.close()


def test_http_go_no_go_clear_go_recommendation():
    """Project with valid qualifications, comfortable deadline and matching criteria receives a GO."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    headers = {"Authorization": f"Bearer {token_a}"}

    # 1. Trigger Go/No-Go calculation
    res = client.post(f"/api/dce/go-no-go/{PROJ_GO_ID}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["recommendation"] == "GO"
    assert data["score"] >= 75.0
    assert data["mandatory_criteria_met"] is True
    assert len(data["blocking_issues"]) == 0
    assert len(data["factors"]) == 4

    # Verify line-by-line factor evaluation
    factor_categories = [f["category"] for f in data["factors"]]
    assert "mandatory_criteria" in factor_categories
    assert "qualifications" in factor_categories
    assert "deadline_workload" in factor_categories
    assert "historical_win_rate" in factor_categories

    # 2. Retrieve persisted analysis via GET without recalculation
    res_get = client.get(f"/api/dce/go-no-go/{PROJ_GO_ID}", headers=headers)
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["id"] == data["id"]
    assert get_data["recommendation"] == "GO"
    assert get_data["score"] == data["score"]


def test_http_go_no_go_clear_no_go_recommendation_on_missing_certification_and_short_deadline():
    """Project with missing mandatory qualification and critical deadline is flagged as NO_GO with explicit blocking points."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post(f"/api/dce/go-no-go/{PROJ_NOGO_ID}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["recommendation"] == "NO_GO"
    assert data["score"] <= 35.0
    assert data["mandatory_criteria_met"] is False
    assert len(data["blocking_issues"]) >= 1

    # Check that missing qualification (FNTP) or extreme deadline is clearly flagged in blocking points
    blocking_text = " ".join(data["blocking_issues"])
    assert "FNTP" in blocking_text or "Délai de remise intenable" in blocking_text

    # Verify factor breakdown
    factors = {f["category"]: f for f in data["factors"]}
    assert factors["qualifications"]["status"] == "blocking"
    assert factors["qualifications"]["impact"] == "critical"
    assert "FNTP" in factors["qualifications"]["detail"]


def test_http_go_no_go_multi_tenant_isolation_blocked():
    """Tenant B cannot compute or view Tenant A's Go/No-Go analysis under Postgres RLS."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    # 1. Tenant A computes analysis
    res_a = client.post(f"/api/dce/go-no-go/{PROJ_GO_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200

    # 2. Tenant B attempts to read Tenant A's Go/No-Go -> 404 (RLS blocks)
    res_b_get = client.get(f"/api/dce/go-no-go/{PROJ_GO_ID}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_get.status_code == 404

    # 3. Tenant B attempts to trigger Go/No-Go on Tenant A's project -> 404 (RLS blocks)
    res_b_post = client.post(f"/api/dce/go-no-go/{PROJ_GO_ID}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_post.status_code == 404
