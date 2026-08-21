"""
HTTP & Worker Integration Tests for AO History, Outcome Tracking, and Continuous Learning Loop.
Tests:
1. POST /projects/{id}/outcome records won/lost status and buyer debrief.
2. When marked lost with buyer feedback, TenantLearning items are automatically distilled and stored.
3. GET /projects/history displays accurate metrics (or 'Données insuffisantes' if no closed projects).
4. generate_section_task integrates tenant learnings into generated memo section.
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
from app.workers.tasks import generate_section_task

TENANT_A_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_B_ID = "bbbbbbbb-2222-2222-2222-222222222222"
USER_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

PROJ_A1_ID = "aaaaaaaa-aaaa-1111-1111-111111111111"
PROJ_A2_ID = "aaaaaaaa-aaaa-2222-2222-222222222222"
PROJ_B1_ID = "bbbbbbbb-bbbb-1111-1111-111111111111"

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_jwt(user_id: str, tenant_id: str, email: str, role: str = "owner") -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": role},
        "user_metadata": {"tenant_id": tenant_id, "role": role},
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_postgres_projects_outcomes():
    """Initializes schema and seeds clean projects for outcome tests."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # Seed Tenants
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES 
            (%s, 'EiffaBTP Construction', 'eiffabtp-outcomes'),
            (%s, 'BouygBTP Bâtiment', 'bouygbtp-outcomes')
            ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug;
        """, (TENANT_A_ID, TENANT_B_ID))

        # Seed Users
        cur.execute("DELETE FROM public.tenant_learnings WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.execute("DELETE FROM public.users WHERE tenant_id IN (%s, %s) OR id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID, USER_A_ID, USER_B_ID))


        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES
            (%s, %s, 'owner.a@eiffabtp.fr', 'Directeur A', 'owner'),
            (%s, %s, 'owner.b@bouygbtp.fr', 'Directeur B', 'owner');
        """, (USER_A_ID, TENANT_A_ID, USER_B_ID, TENANT_B_ID))

        # Seed Projects
        cur.execute("""
            INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, status, outcome_status, created_by)
            VALUES
            (%s, %s, 'Construction Lycée HQE', 'AO-2026-LYC-01', 'Région Île-de-France', 'draft', 'pending', %s),
            (%s, %s, 'Rénovation Énergétique Gymnase', 'AO-2026-GYM-02', 'Ville de Nanterre', 'draft', 'pending', %s),
            (%s, %s, 'Hôpital Extension Nord', 'AO-2026-HOP-01', 'AP-HP', 'draft', 'pending', %s);
        """, (
            PROJ_A1_ID, TENANT_A_ID, USER_A_ID,
            PROJ_A2_ID, TENANT_A_ID, USER_A_ID,
            PROJ_B1_ID, TENANT_B_ID, USER_B_ID,
        ))

    finally:
        cur.close()
        conn.close()


def test_http_projects_history_empty_shows_donnees_insuffisantes():
    """When tenant has no closed projects (all pending), history displays 'Données insuffisantes'."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr")

    res = client.get("/api/projects/history", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_projects"] == 2
    assert data["closed_projects"] == 0
    assert data["won_count"] == 0
    assert data["lost_count"] == 0
    assert data["win_rate_percentage"] is None
    assert data["win_rate_display"] == "Données insuffisantes"


def test_http_record_project_outcome_lost_automatically_creates_tenant_learnings():
    """When an AO is marked lost with buyer feedback, TenantLearning items are extracted and stored."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr")

    payload = {
        "outcome_status": "lost",
        "buyer_feedback": {
            "technical_score": 14.5,
            "price_score": 16.0,
            "points_faibles": [
                "Planning de phasage jugé trop optimiste sans justification des temps de séchage de dalle",
                "Gestion des déchets : absence de précision sur le taux de valorisation des terres excavées",
            ],
            "points_forts": [
                "Excellente qualification de l'encadrement chantier ESTP",
            ],
            "general_comments": "Offre technique solide mais pénalisée sur le planning et le sous-détail RSE.",
            "winning_bidder": "BouygBTP",
            "winning_amount": 4200000.0,
        },
        "notes": "Débriefing acheteur obtenu le 20/08/2026 avec l'acheteur public.",
    }

    # 1. Record outcome
    res = client.post(f"/api/projects/{PROJ_A1_ID}/outcome", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    proj_data = res.json()
    assert proj_data["outcome_status"] == "lost"
    assert proj_data["buyer_feedback"]["technical_score"] == 14.5

    # 2. Check that tenant learnings were automatically extracted
    res_learn = client.get("/api/projects/learnings", headers={"Authorization": f"Bearer {token_a}"})
    assert res_learn.status_code == 200
    learnings = res_learn.json()
    assert len(learnings) >= 2

    categories = [l["category"] for l in learnings]
    assert "planning" in categories
    assert "qse" in categories

    planning_learning = next(l for l in learnings if l["category"] == "planning")
    assert "séchage" in planning_learning["learning_insight"].lower()
    assert "Directive obligatoire" in planning_learning["actionable_directive"]

    # 3. Check that history metrics are now updated
    res_hist = client.get("/api/projects/history", headers={"Authorization": f"Bearer {token_a}"})
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert hist["total_projects"] == 2
    assert hist["closed_projects"] == 1
    assert hist["lost_count"] == 1
    assert hist["won_count"] == 0
    assert hist["win_rate_percentage"] == 0.0
    assert hist["win_rate_display"] == "0.0%"


def test_http_record_project_outcome_won_and_win_rate_computation():
    """Records won project and verifies positive win rate calculation in history."""
    client = TestClient(app)
    token_a = create_jwt(user_id=USER_A_ID, tenant_id=TENANT_A_ID, email="owner.a@eiffabtp.fr")

    # 1. Mark Project A1 as WON
    payload1 = {
        "outcome_status": "won",
        "buyer_feedback": {
            "technical_score": 19.2,
            "points_forts": ["Mémoire technique parfaitement adapté aux contraintes de site urbain dense"],
        },
    }
    client.post(f"/api/projects/{PROJ_A1_ID}/outcome", json=payload1, headers={"Authorization": f"Bearer {token_a}"})

    # 2. Mark Project A2 as LOST
    payload2 = {
        "outcome_status": "lost",
        "buyer_feedback": {
            "technical_score": 15.0,
            "points_faibles": ["Sous-détail du PIC insuffisant"],
        },
    }
    client.post(f"/api/projects/{PROJ_A2_ID}/outcome", json=payload2, headers={"Authorization": f"Bearer {token_a}"})

    # 3. Check history: 1 won, 1 lost -> 50.0% win rate
    res_hist = client.get("/api/projects/history", headers={"Authorization": f"Bearer {token_a}"})
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert hist["total_projects"] == 2
    assert hist["closed_projects"] == 2
    assert hist["won_count"] == 1
    assert hist["lost_count"] == 1
    assert hist["win_rate_percentage"] == 50.0
    assert hist["win_rate_display"] == "50.0%"


def test_celery_generate_section_task_integrates_tenant_learnings():
    """Worker task generate_section_task incorporates accumulated tenant learnings into generated HTML."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        # Seed an active TenantLearning for Tenant A
        cur.execute("""
            INSERT INTO public.tenant_learnings (id, tenant_id, category, title, learning_insight, actionable_directive, is_active)
            VALUES (gen_random_uuid(), %s, 'planning', 'Exigence séchage béton', 'Temps de séchage critiqué', 'Toujours justifier les cadencements avec fiches techniques de prise rapide', true);
        """, (TENANT_A_ID,))
    finally:
        cur.close()
        conn.close()

    # Run celery worker task
    result = generate_section_task(
        tenant_id=TENANT_A_ID,
        project_id=PROJ_A1_ID,
        section_key="planning_phasage",
    )
    assert result["status"] == "completed"


    # Verify generated section in Postgres
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SELECT content_html FROM public.generated_sections WHERE project_id = %s;", (PROJ_A1_ID,))
        row = cur.fetchone()
        assert row is not None
        content_html = row[0]
        assert "Retour d'Expérience & Enseignements Capitalisés du Tenant" in content_html
        assert "cadencements avec fiches techniques de prise rapide" in content_html
    finally:
        cur.close()
        conn.close()


def test_http_cross_tenant_outcomes_and_learnings_isolation():
    """Tenant B cannot view Tenant A's history/learnings or mutate Tenant A's project outcomes."""
    client = TestClient(app)
    token_b = create_jwt(user_id=USER_B_ID, tenant_id=TENANT_B_ID, email="owner.b@bouygbtp.fr")

    # 1. Tenant B history only contains Project B1
    res_hist = client.get("/api/projects/history", headers={"Authorization": f"Bearer {token_b}"})
    assert res_hist.status_code == 200
    projects_b = res_hist.json()["projects"]
    assert len(projects_b) == 1
    assert projects_b[0]["id"] == PROJ_B1_ID

    # 2. Tenant B attempts to record outcome on Project A1 -> 404
    payload = {"outcome_status": "won"}
    res_mutate = client.post(f"/api/projects/{PROJ_A1_ID}/outcome", json=payload, headers={"Authorization": f"Bearer {token_b}"})
    assert res_mutate.status_code == 404
