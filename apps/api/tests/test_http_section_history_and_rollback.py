"""
Real HTTP Integration Test for Section Version History & Rollback Multi-Tenant Isolation.
Tests:
1. Every edit on PUT /api/generate/section/{section_id} automatically archives the prior version in DB.
2. GET /api/generate/section/{section_id}/history lists all archived versions in reverse order.
3. POST /api/generate/section/{section_id}/restore/{version_id} archives current state before restoring target version (no data loss).
4. Cross-tenant access (reading or restoring another tenant's versions) is strictly blocked under Postgres RLS.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PROJ_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJ_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
SEC_A_ID = "55555555-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SEC_B_ID = "66666666-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_jwt(user_id: str, tenant_id: str, email: str) -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": "conducteur_travaux"},
        "user_metadata": {"tenant_id": tenant_id},
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_postgres_section_history():
    """Initializes schema and seeds realistic test sections for both Tenant A and Tenant B."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # 1. Tenants & Projects & Users
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES 
            (%s, 'EiffaBTP Construction', 'eiffabtp-hist'),
            (%s, 'BouygBTP Bâtiment', 'bouygbtp-hist')
            ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug;

            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES
            (%s, %s, 'user.a@eiffabtp.fr', 'Conducteur A', 'conducteur_travaux'),
            (%s, %s, 'user.b@bouygbtp.fr', 'Conducteur B', 'conducteur_travaux')
            ON CONFLICT (id) DO NOTHING;

            INSERT INTO public.projects (id, tenant_id, reference_code, title, client_name, location)
            VALUES 
            (%s, %s, 'AO-HIST-A', 'Chantier A Historique', 'Mairie Paris', 'Paris'),
            (%s, %s, 'AO-HIST-B', 'Chantier B Historique', 'Mairie Lyon', 'Lyon')
            ON CONFLICT (id) DO NOTHING;
        """, (
            TENANT_A_ID, TENANT_B_ID,
            USER_A_ID, TENANT_A_ID,
            USER_B_ID, TENANT_B_ID,
            PROJ_A_ID, TENANT_A_ID,
            PROJ_B_ID, TENANT_B_ID,
        ))


        # 2. Subscriptions
        cur.execute("""
            INSERT INTO public.tenant_subscriptions (id, tenant_id, plan_id, status, billing_mode, allow_overage)
            VALUES 
            (gen_random_uuid(), %s, 'pro', 'active', 'stripe', true),
            (gen_random_uuid(), %s, 'pro', 'active', 'stripe', true)
            ON CONFLICT (tenant_id) DO UPDATE SET status = 'active';
        """, (TENANT_A_ID, TENANT_B_ID))

        # 3. Clean and seed initial generated sections
        cur.execute("DELETE FROM public.generated_section_versions WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))

        cur.execute("""
            INSERT INTO public.generated_sections (id, tenant_id, project_id, section_key, title, order_index, content_html, compliance_score, compliance_notes, status)
            VALUES
            (%s, %s, %s, 'moyens_humains', '1. Encadrement Chantier', 1, '<p>Version Initiale Générée par IA pour Tenant A</p>', 95.0, 'Conforme initiale', 'generated'),
            (%s, %s, %s, 'moyens_humains', '1. Encadrement Chantier', 1, '<p>Version Initiale Générée par IA pour Tenant B</p>', 92.0, 'Conforme initiale', 'generated');
        """, (SEC_A_ID, TENANT_A_ID, PROJ_A_ID, SEC_B_ID, TENANT_B_ID, PROJ_B_ID))

    finally:
        cur.close()
        conn.close()


def test_http_edit_section_automatically_archives_previous_versions():
    """Editing a section twice creates version 1 and version 2 in history, keeping all prior states intact."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    headers = {"Authorization": f"Bearer {token_a}"}

    # 1. Initial history is empty
    res_h0 = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers=headers)
    assert res_h0.status_code == 200
    assert len(res_h0.json()) == 0

    # 2. First edit (archive version 1)
    edit1 = {
        "content_html": "<p>Première modification par le conducteur : ajout de Jean-Marc Alibert ESTP</p>",
        "change_summary": "Ajout du conducteur de travaux principal",
    }
    res1 = client.put(f"/api/generate/section/{SEC_A_ID}", json=edit1, headers=headers)
    assert res1.status_code == 200
    assert "Jean-Marc Alibert" in res1.json()["content_html"]

    # History should now contain 1 version (the initial state)
    res_h1 = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers=headers)
    assert res_h1.status_code == 200
    hist1 = res_h1.json()
    assert len(hist1) == 1
    assert hist1[0]["version_number"] == 1
    assert "Version Initiale Générée par IA" in hist1[0]["content_html"]

    # 3. Second edit (archive version 2)
    edit2 = {
        "content_html": "<p>Deuxième modification : ajout du chef de chantier et grutier CACES</p>",
        "change_summary": "Ajout du chef de chantier",
    }
    res2 = client.put(f"/api/generate/section/{SEC_A_ID}", json=edit2, headers=headers)
    assert res2.status_code == 200
    assert "grutier CACES" in res2.json()["content_html"]

    # History should now contain 2 versions (v2 and v1)
    res_h2 = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers=headers)
    assert res_h2.status_code == 200
    hist2 = res_h2.json()
    assert len(hist2) == 2
    assert hist2[0]["version_number"] == 2
    assert "Jean-Marc Alibert" in hist2[0]["content_html"]
    assert hist2[1]["version_number"] == 1
    assert "Version Initiale" in hist2[1]["content_html"]


def test_http_restore_previous_version_archives_current_state_and_restores_content():
    """Restoring an older version restores its HTML and archives the current state as a new version (zero data loss)."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    headers = {"Authorization": f"Bearer {token_a}"}

    # 1. Make an edit to generate v1 in history
    client.put(
        f"/api/generate/section/{SEC_A_ID}",
        json={"content_html": "<p>Texte Modifié v2 qui sera ensuite écrasé</p>"},
        headers=headers,
    )

    # 2. Get history and find v1
    hist_res = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers=headers)
    versions = hist_res.json()
    assert len(versions) == 1
    v1 = versions[0]
    assert v1["version_number"] == 1
    v1_id = v1["id"]

    # 3. Restore v1
    restore_res = client.post(f"/api/generate/section/{SEC_A_ID}/restore/{v1_id}", headers=headers)
    assert restore_res.status_code == 200
    restored_sec = restore_res.json()
    assert restored_sec["status"] == "restored"
    assert "Version Initiale Générée par IA" in restored_sec["content_html"]

    # 4. Check history after restore: it must contain v2 (the state before restore) and v1
    hist_after = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers=headers).json()
    assert len(hist_after) == 2
    assert hist_after[0]["version_number"] == 2
    assert "Texte Modifié v2 qui sera ensuite écrasé" in hist_after[0]["content_html"]
    assert "Archivé avant restauration" in hist_after[0]["change_summary"]


def test_http_section_history_cross_tenant_isolation_blocked():
    """Tenant B cannot view, modify, or restore Tenant A's section versions under Postgres RLS."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="user.a@eiffabtp.fr")
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="user.b@bouygbtp.fr")

    # 1. Tenant A makes an edit to generate a version
    client.put(
        f"/api/generate/section/{SEC_A_ID}",
        json={"content_html": "<p>Secret confidentiel méthode gros oeuvre Tenant A</p>"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Fetch Tenant A's version id
    hist_a = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert len(hist_a) == 1
    version_a_id = hist_a[0]["id"]

    # 2. Tenant B attempts to read Tenant A's history -> 404 (RLS blocks)
    res_b_get = client.get(f"/api/generate/section/{SEC_A_ID}/history", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_get.status_code == 404

    # 3. Tenant B attempts to restore Tenant A's version into Tenant A's section -> 404
    res_b_restore = client.post(
        f"/api/generate/section/{SEC_A_ID}/restore/{version_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_restore.status_code == 404

    # 4. Tenant B attempts to restore Tenant A's version into Tenant B's own section -> 404 (version belongs to Tenant A)
    res_b_cross_restore = client.post(
        f"/api/generate/section/{SEC_B_ID}/restore/{version_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_cross_restore.status_code == 404
