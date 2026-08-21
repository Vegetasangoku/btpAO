"""
HTTP Integration Tests for Team Multi-User RBAC (owner, member, read_only) & Secure Invitation Flow.
Tests:
1. All authenticated tenant users can list team members of their tenant (and only their tenant).
2. Owner can invite new users with specific roles, and invited users can accept tokens to bind strictly to that tenant.
3. Members cannot invite users, change roles, or access billing (403 Forbidden).
4. Owner can update member roles and remove members (with protection against removing the last owner).
5. Strict Postgres RLS and cross-tenant isolation.
"""
import uuid
from datetime import datetime, timezone
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
OWNER_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
MEMBER_A_ID = "11111111-aaaa-bbbb-cccc-dddddddddddd"
OWNER_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
MEMBER_B_ID = "22222222-bbbb-cccc-dddd-eeeeeeeeeeee"

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_jwt(user_id: str, tenant_id: str, email: str, role: str) -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": role},
        "user_metadata": {"tenant_id": tenant_id, "role": role},
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_postgres_team_users():
    """Initializes schema and seeds multi-user tenants with owners and regular members."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # 1. Seed Tenants
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES 
            (%s, 'EiffaBTP Construction', 'eiffabtp-team'),
            (%s, 'BouygBTP Bâtiment', 'bouygbtp-team')
            ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug;
        """, (TENANT_A_ID, TENANT_B_ID))

        # 2. Clean and Seed Users
        cur.execute("DELETE FROM public.tenant_invitations WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.users WHERE tenant_id IN (%s, %s) OR id IN (%s, %s, %s, %s);", (TENANT_A_ID, TENANT_B_ID, OWNER_A_ID, MEMBER_A_ID, OWNER_B_ID, MEMBER_B_ID))


        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES
            (%s, %s, 'owner.a@eiffabtp.fr', 'Directeur Général A', 'owner'),
            (%s, %s, 'member.a@eiffabtp.fr', 'Conducteur Travaux A', 'member'),
            (%s, %s, 'owner.b@bouygbtp.fr', 'Directeur Général B', 'owner'),
            (%s, %s, 'member.b@bouygbtp.fr', 'Conducteur Travaux B', 'member');
        """, (
            OWNER_A_ID, TENANT_A_ID,
            MEMBER_A_ID, TENANT_A_ID,
            OWNER_B_ID, TENANT_B_ID,
            MEMBER_B_ID, TENANT_B_ID,
        ))

    finally:
        cur.close()
        conn.close()


def test_http_team_members_listing_visible_to_all_tenant_users():
    """Both owners and regular members can list members of their own tenant, strictly isolated from Tenant B."""
    client = TestClient(app)
    token_owner_a = create_jwt(user_id=OWNER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr", role="owner")
    token_member_a = create_jwt(user_id=MEMBER_A_ID, tenant_id=TENANT_A_ID, email="member.a@eiffabtp.fr", role="member")
    token_owner_b = create_jwt(user_id=OWNER_B_ID, tenant_id=TENANT_B_ID, email="owner.b@bouygbtp.fr", role="owner")

    # 1. Owner A lists team members
    res_a1 = client.get("/api/team/members", headers={"Authorization": f"Bearer {token_owner_a}"})
    assert res_a1.status_code == 200
    members_a = res_a1.json()
    assert len(members_a) == 2
    emails_a = [m["email"] for m in members_a]
    assert "owner.a@eiffabtp.fr" in emails_a
    assert "member.a@eiffabtp.fr" in emails_a
    assert "owner.b@bouygbtp.fr" not in emails_a

    # 2. Member A also has access to list their team
    res_a2 = client.get("/api/team/members", headers={"Authorization": f"Bearer {token_member_a}"})
    assert res_a2.status_code == 200
    assert len(res_a2.json()) == 2

    # 3. Owner B only sees Tenant B members
    res_b = client.get("/api/team/members", headers={"Authorization": f"Bearer {token_owner_b}"})
    assert res_b.status_code == 200
    members_b = res_b.json()
    assert len(members_b) == 2
    emails_b = [m["email"] for m in members_b]
    assert "owner.b@bouygbtp.fr" in emails_b
    assert "owner.a@eiffabtp.fr" not in emails_b


def test_http_team_invitation_flow_and_acceptance():
    """Owner invites a new engineer by email, who accepts the token to bind strictly to Tenant A."""
    client = TestClient(app)
    token_owner_a = create_jwt(user_id=OWNER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr", role="owner")

    # 1. Owner creates invitation for a new engineer
    invite_payload = {
        "email": "charlotte.ing@eiffabtp.fr",
        "role": "conducteur_travaux",
    }
    res_inv = client.post("/api/team/invitations", json=invite_payload, headers={"Authorization": f"Bearer {token_owner_a}"})
    assert res_inv.status_code == 200
    invitation = res_inv.json()
    assert invitation["email"] == "charlotte.ing@eiffabtp.fr"
    assert invitation["role"] == "conducteur_travaux"
    assert invitation["status"] == "pending"
    token = invitation["invitation_token"]

    # 2. Owner lists pending invitations
    res_list_inv = client.get("/api/team/invitations", headers={"Authorization": f"Bearer {token_owner_a}"})
    assert res_list_inv.status_code == 200
    assert len(res_list_inv.json()) == 1
    assert res_list_inv.json()[0]["email"] == "charlotte.ing@eiffabtp.fr"

    # 3. Invited user accepts invitation with token
    accept_payload = {
        "token": token,
        "full_name": "Charlotte Dubois Ingénieure ESTP",
    }
    res_accept = client.post("/api/team/invitations/accept", json=accept_payload)
    assert res_accept.status_code == 200
    new_user = res_accept.json()
    assert new_user["email"] == "charlotte.ing@eiffabtp.fr"
    assert new_user["tenant_id"] == TENANT_A_ID
    assert new_user["role"] == "conducteur_travaux"
    assert new_user["full_name"] == "Charlotte Dubois Ingénieure ESTP"

    # 4. Check that team members now contains Charlotte
    res_team = client.get("/api/team/members", headers={"Authorization": f"Bearer {token_owner_a}"})
    assert len(res_team.json()) == 3


def test_http_member_cannot_invite_change_roles_or_access_billing():
    """Regular member cannot invite users, change roles, or start billing checkout (403 Forbidden)."""
    client = TestClient(app)
    token_member_a = create_jwt(user_id=MEMBER_A_ID, tenant_id=TENANT_A_ID, email="member.a@eiffabtp.fr", role="member")

    # 1. Member tries to invite a user -> 403
    res_inv = client.post(
        "/api/team/invitations",
        json={"email": "hacker@domain.fr", "role": "owner"},
        headers={"Authorization": f"Bearer {token_member_a}"},
    )
    assert res_inv.status_code == 403
    assert "Tenant owner privileges required" in res_inv.json()["detail"]

    # 2. Member tries to change their own role to 'owner' -> 403
    res_role = client.put(
        f"/api/team/members/{MEMBER_A_ID}/role",
        json={"role": "owner"},
        headers={"Authorization": f"Bearer {token_member_a}"},
    )
    assert res_role.status_code == 403

    # 3. Member tries to start a Stripe checkout session -> 403
    res_checkout = client.post(
        "/api/billing/create-checkout-session",
        json={"plan_id": "enterprise"},
        headers={"Authorization": f"Bearer {token_member_a}"},
    )
    assert res_checkout.status_code == 403


def test_http_owner_can_update_roles_and_remove_members():
    """Owner can update roles and remove members, but cannot remove the only owner."""
    client = TestClient(app)
    token_owner_a = create_jwt(user_id=OWNER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr", role="owner")

    # 1. Owner updates Member A to 'read_only'
    res_up = client.put(
        f"/api/team/members/{MEMBER_A_ID}/role",
        json={"role": "read_only"},
        headers={"Authorization": f"Bearer {token_owner_a}"},
    )
    assert res_up.status_code == 200
    assert res_up.json()["role"] == "read_only"

    # 2. Owner removes Member A
    res_del = client.delete(f"/api/team/members/{MEMBER_A_ID}", headers={"Authorization": f"Bearer {token_owner_a}"})
    assert res_del.status_code == 200

    # 3. Verify Member A is gone
    res_team = client.get("/api/team/members", headers={"Authorization": f"Bearer {token_owner_a}"})
    assert len(res_team.json()) == 1

    # 4. Attempting to delete the only remaining owner returns 400 Bad Request
    res_del_last_owner = client.delete(f"/api/team/members/{OWNER_A_ID}", headers={"Authorization": f"Bearer {token_owner_a}"})
    assert res_del_last_owner.status_code == 400
    assert "Cannot remove the last owner" in res_del_last_owner.json()["detail"]


def test_http_cross_tenant_member_mutation_blocked():
    """Owner B cannot modify or delete Tenant A's members under Postgres RLS."""
    client = TestClient(app)
    token_owner_b = create_jwt(user_id=OWNER_B_ID, tenant_id=TENANT_B_ID, email="owner.b@bouygbtp.fr", role="owner")

    # 1. Owner B attempts to change Tenant A's member role -> 404
    res_role = client.put(
        f"/api/team/members/{MEMBER_A_ID}/role",
        json={"role": "owner"},
        headers={"Authorization": f"Bearer {token_owner_b}"},
    )
    assert res_role.status_code == 404

    # 2. Owner B attempts to delete Tenant A's member -> 404
    res_del = client.delete(f"/api/team/members/{MEMBER_A_ID}", headers={"Authorization": f"Bearer {token_owner_b}"})
    assert res_del.status_code == 404


def test_http_demoted_owner_with_valid_jwt_immediately_loses_owner_privileges_403():
    """When an owner is demoted in DB to member, their existing valid JWT with role='owner' is immediately rejected (403)."""
    client = TestClient(app)
    SECOND_OWNER_ID = "11111111-cccc-dddd-eeee-ffffffffffff"

    # 1. Promote or insert second owner into Tenant A
    token_primary_owner = create_jwt(user_id=OWNER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr", role="owner")
    
    # First, insert second owner in Postgres
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES (%s, %s, 'co-owner.a@eiffabtp.fr', 'Co-Directeur A', 'owner')
            ON CONFLICT (id) DO UPDATE SET role = 'owner';
        """, (SECOND_OWNER_ID, TENANT_A_ID))
    finally:
        cur.close()
        conn.close()

    # 2. Generate a valid unexpired JWT token for second owner claiming role='owner'
    token_second_owner = create_jwt(
        user_id=SECOND_OWNER_ID,
        tenant_id=TENANT_A_ID,
        email="co-owner.a@eiffabtp.fr",
        role="owner",
    )

    # 3. Before demotion: Second owner can access owner-only endpoint
    res_before = client.get("/api/team/invitations", headers={"Authorization": f"Bearer {token_second_owner}"})
    assert res_before.status_code == 200

    # 4. Primary owner demotes second owner to 'member' in database
    res_demote = client.put(
        f"/api/team/members/{SECOND_OWNER_ID}/role",
        json={"role": "member"},
        headers={"Authorization": f"Bearer {token_primary_owner}"},
    )
    assert res_demote.status_code == 200
    assert res_demote.json()["role"] == "member"

    # 5. Second owner retries owner action with OLD VALID JWT (which still claims role='owner')
    res_after = client.get("/api/team/invitations", headers={"Authorization": f"Bearer {token_second_owner}"})
    
    # Must be 403 Forbidden immediately via live database check
    assert res_after.status_code == 403
    assert "Tenant owner privileges required" in res_after.json()["detail"]
    assert "live role in database is 'member'" in res_after.json()["detail"]

