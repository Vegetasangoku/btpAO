"""
Test suite pour la logique de tri du connecteur SharePoint (03/09), sans aucun appel
réseau réel (Microsoft Graph nécessite une App Registration Azure AD réelle côté
client, impossible à simuler en CI). Couvre les deux garde-fous de coût :
1. filter_syncable_items : seuls les fichiers de type/taille autorisés sont retenus.
2. fetch_delta : le curseur @odata.deltaLink est bien suivi à travers la pagination
   @odata.nextLink -- c'est ce curseur qui garantit qu'un cycle de sync suivant ne
   retraite QUE les fichiers nouveaux/modifiés (jamais un balayage complet répété).
"""
import httpx
import pytest

from app.services.sharepoint_service import fetch_delta, filter_syncable_items


def test_filter_syncable_items_rejects_wrong_extension():
    items = [
        {"id": "1", "name": "cctp.pdf", "size": 1000},
        {"id": "2", "name": "photo_chantier.jpg", "size": 1000},
    ]
    syncable, skipped = filter_syncable_items(items, ["pdf", "docx"], max_file_size_bytes=10_000_000)
    assert [i["id"] for i in syncable] == ["1"]
    assert skipped[0]["_skip_reason"] == "skipped_type"


def test_filter_syncable_items_rejects_oversized_file():
    items = [{"id": "1", "name": "cctp_scanne.pdf", "size": 200_000_000}]
    syncable, skipped = filter_syncable_items(items, ["pdf"], max_file_size_bytes=52_428_800)
    assert syncable == []
    assert skipped[0]["_skip_reason"] == "skipped_size"


def test_filter_syncable_items_ignores_folders_silently():
    items = [{"id": "1", "name": "Dossier CCTP", "folder": {"childCount": 3}}]
    syncable, skipped = filter_syncable_items(items, ["pdf"], max_file_size_bytes=10_000_000)
    assert syncable == []
    assert skipped == []  # un dossier n'est ni synchronisé ni "ignoré" -- juste transparent


def test_filter_syncable_items_flags_deleted_items():
    items = [{"id": "1", "name": "ancien_cctp.pdf", "deleted": {"state": "deleted"}}]
    syncable, skipped = filter_syncable_items(items, ["pdf"], max_file_size_bytes=10_000_000)
    assert syncable == []
    assert skipped[0]["_skip_reason"] == "deleted_upstream"


def test_fetch_delta_follows_pagination_and_returns_new_cursor():
    """Simule 2 pages Microsoft Graph : la première renvoie @odata.nextLink, la
    seconde renvoie @odata.deltaLink (le nouveau curseur à stocker pour le PROCHAIN
    cycle de sync -- c'est le mécanisme qui rend la synchronisation incrémentale)."""
    page_1_url = "https://graph.microsoft.com/v1.0/drives/D1/root/delta"
    page_2_url = "https://graph.microsoft.com/v1.0/drives/D1/root/delta?page=2"
    final_delta_link = "https://graph.microsoft.com/v1.0/drives/D1/root/delta?token=abc123"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == page_1_url:
            return httpx.Response(200, json={
                "value": [{"id": "1", "name": "a.pdf", "size": 100}],
                "@odata.nextLink": page_2_url,
            })
        elif str(request.url) == page_2_url:
            return httpx.Response(200, json={
                "value": [{"id": "2", "name": "b.pdf", "size": 100}],
                "@odata.deltaLink": final_delta_link,
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def _patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    import app.services.sharepoint_service as sp_module
    original = sp_module.httpx.Client
    sp_module.httpx.Client = _patched_client
    try:
        items, new_delta_link = fetch_delta("fake-token", "D1", delta_link=page_1_url)
    finally:
        sp_module.httpx.Client = original

    assert [i["id"] for i in items] == ["1", "2"]
    assert new_delta_link == final_delta_link
