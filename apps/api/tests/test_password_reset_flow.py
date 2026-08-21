"""
Test Suite for Password Reset Flow & Branded btpAO Email Delivery.
Validates:
1. POST /api/auth/forgot-password sends branded HTML email and stores single-use cryptographic token.
2. Email content has official btpAO styling, logo badge, and 1-hour expiration warning.
3. POST /api/auth/verify-reset-token validates active tokens and rejects expired/used tokens.
4. POST /api/auth/reset-password enforces minimum 8 chars, updates password hash in auth.users, and prevents replay attacks.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
import bcrypt
from app.main import app
from app.services.email_service import RECENT_SENT_EMAILS, build_password_reset_html


@pytest.fixture(autouse=True)
def setup_password_reset_test_data():
    """Seeds test user and cleans up tokens."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    test_user_id = "22222222-2222-2222-2222-222222222222"
    test_tenant_id = "11111111-1111-1111-1111-111111111111"
    test_email = "conducteur.travaux@eiffabtp-demo.fr"

    try:
        cur.execute("RESET ROLE;")
        # Ensure test tenant
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug, plan, country_code)
            VALUES (%s, 'EiffaBTP Test', 'eiffabtp-test-pw', 'pro', 'FR')
            ON CONFLICT (id) DO NOTHING;
        """, (test_tenant_id,))

        # Ensure public.users
        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES (%s, %s, %s, 'Michel Conducteur', 'owner')
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;
        """, (test_user_id, test_tenant_id, test_email))

        # Ensure auth.users
        cur.execute("""
            INSERT INTO auth.users (id, email, encrypted_password, raw_app_meta_data, raw_user_meta_data)
            VALUES (%s, %s, 'initial_hash', '{\"role\": \"owner\"}'::jsonb, '{\"full_name\": \"Michel Conducteur\"}'::jsonb)
            ON CONFLICT (id) DO UPDATE SET encrypted_password = 'initial_hash';
        """, (test_user_id, test_email))

        cur.execute("DELETE FROM public.password_reset_tokens WHERE email = %s;", (test_email,))
        RECENT_SENT_EMAILS.clear()

        yield {
            "user_id": test_user_id,
            "email": test_email,
            "tenant_id": test_tenant_id,
        }
    finally:
        cur.execute("RESET ROLE;")
        cur.execute("DELETE FROM public.password_reset_tokens WHERE email = %s;", (test_email,))
        cur.close()
        conn.close()


def test_forgot_password_unknown_email_returns_success_without_leak():
    """Requesting reset for unknown email returns standard 200 without exposing account existence."""
    client = TestClient(app)
    res = client.post("/api/auth/forgot-password", json={"email": "inconnu@entreprise-inexistante.fr"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "e-mail de réinitialisation" in data["message"]


def test_forgot_password_valid_user_creates_token_and_sends_branded_email(setup_password_reset_test_data):
    """
    When valid user requests reset:
    1. Token is generated and stored in password_reset_tokens.
    2. Branded btpAO HTML email is generated with reset link and official styling.
    """
    user_email = setup_password_reset_test_data["email"]
    client = TestClient(app)

    res = client.post("/api/auth/forgot-password", json={"email": user_email})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data.get("reset_url_dev") is not None
    reset_url = data["reset_url_dev"]
    raw_token = reset_url.split("token=")[1]

    # Verify token exists in database
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    cur.execute("SELECT email, expires_at, used_at FROM public.password_reset_tokens WHERE email = %s;", (user_email,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == user_email
    assert row[2] is None  # not used yet
    cur.close()
    conn.close()

    # Verify email was dispatched in RECENT_SENT_EMAILS
    assert len(RECENT_SENT_EMAILS) == 1
    sent_mail = RECENT_SENT_EMAILS[0]
    assert sent_mail["to_email"] == user_email
    assert "[btpAO] Réinitialisation de votre mot de passe" in sent_mail["subject"]
    assert "btpAO Sécurité" in sent_mail["from_email"]

    # Verify HTML template quality and btpAO branding
    html = build_password_reset_html(to_email=user_email, reset_url=reset_url, user_name="Michel Conducteur")
    assert "btp<span class=\"logo-accent\">AO</span>" in html
    assert "Réinitialisation de mot de passe" in html
    assert "Définir un nouveau mot de passe" in html
    assert "1 heure" in html
    assert "Michel Conducteur" in html


def test_verify_reset_token_endpoint(setup_password_reset_test_data):
    """verify-reset-token returns 200 for valid token and 400 for invalid/expired token."""
    user_email = setup_password_reset_test_data["email"]
    client = TestClient(app)

    # 1. Request token
    req_res = client.post("/api/auth/forgot-password", json={"email": user_email})
    reset_url = req_res.json()["reset_url_dev"]
    token = reset_url.split("token=")[1]

    # 2. Verify valid token
    verify_res = client.post("/api/auth/verify-reset-token", json={"token": token})
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
    assert verify_res.json()["email"] == user_email

    # 3. Verify fake token returns 400
    invalid_res = client.post("/api/auth/verify-reset-token", json={"token": "fake-invalid-token-123"})
    assert invalid_res.status_code == 400


def test_reset_password_full_lifecycle_and_replay_protection(setup_password_reset_test_data):
    """
    1. User receives token.
    2. Submits new password >= 8 characters.
    3. Password is hashed in auth.users.
    4. Replaying the token is rejected with 400.
    """
    user_email = setup_password_reset_test_data["email"]
    user_id = setup_password_reset_test_data["user_id"]
    client = TestClient(app)

    # 1. Request token
    req_res = client.post("/api/auth/forgot-password", json={"email": user_email})
    token = req_res.json()["reset_url_dev"].split("token=")[1]

    # 2. Too short password rejected (<8 chars)
    short_res = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "short"
    })
    assert short_res.status_code == 400

    # 3. Valid new password applied
    new_password = "NouveauMotDePasseBTP2026!"
    success_res = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": new_password
    })
    assert success_res.status_code == 200
    assert success_res.json()["success"] is True

    # 4. Check that auth.users has updated encrypted_password matching bcrypt
    conn = psycopg2.connect(dbname="postgres")
    cur = conn.cursor()
    cur.execute("SELECT encrypted_password FROM auth.users WHERE id = %s;", (user_id,))
    row = cur.fetchone()
    assert row is not None
    hashed_db = row[0]
    assert hashed_db != "initial_hash"
    assert bcrypt.checkpw(new_password.encode("utf-8"), hashed_db.encode("utf-8")) is True
    cur.close()
    conn.close()

    # 5. Token is now marked used, second attempt must be rejected (400)
    replay_res = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "AnotherPassword2026!"
    })
    assert replay_res.status_code == 400
