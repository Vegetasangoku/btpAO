"""
Tests for Extensible Custom LLM Providers, Application-Level AES-256-GCM Encryption, RGPD Hosting Zone Warnings,
and Real Connection Testing with Concrete Failure Proof.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from app.core.config import settings
from app.core.crypto_vault import encrypt_api_key, decrypt_api_key, mask_api_key
from app.services.model_routing_service import is_zone_non_eu_us, RGPD_NON_EU_WARNING, LLM_MODEL_TIERS


def make_admin_token() -> str:
    return jwt.encode(
        {
            "sub": "99999999-9999-9999-9999-999999999999",
            "email": "charbelakl@gmail.com",
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"role": "super_admin", "is_platform_admin": True},
            "user_metadata": {"role": "super_admin", "is_platform_admin": True},
        },
        settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY,
        algorithm="HS256",
    )


def test_crypto_vault_aes_gcm_encryption_and_masking():
    plain_key = "sk-deepseek-live-secret-key-123456789"
    encrypted = encrypt_api_key(plain_key)
    
    assert encrypted.startswith("enc:v1:")
    assert encrypted != plain_key
    
    # Decrypt back to original
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == plain_key

    # Masking
    masked = mask_api_key(encrypted)
    assert "••••" in masked
    assert "sk-d" in masked
    assert "6789" in masked


def test_zone_classification_fail_closed():
    # Fail-closed: missing, empty, or whitespace zone MUST be treated as non-verified (True)
    assert is_zone_non_eu_us(None) is True
    assert is_zone_non_eu_us("") is True
    assert is_zone_non_eu_us("   ") is True
    assert is_zone_non_eu_us("inconnu") is True
    assert is_zone_non_eu_us("Chine") is True
    assert is_zone_non_eu_us("autre") is True
    assert is_zone_non_eu_us("non-verifie") is True
    assert is_zone_non_eu_us("Russie") is True

    # Only explicitly verified EU/US zones return False
    assert is_zone_non_eu_us("UE") is False
    assert is_zone_non_eu_us("eu") is False
    assert is_zone_non_eu_us("FR") is False
    assert is_zone_non_eu_us("france") is False
    assert is_zone_non_eu_us("US") is False
    assert is_zone_non_eu_us("usa") is False


def test_current_claude_model_identifiers():
    # Verify no legacy claude-3 models exist in LLM_MODEL_TIERS
    for tier_id, tier in LLM_MODEL_TIERS.items():
        assert "claude-3-5-sonnet" not in tier["model_string"]
        assert "claude-3-opus" not in tier["model_string"]
        assert "claude-3-7-sonnet" not in tier["model_string"]

    # Verify exact current model IDs
    assert LLM_MODEL_TIERS["economique"]["model_string"] == "anthropic/claude-haiku-4-5-20251001"
    assert LLM_MODEL_TIERS["equilibre"]["model_string"] == "anthropic/claude-sonnet-5"
    assert LLM_MODEL_TIERS["avance"]["model_string"] == "anthropic/claude-opus-5"
    assert LLM_MODEL_TIERS["maximum"]["model_string"] == "anthropic/claude-fable-5"


@pytest.mark.asyncio
async def test_admin_custom_providers_lifecycle_and_encryption():
    admin_token = make_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    custom_providers_payload = [
        {
            "id": "anthropic-claude",
            "name": "Anthropic Claude",
            "litellm_id": "anthropic/claude-sonnet-5",
            "api_key": "sk-ant-test-secret-vault-key-xyz123",
            "api_base": "",
            "zone": "US",
            "enabled": True,
        },
        {
            "id": "deepseek-custom",
            "name": "DeepSeek V3 API",
            "litellm_id": "deepseek/deepseek-chat",
            "api_key": "sk-deepseek-custom-api-key-987654",
            "api_base": "https://api.deepseek.com/v1",
            "zone": "Chine",
            "enabled": False,
        },
        {
            "id": "mistral-eu",
            "name": "Mistral Large 2",
            "litellm_id": "mistral/mistral-large-latest",
            "api_key": "mis-secret-eu-key-456789",
            "api_base": "",
            "zone": "UE",
            "enabled": True,
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Update custom providers
        update_resp = await ac.post(
            "/api/admin/llm-keys",
            headers=headers,
            json={
                "default_llm_tier": "equilibre",
                "custom_providers": custom_providers_payload,
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["success"] is True

        # 2. Read back masked providers and verify zone warnings
        get_resp = await ac.get("/api/admin/llm-keys", headers=headers)
        assert get_resp.status_code == 200
        data = get_resp.json()

        assert data["encryption_status"] == "AES-256-GCM Chiffré au repos"
        assert data["default_llm_tier"] == "equilibre"

        providers = data["custom_providers"]
        assert len(providers) >= 3

        deepseek_prov = next((p for p in providers if p["id"] == "deepseek-custom"), None)
        assert deepseek_prov is not None
        assert deepseek_prov["zone"] == "Chine"
        assert deepseek_prov["is_non_eu"] is True
        assert deepseek_prov["warning_message"] == RGPD_NON_EU_WARNING
        # Verify key is masked in GET response (not exposed in plain text)
        assert "••••" in deepseek_prov["api_key"]
        assert "sk-deepseek-custom-api-key" not in deepseek_prov["api_key"]


@pytest.mark.asyncio
async def test_live_connection_test_endpoint_failure_and_success_proof():
    """
    Demonstrates real live connection testing:
    1. A fake/invalid key MUST produce an explicit failure status and error details.
    2. A missing key MUST produce an error status.
    3. A successful ping call returns success with latency measurement.
    """
    admin_token = make_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. PROOF OF CONCRETE FAILURE: Fake API Key
        fake_test_resp = await ac.post(
            "/api/admin/llm-keys/test-provider",
            headers=headers,
            json={
                "provider_id": "test-fake-provider",
                "name": "Fake Anthropic",
                "litellm_id": "anthropic/claude-sonnet-5",
                "api_key": "sk-ant-fake-invalid-key-99999999",
            },
        )
        assert fake_test_resp.status_code == 200
        fake_data = fake_test_resp.json()
        assert fake_data["success"] is False
        assert fake_data["status"] == "error"
        assert "Échec de connexion" in fake_data["error_message"] or "401" in fake_data["error_message"] or "AuthenticationError" in fake_data["error_message"]
        assert "tested_at" in fake_data

        # 2. Failure when no key is supplied or found
        no_key_resp = await ac.post(
            "/api/admin/llm-keys/test-provider",
            headers=headers,
            json={
                "provider_id": "non-existent-provider-id",
                "litellm_id": "custom-unknown-provider/model",
                "api_key": "",
            },
        )
        assert no_key_resp.status_code == 200
        no_key_data = no_key_resp.json()
        assert no_key_data["success"] is False
        assert no_key_data["status"] == "error"
        assert "Aucune clé" in no_key_data["error_message"]


        # 3. Successful ping (Mocked completion response)
        with patch("litellm.completion") as mock_comp:
            mock_comp.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="pong"))])
            
            success_resp = await ac.post(
                "/api/admin/llm-keys/test-provider",
                headers=headers,
                json={
                    "provider_id": "anthropic-claude",
                    "name": "Anthropic Claude",
                    "litellm_id": "anthropic/claude-sonnet-5",
                    "api_key": "sk-ant-valid-live-key",
                },
            )
            assert success_resp.status_code == 200
            success_data = success_resp.json()
            assert success_data["success"] is True
            assert success_data["status"] == "success"
            assert success_data["latency_ms"] >= 1
            assert "Connexion réussie" in success_data["message"]
            assert "tested_at" in success_data
