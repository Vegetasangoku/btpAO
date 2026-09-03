"""
Connecteur SharePoint (Microsoft Graph) -- gestion du connecteur par tenant.
Strictement scopé par tenant_id (SQLAlchemy 2 Async + Postgres RLS), un seul
connecteur par tenant (voir migration 00033_sharepoint_connectors.sql).

La synchronisation réelle (delta-query, téléchargement, OCR/embeddings, quotas) se
fait de façon asynchrone dans app/workers/tasks.py:sharepoint_sync_task, déclenchée
soit manuellement ici (POST /sync), soit automatiquement toutes les 6h (Celery beat,
voir app/core/celery_app.py) -- jamais en synchrone dans une requête HTTP, un site
SharePoint pouvant contenir des centaines de fichiers.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto_vault import encrypt_api_key, mask_api_key
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import SharePointConnection, SharePointSyncItem
from app.services import sharepoint_service as sp
from app.services.billing_service import billing_service

router = APIRouter(prefix="/sharepoint", tags=["SharePoint Connector"])


class SharePointConnectRequest(BaseModel):
    ms_tenant_id: str = Field(..., description="Azure AD tenant ID du client (Microsoft 365).")
    client_id: str = Field(..., description="Application (client) ID de l'App Registration Azure AD.")
    client_secret: str = Field(..., description="Client secret de l'App Registration (chiffré au repos).")
    site_url: str = Field(..., description="URL du site SharePoint, ex: https://contoso.sharepoint.com/sites/AppelsOffres")
    selected_folder_path: str = Field("/", description="Dossier racine à synchroniser dans le Drive du site.")
    allowed_extensions: List[str] = Field(default_factory=lambda: ["pdf", "docx", "xlsx"])
    max_file_size_bytes: int = Field(52428800, description="Taille max par fichier (50 Mo par défaut).")


class SharePointStatusOut(BaseModel):
    connected: bool
    status: str
    site_url: Optional[str] = None
    client_id_masked: Optional[str] = None
    selected_folder_path: Optional[str] = None
    allowed_extensions: List[str] = []
    last_synced_at: Optional[datetime] = None
    last_error: Optional[str] = None
    files_indexed_this_month: int = 0
    files_quota_this_month: Optional[int] = None


@router.post("/connect", response_model=SharePointStatusOut, status_code=status.HTTP_201_CREATED)
async def connect_sharepoint(
    payload: SharePointConnectRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre (ou remplace) le connecteur SharePoint de ce tenant. Vérifie
    immédiatement les identifiants (authentification + résolution du site) avant de
    les stocker, pour ne jamais garder une configuration silencieusement cassée.
    """
    t_uuid = uuid.UUID(current_user.tenant_id)

    try:
        token = sp.get_access_token(payload.ms_tenant_id, payload.client_id, payload.client_secret)
        drive_id = sp.resolve_drive_id(token, payload.site_url)
    except sp.SharePointGraphError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connexion SharePoint impossible avec ces identifiants : {e}",
        )

    existing_res = await db.execute(select(SharePointConnection).where(SharePointConnection.tenant_id == t_uuid))
    existing = existing_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    encrypted_secret = encrypt_api_key(payload.client_secret)

    if existing:
        existing.ms_tenant_id = payload.ms_tenant_id
        existing.client_id = payload.client_id
        existing.client_secret_encrypted = encrypted_secret
        existing.site_url = payload.site_url
        existing.drive_id = drive_id
        existing.selected_folder_path = payload.selected_folder_path
        existing.allowed_extensions = payload.allowed_extensions
        existing.max_file_size_bytes = payload.max_file_size_bytes
        existing.status = "connected"
        existing.last_error = None
        existing.delta_link = None  # nouvelle config => on repart d'un premier sync complet
        existing.updated_at = now
        conn = existing
    else:
        conn = SharePointConnection(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            ms_tenant_id=payload.ms_tenant_id,
            client_id=payload.client_id,
            client_secret_encrypted=encrypted_secret,
            site_url=payload.site_url,
            drive_id=drive_id,
            selected_folder_path=payload.selected_folder_path,
            allowed_extensions=payload.allowed_extensions,
            max_file_size_bytes=payload.max_file_size_bytes,
            status="connected",
            created_at=now,
            updated_at=now,
        )
        db.add(conn)

    await db.flush()

    from app.workers.tasks import sharepoint_sync_task
    sharepoint_sync_task.delay(tenant_id=current_user.tenant_id)

    return await _build_status_response(conn, t_uuid, db)


@router.get("/status", response_model=SharePointStatusOut)
async def get_sharepoint_status(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    t_uuid = uuid.UUID(current_user.tenant_id)
    res = await db.execute(select(SharePointConnection).where(SharePointConnection.tenant_id == t_uuid))
    conn = res.scalar_one_or_none()
    if not conn:
        return SharePointStatusOut(connected=False, status="disconnected")
    return await _build_status_response(conn, t_uuid, db)


@router.post("/sync", response_model=SharePointStatusOut)
async def trigger_sharepoint_sync(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Déclenche un cycle de synchronisation delta immédiat (asynchrone, Celery) --
    ne retélécharge que les fichiers nouveaux/modifiés depuis le dernier cycle."""
    t_uuid = uuid.UUID(current_user.tenant_id)
    res = await db.execute(select(SharePointConnection).where(SharePointConnection.tenant_id == t_uuid))
    conn = res.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun connecteur SharePoint configuré pour ce tenant.")

    from app.workers.tasks import sharepoint_sync_task
    sharepoint_sync_task.delay(tenant_id=current_user.tenant_id)

    return await _build_status_response(conn, t_uuid, db)


@router.delete("/disconnect")
async def disconnect_sharepoint(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Désactive le connecteur (les fichiers déjà indexés restent dans la base de
    connaissances -- seule la synchronisation automatique s'arrête)."""
    t_uuid = uuid.UUID(current_user.tenant_id)
    res = await db.execute(select(SharePointConnection).where(SharePointConnection.tenant_id == t_uuid))
    conn = res.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun connecteur SharePoint configuré pour ce tenant.")

    conn.status = "disconnected"
    conn.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {"success": True, "message": "Connecteur SharePoint désactivé. Les documents déjà indexés restent disponibles."}


async def _build_status_response(conn: SharePointConnection, t_uuid: uuid.UUID, db: AsyncSession) -> SharePointStatusOut:
    usage = await billing_service.get_or_create_usage(t_uuid, db)
    quota = await billing_service._effective_int_limit(
        t_uuid, db, "custom_sharepoint_files_month", "included_sharepoint_files_month"
    )
    return SharePointStatusOut(
        connected=conn.status == "connected",
        status=conn.status,
        site_url=conn.site_url,
        client_id_masked=mask_api_key(conn.client_id),
        selected_folder_path=conn.selected_folder_path,
        allowed_extensions=list(conn.allowed_extensions or []),
        last_synced_at=conn.last_synced_at,
        last_error=conn.last_error,
        files_indexed_this_month=usage.sharepoint_files_indexed,
        files_quota_this_month=quota,
    )
