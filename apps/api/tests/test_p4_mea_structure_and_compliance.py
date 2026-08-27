"""
Test Suite for Lot P4:
1. CSI MasterFormat Technical Structure (Divisions 01 to 48).
2. Bill of Quantities (BoQ) POMI / CESMM4 Standardization.
3. Contractor Prequalification Dossier (PQD) Export.
4. Regional Building Codes & Statutory Compliance Validation (SBC, QCS, DBC, OIA).
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
from app.models.entities import Tenant, User

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

            t = Tenant(id=uuid.UUID(TENANT_ID), name="Al-Bawani Construction Ltd", slug="al-bawani", siret="1010887410", country_code="SA")
            db.add(t)
            await db.flush()

            u = User(id=uuid.UUID(USER_ID), tenant_id=uuid.UUID(TENANT_ID), email="eng@albawani.sa", full_name="Project Director", role="admin")
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


def test_csi_masterformat_endpoint():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        "/api/mea-structure/csi-masterformat",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_divisions"] >= 20
    assert any(d["division_code"] == "03" and "Concrete" in d["title"] for d in data["divisions"])
    assert any(d["division_code"] == "26" and "Electrical" in d["title"] for d in data["divisions"])


def test_boq_template_endpoint_pomi_and_cesmm4():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    # POMI in SAR
    res_pomi = client.get(
        "/api/mea-structure/boq-template?method=POMI&currency=SAR",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_pomi.status_code == 200
    data_pomi = res_pomi.json()
    assert data_pomi["measurement_standard"] == "POMI"
    assert data_pomi["currency"] == "SAR"
    assert len(data_pomi["boq_sections"]) == 4

    # CESMM4 in AED
    res_cesmm = client.get(
        "/api/mea-structure/boq-template?method=CESMM4&currency=AED",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_cesmm.status_code == 200
    data_cesmm = res_cesmm.json()
    assert data_cesmm["measurement_standard"] == "CESMM4"
    assert data_cesmm["currency"] == "AED"


def test_pqd_dossier_export_docx():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    res = client.get(
        "/api/mea-structure/pqd-dossier?country_code=SA",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert len(res.content) > 2000
    assert "Contractor_PQD_Prequalification_SA.docx" in res.headers.get("content-disposition", "")


def test_compliance_validation_saudi_sbc():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    # 1. Sans assets validés : seul le SIRET passe, les 3 autres sont non_vérifiés (anti-fabrication)
    payload_without_assets = {
        "country_code": "SA",
        "contractor_data": {
            "name": "Al-Bawani LLC",
            "siret": "1010887410",
        },
    }
    res = client.post(
        "/api/mea-structure/validate-compliance",
        json=payload_without_assets,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("partial", "non_vérifié")
    assert "Saudi Building Code (SBC)" in data["primary_code"]
    assert len(data["code_components"]) >= 6
    assert data["compliance_checks"][0]["passed"] is True  # CR / SIRET passed
    assert data["compliance_checks"][1]["passed"] is False # Qualification non vérifiée
    assert data["compliance_checks"][2]["passed"] is False # Assurance non vérifiée
    assert data["compliance_checks"][3]["passed"] is False # PoA non vérifié

    # 2. Avec assets validés complets : tous les checks passent
    payload_with_assets = {
        "country_code": "SA",
        "contractor_data": {
            "name": "Al-Bawani LLC",
            "siret": "1010887410",
            "_company_assets": [
                {"category": "qualification", "title": "SBC Certified Contractor"},
                {"category": "insurance", "title": "CAR & Third Party Liability Policy"},
                {"category": "legal", "title": "Najiz Electronic PoA"},
            ],
        },
    }
    res_full = client.post(
        "/api/mea-structure/validate-compliance",
        json=payload_with_assets,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_full.status_code == 200
    data_full = res_full.json()
    assert data_full["status"] == "compliant"
    assert all(c["passed"] for c in data_full["compliance_checks"])


def test_compliance_validation_qatar_qcs():
    client = TestClient(app)
    token = create_token(USER_ID, TENANT_ID)

    payload = {
        "country_code": "QA",
        "contractor_data": {
            "name": "Qatar Construction Partners",
            "siret": "CR-998811",
            "_company_assets": [
                {"category": "qualification", "title": "Ashghal Prequalification Grade A"},
                {"category": "insurance", "title": "Tawteen ICV Certificate & Insurance"},
                {"category": "legal", "title": "MoJ Authenticated Power of Attorney"},
            ],
        },
    }
    res = client.post(
        "/api/mea-structure/validate-compliance",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "compliant"
    assert "Qatar Construction Specifications (QCS 2018)" in data["primary_code"]
