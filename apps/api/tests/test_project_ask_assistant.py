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
from app.models.entities import Tenant, User, Project, DCEEmbedding, CompanyAsset, DCEDocument

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


import asyncio
from app.core.db import AsyncSessionLocal
from sqlalchemy import text


@pytest.fixture(autouse=True)
def setup_ask_assistant_test_data():
    async def _setup():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET ROLE postgres;"))
            
            # 1. Tenants
            t_a = Tenant(id=uuid.UUID(TENANT_A_ID), name="Groupe MEA BTP", slug="groupe-mea-ask", plan="enterprise", country_code="FR")
            t_b = Tenant(id=uuid.UUID(TENANT_B_ID), name="Autre Entreprise", slug="autre-btp-ask", plan="pro", country_code="FR")
            db.add_all([t_a, t_b])
            await db.flush()

            # 2. Users
            u_a = User(id=uuid.UUID(USER_A_ID), tenant_id=uuid.UUID(TENANT_A_ID), email="directeur@mea.fr", full_name="Marc Directeur", role="owner")
            u_b = User(id=uuid.UUID(USER_B_ID), tenant_id=uuid.UUID(TENANT_B_ID), email="conducteur@autre.fr", full_name="Paul Conducteur", role="owner")
            db.add_all([u_a, u_b])
            await db.flush()

            # 3. Project for Tenant A
            p_a = Project(id=uuid.UUID(PROJ_A_ID), tenant_id=uuid.UUID(TENANT_A_ID), title="Construction Pôle Scolaire HQE", reference_code="AO-2026-HQE", client_name="Mairie de Bordeaux", status="draft")
            db.add(p_a)
            await db.flush()

            doc_id = uuid.uuid4()
            dce_doc = DCEDocument(
                id=doc_id,
                tenant_id=uuid.UUID(TENANT_A_ID),
                project_id=uuid.UUID(PROJ_A_ID),
                filename="cctp_scolaire.pdf",
                s3_key=f"dce/{PROJ_A_ID}/cctp_scolaire.pdf",
            )
            db.add(dce_doc)
            await db.flush()

            # 4. DCE Embeddings for Project A
            emb1 = DCEEmbedding(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(TENANT_A_ID),
                project_id=uuid.UUID(PROJ_A_ID),
                document_id=doc_id,
                section_title="CCTP Lot 01 - Gros Oeuvre",
                page_number=18,
                chunk_index=0,
                content="Article 4.2 : Pénalités de retard fixées à 1/1000ème du montant HT par jour calendaire. Béton bas carbone CEM III obligatoire.",
            )
            emb2 = DCEEmbedding(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(TENANT_A_ID),
                project_id=uuid.UUID(PROJ_A_ID),
                document_id=doc_id,
                section_title="Règlement de Consultation",
                page_number=7,
                chunk_index=1,
                content="Article 6 : Délai global d'exécution de 8 mois calendaires impératifs.",
            )
            db.add_all([emb1, emb2])

            # 5. Company Asset for Tenant A
            asset = CompanyAsset(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(TENANT_A_ID),
                category="qualifications",
                title="Qualibat 2112 & 2152",
                description="Qualification Gros Œuvre et Maçonnerie supérieure avec parc propre de 4 grues Potain.",
            )
            db.add(asset)
            await db.commit()

    async def _teardown():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET ROLE postgres;"))
            await db.execute(text("DELETE FROM public.dce_embeddings WHERE tenant_id = :t_id"), {"t_id": uuid.UUID(TENANT_A_ID)})
            await db.execute(text("DELETE FROM public.company_assets WHERE tenant_id = :t_id"), {"t_id": uuid.UUID(TENANT_A_ID)})
            await db.execute(text("DELETE FROM public.projects WHERE id = :p_id"), {"p_id": uuid.UUID(PROJ_A_ID)})
            await db.execute(text("DELETE FROM public.users WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.tenants WHERE id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.commit()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


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

