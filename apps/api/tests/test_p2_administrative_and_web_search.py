"""
Test Suite for Lot P2:
1. Administrative Legal Dossiers (DC1, DC2, DUME Summary).
2. Multi-Provider Web Search Service (Brave Search / Serper).
3. Country Regulatory Profiles for Multi-Country Coverage.
"""
import asyncio
import uuid
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.entities import CountryRegulatoryProfile, Project, Tenant, User
from app.services.admin_dossier_service import admin_dossier_service
from app.services.web_search_service import web_search_service

TENANT_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "33333333-3333-3333-3333-333333333333"
PROJECT_ID = "55555555-5555-5555-5555-555555555555"

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
            await db.execute(text("DELETE FROM generated_sections WHERE tenant_id = :t1"), {"t1": TENANT_ID})
            await db.execute(text("DELETE FROM projects WHERE tenant_id = :t1"), {"t1": TENANT_ID})
            await db.execute(text("DELETE FROM users WHERE tenant_id = :t1"), {"t1": TENANT_ID})
            await db.execute(text("DELETE FROM tenants WHERE id = :t1"), {"t1": TENANT_ID})
            await db.commit()

            t = Tenant(id=uuid.UUID(TENANT_ID), name="BTP Construction Grand Ouest SAS", slug="btp-grand-ouest", siret="98765432100019", country_code="FR")
            u = User(id=uuid.UUID(USER_ID), tenant_id=uuid.UUID(TENANT_ID), email="u@grandouest.fr", full_name="Directeur Technique", role="admin")
            p = Project(id=uuid.UUID(PROJECT_ID), tenant_id=uuid.UUID(TENANT_ID), title="Construction Médiathèque Haute Performance", reference_code="AO-2026-MED", client_name="Région Bretagne")
            db.add(t)
            await db.flush()
            db.add(u)
            db.add(p)
            await db.commit()

    async def _teardown():
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM generated_sections WHERE tenant_id = :t1"), {"t1": TENANT_ID})
            await db.execute(text("DELETE FROM projects WHERE tenant_id = :t1"), {"t1": TENANT_ID})
            await db.execute(text("DELETE FROM users WHERE tenant_id = :t1"), {"t1": TENANT_ID})
            await db.execute(text("DELETE FROM tenants WHERE id = :t1"), {"t1": TENANT_ID})
            await db.commit()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


def test_dc1_export_endpoint():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        f"/api/dossiers/{PROJECT_ID}/dc1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert len(res.content) > 2000
    assert "DC1_Candidature_AO-2026-MED.docx" in res.headers.get("content-disposition", "")


def test_dc2_export_endpoint():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        f"/api/dossiers/{PROJECT_ID}/dc2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert len(res.content) > 2000
    assert "DC2_Declaration_AO-2026-MED.docx" in res.headers.get("content-disposition", "")


def test_dume_summary_endpoint():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        f"/api/dossiers/{PROJECT_ID}/dume",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["dume_version"] == "ESPD-EDM-V2.1.1"
    assert data["economic_operator"]["siret"] == "98765432100019"
    assert data["declaration_status"] == "draft_requires_human_validation"
    assert data["mandatory_validation_required"] is True
    assert data["exclusion_grounds"]["criminal_convictions"] is None


def test_regulatory_profile_endpoint():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        f"/api/dossiers/{PROJECT_ID}/regulatory-profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "code de la commande publique" in data["procurement_framework"].lower()


@pytest.mark.asyncio
async def test_multi_provider_web_search_service():
    results = await web_search_service.search(
        tenant_id=TENANT_ID,
        query="Béton bas carbone CEM III RE2020",
        num_results=3,
        project_id=PROJECT_ID,
    )
    assert len(results) > 0
    assert any("RE2020" in r.title or "Béton" in r.title or "INIES" in r.title for r in results)
    assert all(len(r.url) > 0 for r in results)
