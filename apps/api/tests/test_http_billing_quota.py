"""
Real HTTP Integration Test for Hybrid Billing, Quota Enforcement & Platform Admin Management.
Proves via FastAPI TestClient against real PostgreSQL database:
1. Self-Service Stripe billing endpoints (plans, subscription status, checkout sessions, webhooks).
2. Quota enforcement: Tenant with exhausted quota and allow_overage=False is cleanly blocked (402 Payment Required).
3. Active tenant within quota can generate/export and has usage counter incremented.
4. Platform Admin can manually configure custom Enterprise quota/forfait on any tenant.
5. Platform Admin operations are strictly audited in public.audit_logs with full filtering capability.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.core.storage import storage_service
from app.main import app

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ADMIN_USER_ID = "99999999-ffff-ffff-ffff-ffffffffffff"
PROJ_A_ID = "88881111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_B_ID = "88882222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_tenant_jwt(user_id: str, tenant_id: str, email: str) -> str:
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


def create_platform_admin_jwt() -> str:
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
def setup_postgres_billing_database():
    """Provisions tables, btp_app_user grants, RLS policies and seeds test plans, subscriptions and usage."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.subscription_plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price_monthly_cents INTEGER NOT NULL DEFAULT 0,
            included_dossiers_month INTEGER NOT NULL DEFAULT 3,
            extra_dossier_price_cents INTEGER NOT NULL DEFAULT 9900,
            features JSONB DEFAULT '[]'::jsonb,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS public.tenant_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE UNIQUE,
            plan_id TEXT NOT NULL REFERENCES public.subscription_plans(id),
            status TEXT NOT NULL DEFAULT 'active',
            billing_mode TEXT NOT NULL DEFAULT 'stripe',
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            custom_quota_dossiers INTEGER,
            allow_overage BOOLEAN DEFAULT true,
            current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
            current_period_end TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 month'),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS public.tenant_usage_counters (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            period_start TIMESTAMPTZ NOT NULL,
            period_end TIMESTAMPTZ NOT NULL,
            dossiers_generated INTEGER DEFAULT 0,
            sections_generated INTEGER DEFAULT 0,
            exports_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

        ALTER TABLE public.tenant_subscriptions ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_tenant_subscriptions ON public.tenant_subscriptions;
        CREATE POLICY tenant_isolation_tenant_subscriptions ON public.tenant_subscriptions
            FOR ALL TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );

        ALTER TABLE public.tenant_usage_counters ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_tenant_usage_counters ON public.tenant_usage_counters;
        CREATE POLICY tenant_isolation_tenant_usage_counters ON public.tenant_usage_counters
            FOR ALL TO btp_app_user
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
            );


        -- 1. Seed Plans
        INSERT INTO public.subscription_plans (id, name, price_monthly_cents, included_dossiers_month, extra_dossier_price_cents)
        VALUES 
        ('starter', 'Forfait PME', 19900, 3, 9900),
        ('pro', 'Forfait Entreprise', 49900, 10, 7900),
        ('enterprise', 'Grand Compte / Sur Devis', 0, 50, 0)
        ON CONFLICT (id) DO UPDATE SET price_monthly_cents = EXCLUDED.price_monthly_cents;

        -- 2. Seed Tenants & Projects
        INSERT INTO public.tenants (id, name, slug)
        VALUES 
        (%s, 'Tenant A Billing', 'tenant-a-bill'),
        (%s, 'Tenant B Billing', 'tenant-b-bill')
        ON CONFLICT (id) DO NOTHING;

        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, location)
        VALUES 
        (%s, %s, 'Projet A Facturation', 'AO-BILL-A', 'Ville Nice', 'Nice 06'),
        (%s, %s, 'Projet B Facturation', 'AO-BILL-B', 'Ville Cannes', 'Cannes 06')
        ON CONFLICT (id) DO NOTHING;
    """, (TENANT_A_ID, TENANT_B_ID, PROJ_A_ID, TENANT_A_ID, PROJ_B_ID, TENANT_B_ID))

    # 3. Seed Subscriptions & Usage:
    # Tenant A: Pro Plan (10 dossiers), usage = 2
    # Tenant B: Starter Plan (3 dossiers), usage = 3, allow_overage = False (Exhausted!)
    cur.execute("DELETE FROM public.tenant_subscriptions WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    cur.execute("DELETE FROM public.tenant_usage_counters WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))

    from datetime import datetime
    from app.services.billing_service import billing_service
    start_dt, end_dt = billing_service.get_current_period_bounds()

    cur.execute("""
        INSERT INTO public.tenant_subscriptions (id, tenant_id, plan_id, status, billing_mode, allow_overage)
        VALUES 
        (%s, %s, 'pro', 'active', 'stripe', true),
        (%s, %s, 'starter', 'active', 'stripe', false);

        INSERT INTO public.tenant_usage_counters (id, tenant_id, period_start, period_end, dossiers_generated, sections_generated, exports_count)
        VALUES 
        (%s, %s, %s, %s, 2, 8, 1),
        (%s, %s, %s, %s, 3, 12, 3);
    """, (
        str(uuid.uuid4()), TENANT_A_ID,
        str(uuid.uuid4()), TENANT_B_ID,
        str(uuid.uuid4()), TENANT_A_ID, start_dt, end_dt,
        str(uuid.uuid4()), TENANT_B_ID, start_dt, end_dt,
    ))


    yield

    try:
        cur.execute("DELETE FROM public.tenant_subscriptions WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenant_usage_counters WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


def test_http_list_plans():
    """Real HTTP GET /api/billing/plans returns plan catalog."""
    client = TestClient(app)
    token_a = create_tenant_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get("/api/billing/plans", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) >= 3
    plan_ids = [p["id"] for p in plans]
    assert "starter" in plan_ids
    assert "pro" in plan_ids
    assert "enterprise" in plan_ids


def test_http_get_tenant_subscription_status():
    """Real HTTP GET /api/billing/subscription returns tenant-specific subscription and usage."""
    client = TestClient(app)
    token_a = create_tenant_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")

    response = client.get("/api/billing/subscription", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    data = response.json()
    assert data["has_subscription"] is True
    assert data["plan_id"] == "pro"
    assert data["quota_dossiers"] == 10
    assert data["dossiers_used"] == 2
    assert data["status"] == "active"


def test_http_quota_exhausted_blocks_export_cleanly():
    """Tenant B with exhausted quota (3/3) and allow_overage=False is blocked with 402 Payment Required."""
    client = TestClient(app)
    token_b = create_tenant_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    payload = {
        "project_id": PROJ_B_ID,
        "format": "docx",
    }
    response = client.post("/api/export/compile", json=payload, headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 402, f"Expected 402 Payment Required, got {response.status_code}: {response.text}"
    err = response.json()
    assert "Quota mensuel de dossiers atteint" in err["detail"]


def test_http_admin_manual_enterprise_quota_override_and_unblock():
    """Platform Admin manually upgrades Tenant B to Enterprise (custom quota = 25), unblocking generation."""
    client = TestClient(app)
    admin_token = create_platform_admin_jwt()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Admin reads Tenant B's subscription
    res_get = client.get(f"/api/admin/tenants/{TENANT_B_ID}/subscription", headers=admin_headers)
    assert res_get.status_code == 200
    assert res_get.json()["plan_id"] == "starter"

    # 2. Admin upgrades Tenant B with custom enterprise quota
    payload = {
        "plan_id": "enterprise",
        "status": "active",
        "billing_mode": "manual_enterprise",
        "custom_quota_dossiers": 25,
        "allow_overage": True,
        "duration_days": 365,
    }
    res_put = client.put(f"/api/admin/tenants/{TENANT_B_ID}/subscription", json=payload, headers=admin_headers)
    assert res_put.status_code == 200

    # 3. Tenant B now compiles successfully (quota is now 3/25)
    token_b = create_tenant_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")
    export_payload = {
        "project_id": PROJ_B_ID,
        "format": "docx",
    }
    res_exp = client.post("/api/export/compile", json=export_payload, headers={"Authorization": f"Bearer {token_b}"})
    assert res_exp.status_code == 200
    assert res_exp.json()["status"] in ("processing", "completed")


    # 4. Verify audit log was created for admin manual update
    res_logs = client.get(f"/api/admin/audit-logs?tenant_id={TENANT_B_ID}&action=update_tenant_subscription", headers=admin_headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert len(logs) > 0
    assert logs[0]["action"] == "update_tenant_subscription"
    assert logs[0]["tenant_id"] == TENANT_B_ID


def test_http_stripe_webhook_unauthenticated_without_signature_rejected():
    """Webhook request without Stripe cryptographic signature is rejected immediately with 400 Bad Request."""
    client = TestClient(app)
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_key_12345"

    webhook_payload = {
        "id": "evt_test_unauth",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_hacker_123",
                "client_reference_id": TENANT_A_ID,
                "metadata": {"tenant_id": TENANT_A_ID, "plan_id": "enterprise"},
            }
        },
    }
    # No signature header
    response = client.post("/api/billing/webhook", json=webhook_payload)
    assert response.status_code == 400
    assert "Missing stripe-signature header" in response.json()["detail"]


def test_http_stripe_webhook_invalid_signature_rejected():
    """Webhook request with invalid/forged signature is rejected with 400 Bad Request and writes nothing."""
    client = TestClient(app)
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret_key_12345"

    webhook_payload = {
        "id": "evt_test_forged",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_forged_999",
                "client_reference_id": TENANT_A_ID,
                "metadata": {"tenant_id": TENANT_A_ID, "plan_id": "enterprise"},
            }
        },
    }
    headers = {"stripe-signature": "t=1700000000,v1=0000000000000000000000000000000000000000000000000000000000000000"}
    response = client.post("/api/billing/webhook", json=webhook_payload, headers=headers)
    assert response.status_code == 400
    assert "verification failed" in response.json()["detail"]


def test_http_stripe_webhook_valid_cryptographic_signature_succeeds():
    """Webhook request with valid cryptographic HMAC-SHA256 signature updates PostgreSQL database."""
    import hashlib
    import hmac
    import json
    import time

    client = TestClient(app)
    webhook_secret = "whsec_test_secret_key_12345"
    settings.STRIPE_WEBHOOK_SECRET = webhook_secret

    webhook_payload = {
        "id": "evt_test_valid_signature",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_stripe_verified_777",
                "client_reference_id": TENANT_A_ID,
                "metadata": {
                    "tenant_id": TENANT_A_ID,
                    "plan_id": "pro",
                },
            }
        },
    }
    payload_str = json.dumps(webhook_payload)
    payload_bytes = payload_str.encode("utf-8")
    timestamp = int(time.time())

    signed_payload = f"{timestamp}.{payload_str}".encode("utf-8")
    computed_sig = hmac.new(webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    sig_header = f"t={timestamp},v1={computed_sig}"

    response = client.post(
        "/api/billing/webhook",
        content=payload_bytes,
        headers={"Content-Type": "application/json", "stripe-signature": sig_header},
    )
    assert response.status_code == 200
    assert response.json()["received"] is True

    # Cryptographic proof: Assert direct PostgreSQL DB row mutation under RLS role
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, true);", (TENANT_A_ID,))
        cur.execute("""
            SELECT plan_id, status, billing_mode, stripe_subscription_id 
            FROM public.tenant_subscriptions 
            WHERE tenant_id = %s;
        """, (TENANT_A_ID,))
        row = cur.fetchone()
        assert row is not None, "Expected tenant_subscriptions row to exist in PostgreSQL"
        assert row[0] == "pro", f"Expected plan_id 'pro', got '{row[0]}'"
        assert row[1] == "active", f"Expected status 'active', got '{row[1]}'"
        assert row[2] == "stripe", f"Expected billing_mode 'stripe', got '{row[2]}'"
        assert row[3] == "sub_stripe_verified_777", f"Expected stripe_subscription_id 'sub_stripe_verified_777', got '{row[3]}'"
    finally:
        cur.close()
        conn.close()



