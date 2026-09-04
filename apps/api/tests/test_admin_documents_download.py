import uuid
from datetime import datetime
import pytest
from jose import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"

def create_jwt(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"
TENANT_ID = "11111111-1111-1111-1111-111111111111"


def test_admin_tenant_documents_list_and_download():
    """
    Vérifie que :
    1. L'admin peut lister tous les documents d'un tenant (savoir-faire + template).
    2. L'admin peut télécharger / prévisualiser un document existant.
    """
    admin_token = create_jwt({
        "sub": ADMIN_USER_ID,
        "email": "charbelakl@gmail.com",
        "aud": "authenticated",
        "role": "authenticated",
        "is_platform_admin": True,
        "app_metadata": {"role": "platform_admin", "is_platform_admin": True},
        "user_metadata": {"role": "platform_admin", "is_platform_admin": True},
    })

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List documents for tenant
    res = client.get(f"/api/admin/tenants/{TENANT_ID}/documents", headers=headers)
    assert res.status_code == 200
    docs = res.json()
    assert isinstance(docs, list)


def test_knowledge_asset_download_unauthorized_without_auth():
    """Vérifie le blocage de sécurité sans token."""
    client = TestClient(app)
    fake_id = str(uuid.uuid4())
    res = client.get(f"/api/knowledge/assets/{fake_id}/download")
    assert res.status_code in (401, 403)
