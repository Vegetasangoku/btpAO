"""
Tests for RGPD / Right to Erasure Account Deletion Lifecycle (30-day soft delete + hard purge).
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select, text
import psycopg2

from app.main import app
from app.core.config import settings

TENANT_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "44444444-4444-4444-4444-444444444444"
EXPIRED_USER_ID = "55555555-5555-5555-5555-555555555555"
JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_token(user_id: str, tenant_id: str) -> str:
    claims = {
        "sub": user_id,
        "email": f"gdpr_user_{user_id[:6]}@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": "member"},
        "user_metadata": {"tenant_id": tenant_id, "role": "member"},
    }
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


@pytest.fixture(autouse=True, scope="function")
def setup_gdpr_test_users():

    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO public.tenants (id, name, slug, plan, country_code)
        VALUES ('11111111-1111-1111-1111-111111111111', 'GDPR Test Corp', 'gdpr-corp', 'pro', 'FR')
        ON CONFLICT (id) DO NOTHING;
    """)

    cur.execute("""
        INSERT INTO public.users (id, tenant_id, email, full_name, role, status)
        VALUES ('44444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', 'jean.dupont@gdpr-corp.fr', 'Jean Dupont', 'member', 'active')
        ON CONFLICT (id) DO UPDATE SET status = 'active', deletion_requested_at = NULL, scheduled_purge_at = NULL;
    """)

    # Expired user for purge execution
    expired_purge_date = datetime.now(timezone.utc) - timedelta(days=2)
    cur.execute("""
        INSERT INTO public.users (id, tenant_id, email, full_name, role, status, deletion_requested_at, scheduled_purge_at)
        VALUES ('55555555-5555-5555-5555-555555555555', '11111111-1111-1111-1111-111111111111', 'expired.user@gdpr-corp.fr', 'Expired User', 'member', 'pending_deletion', NOW() - INTERVAL '32 days', NOW() - INTERVAL '2 days')
        ON CONFLICT (id) DO UPDATE SET status = 'pending_deletion', scheduled_purge_at = NOW() - INTERVAL '2 days';
    """)

    # Audit log linked to expired user
    cur.execute("""
        INSERT INTO public.audit_logs (id, tenant_id, user_id, action, entity_type, entity_id, details)
        VALUES ('66666666-6666-6666-6666-666666666666', '11111111-1111-1111-1111-111111111111', '55555555-5555-5555-5555-555555555555', 'test_action', 'document', '77777777-7777-7777-7777-777777777777', '{"doc_name": "CCTP.pdf"}')
        ON CONFLICT (id) DO NOTHING;
    """)

    conn.commit()
    yield
    cur.execute("DELETE FROM public.audit_logs WHERE id = '66666666-6666-6666-6666-666666666666';")
    cur.execute("DELETE FROM public.users WHERE id IN ('44444444-4444-4444-4444-444444444444', '55555555-5555-5555-5555-555555555555');")
    conn.commit()
    conn.close()


def test_gdpr_deletion_request_and_cancellation():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Request deletion
    res = client.post("/api/auth/account/delete-request", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "pending_deletion"
    assert "30 jours" in data["message"]
    assert "décennale" in data["legal_notice"]

    # Verify DB state
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    cur.execute("SELECT status, scheduled_purge_at FROM public.users WHERE id = '44444444-4444-4444-4444-444444444444';")
    row = cur.fetchone()
    assert row[0] == "pending_deletion"
    assert row[1] is not None

    # 2. Cancel deletion
    cancel_res = client.post("/api/auth/account/cancel-deletion", headers=headers)
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["success"] is True
    assert cancel_data["status"] == "active"

    # Verify restored state
    cur.execute("SELECT status, scheduled_purge_at FROM public.users WHERE id = '44444444-4444-4444-4444-444444444444';")
    row_restored = cur.fetchone()
    assert row_restored[0] == "active"
    assert row_restored[1] is None
    conn.close()


def test_gdpr_execute_expired_purge_security():
    client = TestClient(app)

    # 1. Unauthenticated -> 403 Forbidden (fail closed)
    res_no_auth = client.post("/api/auth/account/execute-purge")
    assert res_no_auth.status_code == 403
    assert "Accès interdit" in res_no_auth.json()["detail"]

    # 2. Invalid Cron Secret -> 403 Forbidden
    res_bad_secret = client.post(
        "/api/auth/account/execute-purge",
        headers={"X-Cron-Secret": "invalid-secret-key-123"}
    )
    assert res_bad_secret.status_code == 403

    # 3. Regular member user token -> 403 Forbidden
    member_token = create_token(USER_ID, TENANT_ID)
    res_member = client.post(
        "/api/auth/account/execute-purge",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert res_member.status_code == 403

    # 4. Valid Platform Admin Token -> 200 OK
    admin_claims = {
        "sub": "99999999-9999-9999-9999-999999999999",
        "email": "charbelakl@gmail.com",
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"role": "super_admin", "is_platform_admin": True},
        "user_metadata": {"role": "super_admin", "is_platform_admin": True},
    }
    admin_token = jwt.encode(admin_claims, JWT_SECRET, algorithm="HS256")
    res_admin = client.post(
        "/api/auth/account/execute-purge",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["success"] is True


def test_gdpr_execute_expired_purge_via_cron_secret_and_celery():
    client = TestClient(app)
    cron_secret = "btp-cron-purge-secret-secure-prod-2026"
    settings.CRON_PURGE_SECRET = cron_secret

    # Call with valid X-Cron-Secret header
    res = client.post(
        "/api/auth/account/execute-purge",
        headers={"X-Cron-Secret": cron_secret}
    )
    assert res.status_code == 200

    data = res.json()
    assert data["success"] is True
    assert data["purged_accounts_count"] >= 1

    # Verify user record hard deleted and audit log anonymized
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM public.users WHERE id = '55555555-5555-5555-5555-555555555555';")
    count = cur.fetchone()[0]
    assert count == 0

    cur.execute("SELECT user_id, details FROM public.audit_logs WHERE id = '66666666-6666-6666-6666-666666666666';")
    audit_row = cur.fetchone()
    assert audit_row[0] is None
    assert audit_row[1].get("anonymized") is True
    conn.close()

    # Test Celery task directly
    from app.workers.tasks import purge_expired_accounts_task
    celery_result = purge_expired_accounts_task()
    assert celery_result["success"] is True

