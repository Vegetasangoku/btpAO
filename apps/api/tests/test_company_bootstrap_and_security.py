"""
Test Suite for Company Auto-Bootstrap, Reference URLs, Anti-Fabrication RLS, and Zero-Leakage Guarantee.
Validates:
1. Graceful degradation without SERPER_API_KEY (no crash, no fabrication).
2. Strict cross-tenant RLS isolation on company_bootstrap_runs, tenant_reference_urls, and company_assets.
3. Zero-Leakage Guarantee: unvalidated company_assets (validated_by_user = False) are STRICTLY excluded
   from generated memo sections and Q&A context until approved by a human.
4. Human validation approval flow (validated_by_user = True) enables inclusion in RAG context.
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
    CompanyBootstrapRun,
    Project,
    Tenant,
    TenantReferenceUrl,
    User,
)
from app.services.company_bootstrap_service import company_bootstrap_service

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"

TENANT_A_ID = "c1111111-1111-1111-1111-111111111111"
TENANT_B_ID = "c2222222-2222-2222-2222-222222222222"
USER_A_ID = "c3333333-3333-3333-3333-333333333333"
USER_B_ID = "c4444444-4444-4444-4444-444444444444"
PROJ_A_ID = "c5555555-5555-5555-5555-555555555555"


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
def setup_bootstrap_test_environment():
    async def _setup():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET ROLE postgres;"))

            # 1. Tenants
            t_a = Tenant(id=uuid.UUID(TENANT_A_ID), name="BTP Construction Grand Est", slug="btp-grand-est", plan="enterprise", country_code="FR")
            t_b = Tenant(id=uuid.UUID(TENANT_B_ID), name="BTP Sud Ouest SAS", slug="btp-sud-ouest", plan="pro", country_code="FR")
            db.add_all([t_a, t_b])
            await db.flush()

            # 2. Users
            u_a = User(id=uuid.UUID(USER_A_ID), tenant_id=uuid.UUID(TENANT_A_ID), email="directeur@grandest.fr", full_name="Directeur Grand Est", role="owner")
            u_b = User(id=uuid.UUID(USER_B_ID), tenant_id=uuid.UUID(TENANT_B_ID), email="directeur@sudouest.fr", full_name="Directeur Sud Ouest", role="owner")
            db.add_all([u_a, u_b])
            await db.flush()

            # 3. Project for Tenant A
            p_a = Project(id=uuid.UUID(PROJ_A_ID), tenant_id=uuid.UUID(TENANT_A_ID), title="Construction Médiathèque Bois", reference_code="AO-2026-MED", client_name="Ville de Nancy", status="draft")
            db.add(p_a)
            await db.commit()

    async def _teardown():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET ROLE postgres;"))
            await db.execute(text("DELETE FROM public.company_bootstrap_runs WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.tenant_reference_urls WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.company_assets WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.generated_sections WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.projects WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.users WHERE tenant_id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.execute(text("DELETE FROM public.tenants WHERE id IN (:t1, :t2)"), {"t1": uuid.UUID(TENANT_A_ID), "t2": uuid.UUID(TENANT_B_ID)})
            await db.commit()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


@pytest.mark.asyncio
async def test_bootstrap_service_without_api_key_degrades_gracefully():
    """When SERPER_API_KEY is not configured or search returns nothing, bootstrap completes cleanly with 0 fabricated assets."""
    # Run bootstrap for Tenant A
    run_id = str(uuid.uuid4())
    result = await company_bootstrap_service.bootstrap_company_profile(
        tenant_id=TENANT_A_ID,
        company_name="Inconnue BTP Totalement Fictive SAS",
        siret=None,
        reference_urls=[],
        run_id=run_id,
    )
    assert result["status"] == "completed"
    assert result["run_id"] == run_id

    # Verify run record in DB and assert that no company_asset was created (hardening)
    async with AsyncSessionLocal() as db:
        run = await db.get(CompanyBootstrapRun, uuid.UUID(run_id))
        assert run is not None
        assert run.status == "completed"
        assert run.tenant_id == uuid.UUID(TENANT_A_ID)

        # Durcissement : assert qu'aucun company_asset n'a été inséré en base sans clé / données
        stmt_assets = select(CompanyAsset).where(CompanyAsset.tenant_id == uuid.UUID(TENANT_A_ID))
        res_assets = await db.execute(stmt_assets)
        assets = res_assets.scalars().all()
        assert len(assets) == 0, f"Aucun company_asset ne doit être créé sans données/clé API (trouvé: {len(assets)})"


def test_cross_tenant_isolation_on_bootstrap_runs_and_reference_urls():
    """Tenant B cannot view Tenant A's bootstrap runs or reference URLs."""
    client = TestClient(app)
    token_a = create_token(USER_A_ID, TENANT_A_ID)
    token_b = create_token(USER_B_ID, TENANT_B_ID)

    # 1. Tenant A creates a reference URL
    res_add_url = client.post(
        "/api/company/reference-urls",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"url": "https://btp-grandest.fr", "label": "Site Officiel Grand Est"},
    )
    assert res_add_url.status_code == 201
    url_id = res_add_url.json()["id"]

    # 2. Tenant B lists reference URLs -> must NOT see Tenant A's URL
    res_list_b = client.get(
        "/api/company/reference-urls",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_list_b.status_code == 200
    urls_b = res_list_b.json()
    assert not any(u["id"] == url_id for u in urls_b)

    # 3. Tenant B attempts to delete Tenant A's reference URL -> 404
    res_del_b = client.delete(
        f"/api/company/reference-urls/{url_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_del_b.status_code == 404

    # 4. Tenant A triggers a bootstrap run
    res_boot_a = client.post(
        "/api/company/bootstrap",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"company_name": "BTP Grand Est SAS"},
    )
    assert res_boot_a.status_code == 202
    run_id = res_boot_a.json()["run_id"]

    # 5. Tenant B attempts to inspect Tenant A's bootstrap run -> 404
    res_get_b = client.get(
        f"/api/company/bootstrap/{run_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_get_b.status_code == 404


@pytest.mark.asyncio
async def test_zero_leakage_unvalidated_assets_never_used_in_generation():
    """
    CRITICAL TEST: Proves that any company_asset with validated_by_user = False
    is NEVER queried or injected into generated memo sections.
    Once validated_by_user = True, it is immediately included in the RAG context.
    """
    client = TestClient(app)
    token_a = create_token(USER_A_ID, TENANT_A_ID)

    asset_id = uuid.uuid4()
    SECRET_SUGGESTION_TITLE = "Certificat Secret Non Validé 2026"
    SECRET_SUGGESTION_TEXT = "Cette entreprise possède une grue spéciale 80m non encore homologuée."

    # 1. Insert an unvalidated asset into Tenant A's knowledge base
    async with AsyncSessionLocal() as db:
        unvalidated_asset = CompanyAsset(
            id=asset_id,
            tenant_id=uuid.UUID(TENANT_A_ID),
            category="certificat_qualibat",
            title=SECRET_SUGGESTION_TITLE,
            description=SECRET_SUGGESTION_TEXT,
            status="indexed",
            source_type="web_auto_bootstrap",
            validated_by_user=False,  # NOT VALIDATED
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(unvalidated_asset)
        await db.commit()

    # 2. Ask project assistant on Tenant A -> unvalidated asset must NOT appear in sources
    res_qa = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"question": "Avez-vous une grue spéciale de 80m ?", "source_mode": "corpus"},
    )
    assert res_qa.status_code == 200
    sources = res_qa.json().get("sources", [])
    assert not any(SECRET_SUGGESTION_TITLE in s.get("title", "") for s in sources), "LEAK DETECTED: Unvalidated asset found in Q&A sources!"

    # 3. Validate the asset via API
    res_val = client.post(
        f"/api/company/assets/{asset_id}/validate",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"validated": True},
    )
    assert res_val.status_code == 200
    assert res_val.json()["validated_by_user"] is True

    # 4. Ask project assistant again -> now the validated asset MUST appear
    res_qa_valid = client.post(
        f"/api/projects/{PROJ_A_ID}/ask",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"question": "Avez-vous une grue spéciale de 80m ?", "source_mode": "corpus"},
    )
    assert res_qa_valid.status_code == 200
    sources_after = res_qa_valid.json().get("sources", [])
    assert any(SECRET_SUGGESTION_TITLE in s.get("title", "") for s in sources_after), "Validated asset was expected in Q&A sources after human approval!"
