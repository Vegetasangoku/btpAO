"""
Test Suite for Phase B (Pre-filling & Missing Data Detection) and Phase C (Consent-based Continuous Learning).
"""
import asyncio
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.entities import (
    CompanyAsset,
    GeneratedSection,
    Project,
    Tenant,
    TenantLearning,
    User,
)
from app.services.learning_service import learning_service

TENANT_1_ID = "11111111-1111-1111-1111-111111111111"
TENANT_2_ID = "22222222-2222-2222-2222-222222222222"
USER_1_ID = "33333333-3333-3333-3333-333333333333"
USER_2_ID = "44444444-4444-4444-4444-444444444444"
PROJECT_1_ID = "55555555-5555-5555-5555-555555555555"
PROJECT_2_ID = "66666666-6666-6666-6666-666666666666"


JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"

def create_token(user_id: str, tenant_id: str) -> str:
    payload = {
        "sub": user_id,
        "email": f"user_{user_id[:8]}@test.fr",
        "tenant_id": tenant_id,
        "app_metadata": {"tenant_id": tenant_id},
        "user_metadata": {"tenant_id": tenant_id},
        "aud": "authenticated",
        "role": "authenticated",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    async def _setup():
        async with AsyncSessionLocal() as db:
            # 1. Clean up
            await db.execute(text("DELETE FROM tenant_learnings WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM generated_sections WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM company_assets WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM projects WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.commit()

            # 2. Tenants & Users
            t1 = Tenant(id=uuid.UUID(TENANT_1_ID), name="Entreprise BTP Riche SAS", slug="btp-riche")
            t2 = Tenant(id=uuid.UUID(TENANT_2_ID), name="Entreprise BTP Neuve SAS", slug="btp-neuve")
            u1 = User(id=uuid.UUID(USER_1_ID), tenant_id=uuid.UUID(TENANT_1_ID), email="u1@riche.fr", full_name="User 1", role="admin")
            u2 = User(id=uuid.UUID(USER_2_ID), tenant_id=uuid.UUID(TENANT_2_ID), email="u2@neuve.fr", full_name="User 2", role="admin")
            db.add_all([t1, t2, u1, u2])
            await db.commit()

            # 3. Projects
            p1 = Project(id=uuid.UUID(PROJECT_1_ID), tenant_id=uuid.UUID(TENANT_1_ID), title="Projet EHPAD Riche", reference_code="AO-2026-01", client_name="Conseil Dép")
            p2 = Project(id=uuid.UUID(PROJECT_2_ID), tenant_id=uuid.UUID(TENANT_2_ID), title="Projet Neuf", reference_code="AO-2026-02", client_name="Mairie")
            db.add_all([p1, p2])
            await db.commit()

            # 4. Rich history for Tenant 1
            a1 = CompanyAsset(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(TENANT_1_ID),
                title="Grue Potain MDT 219",
                category="materiel",
                description="Grue à tour de 65m de flèche disponible immédiatement avec système de limitation d'emprise.",
                validated_by_user=True,
            )
            l1 = TenantLearning(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(TENANT_1_ID),
                title="Béton bas carbone CEM III",
                category="methodology",
                learning_insight="Les acheteurs valorisent les bétons CEM III",
                actionable_directive="Spécifier le béton CEM III pour toutes les fondations et élévations.",
                learned_content="Utilisation systématique de formules de béton bas carbone CEM III/A certifiées NF.",
                is_active=True,
            )
            sec_past = GeneratedSection(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(TENANT_1_ID),
                project_id=uuid.UUID(PROJECT_1_ID),
                section_key="moyens_materiels",
                title="2. Moyens Matériels & PIC",
                order_index=2,
                content_html="<p>Notre parc comprend des grues électriques et des centrales à béton mobiles de dernière génération.</p>",
                status="validated",
            )
            db.add_all([a1, l1, sec_past])
            await db.commit()

    async def _teardown():
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM tenant_learnings WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM generated_sections WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM company_assets WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM projects WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": TENANT_1_ID, "t2": TENANT_2_ID})
            await db.commit()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


def test_diff_significance_calculation():
    # Minor edit (< 15%)
    old_t = "Notre entreprise met en place une grue a tour Potain MDT 219 de 65m de fleche."
    new_t = "Notre entreprise met en place une grue à tour Potain MDT 219 de 65m de flèche."
    is_sig, pct, summary = learning_service.calculate_diff_significance(old_t, new_t)
    assert is_sig is False
    assert pct < 15.0

    # Major edit (> 15% and content addition)
    major_t = "Notre entreprise met en place une grue à tour Potain MDT 219 de 65m de flèche avec télémétrie IoT en temps réel, bridage de zone automatique et un groupe électrogène hybride zéro émission sonore la nuit."
    is_sig2, pct2, summary2 = learning_service.calculate_diff_significance(old_t, major_t)
    assert is_sig2 is True
    assert pct2 > 15.0
    assert len(summary2) > 0


def test_prefill_with_rich_history_produces_prefilled_draft():
    client = TestClient(app)
    token1 = create_token(USER_1_ID, TENANT_1_ID)

    res = client.post(
        "/api/generate/section",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "project_id": PROJECT_1_ID,
            "section_key": "moyens_materiels",
            "mode": "prefill_draft",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "prefilled_draft"
    assert data["is_prefilled"] is True
    assert len(data["prefill_source"]) > 0
    assert "Grue Potain" in data["content_html"] or "moyens" in data["content_html"].lower()


def test_prefill_without_data_signals_missing_data():
    client = TestClient(app)
    token2 = create_token(USER_2_ID, TENANT_2_ID)

    res = client.post(
        "/api/generate/section",
        headers={"Authorization": f"Bearer {token2}"},
        json={
            "project_id": PROJECT_2_ID,
            "section_key": "securite_ppsps",
            "mode": "prefill_draft",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "missing_data"
    assert data["is_prefilled"] is False
    assert "Information requise :" in data["content_html"]
    assert "Il manque des informations sur" in data["content_html"]


def test_update_section_triggers_learning_opportunity_and_crud():
    client = TestClient(app)
    token1 = create_token(USER_1_ID, TENANT_1_ID)

    # 1. Fetch created section id
    res_list = client.get(f"/api/generate/sections/{PROJECT_1_ID}", headers={"Authorization": f"Bearer {token1}"})
    assert res_list.status_code == 200
    sections = res_list.json()
    assert len(sections) > 0
    sec_id = sections[0]["id"]

    # 2. Update section with major adjustment
    res_upd = client.put(
        f"/api/generate/section/{sec_id}",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "content_html": "<p>Nouvelle politique QSE : Nous imposons 100% de recyclage des agrégats avec tri 7 flux sur site et concassage mobile certifié CE.</p>",
            "change_summary": "Ajout politique QSE avancée",
        },
    )
    assert res_upd.status_code == 200
    upd_data = res_upd.json()
    assert upd_data["success"] is True
    assert upd_data["learning_opportunity"] is True
    assert upd_data["learning_proposal"] is not None

    # 3. Accept learning opportunity -> create tenant learning
    res_learn = client.post(
        "/api/generate/learnings",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "title": "Recyclage des agrégats tri 7 flux",
            "category": "qse",
            "section_type": "qse_environnement",
            "learned_content": upd_data["learning_proposal"]["suggested_content"],
        },
    )
    assert res_learn.status_code == 200
    learn_data = res_learn.json()
    learn_id = learn_data["id"]

    # 4. List learnings
    res_get_learn = client.get("/api/generate/learnings", headers={"Authorization": f"Bearer {token1}"})
    assert res_get_learn.status_code == 200
    all_learnings = res_get_learn.json()
    assert any(l["id"] == learn_id for l in all_learnings)

    # 5. Isolation: Tenant 2 cannot see Tenant 1 learning
    token2 = create_token(USER_2_ID, TENANT_2_ID)
    res_get_t2 = client.get("/api/generate/learnings", headers={"Authorization": f"Bearer {token2}"})
    assert res_get_t2.status_code == 200
    assert not any(l["id"] == learn_id for l in res_get_t2.json())

    # 6. Delete learning
    res_del = client.delete(f"/api/generate/learnings/{learn_id}", headers={"Authorization": f"Bearer {token1}"})
    assert res_del.status_code == 200
