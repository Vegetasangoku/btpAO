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
from typing import Dict, Any, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import PlatformSettings, Tenant


LLM_MODEL_TIERS: Dict[str, Dict[str, Any]] = {
    "economique": {
        "id": "economique",
        "name": "Économique — Claude Haiku 4.5",
        "pricing": "≈ 1 $ / 5 $ par million de tokens",
        "display_label": "Économique — Claude Haiku 4.5 (≈ 1 $ / 5 $ par million de tokens)",
        "model_string": "anthropic/claude-3-5-haiku-20241022",
        "provider": "anthropic",
    },
    "equilibre": {
        "id": "equilibre",
        "name": "Équilibré — Claude Sonnet 5",
        "pricing": "≈ 2 $ / 10 $ par million de tokens",
        "display_label": "Équilibré — Claude Sonnet 5 (≈ 2 $ / 10 $ par million de tokens)",
        "model_string": "anthropic/claude-3-5-sonnet-20241022",
        "provider": "anthropic",
    },
    "avance": {
        "id": "avance",
        "name": "Avancé — Claude Opus 5",
        "pricing": "≈ 5 $ / 25 $ par million de tokens",
        "display_label": "Avancé — Claude Opus 5 (≈ 5 $ / 25 $ par million de tokens)",
        "model_string": "anthropic/claude-3-opus-20240229",
        "provider": "anthropic",
    },
    "maximum": {
        "id": "maximum",
        "name": "Maximum — Claude Fable 5",
        "pricing": "≈ 10 $ / 50 $ par million de tokens",
        "display_label": "Maximum — Claude Fable 5 (≈ 10 $ / 50 $ par million de tokens)",
        "model_string": "anthropic/claude-3-7-sonnet-20250219",
        "provider": "anthropic",
    },
}

DEFAULT_PLATFORM_TIER = "equilibre"


class ModelRoutingService:
    @staticmethod
    def get_available_tiers() -> Dict[str, Dict[str, Any]]:
        return LLM_MODEL_TIERS

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
        1. Checks if tenant has a specific override (llm_model_tier != 'inherit' and != None).
        2. If 'inherit' or unset, falls back to platform default tier.
        Returns: {
            "tier_id": str,
            "tier_name": str,
            "display_label": str,
            "pricing": str,
            "model_string": str,
            "provider": str,
            "is_override": bool,
        }
        """
        t_stmt = select(Tenant).where(Tenant.id == tenant_id)
        t_res = await db.execute(t_stmt)
        tenant = t_res.scalar_one_or_none()

        tenant_tier = None
        if tenant and tenant.branding_config:
            tenant_tier = tenant.branding_config.get("llm_model_tier")
            if not tenant_tier or tenant_tier == "inherit":
                direct_model = tenant.branding_config.get("llm_model") or tenant.llm_model
                for k, v in LLM_MODEL_TIERS.items():
                    if direct_model and (direct_model == v["model_string"] or direct_model == v["id"] or direct_model in v["model_string"]):
                        tenant_tier = k
                        break

        is_override = False
        if tenant_tier and tenant_tier != "inherit" and tenant_tier in LLM_MODEL_TIERS:
            selected_tier = tenant_tier
            is_override = True
        else:
            selected_tier = await ModelRoutingService.get_platform_default_tier(db)

        tier_info = LLM_MODEL_TIERS.get(selected_tier, LLM_MODEL_TIERS[DEFAULT_PLATFORM_TIER])

        return {
            "tier_id": tier_info["id"],
            "tier_name": tier_info["name"],
            "display_label": tier_info["display_label"],
            "pricing": tier_info["pricing"],
            "model_string": tier_info["model_string"],
            "provider": tier_info["provider"],
            "is_override": is_override,
        }


model_routing_service = ModelRoutingService()
