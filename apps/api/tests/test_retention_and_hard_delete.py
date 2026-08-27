"""
Test suite for Document Retention Policy, Q&A Message Hard-Delete, and RGPD Purge Certificate.
Verifies:
1. Document can be marked as obsolete and is excluded from active search results.
2. Celery retention task purges obsolete documents older than 90 days.
3. Individual Q&A message hard-delete endpoint removes the specific message without trace.
4. Admin Tenant Purge executes full cascading delete and generates formal RGPD certificate.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from jose import jwt
from sqlalchemy import text
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.models.entities import Tenant, Project, CompanyAsset, User, DCEDocument
from app.core.storage import storage_service
from app.core.db import AsyncSessionLocal
from app.workers.tasks import purge_obsolete_knowledge_assets_async

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def make_token(user_id: str, tenant_id: str = None, role: str = "admin", is_admin: bool = False, email: str = "user@test.com") -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {
            "tenant_id": tenant_id,
            "role": "platform_admin" if is_admin else role,
            "is_platform_admin": is_admin,
        },
        "user_metadata": {
            "tenant_id": tenant_id,
            "is_platform_admin": is_admin,
        },
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.mark.asyncio
async def test_document_obsolete_marking_and_exclusion():
    t_uuid = uuid.uuid4()
    u_uuid = uuid.uuid4()
    token = make_token(str(u_uuid), str(t_uuid), "admin")

    asset_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET ROLE postgres;"))
        tenant = Tenant(id=t_uuid, name="Tenant Retention Test", slug=f"retention-{str(t_uuid)[:6]}", plan="pro")
        db.add(tenant)
        await db.flush()
        asset = CompanyAsset(
            id=asset_id,
            tenant_id=t_uuid,
            category="certificat",
            title="Certificat Ancien 2020",
            description="Certificat expiré à archiver",
            status="indexed",
        )
        db.add(asset)
        await db.commit()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Mark as obsolete
    obs_res = client.post(f"/api/knowledge/assets/{asset_id}/obsolete", headers=headers)
    assert obs_res.status_code == 200
    assert obs_res.json()["status"] == "obsolete"

    # 2. Search must exclude obsolete asset
    search_res = client.get("/api/knowledge/search?query=certificat", headers=headers)
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert all(r["id"] != str(asset_id) for r in results)


@pytest.mark.asyncio
async def test_purge_obsolete_celery_task():
    t_uuid = uuid.uuid4()
    asset_id = uuid.uuid4()
    old_date = datetime.now(timezone.utc) - timedelta(days=95)

    # Upload real file to storage
    s3_key = storage_service.upload_file(str(t_uuid), "assets/test_obsolete.pdf", b"test pdf content")

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET ROLE postgres;"))
        tenant = Tenant(id=t_uuid, name="Tenant Purge Test", slug=f"purge-{str(t_uuid)[:6]}", plan="pro")
        db.add(tenant)
        await db.flush()
        asset = CompanyAsset(
            id=asset_id,
            tenant_id=t_uuid,
            category="certificat",
            title="Certificat Tres Ancien",
            description="Certificat vieux de 95 jours",
            s3_url=s3_key,
            status="obsolete",
            obsolete_at=old_date,
        )
        db.add(asset)
        await db.commit()

        # Execute retention purge
        res = await purge_obsolete_knowledge_assets_async(db)
        assert res["purged_count"] >= 1

    # Verify asset is deleted from database
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET ROLE postgres;"))
        from sqlalchemy import select
        chk = await db.execute(select(CompanyAsset).where(CompanyAsset.id == asset_id))
        assert chk.scalar_one_or_none() is None

    # Verify file is deleted from storage
    with pytest.raises(FileNotFoundError):
        storage_service.download_file(str(t_uuid), s3_key)


@pytest.mark.asyncio
async def test_assistant_qa_message_hard_delete():
    t_uuid = uuid.uuid4()
    u_uuid = uuid.uuid4()
    p_uuid = uuid.uuid4()
    token = make_token(str(u_uuid), str(t_uuid), "admin")

    msg_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET ROLE postgres;"))
        tenant = Tenant(id=t_uuid, name="Tenant QA Test", slug=f"qa-{str(t_uuid)[:6]}", plan="pro")
        db.add(tenant)
        await db.flush()
        project = Project(
            id=p_uuid,
            tenant_id=t_uuid,
            title="Projet Test QA",
            reference_code="AO-QA-01",
            client_name="Mairie de Lyon",
            metadata_json={
                "assistant_history": [
                    {"id": msg_id, "question": "Question confidentielle", "answer": "Réponse secrète"}
                ]
            }
        )
        db.add(project)
        await db.commit()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Hard delete individual message
    del_res = client.delete(f"/api/projects/{p_uuid}/assistant/messages/{msg_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted_message_id"] == msg_id

    # Verify message is gone from database
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET ROLE postgres;"))
        from sqlalchemy import select
        res = await db.execute(select(Project).where(Project.id == p_uuid))
        proj = res.scalar_one()
        history = proj.metadata_json.get("assistant_history", [])
        assert all(m["id"] != msg_id for m in history)


@pytest.mark.asyncio
async def test_admin_tenant_purge_generates_rgpd_certificate():
    t_uuid = uuid.uuid4()
    p_uuid = uuid.uuid4()
    admin_uuid = uuid.uuid4()
    admin_token = make_token(str(admin_uuid), None, role="platform_admin", is_admin=True, email="charbelakl@gmail.com")

    # 1. Upload storage files for CompanyAsset and DCEDocument
    asset_file_key = storage_service.upload_file(str(t_uuid), "knowledge/memoire_cert.pdf", b"Memoire technique PDF content")
    dce_file_key = storage_service.upload_file(str(t_uuid), f"dce/{p_uuid}/cctp_lot1.pdf", b"CCTP Lot 1 PDF content")

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET ROLE postgres;"))
        tenant = Tenant(id=t_uuid, name="Entreprise A Supprimer", slug=f"to-delete-{str(t_uuid)[:6]}", plan="pro", siret="12345678901234")
        db.add(tenant)
        await db.flush()
        
        user = User(id=uuid.uuid4(), tenant_id=t_uuid, email="user@entreprise.com", full_name="User Test", role="member")
        db.add(user)

        project = Project(id=p_uuid, tenant_id=t_uuid, title="Projet Test RGPD", reference_code="AO-RGPD-01", client_name="Client Test")
        db.add(project)
        await db.flush()

        asset = CompanyAsset(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            category="certificat",
            title="Certificat Qualibat",
            s3_url=asset_file_key,
            status="indexed",
        )
        db.add(asset)

        dce_doc = DCEDocument(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            project_id=p_uuid,
            filename="cctp_lot1.pdf",
            s3_key=dce_file_key,
        )
        db.add(dce_doc)
        await db.commit()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {admin_token}"}

    del_res = client.delete(f"/api/admin/tenants/{t_uuid}", headers=headers)
    assert del_res.status_code == 200
    body = del_res.json()
    assert body["success"] is True
    assert "certificate" in body
    cert = body["certificate"]
    assert cert["tenant_id"] == str(t_uuid)
    assert cert["tenant_name"] == "Entreprise A Supprimer"
    assert "Article 17" in cert["regulation"]
    assert "certificat" in cert["legal_notice"].lower() or "atteste" in cert["legal_notice"].lower()
    
    # Assert real storage files deletion count
    deleted_elements = cert["deleted_elements"]
    assert deleted_elements["s3_files_deleted_count"] == 2
    assert "2/2 fichiers purgés (100%)" in deleted_elements["s3_storage_objects"]

    # Verify files no longer exist in storage
    with pytest.raises(FileNotFoundError):
        storage_service.download_file(str(t_uuid), asset_file_key)

    with pytest.raises(FileNotFoundError):
        storage_service.download_file(str(t_uuid), dce_file_key)

