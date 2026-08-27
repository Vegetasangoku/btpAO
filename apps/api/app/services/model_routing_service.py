"""
Model Routing & Tier Resolution Service.
Manages the 4 BTP AI model performance & pricing tiers:
1. Economique (Claude Haiku 4.5)
2. Equilibre (Claude Sonnet 5)
3. Avance (Claude Opus 5)
4. Maximum (Claude Fable 5)

Two-level configuration hierarchy:
- Level 1: Platform-wide default model tier (stored in public.platform_settings)
- Level 2: Per-tenant override (stored in tenant.branding_config->>'llm_model_tier')
"""
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import PlatformSettings, Tenant
from app.core.crypto_vault import encrypt_api_key, decrypt_api_key, mask_api_key


NON_EU_US_ZONES = {"chine", "autre", "non-verifie", "autre-non verifie", "autre-non vérifié", "russie", "asia"}
RGPD_NON_EU_WARNING = "Hébergement hors UE — conformité RGPD non confirmée, voir avec un juriste avant usage sur des données clients réelles"


def is_zone_non_eu_us(zone: Optional[str]) -> bool:
    """
    Returns True if the hosting zone is outside EU and US, or if the zone is missing/unspecified.
    Fail-closed: absence of zone data is strictly treated as non-verified (is_non_eu = True).
    """
    if not zone or not str(zone).strip():
        return True  # Fail-closed: missing zone = unverified / non-EU/US

    normalized = str(zone).strip().lower().replace(" ", "-").replace("_", "-")
    # Only explicitly verified EU/US zones are exempt from warning
    if normalized in {"ue", "eu", "fr", "france", "de", "germany", "allemagne", "it", "italie", "es", "espagne", "nl", "pays-bas", "be", "belgique", "us", "usa", "united-states", "etats-unis"}:
        return False
    return True


BUILTIN_PROVIDERS_SOURCES = {
    "anthropic": "US (stockage par défaut aux États-Unis même si le trafic peut transiter par l'UE) — source : privacy.claude.com, art. 7996890",
    "openai": "US / Global par défaut — résidence UE possible mais non activée ici (nécessite eu.api.openai.com + accord commercial OpenAI) — source : platform.openai.com/docs/guides/your-data",
    "mistral": "UE — société et infrastructure françaises (Suède/France) — source : documentation Mistral AI",
    "deepseek": "Chine — aucune décision d'adéquation RGPD",
}

DEFAULT_CUSTOM_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "anthropic",
        "name": "Anthropic (Claude Sonnet 5)",
        "litellm_id": "anthropic/claude-sonnet-5",
        "api_key": "",
        "api_base": "",
        "zone": "US",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["anthropic"],
        "enabled": True,
    },
    {
        "id": "openai",
        "name": "OpenAI (GPT-4o & Embeddings)",
        "litellm_id": "openai/gpt-4o",
        "api_key": "",
        "api_base": "",
        "zone": "US",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["openai"],
        "enabled": True,
    },
    {
        "id": "mistral",
        "name": "Mistral AI (Souveraineté Européenne)",
        "litellm_id": "mistral/mistral-large-latest",
        "api_key": "",
        "api_base": "",
        "zone": "UE",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["mistral"],
        "enabled": True,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek (DeepSeek V3 / R1)",
        "litellm_id": "deepseek/deepseek-chat",
        "api_key": "",
        "api_base": "https://api.deepseek.com/v1",
        "zone": "Chine",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["deepseek"],
        "enabled": False,  # Disabled by default
    },
]



LLM_MODEL_TIERS: Dict[str, Dict[str, Any]] = {
    "economique": {
        "id": "economique",
        "name": "Économique — Claude Haiku 4.5",
        "pricing": "≈ 1 $ / 5 $ par million de tokens",
        "display_label": "Économique — Claude Haiku 4.5 (≈ 1 $ / 5 $ par million de tokens)",
        "model_string": "anthropic/claude-haiku-4-5-20251001",
        "provider": "anthropic",
        "zone": "US",
        "is_non_eu": False,
        "warning_message": None,
    },
    "equilibre": {
        "id": "equilibre",
        "name": "Équilibré — Claude Sonnet 5",
        "pricing": "≈ 2 $ / 10 $ par million de tokens",
        "display_label": "Équilibré — Claude Sonnet 5 (≈ 2 $ / 10 $ par million de tokens)",
        "model_string": "anthropic/claude-sonnet-5",
        "provider": "anthropic",
        "zone": "US",
        "is_non_eu": False,
        "warning_message": None,
    },
    "avance": {
        "id": "avance",
        "name": "Avancé — Claude Opus 5",
        "pricing": "≈ 5 $ / 25 $ par million de tokens",
        "display_label": "Avancé — Claude Opus 5 (≈ 5 $ / 25 $ par million de tokens)",
        "model_string": "anthropic/claude-opus-5",
        "provider": "anthropic",
        "zone": "US",
        "is_non_eu": False,
        "warning_message": None,
    },
    "maximum": {
        "id": "maximum",
        "name": "Maximum — Claude Fable 5",
        "pricing": "≈ 10 $ / 50 $ par million de tokens",
        "display_label": "Maximum — Claude Fable 5 (≈ 10 $ / 50 $ par million de tokens)",
        "model_string": "anthropic/claude-fable-5",
        "provider": "anthropic",
        "zone": "US",
        "is_non_eu": False,
        "warning_message": None,
    },
}


DEFAULT_PLATFORM_TIER = "equilibre"


class ModelRoutingService:
    @staticmethod
    def get_available_tiers() -> Dict[str, Dict[str, Any]]:
        return LLM_MODEL_TIERS

    @staticmethod
    async def get_custom_providers(db: AsyncSession, mask_keys: bool = True) -> List[Dict[str, Any]]:
        """Retrieves configured custom providers with encrypted or masked keys."""
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        raw_providers = (ps.settings.get("custom_providers") if ps and ps.settings else None) or DEFAULT_CUSTOM_PROVIDERS
        test_results = ps.settings.get("test_results", {}) if ps and ps.settings else {}

        processed = []
        for p in raw_providers:
            prov_id = p.get("id") or str(uuid.uuid4())[:8]
            zone = p.get("zone", "US")
            is_non_eu = is_zone_non_eu_us(zone)
            raw_key = p.get("api_key", "")
            t_res = test_results.get(prov_id, {})

            is_builtin = prov_id in BUILTIN_PROVIDERS_SOURCES
            legal_source = BUILTIN_PROVIDERS_SOURCES.get(prov_id) or "Zone déclarée par l'administrateur (non vérifiée techniquement)"
            if is_builtin:
                # Enforce immutable zone for built-ins
                if prov_id == "anthropic": zone = "US"
                elif prov_id == "openai": zone = "US"
                elif prov_id == "mistral": zone = "UE"
                elif prov_id == "deepseek": zone = "Chine"
                is_non_eu = is_zone_non_eu_us(zone)

            processed.append({
                "id": prov_id,
                "name": p.get("name", "Fournisseur"),
                "litellm_id": p.get("litellm_id", ""),
                "api_key": mask_api_key(raw_key) if mask_keys else raw_key,
                "api_base": p.get("api_base", ""),
                "zone": zone,
                "is_builtin": is_builtin,
                "legal_source": legal_source,
                "is_non_eu": is_non_eu,
                "warning_message": RGPD_NON_EU_WARNING if is_non_eu else None,
                "enabled": p.get("enabled", True),
                "test_status": t_res.get("status", "untested"),
                "last_tested_at": t_res.get("last_tested_at"),
                "last_latency_ms": t_res.get("latency_ms"),
                "last_error_message": t_res.get("error"),
            })

        return processed



    @staticmethod
    async def get_platform_default_tier(db: AsyncSession) -> str:
        """Retrieves the global default model tier from platform_settings."""
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        if ps and ps.settings:
            tier = ps.settings.get("default_llm_tier")
            if tier in LLM_MODEL_TIERS:
                return tier
        return DEFAULT_PLATFORM_TIER

    @staticmethod
    async def resolve_model_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Resolves the exact LLM model string for a given tenant:
        Returns: {
            "tier_id": str,
            "tier_name": str,
            "display_label": str,
            "pricing": str,
            "model_string": str,
            "provider": str,
            "zone": str,
            "is_non_eu": bool,
            "warning_message": Optional[str],
            "is_override": bool,
        }
        """
        t_stmt = select(Tenant).where(Tenant.id == tenant_id)
        t_res = await db.execute(t_stmt)
        tenant = t_res.scalar_one_or_none()

        tenant_tier = None
        if tenant and tenant.branding_config:
            tenant_tier = tenant.branding_config.get("llm_model_tier")

        # Case 1: Tenant has an explicit override
        if tenant_tier and tenant_tier != "inherit" and tenant_tier in LLM_MODEL_TIERS:
            tier_info = LLM_MODEL_TIERS[tenant_tier]
            return {
                "tier_id": tenant_tier,
                "tier_name": tier_info["name"],
                "display_label": tier_info["display_label"],
                "pricing": tier_info["pricing"],
                "model_string": tier_info["model_string"],
                "provider": tier_info["provider"],
                "zone": tier_info.get("zone", "US"),
                "is_non_eu": tier_info.get("is_non_eu", False),
                "warning_message": tier_info.get("warning_message"),
                "is_override": True,
            }

        # Case 2: Tenant inherits from platform default
        platform_tier = await ModelRoutingService.get_platform_default_tier(db)
        tier_info = LLM_MODEL_TIERS.get(platform_tier, LLM_MODEL_TIERS[DEFAULT_PLATFORM_TIER])

        return {
            "tier_id": platform_tier,
            "tier_name": tier_info["name"],
            "display_label": tier_info["display_label"],
            "pricing": tier_info["pricing"],
            "model_string": tier_info["model_string"],
            "provider": tier_info["provider"],
            "zone": tier_info.get("zone", "US"),
            "is_non_eu": tier_info.get("is_non_eu", False),
            "warning_message": tier_info.get("warning_message"),
            "is_override": False,
        }

    @staticmethod
    async def get_credentials_for_model(
        db: AsyncSession,
        model_string: str,
    ) -> Dict[str, Any]:
        """
        Retrieves decrypted API key and optional api_base endpoint for a given model string.
        """
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        if not ps or not ps.settings:
            return {"api_key": None, "api_base": None}

        settings_dict = ps.settings
        custom_providers = settings_dict.get("custom_providers", [])
        
        # Match custom provider by litellm_id or id
        for prov in custom_providers:
            if prov.get("litellm_id") == model_string or prov.get("id") == model_string:
                encrypted_key = prov.get("api_key", "")
                return {
                    "api_key": decrypt_api_key(encrypted_key) if encrypted_key else None,
                    "api_base": prov.get("api_base") or None,
                }

        # Fallback to standard provider keys
        if "anthropic" in model_string or "claude" in model_string:
            key = settings_dict.get("anthropic_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None}
        elif "openai" in model_string or "gpt" in model_string:
            key = settings_dict.get("openai_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None}
        elif "mistral" in model_string:
            key = settings_dict.get("mistral_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None}

        return {"api_key": None, "api_base": None}


model_routing_service = ModelRoutingService()
