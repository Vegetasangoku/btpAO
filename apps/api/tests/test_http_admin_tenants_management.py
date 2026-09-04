"""
HTTP Tests for Admin Tenant Management API (GET /admin/tenants, POST /admin/tenants).
Validates:
1. Strict platform_admin protection: 401 without auth, 403 for regular tenant users/owners on both endpoints.
2. Platform admin can create a new tenant with siret, email, plan, country_code, and custom routing.
3. Created tenant immediately appears in GET /admin/tenants with live user and project counts.
4. Extensible country code handling (e.g. BE / FR) during tenant provisioning.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"

TENANT_TEST_ID = "11111111-1111-1111-1111-111111111111"
REGULAR_USER_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


def create_jwt(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def setup_postgres_admin_test_data():
    """Seeds test database and cleans up created admin test tenants."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # Ensure country profiles
        cur.execute("""
            INSERT INTO public.country_regulatory_profiles (
                country_code, country_name, technical_standards_reference,
                environmental_regulation, public_procurement_regime,
                recognized_qualifications, waste_tracking_regime,
                safety_plan_regime, is_active
            ) VALUES (
                'FR', 'France', 'DTU / Eurocodes / Normes NF BTP',
                'RE2020 / FDES / Base INIES', 'Code de la Commande Publique & CCAG Travaux',
                '["QUALIBAT", "FNTP", "QUALIFELEC", "OPQIBI"]'::jsonb,
                'Trackdéchets / BSD dématérialisé (Bordereau de Suivi des Déchets)',
                'PPSPS (Plan Particulier de Sécurité et de Protection de la Santé) & PAQ',
                true
            ) ON CONFLICT (country_code) DO NOTHING;
        """)

        # Clean existing test tenants
        cur.execute("DELETE FROM public.tenant_subscriptions WHERE tenant_id IN (SELECT id FROM public.tenants WHERE slug LIKE 'test-admin-tenant-%' OR name LIKE 'Test Admin %');")
        cur.execute("DELETE FROM public.tenants WHERE slug LIKE 'test-admin-tenant-%' OR name LIKE 'Test Admin %';")

        yield
    finally:
        cur.execute("RESET ROLE;")
        cur.execute("DELETE FROM public.tenant_subscriptions WHERE tenant_id IN (SELECT id FROM public.tenants WHERE slug LIKE 'test-admin-tenant-%' OR name LIKE 'Test Admin %');")
        cur.execute("DELETE FROM public.tenants WHERE slug LIKE 'test-admin-tenant-%' OR name LIKE 'Test Admin %';")
        cur.close()
        conn.close()


def test_admin_tenants_unauthenticated_returns_401():
    """Unauthenticated requests to /admin/tenants must return 401."""
    client = TestClient(app)

    # GET /admin/tenants
    get_res = client.get("/api/admin/tenants")
    assert get_res.status_code == 401, f"Expected 401 on GET, got {get_res.status_code}"

    # POST /admin/tenants
    post_res = client.post("/api/admin/tenants", json={"name": "Test Tenant Unauth"})
    assert post_res.status_code == 401, f"Expected 401 on POST, got {post_res.status_code}"


def test_admin_tenants_forbidden_for_regular_tenant_user():
    """Regular tenant members and owners (non-platform-admins) must receive 403 on /admin/tenants."""
    regular_token = create_jwt({
        "sub": REGULAR_USER_ID,
        "email": "directeur@eiffabtp.fr",
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"tenant_id": TENANT_TEST_ID, "role": "owner"},
        "user_metadata": {"tenant_id": TENANT_TEST_ID, "role": "owner"},
    })

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {regular_token}"}

    # 1. GET /admin/tenants must be rejected with 403
    get_res = client.get("/api/admin/tenants", headers=headers)
    assert get_res.status_code == 403, f"Expected 403 for non-platform-admin, got {get_res.status_code}: {get_res.text}"

    # 2. POST /admin/tenants must be rejected with 403
    post_res = client.post(
        "/api/admin/tenants",
        headers=headers,
        json={"name": "Attaque Création Tenant", "plan": "enterprise"}
    )
    assert post_res.status_code == 403, f"Expected 403 for non-platform-admin on POST, got {post_res.status_code}: {post_res.text}"


def test_platform_admin_create_and_list_tenants_full_lifecycle():
    """
    Platform admin can:
    1. Call POST /admin/tenants to create a new client tenant with SIRET, email, plan, and routing.
    2. Call GET /admin/tenants and verify the newly created tenant appears in the list with all fields.
    """
    admin_token = create_jwt({
        "sub": ADMIN_USER_ID,
        "email": "charbelakl@gmail.com",
        "aud": "authenticated",
        "role": "authenticated",
        "is_platform_admin": True,
        "app_metadata": {"role": "platform_admin", "is_platform_admin": True},
        "user_metadata": {"role": "platform_admin", "is_platform_admin": True},
    })

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {admin_token}"}
    suffix = uuid.uuid4().hex[:6]
    test_name = f"Test Admin Eiffage {suffix}"
    test_slug = f"test-admin-tenant-{suffix}"

    test_siret = f"444{uuid.uuid4().int % 100000000000:011d}"

    payload = {
        "name": test_name,
        "slug": test_slug,
        "siret": test_siret,
        "contact_email": f"contact-{suffix}@eiffage-med.fr",
        "plan": "enterprise",
        "country_code": "FR",
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-5",
        "model_routing_config": {
            "extraction_gonogo": {"provider": "Anthropic", "model": "claude-sonnet-5"},
            "redaction_memoire": {"provider": "Anthropic", "model": "claude-sonnet-5"},
            "analyse_prix": {"provider": "Mistral AI", "model": "mistral-large-2407"}
        }
    }

    # 1. Create tenant via POST /admin/tenants
    create_res = client.post("/api/admin/tenants", headers=headers, json=payload)
    assert create_res.status_code == 200, f"Expected 200 on creation, got {create_res.status_code}: {create_res.text}"
    
    created_data = create_res.json()
    assert created_data["name"] == test_name
    assert created_data["slug"] == test_slug
    assert created_data["plan"] == "enterprise"
    assert created_data["country_code"] == "FR"
    assert created_data["siret"] == test_siret
    assert created_data["contact_email"] == f"contact-{suffix}@eiffage-med.fr"
    assert created_data["monthly_limit"] == 50
    created_id = created_data["id"]

    # 2. List all tenants via GET /admin/tenants and verify created tenant is present
    list_res = client.get("/api/admin/tenants", headers=headers)
    assert list_res.status_code == 200, f"Expected 200 on list, got {list_res.status_code}: {list_res.text}"
    
    tenants_list = list_res.json()
    assert isinstance(tenants_list, list)
    assert len(tenants_list) > 0

    matching = [t for t in tenants_list if t["id"] == created_id]
    assert len(matching) == 1, f"Created tenant ID {created_id} not found in GET /admin/tenants list!"
    
    item = matching[0]
    assert item["name"] == test_name
    assert item["slug"] == test_slug
    assert item["plan"] == "enterprise"
    assert item["country_code"] == "FR"
    assert item["siret"] == test_siret
    assert item["contact_email"] == f"contact-{suffix}@eiffage-med.fr"
    assert "users_count" in item
    assert "active_projects_count" in item
    assert item["monthly_limit"] == 50


def test_platform_admin_create_belgium_tenant():
    """Platform admin can create an international tenant (e.g. Belgium) without hardcoded French defaults."""
    admin_token = create_jwt({
        "sub": ADMIN_USER_ID,
        "email": "charbelakl@gmail.com",
        "aud": "authenticated",
        "role": "authenticated",
        "is_platform_admin": True,
        "app_metadata": {"role": "platform_admin", "is_platform_admin": True},
        "user_metadata": {"role": "platform_admin", "is_platform_admin": True},
    })

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {admin_token}"}
    suffix = uuid.uuid4().hex[:6]
    test_name = f"Test Admin Bespix Belgique {suffix}"
    test_slug = f"test-admin-tenant-bespix-{suffix}"

    payload = {
        "name": test_name,
        "slug": test_slug,
        "contact_email": f"direction-{suffix}@bespix.be",
        "plan": "pro",
        "country_code": "BE",
    }

    create_res = client.post("/api/admin/tenants", headers=headers, json=payload)
    assert create_res.status_code == 200, f"Expected 200, got {create_res.status_code}: {create_res.text}"
    
    data = create_res.json()
    assert data["name"] == test_name
    assert data["country_code"] == "BE"
    assert data["plan"] == "pro"
    assert data["monthly_limit"] == 15
