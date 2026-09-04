"""
Test suite for Supabase Auth Signup Trigger and Default Owner Role.
Validates:
1. Self-registering users creating their company get role 'owner' (not 'admin' or 'member').
2. Tenant is automatically created with slug, plan, country_code ('FR'), and branding.
3. User row is created in public.users linked to the tenant with role 'owner'.
4. auth.users.raw_app_meta_data is populated with tenant_id, role='owner', and company_name.
5. Users joining via invitation with tenant_id in metadata get role 'member'.
"""
import uuid
import psycopg2
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"


@pytest.fixture(autouse=True)
def setup_auth_signup_test_data():
    """Sets up schema and cleans up test auth and tenant data."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth.users (
                id UUID PRIMARY KEY,
                instance_id UUID DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
                email TEXT,
                encrypted_password TEXT DEFAULT 'dummy_pw',
                email_confirmed_at TIMESTAMPTZ DEFAULT now(),
                raw_app_meta_data JSONB DEFAULT '{}'::jsonb,
                raw_user_meta_data JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now(),
                role VARCHAR DEFAULT 'authenticated',
                aud VARCHAR DEFAULT 'authenticated'
            );
        """)

        migration_path = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "00011_fix_auth_signup_trigger_and_default_owner_role.sql"
        with open(migration_path, 'r') as f:
            cur.execute(f.read())

        yield
    finally:
        cur.execute("RESET ROLE;")
        cur.execute("DELETE FROM auth.users WHERE email LIKE '%@test-signup-btp.fr';")
        cur.execute("DELETE FROM public.tenant_subscriptions WHERE tenant_id IN (SELECT id FROM public.tenants WHERE slug LIKE 'test-signup-%' OR name LIKE 'Test Signup %');")
        cur.execute("DELETE FROM public.tenants WHERE slug LIKE 'test-signup-%' OR name LIKE 'Test Signup %';")
        cur.close()
        conn.close()


def test_auth_signup_creates_tenant_and_assigns_owner_role():
    """
    Simulates a new user signup in auth.users.
    Verifies that handle_new_user_signup() trigger:
    1. Creates tenant with correct plan, SIRET, country_code='FR'.
    2. Creates public.users with role='owner'.
    3. Injects tenant_id and role='owner' in raw_app_meta_data.
    """
    user_id = str(uuid.uuid4())
    user_email = f"directeur-{user_id[:6]}@test-signup-btp.fr"
    company_name = "Test Signup Charpente SAS"
    siret = "98765432100019"

    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # Simulate Supabase Auth inserting new user
        cur.execute("""
            INSERT INTO auth.users (
                id,
                email,
                raw_user_meta_data
            ) VALUES (
                %s,
                %s,
                %s
            );
        """, (
            user_id,
            user_email,
            f'{{"full_name": "Jean Dupont", "company_name": "{company_name}", "siret": "{siret}", "plan": "pro", "role": "owner"}}'
        ))

        # Check public.users and public.tenants
        cur.execute("""
            SELECT u.id, u.email, u.full_name, u.role, t.id, t.name, t.slug, t.plan, t.country_code, t.siret, a.raw_app_meta_data
            FROM public.users u
            JOIN public.tenants t ON t.id = u.tenant_id
            JOIN auth.users a ON a.id = u.id
            WHERE u.id = %s;
        """, (user_id,))

        row = cur.fetchone()
        assert row is not None, "Trigger failed to create public.users or public.tenants!"

        u_id, u_email, u_name, u_role, t_id, t_name, t_slug, t_plan, t_country, t_siret, app_meta = row

        assert str(u_id) == user_id
        assert u_email == user_email

        assert u_name == "Jean Dupont"
        assert u_role == "owner", f"Expected role 'owner', got {u_role}"

        assert t_name == company_name
        assert t_plan == "pro"
        assert t_country == "FR"
        assert t_siret == siret

        assert app_meta.get("role") == "owner", f"Expected app_meta role 'owner', got {app_meta.get('role')}"
        assert app_meta.get("tenant_id") == str(t_id)
        assert app_meta.get("company_name") == company_name

    finally:
        cur.close()
        conn.close()


def test_auth_signup_invited_member_attaches_to_existing_tenant():
    """
    When an invited member signs up with tenant_id in raw_user_meta_data,
    they are attached to that tenant with role 'member'.
    """
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    existing_tenant_id = str(uuid.uuid4())
    invited_user_id = str(uuid.uuid4())
    invited_email = f"conducteur-{invited_user_id[:6]}@test-signup-btp.fr"

    try:
        # Create existing tenant
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug, plan, country_code)
            VALUES (%s, 'Test Signup Existante PME', 'test-signup-existante-pme', 'starter', 'FR');
        """, (existing_tenant_id,))

        # Invite signup
        cur.execute("""
            INSERT INTO auth.users (
                id,
                email,
                raw_user_meta_data
            ) VALUES (
                %s,
                %s,
                %s
            );
        """, (
            invited_user_id,
            invited_email,
            f'{{"full_name": "Paul Conducteur", "tenant_id": "{existing_tenant_id}", "role": "member"}}'
        ))

        cur.execute("""
            SELECT u.role, u.tenant_id, a.raw_app_meta_data
            FROM public.users u
            JOIN auth.users a ON a.id = u.id
            WHERE u.id = %s;
        """, (invited_user_id,))

        row = cur.fetchone()
        assert row is not None
        u_role, u_tenant_id, app_meta = row

        assert u_role == "member"
        assert str(u_tenant_id) == existing_tenant_id
        assert app_meta.get("role") == "member"
        assert app_meta.get("tenant_id") == existing_tenant_id

    finally:
        cur.close()
        conn.close()
