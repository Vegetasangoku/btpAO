"""
Test Suite for Lot P3:
1. MEA Regional Tender Dossiers (Saudi Arabia, Qatar, UAE, Lebanon).
2. Bilingual English / Arabic Generation with OpenXML RTL Directives.
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
from app.models.entities import Project, Tenant, User

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

            t = Tenant(id=uuid.UUID(TENANT_ID), name="Al-Bawani Construction Ltd", slug="al-bawani", siret="1010887410", country_code="SA")
            db.add(t)
            await db.flush()

            u = User(id=uuid.UUID(USER_ID), tenant_id=uuid.UUID(TENANT_ID), email="eng@albawani.sa", full_name="Project Director", role="admin")
            p = Project(id=uuid.UUID(PROJECT_ID), tenant_id=uuid.UUID(TENANT_ID), title="Riyadh Metro Extension Line 7", reference_code="RCRC-2026-METRO", client_name="Royal Commission for Riyadh City")
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


def test_saudi_tender_export_en_and_ar_rtl():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    # English version
    res_en = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=SA&language=en",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_en.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res_en.headers["content-type"]
    assert len(res_en.content) > 2000
    assert "Saudi_GTPL_FormOfTender" in res_en.headers.get("content-disposition", "")

    # Arabic RTL version
    res_ar = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=SA&language=ar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ar.status_code == 200
    assert len(res_ar.content) > 2000


def test_qatar_tender_export_en_and_ar_rtl():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    # English version
    res_en = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=QA&language=en",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_en.status_code == 200
    assert len(res_en.content) > 2000
    assert "Qatar_Ashghal_FormOfTender" in res_en.headers.get("content-disposition", "")

    # Arabic RTL version
    res_ar = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=QA&language=ar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ar.status_code == 200
    assert len(res_ar.content) > 2000


def test_uae_tender_export_en_and_ar_rtl():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    # English version
    res_en = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=AE&language=en",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_en.status_code == 200
    assert len(res_en.content) > 2000
    assert "UAE_Federal_FormOfTender" in res_en.headers.get("content-disposition", "")

    # Arabic RTL version
    res_ar = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=AE&language=ar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ar.status_code == 200
    assert len(res_ar.content) > 2000


def test_lebanon_tender_export_fr_and_ar_rtl():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    # French version
    res_fr = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=LB&language=fr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_fr.status_code == 200
    assert len(res_fr.content) > 2000
    assert "Lebanon_PPA_Dossier" in res_fr.headers.get("content-disposition", "")

    # Arabic RTL version
    res_ar = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=LB&language=ar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ar.status_code == 200
    assert len(res_ar.content) > 2000


def test_unsupported_mea_country_rejection():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        f"/api/dossiers/{PROJECT_ID}/mea?country_code=XX",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "non supporté" in res.json()["detail"]
