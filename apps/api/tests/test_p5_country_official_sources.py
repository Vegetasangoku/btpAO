"""
Test Suite for Lot P5:
1. Country Official Sources Registry (Table country_official_sources).
2. Regulatory Watch Engine & SHA-256 Integrity Verification.
3. Anti-Fabrication Regulatory Brief per Country.
"""
import asyncio
import uuid
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import text

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.entities import CountryOfficialSource, Tenant, User
from app.services.regulatory_watch_service import regulatory_watch_service

TENANT_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "33333333-3333-3333-3333-333333333333"

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
            db.add(t)
            await db.flush()

            u = User(id=uuid.UUID(USER_ID), tenant_id=uuid.UUID(TENANT_ID), email="u@grandouest.fr", full_name="Directeur Technique", role="admin")
            db.add(u)
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


def test_list_country_official_sources():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        "/api/country-sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0

    # Filter France
    res_fr = client.get(
        "/api/country-sources?country_code=FR",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_fr.status_code == 200
    data_fr = res_fr.json()
    assert all(item["country_code"] == "FR" for item in data_fr)


def test_check_official_sources_updates_sha256():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.post(
        "/api/country-sources/check-updates?country_code=SA",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["checked_sources_count"] > 0
    assert all(
        (item["sha256_hash"] is not None and len(item["sha256_hash"]) == 64)
        or item["fetch_error"] is not None
        for item in data["results"]
    )


def test_country_regulatory_brief_anti_fabrication():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        "/api/country-sources/SA/brief",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["country_code"] == "SA"
    assert data["verified_official_sources_count"] > 0
    assert "Strict sourcing enforcement" in data["anti_hallucination_rule"]


def test_country_regulatory_brief_france():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        "/api/country-sources/FR/brief",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["country_code"] == "FR"
    assert "EUR" in data["currency"]
