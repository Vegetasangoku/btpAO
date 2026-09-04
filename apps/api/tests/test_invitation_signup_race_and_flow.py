"""
Test suite validating seamless cooperation between Team Invitations and Supabase Auth Signup Trigger.
Confirms that:
1. An invited user who accepts an invitation then registers in auth.users does NOT create a duplicate tenant.
2. An invited user who signs up in auth.users FIRST (before clicking accept) is automatically attached to the inviting tenant and does not create an orphan company.
3. auth.users.raw_app_meta_data and public.users are synchronized with the exact invited role and tenant_id.
"""
import uuid
import psycopg2
import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from app.core.config import settings


@pytest.fixture(autouse=True)
def setup_invitation_test_db():
    """Sets up schema and cleans up test auth, invitation, and tenant data."""
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

        migration_11 = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "00011_fix_auth_signup_trigger_and_default_owner_role.sql"
        with open(migration_11, 'r') as f:
            cur.execute(f.read())

        migration_path = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "00015_fix_invitation_signup_race_and_deduplication.sql"
        with open(migration_path, 'r') as f:
            cur.execute(f.read())

        yield
    finally:
        cur.execute("RESET ROLE;")
        cur.execute("DELETE FROM auth.users WHERE email LIKE '%@test-invitation-btp.fr';")
        cur.execute("DELETE FROM public.tenant_invitations WHERE email LIKE '%@test-invitation-btp.fr';")
        cur.execute("DELETE FROM public.users WHERE email LIKE '%@test-invitation-btp.fr';")
        cur.execute("DELETE FROM public.tenants WHERE slug LIKE 'test-invitation-%';")
        cur.close()
        conn.close()


def make_tenant_owner_token(tenant_id: str, user_id: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": f"owner-{tenant_id[:6]}@test-invitation-btp.fr",
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"tenant_id": tenant_id, "role": "owner"},
            "user_metadata": {"tenant_id": tenant_id, "role": "owner"},
        },
        settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY,
        algorithm="HS256",
    )



@pytest.mark.asyncio
async def test_invitation_accepted_then_signup_no_duplicate_tenant():
    """
    Scenario A:
    1. Owner invites conducteur@test-invitation-btp.fr with role 'conducteur_travaux'.
    2. User accepts invitation via POST /api/team/invitations/accept.
    3. User later registers in Supabase Auth (auth.users INSERT triggers handle_new_user_signup).
    4. Assert: Exactly 1 tenant exists, user is bound to the owner's tenant with role 'conducteur_travaux', NO duplicate tenant created.
    """
    owner_tenant_id = str(uuid.uuid4())
    owner_user_id = str(uuid.uuid4())
    owner_token = make_tenant_owner_token(owner_tenant_id, owner_user_id)
    headers = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}

    # Seed owner's tenant and user in public.users
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.tenants (id, name, slug, plan, country_code, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, now(), now());
        """,
        (owner_tenant_id, "EiffaBTP Travaux Publics SAS", f"test-invitation-{owner_tenant_id[:6]}", "pro", "FR"),
    )
    cur.execute(
        """
        INSERT INTO public.users (id, tenant_id, email, role, full_name, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 'active', now(), now());
        """,
        (owner_user_id, owner_tenant_id, f"owner-{owner_tenant_id[:6]}@test-invitation-btp.fr", "owner", "Owner Admin"),
    )
    cur.close()
    conn.close()

    invited_email = f"conducteur-{owner_tenant_id[:6]}@test-invitation-btp.fr"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Owner invites user
        invite_resp = await ac.post(
            "/api/team/invitations",
            headers=headers,
            json={
                "email": invited_email,
                "role": "conducteur_travaux",
            },
        )
        assert invite_resp.status_code == 200
        invite_data = invite_resp.json()
        token = invite_data["invitation_token"]

        # 2. User accepts invitation
        accept_resp = await ac.post(
            "/api/team/invitations/accept",
            json={
                "token": token,
                "full_name": "Jean Conducteur",
            },
        )
        assert accept_resp.status_code == 200
        accept_data = accept_resp.json()
        assert accept_data["tenant_id"] == owner_tenant_id
        assert accept_data["role"] == "conducteur_travaux"

        # 3. User registers in Supabase Auth (simulate auth.users insert)
        auth_uid = str(uuid.uuid4())
        conn = psycopg2.connect(dbname="postgres")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.users (id, email, raw_user_meta_data)
            VALUES (%s, %s, %s);
            """,
            (auth_uid, invited_email, '{"full_name": "Jean Conducteur"}'),
        )

        # 4. Verification: check that NO duplicate tenant was created
        cur.execute("SELECT count(*) FROM public.tenants WHERE contact_email = %s;", (invited_email,))
        orphan_tenants = cur.fetchone()[0]
        assert orphan_tenants == 0, "No duplicate tenant should be created for invited user"

        # Verify public.users is bound to owner's tenant with role conducteur_travaux
        cur.execute("SELECT tenant_id, role, full_name FROM public.users WHERE lower(email) = lower(%s);", (invited_email,))
        user_row = cur.fetchone()
        assert user_row is not None
        assert str(user_row[0]) == owner_tenant_id
        assert user_row[1] == "conducteur_travaux"

        # Verify auth.users raw_app_meta_data received correct tenant_id and role
        cur.execute("SELECT raw_app_meta_data FROM auth.users WHERE id = %s;", (auth_uid,))
        app_meta = cur.fetchone()[0]
        assert app_meta["tenant_id"] == owner_tenant_id
        assert app_meta["role"] == "conducteur_travaux"

        cur.close()
        conn.close()


@pytest.mark.asyncio
async def test_invitation_signup_first_then_automatic_tenant_binding():
    """
    Scenario B:
    1. Owner invites chiffreur@test-invitation-btp.fr with role 'chiffreur'.
    2. User signs up in Supabase Auth directly via standard signup page before clicking accept.
    3. Trigger handle_new_user_signup detects the pending invitation for this email.
    4. Assert: User is immediately attached to the owner's tenant with role 'chiffreur' and invitation is marked 'accepted'.
    """
    owner_tenant_id = str(uuid.uuid4())
    owner_user_id = str(uuid.uuid4())
    owner_token = make_tenant_owner_token(owner_tenant_id, owner_user_id)
    headers = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}

    # Seed owner's tenant and user in public.users
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.tenants (id, name, slug, plan, country_code, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, now(), now());
        """,
        (owner_tenant_id, "BouygBTP Construction SAS", f"test-invitation-{owner_tenant_id[:6]}", "enterprise", "FR"),
    )
    cur.execute(
        """
        INSERT INTO public.users (id, tenant_id, email, role, full_name, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 'active', now(), now());
        """,
        (owner_user_id, owner_tenant_id, f"owner-{owner_tenant_id[:6]}@test-invitation-btp.fr", "owner", "Owner Admin"),
    )
    cur.close()
    conn.close()


    invited_email = f"chiffreur-{owner_tenant_id[:6]}@test-invitation-btp.fr"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Owner invites user
        invite_resp = await ac.post(
            "/api/team/invitations",
            headers=headers,
            json={
                "email": invited_email,
                "role": "chiffreur",
            },
        )
        assert invite_resp.status_code == 200

        # 2. User signs up on auth.users directly
        auth_uid = str(uuid.uuid4())
        conn = psycopg2.connect(dbname="postgres")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.users (id, email, raw_user_meta_data)
            VALUES (%s, %s, %s);
            """,
            (auth_uid, invited_email, '{"full_name": "Marc Chiffreur"}'),
        )

        # 3. Verification: trigger automatically bound user to owner_tenant_id
        cur.execute("SELECT tenant_id, role FROM public.users WHERE lower(email) = lower(%s);", (invited_email,))
        user_row = cur.fetchone()
        assert user_row is not None
        assert str(user_row[0]) == owner_tenant_id
        assert user_row[1] == "chiffreur"

        # Invitation marked accepted
        cur.execute("SELECT status FROM public.tenant_invitations WHERE lower(email) = lower(%s);", (invited_email,))
        inv_status = cur.fetchone()[0]
        assert inv_status == "accepted"

        # No duplicate company created
        cur.execute("SELECT count(*) FROM public.tenants WHERE contact_email = %s;", (invited_email,))
        assert cur.fetchone()[0] == 0

        cur.close()
        conn.close()
