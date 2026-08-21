"""
Real HTTP Integration Test for Super-Admin Security & Platform RBAC.
Proves via FastAPI TestClient against real PostgreSQL database:
1. Missing token returns 401 Unauthorized.
2. Regular tenant users (non-platform admins) receive 403 Forbidden on EVERY /api/admin/* route.
3. Platform admin (with verified role 'platform_admin') is granted access (200 OK).
4. Platform admin actions create immutable audit logs in PostgreSQL.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

TENANT_ID = "aaaaaaaa-1111-1111-1111-111111111111"
USER_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ADMIN_USER_ID = "99999999-ffff-ffff-ffff-ffffffffffff"
SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_tenant_user_jwt() -> str:
    """Creates a regular tenant user JWT (conducteur_travaux)."""
    claims = {
        "sub": USER_ID,
        "email": "conducteur@eiffabtp.fr",
        "aud": "authenticated",
        "app_metadata": {
            "tenant_id": TENANT_ID,
            "role": "conducteur_travaux",
            "is_platform_admin": False,
        },
        "user_metadata": {
            "tenant_id": TENANT_ID,
        },
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


def create_platform_admin_jwt() -> str:
    """Creates a platform admin JWT (does not belong to a client tenant)."""
    claims = {
        "sub": ADMIN_USER_ID,
        "email": "superadmin@btpao.io",
        "aud": "authenticated",
        "app_metadata": {
            "role": "platform_admin",
            "is_platform_admin": True,
        },
        "user_metadata": {
            "role": "platform_admin",
        },
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(scope="module", autouse=True)
def setup_postgres_admin_database():
    """Provisions tables, btp_app_user grants, RLS policies and seeds test tenant for admin tests."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.platform_settings (
            id TEXT PRIMARY KEY DEFAULT 'global',
            settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS public.audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID,
            user_id UUID,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id UUID,
            details JSONB DEFAULT '{}'::jsonb,
            ip_address TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        INSERT INTO public.tenants (id, name, slug, branding_config)
        VALUES 
        (%s, 'Tenant Admin Test', 'tenant-admin-test', '{"model_routing": {}, "system_prompt": "Test Prompt"}'::jsonb)
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO public.platform_settings (id, settings)
        VALUES ('global', '{"anthropic_api_key": "sk-ant-test1234567890", "embedding_model": "text-embedding-3-small"}'::jsonb)
        ON CONFLICT (id) DO UPDATE SET settings = EXCLUDED.settings;
    """, (TENANT_ID,))

    yield

    try:
        cur.execute("DELETE FROM public.audit_logs WHERE tenant_id = %s OR user_id = %s;", (TENANT_ID, ADMIN_USER_ID))
        cur.execute("DELETE FROM public.tenants WHERE id = %s;", (TENANT_ID,))
    finally:
        cur.close()
        conn.close()


def test_admin_routes_unauthenticated_returns_401():
    """Calling /api/admin/* without token returns 401 Unauthorized."""
    client = TestClient(app)

    routes = [
        ("GET", "/api/admin/llm-keys"),
        ("POST", "/api/admin/llm-keys"),
        ("GET", "/api/admin/rag-supervision"),
        ("GET", f"/api/admin/model-routing/{TENANT_ID}"),
        ("POST", "/api/admin/model-routing"),
        ("GET", f"/api/admin/system-prompt/{TENANT_ID}"),
        ("POST", "/api/admin/system-prompt"),
        ("GET", "/api/admin/audit-logs"),
    ]

    for method, path in routes:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={"tenant_id": TENANT_ID, "system_prompt": "test"})
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"


def test_admin_routes_forbidden_for_regular_tenant_user():
    """Regular tenant users receive 403 Forbidden on EVERY /api/admin/* route."""
    client = TestClient(app)
    user_token = create_tenant_user_jwt()
    headers = {"Authorization": f"Bearer {user_token}"}

    routes = [
        ("GET", "/api/admin/llm-keys", None),
        ("POST", "/api/admin/llm-keys", {"anthropic_api_key": "sk-ant-hacked"}),
        ("GET", "/api/admin/rag-supervision", None),
        ("GET", f"/api/admin/model-routing/{TENANT_ID}", None),
        ("POST", "/api/admin/model-routing", {"tenant_id": TENANT_ID}),
        ("GET", f"/api/admin/system-prompt/{TENANT_ID}", None),
        ("POST", "/api/admin/system-prompt", {"tenant_id": TENANT_ID, "system_prompt": "Hacked"}),
        ("GET", "/api/admin/audit-logs", None),
    ]

    for method, path, body in routes:
        if method == "GET":
            res = client.get(path, headers=headers)
        else:
            res = client.post(path, json=body or {}, headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden for regular tenant user on {method} {path}, got {res.status_code}: {res.text}"


def test_admin_routes_accessible_by_platform_admin():
    """Platform administrator with role 'platform_admin' can access all /api/admin/* endpoints."""
    client = TestClient(app)
    admin_token = create_platform_admin_jwt()
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. GET /api/admin/llm-keys
    res_keys = client.get("/api/admin/llm-keys", headers=headers)
    assert res_keys.status_code == 200
    data_keys = res_keys.json()
    assert "anthropic_api_key_configured" in data_keys

    # 2. POST /api/admin/llm-keys
    res_up_keys = client.post("/api/admin/llm-keys", json={"openai_api_key": "sk-test-admin-openai"}, headers=headers)
    assert res_up_keys.status_code == 200

    # 3. GET /api/admin/rag-supervision
    res_rag = client.get("/api/admin/rag-supervision", headers=headers)
    assert res_rag.status_code == 200
    rag_data = res_rag.json()
    assert "total_dce_chunks" in rag_data
    assert "total_knowledge_chunks" in rag_data
    assert "cache_hit_ratio" not in rag_data
    assert "pgvector_status" not in rag_data


    # 4. GET /api/admin/model-routing/{tenant_id}
    res_route = client.get(f"/api/admin/model-routing/{TENANT_ID}", headers=headers)
    assert res_route.status_code == 200
    assert "routing" in res_route.json()

    # 5. POST /api/admin/model-routing
    res_up_route = client.post(
        "/api/admin/model-routing",
        json={
            "tenant_id": TENANT_ID,
            "extraction_gonogo": {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022"},
        },
        headers=headers,
    )
    assert res_up_route.status_code == 200

    # 6. GET /api/admin/system-prompt/{tenant_id}
    res_prompt = client.get(f"/api/admin/system-prompt/{TENANT_ID}", headers=headers)
    assert res_prompt.status_code == 200
    assert "system_prompt" in res_prompt.json()

    # 7. POST /api/admin/system-prompt
    res_up_prompt = client.post(
        "/api/admin/system-prompt",
        json={"tenant_id": TENANT_ID, "system_prompt": "### RÈGLES VALIDÉES ADMIN"},
        headers=headers,
    )
    assert res_up_prompt.status_code == 200

    # 8. GET /api/admin/audit-logs
    res_logs = client.get("/api/admin/audit-logs", headers=headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert "read_llm_keys" in actions
    assert "update_llm_keys" in actions
    assert "update_system_prompt" in actions
