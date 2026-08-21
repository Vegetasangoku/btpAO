"""
Security & Tenant Isolation Tests
Proves:
1. Request without token -> 401 Unauthorized
2. Request with invalid/empty token -> 401 Unauthorized
3. Request with valid JWT from Tenant A + header X-Tenant-ID pointing to Tenant B -> strictly bound to Tenant A
"""
import pytest
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.core.security import get_current_tenant_user
from app.main import app


TENANT_A_ID = "11111111-1111-1111-1111-aaaaaaaaaaaa"
TENANT_B_ID = "22222222-2222-2222-2222-bbbbbbbbbbbb"
USER_A_ID = "33333333-3333-3333-3333-aaaaaaaaaaaa"
SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_mock_jwt(user_id: str, tenant_id: str, email: str = "user@tenant-a.com") -> str:
    """Helper to generate a valid signed JWT with app_metadata.tenant_id."""
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
def setup_tenants_for_auth_tests():
    """Ensure test tenants exist in DB for FK validation."""
    import psycopg2
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
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
        INSERT INTO public.tenants (id, name, slug)
        VALUES 
        (%s, 'Tenant A Auth Test', 'tenant-a-auth-test'),
        (%s, 'Tenant B Auth Test', 'tenant-b-auth-test')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID))
    yield
    try:
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()



@pytest.mark.asyncio
async def test_auth_missing_token_raises_401():
    """Requirement 1: Missing token must raise 401 without exception or silent fallback."""
    req = Request(scope={"type": "http"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant_user(request=req, credentials=None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "missing bearer token" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_auth_invalid_token_raises_401():
    """Invalid token must raise 401."""
    req = Request(scope={"type": "http"})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-garbage-token")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant_user(request=req, credentials=credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_tenant_isolation_ignores_x_tenant_id_header():
    """Requirement 2: Token for Tenant A with X-Tenant-ID: Tenant B must remain strictly bound to Tenant A."""
    token_tenant_a = create_mock_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_tenant_a)

    # Simulated incoming HTTP request with spoofed X-Tenant-ID header
    req = Request(
        scope={
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {token_tenant_a}".encode("latin-1")),
                (b"x-tenant-id", TENANT_B_ID.encode("latin-1")),
            ],
        }
    )

    user = await get_current_tenant_user(request=req, credentials=credentials)

    # Crucial security assertion: User is strictly bound to Tenant A, NEVER Tenant B
    assert user.tenant_id == TENANT_A_ID
    assert user.tenant_id != TENANT_B_ID
    assert user.user_id == USER_A_ID


def test_api_endpoint_without_token_returns_401():
    """HTTP integration test: Calling protected endpoints without token returns 401 status."""
    client = TestClient(app)

    # 1. Unauthenticated call to /api/projects
    response = client.get("/api/projects")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

    # 2. Unauthenticated call to /projects alias
    response_root = client.get("/projects")
    assert response_root.status_code == 401, f"Expected 401, got {response_root.status_code}: {response_root.text}"


def test_api_endpoint_tenant_spoofing_prevented():
    """HTTP integration test: Tenant spoofing via X-Tenant-ID header is strictly ignored by endpoint."""
    client = TestClient(app)
    token_tenant_a = create_mock_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID)

    headers = {
        "Authorization": f"Bearer {token_tenant_a}",
        "X-Tenant-ID": TENANT_B_ID,  # Attacker attempts to spoof Tenant B
    }

    # 1. Create a project under Tenant A with spoofed header
    create_payload = {
        "title": "Chantier Sécurisé Tenant A",
        "reference_code": "AO-SEC-001",
        "client_name": "Ville de Paris",
        "lot_number": "Lot 01",
        "budget_estimate": 1500000.0,
    }
    create_res = client.post("/api/projects", json=create_payload, headers=headers)
    assert create_res.status_code in [200, 201], f"Expected 200/201, got {create_res.status_code}: {create_res.text}"
    created_proj = create_res.json()
    assert created_proj["tenant_id"] == TENANT_A_ID, "Project must be created under Tenant A"
    assert created_proj["tenant_id"] != TENANT_B_ID, "Project MUST NOT be created under Tenant B"

    # 2. Fetch projects with spoofed header
    response = client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    projects = response.json()

    # Crucial assertion: Must not be empty, must be validated
    assert isinstance(projects, list)
    assert len(projects) > 0, "Projects list must not be empty"

    # All returned projects must strictly belong to Tenant A, never Tenant B
    for proj in projects:
        assert proj.get("tenant_id") == TENANT_A_ID, f"Project {proj.get('id')} leaked to wrong tenant"
        assert proj.get("tenant_id") != TENANT_B_ID, "Tenant B data must never be visible"

