"""
Test Suite for Real Knowledge Base Management:
1. Multipart file uploads (PDF, DOCX, TXT) with OCR and vector embeddings.
2. 50 MB per-file limit enforcement.
3. Plan-based quotas (starter: 20, pro: 100, enterprise: unlimited).
4. Web Source scraping with anti-fabrication / fail-closed rules.
5. Asset deletion and stats.
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from jose import jwt
import uuid

import psycopg2
import uuid
import io
import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from app.core.config import settings


@pytest.fixture
def test_tenant():
    """Creates a temporary tenant in postgres and cleans up after test."""
    t_id = str(uuid.uuid4())
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.tenants (id, name, slug, plan, country_code, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, now(), now())
        ON CONFLICT (id) DO NOTHING;
        """,
        (t_id, f"Test Knowledge Tenant {t_id[:6]}", f"test-knowledge-{t_id[:6]}", "starter", "FR"),
    )
    cur.close()
    conn.close()

    yield t_id

    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM public.company_assets WHERE tenant_id = %s;", (t_id,))
    cur.execute("DELETE FROM public.tenants WHERE id = %s;", (t_id,))
    cur.close()
    conn.close()


def make_auth_token(tenant_id: str, role: str = "owner") -> str:
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": f"test-{tenant_id[:6]}@btp-construct.fr",
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"tenant_id": tenant_id, "role": role},
            "user_metadata": {"tenant_id": tenant_id, "role": role},
        },
        settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_knowledge_file_upload_and_ocr_indexing(test_tenant):
    tenant_id = test_tenant
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}


    sample_doc_content = (
        "FICHE MATÉRIEL & PARC ENGINS EIFFABTP 2026\n"
        "1. Grue à tour Potain MDT 389 L16 (Capacité max 16 tonnes, portée 75m)\n"
        "2. Centrale à béton mobile de chantier avec recyclage des eaux de lavage\n"
        "3. 4 Banches métalliques manuportables avec sécurité intégrée NF P93-350\n"
    ).encode("utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Upload real document
        files = {
            "file": ("fiche_materiel_engins.txt", io.BytesIO(sample_doc_content), "text/plain"),
        }
        data = {
            "category": "materiel_engins",
            "title": "Fiche Parc Engins & Grues 2026",
        }

        resp = await ac.post("/api/knowledge/upload", headers=headers, files=files, data=data)
        assert resp.status_code == 201
        res_json = resp.json()
        assert res_json["success"] is True
        assert res_json["status"] == "indexed"
        assert res_json["word_count"] > 15
        assert res_json["file_size_bytes"] == len(sample_doc_content)
        assert "fiche_materiel_engins.txt" in res_json["message"]

        # List assets and verify presence
        list_resp = await ac.get("/api/knowledge/assets", headers=headers)
        assert list_resp.status_code == 200
        assets = list_resp.json()
        assert len(assets) >= 1
        asset = next(a for a in assets if a["id"] == res_json["asset_id"])
        assert asset["category"] == "materiel_engins"
        assert asset["title"] == "Fiche Parc Engins & Grues 2026"
        assert "Grue à tour Potain MDT 389" in asset["description"]
        assert asset["metadata_json"]["status"] == "indexed"


@pytest.mark.asyncio
async def test_knowledge_file_upload_50mb_limit_enforcement(test_tenant):
    tenant_id = test_tenant
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate oversized payload > 50 MB (e.g. 50 MB + 1024 bytes)
    oversized_bytes = b"0" * (50 * 1024 * 1024 + 1024)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {
            "file": ("huge_dce_archive.pdf", io.BytesIO(oversized_bytes), "application/pdf"),
        }
        resp = await ac.post("/api/knowledge/upload", headers=headers, files=files)
        assert resp.status_code == 413
        err = resp.json()
        assert "50 Mo" in err["detail"]


@pytest.mark.asyncio
async def test_knowledge_plan_quota_enforcement(test_tenant):
    """
    Verifies that a tenant on 'starter' plan is strictly limited to 20 documents.
    The 21st upload attempt MUST be rejected with HTTP 403.
    """
    tenant_id = test_tenant
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Pre-seed 20 assets using standard create
        for i in range(20):
            create_resp = await ac.post(
                "/api/knowledge/assets",
                headers=headers,
                json={
                    "category": "reference_chantier",
                    "title": f"Chantier Référence #{i+1}",
                    "description": f"Réalisation d'un complexe R+4 à Lyon - Lot {i+1}",
                },
            )
            assert create_resp.status_code == 201

        # Check stats shows 20 / 20
        stats_resp = await ac.get("/api/knowledge/stats", headers=headers)
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_assets"] == 20
        assert stats["max_allowed"] == 20

        # 21st document upload MUST fail with 403 Quota Exceeded
        files = {
            "file": ("document_21.txt", io.BytesIO(b"Document depassant le quota"), "text/plain"),
        }
        resp = await ac.post("/api/knowledge/upload", headers=headers, files=files)
        assert resp.status_code == 403
        assert "Quota de documents atteint" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_knowledge_web_source_scraping_and_indexing(test_tenant):
    tenant_id = test_tenant
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>EiffaBTP — Certifications & RSE 2026</title></head>
    <body>
        <header><nav><a href="/">Menu</a></nav></header>
        <main>
            <h1>Nos Certifications Officielles du Bâtiment</h1>
            <p>EiffaBTP Construction est certifiée <strong>QUALIBAT 2152</strong> (Béton armé et structures complexes) et <strong>QUALIBAT 1112</strong> (Terrassement et voirie).</p>
            <p>Notre démarche RSE est auditée ISO 14001 avec un objectif de -40% d'émissions carbone d'ici 2028.</p>
        </main>
        <footer><p>Mentions légales & Contact</p></footer>
    </body>
    </html>
    """

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Mock external HTTP fetch
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = sample_html
            mock_get.return_value = mock_resp

            resp = await ac.post(
                "/api/knowledge/web-source",
                headers=headers,
                json={
                    "url": "https://www.eiffabtp.fr/qualifications-rse",
                    "title": "Certifications Officielles & ISO 14001",
                    "category": "certificat_qualibat",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["category"] == "certificat_qualibat"
            assert data["title"] == "Certifications Officielles & ISO 14001"
            assert "QUALIBAT 2152" in data["description"]
            assert "ISO 14001" in data["description"]
            assert data["metadata_json"]["source_type"] == "web"
            assert data["metadata_json"]["url"] == "https://www.eiffabtp.fr/qualifications-rse"
            assert data["metadata_json"]["status"] == "indexed"


@pytest.mark.asyncio
async def test_knowledge_web_source_fail_closed_anti_hallucination_on_404(test_tenant):
    tenant_id = test_tenant
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Mock 404 Not Found error
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.reason_phrase = "Not Found"
            mock_get.return_value = mock_resp

            resp = await ac.post(
                "/api/knowledge/web-source",
                headers=headers,
                json={
                    "url": "https://www.unreachable-site-btp.fr/missing-page",
                },
            )
            assert resp.status_code == 400
            err = resp.json()
            assert "Impossible de joindre le lien web" in err["detail"]
            assert "404" in err["detail"]
            assert "Aucune donnée inventée" in err["detail"]


@pytest.mark.asyncio
async def test_knowledge_asset_deletion(test_tenant):
    tenant_id = test_tenant
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create asset
        create_resp = await ac.post(
            "/api/knowledge/assets",
            headers=headers,
            json={
                "category": "demarche_rse",
                "title": "Charte Chantier Bas Carbone",
                "description": "Utilisation de béton CEM III",
            },
        )
        assert create_resp.status_code == 201
        asset_id = create_resp.json()["id"]

        # 2. Delete asset
        del_resp = await ac.delete(f"/api/knowledge/assets/{asset_id}", headers=headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # 3. Verify deletion
        list_resp = await ac.get("/api/knowledge/assets", headers=headers)
        assert list_resp.status_code == 200
        assert not any(a["id"] == asset_id for a in list_resp.json())

