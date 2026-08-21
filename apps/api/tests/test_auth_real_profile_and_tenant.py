"""
Test Suite for Real User Profile & Tenant Endpoints (GET /api/auth/me, GET /api/auth/tenant).
Verifies that no hardcoded data is returned and real PostgreSQL records are fetched.
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

TEST_TENANT_ID = "aaaaaaaa-1111-2222-3333-444444444444"
TEST_USER_ID = "bbbbbbbb-1111-2222-3333-444444444444"
TEST_EMAIL = "direction@bouyg-nord.fr"


def create_token(user_id: str, tenant_id: str, email: str, role: str = "owner") -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": role},
        "user_metadata": {"tenant_id": tenant_id, "role": role},
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def setup_real_auth_db_records():
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")
        # Insert real custom tenant
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug, plan, country_code, branding_config)
            VALUES (
                %s,
                'Bouygues Bâtiment Grand Nord',
                'bouygues-batiment-nord',
                'enterprise',
                'FR',
                '{"primary_color": "#e11d48", "secondary_color": "#020617", "company_name": "Bouygues Bâtiment Grand Nord SAS", "header_text": "Mémoire Technique — Pôle Ouvrages d''Art"}'::jsonb
            ) ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                branding_config = EXCLUDED.branding_config;
        """, (TEST_TENANT_ID,))

        # Insert real user in public.users
        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES (%s, %s, %s, 'Claire Dumont', 'owner')
            ON CONFLICT (id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                email = EXCLUDED.email;
        """, (TEST_USER_ID, TEST_TENANT_ID, TEST_EMAIL))

        yield
    finally:
        cur.execute("RESET ROLE;")
        cur.execute("DELETE FROM public.users WHERE id = %s;", (TEST_USER_ID,))
        cur.execute("DELETE FROM public.tenants WHERE id = %s;", (TEST_TENANT_ID,))
        cur.close()
        conn.close()


def test_get_my_profile_returns_real_database_user():
    token = create_token(TEST_USER_ID, TEST_TENANT_ID, TEST_EMAIL, role="owner")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["id"] == TEST_USER_ID
    assert data["email"] == TEST_EMAIL
    assert data["full_name"] == "Claire Dumont"
    assert data["role"] == "owner"
    assert data["tenant_id"] == TEST_TENANT_ID


def test_get_tenant_info_returns_real_database_tenant():
    token = create_token(TEST_USER_ID, TEST_TENANT_ID, TEST_EMAIL, role="owner")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/auth/tenant", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["id"] == TEST_TENANT_ID
    assert data["name"] == "Bouygues Bâtiment Grand Nord"
    assert data["slug"] == "bouygues-batiment-nord"
    assert data["plan"] == "enterprise"
    
    branding = data["branding_config"]
    assert branding["company_name"] == "Bouygues Bâtiment Grand Nord SAS"
    assert branding["primary_color"] == "#e11d48"
    assert branding["header_text"] == "Mémoire Technique — Pôle Ouvrages d'Art"
