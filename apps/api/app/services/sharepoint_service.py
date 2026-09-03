"""
Connecteur Microsoft SharePoint (Microsoft Graph API), synchronisation incrémentale.

Principe de cout (03/09, demande explicite) : ne JAMAIS relister/retelecharger
l'integralite d'un site SharePoint a chaque cycle. Microsoft Graph expose un
mecanisme de delta-query (/drives/{id}/root/delta) concu exactement pour ca : le
premier appel liste tout, et retourne un curseur opaque (@odata.deltaLink). Chaque
appel SUIVANT avec ce curseur ne retourne QUE les fichiers ajoutes/modifies/supprimes
depuis le dernier passage. Ce module ne fait JAMAIS d'appel OCR/embedding lui-meme --
il se contente de resoudre les identifiants Graph, suivre le delta, filtrer par
extension/taille, et telecharger le contenu brut des fichiers a synchroniser. Le
pipeline d'ingestion reel (OCR, chunking, embeddings, quotas) est reutilise tel quel
depuis app/api/knowledge.py (chunk_and_embed_asset_text / extract_text_from_upload)
par app/workers/tasks.py:sharepoint_sync_task -- aucune logique dupliquee.

Authentification : client-credentials flow (l'application s'authentifie elle-meme,
sans utilisateur interactif). Le client_id/client_secret proviennent d'une App
Registration Azure AD CREEE ET CONSENTIE PAR L'IT DU CLIENT (jamais par btpAO), avec
les permissions d'application Sites.Selected ou Sites.Read.All / Files.Read.All,
limitees en lecture seule au site/dossier choisi.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


class SharePointGraphError(RuntimeError):
    """Toute erreur d'appel Microsoft Graph (auth, site introuvable, delta, download) --
    jamais de repli silencieux : l'appelant doit voir l'erreur reelle pour la
    diagnostiquer (identifiants expires, permissions insuffisantes, site renomme...)."""


def get_access_token(ms_tenant_id: str, client_id: str, client_secret: str) -> str:
    url = TOKEN_URL_TEMPLATE.format(tenant_id=ms_tenant_id)
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, data=data)
        if resp.status_code != 200:
            raise SharePointGraphError(
                f"Authentification Microsoft Graph refusée (HTTP {resp.status_code}) : {resp.text[:300]}"
            )
        token = resp.json().get("access_token")
        if not token:
            raise SharePointGraphError("Réponse Microsoft Graph sans access_token.")
        return token


def resolve_drive_id(access_token: str, site_url: str) -> str:
    """Resout le drive_id du Drive documentaire par defaut du site a partir de son URL
    (ex: https://contoso.sharepoint.com/sites/AppelsOffres)."""
    cleaned = site_url.strip().rstrip("/")
    without_scheme = cleaned.split("://", 1)[-1]
    hostname, _, site_path = without_scheme.partition("/")
    site_path = f"/{site_path}" if site_path else ""

    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=30.0) as client:
        site_resp = client.get(f"{GRAPH_BASE_URL}/sites/{hostname}:{site_path}", headers=headers)
        if site_resp.status_code != 200:
            raise SharePointGraphError(
                f"Site SharePoint introuvable pour « {site_url} » (HTTP {site_resp.status_code}) : {site_resp.text[:300]}"
            )
        site_id = site_resp.json().get("id")

        drive_resp = client.get(f"{GRAPH_BASE_URL}/sites/{site_id}/drive", headers=headers)
        if drive_resp.status_code != 200:
            raise SharePointGraphError(
                f"Drive documentaire introuvable pour ce site (HTTP {drive_resp.status_code}) : {drive_resp.text[:300]}"
            )
        drive_id = drive_resp.json().get("id")
        if not drive_id:
            raise SharePointGraphError("Réponse Microsoft Graph sans drive_id.")
        return drive_id


def fetch_delta(access_token: str, drive_id: str, delta_link: Optional[str]) -> Tuple[List[Dict[str, Any]], str]:
    """Suit la pagination @odata.nextLink jusqu'a @odata.deltaLink. Si delta_link est
    fourni (curseur d'un sync precedent), Microsoft Graph ne renvoie QUE les items
    nouveaux/modifies/supprimes depuis ce curseur -- coeur du sync incrémental."""
    headers = {"Authorization": f"Bearer {access_token}"}
    url = delta_link or f"{GRAPH_BASE_URL}/drives/{drive_id}/root/delta"
    items: List[Dict[str, Any]] = []
    new_delta_link = delta_link or ""

    with httpx.Client(timeout=60.0) as client:
        while url:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                raise SharePointGraphError(
                    f"Échec de la synchronisation delta Microsoft Graph (HTTP {resp.status_code}) : {resp.text[:300]}"
                )
            payload = resp.json()
            items.extend(payload.get("value", []))
            url = payload.get("@odata.nextLink")
            if not url and payload.get("@odata.deltaLink"):
                new_delta_link = payload["@odata.deltaLink"]

    return items, new_delta_link


def filter_syncable_items(
    items: List[Dict[str, Any]],
    allowed_extensions: List[str],
    max_file_size_bytes: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Sépare (à synchroniser, ignorés) selon extension/taille. Dossiers ignorés
    silencieusement (ni synchronisés ni comptés comme "ignorés"). Un item supprimé côté
    SharePoint est renvoyé avec le motif 'deleted_upstream' pour que l'appelant marque
    l'entrée sharepoint_sync_items correspondante, sans jamais supprimer le contenu déjà
    indexé côté btpAO (l'historique de connaissance reste disponible même si la source
    a bougé)."""
    syncable: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    allowed = {ext.lower().lstrip(".") for ext in allowed_extensions}

    for item in items:
        if item.get("deleted"):
            skipped.append({**item, "_skip_reason": "deleted_upstream"})
            continue
        if "folder" in item:
            continue
        name = item.get("name", "")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        size = item.get("size", 0) or 0
        if ext not in allowed:
            skipped.append({**item, "_skip_reason": "skipped_type"})
            continue
        if max_file_size_bytes and size > max_file_size_bytes:
            skipped.append({**item, "_skip_reason": "skipped_size"})
            continue
        syncable.append(item)

    return syncable, skipped


def download_file_content(access_token: str, drive_id: str, item_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content"
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            raise SharePointGraphError(
                f"Échec du téléchargement du fichier SharePoint (HTTP {resp.status_code})."
            )
        return resp.content
