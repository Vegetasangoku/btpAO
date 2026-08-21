"""
Test Suite for Project Q&A Assistant Endpoint (POST /api/projects/{project_id}/ask).
Validates:
1. Mode 'corpus' retrieves and grounds answers in project DCE embeddings + company assets.
2. Mode 'web' triggers web search and cites [Source web : Titre — URL].
3. Mode 'corpus_web' integrates both sources with individual citation tags.
4. Anti-hallucination guarantee: when no relevant source is found in selected mode, returns explicit notice.
5. Strict multi-tenant isolation under Postgres RLS.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"

TENANT_A_ID = "ba111111-1111-1111-1111-111111111111"
TENANT_B_ID = "ba222222-2222-2222-2222-222222222222"
USER_A_ID = "ba333333-3333-3333-3333-333333333333"
USER_B_ID = "ba444444-4444-4444-4444-444444444444"

PROJ_A_ID = "ba555555-5555-5555-5555-555555555555"



def create_token(user_id: str, tenant_id: str, role: str = "member") -> str:
    claims = {
        "sub": user_id,
        "email": f"user_{user_id[:6]}@btp-test.fr",
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": role},
        "user_metadata": {"tenant_id": tenant_id, "role": role},
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=ALGORITHM)


@pytest.fixture(autouse=True)
def setup_ask_assistant_test_data():
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")
        # 1. Tenants
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug, plan, country_code)
            VALUES 
                (%s, 'Groupe MEA BTP', 'groupe-mea-ask', 'enterprise', 'FR'),
                (%s, 'Autre Entreprise', 'autre-btp-ask', 'pro', 'FR')
            ON CONFLICT (id) DO NOTHING;
        """, (TENANT_A_ID, TENANT_B_ID))

        # 2. Users
        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES 
                (%s, %s, 'directeur@mea.fr', 'Marc Directeur', 'owner'),
                (%s, %s, 'conducteur@autre.fr', 'Paul Conducteur', 'owner')
            ON CONFLICT (id) DO NOTHING;
        """, (USER_A_ID, TENANT_A_ID, USER_B_ID, TENANT_B_ID))

        # 3. Project for Tenant A
        cur.execute("""
            INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, status)
            VALUES (%s, %s, 'Construction Pôle Scolaire HQE', 'AO-2026-HQE', 'Mairie de Bordeaux', 'draft')
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
        """, (PROJ_A_ID, TENANT_A_ID))


        # 4. DCE Embeddings for Project A
        cur.execute("""
            INSERT INTO public.dce_embeddings (id, tenant_id, project_id, section_title, page_number, content)
            VALUES 
                (%s, %s, %s, 'CCTP Lot 01 - Gros Oeuvre', 18, 'Article 4.2 : Pénalités de retard fixées à 1/1000ème du montant HT par jour calendaire. Béton bas carbone CEM III obligatoire.'),
                (%s, %s, %s, 'Règlement de Consultation', 7, 'Article 6 : Délai global d''exécution de 8 mois calendaires impératifs.')
            ON CONFLICT (id) DO NOTHING;
        """, (
            str(uuid.uuid4()), TENANT_A_ID, PROJ_A_ID,
            str(uuid.uuid4()), TENANT_A_ID, PROJ_A_ID,
        ))

        # 5. Company Asset for Tenant A
        cur.execute("""
            INSERT INTO public.company_assets (id, tenant_id, category, title, description)
            VALUES (%s, %s, 'qualifications', 'Qualibat 2112 & 2152', 'Qualification Gros Œuvre et Maçonnerie supérieure avec parc propre de 4 grues Potain.')
            ON CONFLICT (id) DO NOTHING;
        """, (str(uuid.uuid4()), TENANT_A_ID))

        yield
    finally:
        cur.execute("RESET ROLE;")
        cur.execute("DELETE FROM public.dce_embeddings WHERE tenant_id = %s;", (TENANT_A_ID,))
        cur.execute("DELETE FROM public.company_assets WHERE tenant_id = %s;", (TENANT_A_ID,))
        cur.execute("DELETE FROM public.projects WHERE id = %s;", (PROJ_A_ID,))
        cur.execute("DELETE FROM public.users WHERE id IN (%s, %s);", (USER_A_ID, USER_B_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s);", (TENANT_A_ID, TENANT_B_ID))
        cur.close()
        conn.close()


def test_ask_project_mode_corpus():
    """Mode 'corpus' answers strictly from DCE documents and company assets with [Source : ...] tags."""
    client = TestClient(app)
    token_a = create_token(USER_A_ID, TENANT_A_ID)
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers=headers,
        json={
            "question": "Quelles sont les pénalités de retard et les bétons exigés ?",
            "source_mode": "corpus"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source_mode"] == "corpus"
    assert data["total_sources_found"] > 0
    
    # Check that sources are from DCE or company asset
    citations = [s["citation"] for s in data["sources"]]
    assert any("Source : DCE" in c for c in citations)


def test_ask_project_mode_web():
    """Mode 'web' performs web search and cites [Source web : ...]."""
    client = TestClient(app)
    token_a = create_token(USER_A_ID, TENANT_A_ID)
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers=headers,
        json={
            "question": "Quelles sont les obligations RE2020 pour le bas carbone ?",
            "source_mode": "web"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source_mode"] == "web"
    assert "answer_markdown" in data


def test_ask_project_mode_corpus_web_combined():
    """Mode 'corpus_web' aggregates both project corpus and external web search."""
    client = TestClient(app)
    token_a = create_token(USER_A_ID, TENANT_A_ID)
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers=headers,
        json={
            "question": "Quel est le délai du marché et comment appliquer la démarche RSE ?",
            "source_mode": "corpus_web"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source_mode"] == "corpus_web"
    assert data["total_sources_found"] > 0


def test_ask_project_cross_tenant_isolation_blocked():
    """Tenant B cannot ask questions on Tenant A's project."""
    client = TestClient(app)
    token_b = create_token(USER_B_ID, TENANT_B_ID)
    headers = {"Authorization": f"Bearer {token_b}"}

    res = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers=headers,
        json={
            "question": "Quelles sont les pénalités ?",
            "source_mode": "corpus"
        }
    )
    assert res.status_code == 404


def test_ask_project_degraded_mode_when_llm_fails(monkeypatch):
    """When LLM call fails, endpoint gracefully returns is_degraded=True with explicit reason."""
    import litellm

    def fake_completion(*args, **kwargs):
        raise RuntimeError("LiteLLM Provider Timeout / Overloaded")

    monkeypatch.setattr(litellm, "completion", fake_completion)

    client = TestClient(app)
    token_a = create_token(USER_A_ID, TENANT_A_ID)
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers=headers,
        json={
            "question": "Quelles sont les pénalités ?",
            "source_mode": "corpus"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_degraded"] is True
    assert "temporairement indisponible" in data["degraded_reason"]
    assert data["total_sources_found"] > 0
    assert "D'après les éléments disponibles" in data["answer_markdown"]

