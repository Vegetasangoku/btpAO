"""
Routage des modèles et résolution des paliers.

Trois niveaux de configuration, du plus général au plus spécifique :
  1. palier par défaut de la plateforme (public.platform_settings) ;
  2. palier surchargé pour un client (tenant.branding_config->>'llm_model_tier') ;
  3. modèle imposé pour un client ET une tâche (tenant.branding_config->>'model_routing').

Les modèles et leurs tarifs proviennent de app/services/llm_reference_catalog.py,
relevé sur les pages tarifaires officielles — rien n'est recopié à la main ici.
"""
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import PlatformSettings, Tenant, LlmUsageLog
from app.core.crypto_vault import encrypt_api_key, decrypt_api_key, mask_api_key
from app.services.llm_reference_catalog import (
    PROVIDER_ZONES,
    REFERENCE_AS_OF,
    REFERENCE_BY_ID,
    price_for as reference_price_for,
)


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
    "gemini": "US / Global par défaut sur Google AI Studio — la résidence UE nécessite Vertex AI et une région européenne explicite — source : ai.google.dev",
    "deepseek": "Chine — aucune décision d'adéquation RGPD",
}

# Identifiants de fournisseurs livrés d'origine. L'ordre fixe celui de la console admin.
BUILTIN_PROVIDER_IDS = ["anthropic", "openai", "mistral", "gemini", "deepseek"]

DEFAULT_CUSTOM_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "anthropic",
        "name": "Anthropic Claude — rédaction des mémoires techniques",
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
        "name": "OpenAI — lecture des plans et raisonnement sur la DPGF",
        "litellm_id": "openai/gpt-5.6-terra",
        "api_key": "",
        "api_base": "",
        "zone": "US",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["openai"],
        "enabled": True,
    },
    {
        "id": "mistral",
        "name": "Mistral AI — hébergement européen, marchés publics",
        "litellm_id": "mistral/mistral-large-3-25-12",
        "api_key": "",
        "api_base": "",
        "zone": "UE",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["mistral"],
        "enabled": True,
    },
    {
        "id": "gemini",
        "name": "Google Gemini — palier gratuit pour les essais",
        "litellm_id": "gemini/gemini-3.8-flash",
        "api_key": "",
        "api_base": "",
        "zone": "US",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["gemini"],
        "enabled": True,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek — coût plancher, hors UE",
        "litellm_id": "deepseek/deepseek-v4-flash",
        "api_key": "",
        "api_base": "https://api.deepseek.com/v1",
        "zone": "Chine",
        "is_builtin": True,
        "legal_source": BUILTIN_PROVIDERS_SOURCES["deepseek"],
        "enabled": True,
    },
]


def _tier(tier_id, name, model_id, provider, zone, usage):
    """Construit un palier à partir du socle tarifaire de référence, pour que le prix
    affiché dans l'admin soit toujours celui relevé sur la page officielle du
    fournisseur (llm_reference_catalog) et jamais une valeur recopiée à la main."""
    price = reference_price_for(model_id)
    if price is None:
        pricing_label = "tarif non référencé"
    elif price == (0.0, 0.0):
        pricing_label = "inclus dans le palier gratuit du fournisseur"
    else:
        pricing_label = f"{price[0]:.2f} $ / {price[1]:.2f} $ par million de tokens"
    non_eu = is_zone_non_eu_us(zone)
    return {
        "id": tier_id,
        "name": name,
        "pricing": pricing_label,
        "display_label": f"{name} — {usage} ({pricing_label})",
        "model_string": model_id,
        "provider": provider,
        "zone": zone,
        "is_non_eu": non_eu,
        "warning_message": RGPD_NON_EU_WARNING if non_eu else None,
        "usage_hint": usage,
        "priced_as_of": REFERENCE_AS_OF,
    }


# Paliers proposés dans l'admin. Les quatre identifiants historiques (economique,
# equilibre, avance, maximum) sont conservés pour ne pas invalider les choix déjà
# enregistrés en base ; « gratuit » et « souverain » les complètent.
LLM_MODEL_TIERS: Dict[str, Dict[str, Any]] = {
    "gratuit": _tier(
        "gratuit", "Gratuit — Gemini 3.8 Flash", "gemini/gemini-3.8-flash", "gemini", "US",
        "essais et recette, dans les quotas gratuits de Google AI Studio",
    ),
    "economique": _tier(
        "economique", "Économique — Claude Haiku 4.5", "anthropic/claude-haiku-4-5-20251001", "anthropic", "US",
        "extraction rapide des pièces du DCE",
    ),
    "souverain": _tier(
        "souverain", "Souverain UE — Mistral Large 3", "mistral/mistral-large-3-25-12", "mistral", "UE",
        "marchés publics et données sensibles hébergées dans l'Union européenne",
    ),
    "equilibre": _tier(
        "equilibre", "Équilibré — Claude Sonnet 5", "anthropic/claude-sonnet-5", "anthropic", "US",
        "rédaction du mémoire technique au quotidien",
    ),
    "avance": _tier(
        "avance", "Avancé — Claude Opus 5", "anthropic/claude-opus-5", "anthropic", "US",
        "analyse juridique et pièces de marché complexes",
    ),
    "maximum": _tier(
        "maximum", "Maximum — Claude Fable 5.1", "anthropic/claude-fable-5-1", "anthropic", "US",
        "dossiers à fort enjeu, raisonnement long",
    ),
}


DEFAULT_PLATFORM_TIER = "equilibre"


class ModelRoutingService:
    @staticmethod
    def get_available_tiers() -> Dict[str, Dict[str, Any]]:
        return LLM_MODEL_TIERS

    @staticmethod
    async def get_custom_providers(db: AsyncSession, mask_keys: bool = True) -> List[Dict[str, Any]]:
        """Retrieves configured custom providers with encrypted or masked keys, ensuring all 4 built-in providers always exist."""
        from app.core.config import settings
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        ps_dict = ps.settings if ps and ps.settings else {}
        raw_providers = ps_dict.get("custom_providers") or []
        test_results = ps_dict.get("test_results", {})

        # Built-in defaults map
        builtin_defaults = {p["id"]: dict(p) for p in DEFAULT_CUSTOM_PROVIDERS}

        # Normalize legacy IDs if present
        normalized_map: Dict[str, Dict[str, Any]] = {}
        user_custom_providers: List[Dict[str, Any]] = []

        for p in raw_providers:
            p_copy = dict(p)
            pid = p_copy.get("id") or ""
            if pid in ("anthropic", "anthropic-claude", "anthropic_claude"):
                p_copy["id"] = "anthropic"
                normalized_map["anthropic"] = p_copy
            elif pid in ("openai", "openai-custom", "openai_custom"):
                p_copy["id"] = "openai"
                normalized_map["openai"] = p_copy
            elif pid in ("mistral", "mistral-eu", "mistral_eu"):
                p_copy["id"] = "mistral"
                normalized_map["mistral"] = p_copy
            elif pid in ("gemini", "google", "google-gemini", "google_gemini"):
                p_copy["id"] = "gemini"
                normalized_map["gemini"] = p_copy
            elif pid in ("deepseek", "deepseek-custom", "deepseek_custom"):
                p_copy["id"] = "deepseek"
                normalized_map["deepseek"] = p_copy
            else:
                user_custom_providers.append(p_copy)

        # Merge standard built-ins: anthropic, openai, mistral, deepseek
        final_list: List[Dict[str, Any]] = []
        for b_id in BUILTIN_PROVIDER_IDS:
            if b_id in normalized_map:
                item = normalized_map[b_id]
                # Sync default names and litellm_id if missing or generic
                if not item.get("litellm_id"):
                    item["litellm_id"] = builtin_defaults[b_id]["litellm_id"]
                # Un identifiant enregistré en base peut désigner une génération
                # retirée depuis (« mistral-large-latest », « deepseek-chat »…).
                # Comme la base a priorité sur les valeurs par défaut, l'écran
                # continuait d'afficher — et le routage d'utiliser — un modèle qui
                # n'existe plus chez le fournisseur. On revient au modèle courant
                # dès que l'identifiant stocké est absent du socle de référence.
                elif item["litellm_id"] not in REFERENCE_BY_ID:
                    item["litellm_id"] = builtin_defaults[b_id]["litellm_id"]
                if not item.get("name"):
                    item["name"] = builtin_defaults[b_id]["name"]
                final_list.append(item)
            else:
                item = dict(builtin_defaults[b_id])
                # Check if legacy key is present in settings
                if b_id == "anthropic" and (ps_dict.get("anthropic_api_key") or settings.ANTHROPIC_API_KEY):
                    item["api_key"] = ps_dict.get("anthropic_api_key") or settings.ANTHROPIC_API_KEY
                elif b_id == "openai" and (ps_dict.get("openai_api_key") or settings.OPENAI_API_KEY):
                    item["api_key"] = ps_dict.get("openai_api_key") or settings.OPENAI_API_KEY
                elif b_id == "mistral" and (ps_dict.get("mistral_api_key") or settings.MISTRAL_API_KEY):
                    item["api_key"] = ps_dict.get("mistral_api_key") or settings.MISTRAL_API_KEY
                final_list.append(item)

        # Append custom providers created by user
        final_list.extend(user_custom_providers)

        processed = []
        for p in final_list:
            prov_id = p.get("id") or str(uuid.uuid4())[:8]
            zone = p.get("zone", "US")
            is_non_eu = is_zone_non_eu_us(zone)
            raw_key = p.get("api_key", "")
            t_res = test_results.get(prov_id, {})

            is_builtin = prov_id in BUILTIN_PROVIDERS_SOURCES
            legal_source = BUILTIN_PROVIDERS_SOURCES.get(prov_id) or "Zone déclarée par l'administrateur (non vérifiée techniquement)"
            if is_builtin:
                zone = PROVIDER_ZONES.get(prov_id, zone)
                is_non_eu = is_zone_non_eu_us(zone)

            processed.append({
                "id": prov_id,
                "name": p.get("name") or (builtin_defaults.get(prov_id, {}).get("name") or "Fournisseur"),
                "litellm_id": p.get("litellm_id") or (builtin_defaults.get(prov_id, {}).get("litellm_id") or ""),
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
                "monthly_budget_usd": p.get("monthly_budget_usd"),
            })

        return processed



    @staticmethod
    async def get_platform_default_tier(db: AsyncSession) -> str:
        """Retrieves the global default model tier or model string from platform_settings."""
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        if ps and ps.settings:
            tier = ps.settings.get("default_llm_tier")
            if tier and str(tier).strip():
                return str(tier).strip()
        return DEFAULT_PLATFORM_TIER

    @staticmethod
    async def get_platform_default_fallback_tier(db: AsyncSession) -> Optional[str]:
        """
        Palier de repli configure explicitement au niveau plateforme (reglage admin
        'default_fallback_tier', distinct du palier principal 'default_llm_tier').
        Renvoie None si l'admin n'a rien choisi -- dans ce cas get_fallback_candidate()
        garde son comportement historique (premier fournisseur actif dote d'une cle
        reelle, dans l'ordre des fournisseurs) plutot que d'echouer.
        """
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        if ps and ps.settings:
            tier = ps.settings.get("default_fallback_tier")
            if tier and str(tier).strip():
                return str(tier).strip()
        return None

    @staticmethod
    async def get_effective_tiers(db: AsyncSession) -> Dict[str, Dict[str, Any]]:
        """
        Renvoie les 4 tiers avec, pour chacun, le model_string réellement actif :
        celui surchargé par un admin via model_tier_overrides (platform_settings, même
        table que les clés/fournisseurs) si présent, sinon la valeur par défaut codée
        dans LLM_MODEL_TIERS. Objectif (29/08, en réponse à la proposition de "registre
        LLM dynamique") : permettre de repointer un tier vers un nouveau modèle
        (renommage/dépréciation chez le fournisseur) sans déploiement de code, sans pour
        autant construire toute l'infrastructure de synchronisation nocturne proposée --
        jugée disproportionnée tant que le catalogue réel ne compte que 4 tiers.
        Ne lève jamais d'exception : en cas de souci, renvoie les tiers par défaut inchangés.
        """
        effective = {tid: dict(tinfo) for tid, tinfo in LLM_MODEL_TIERS.items()}
        try:
            stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
            res = await db.execute(stmt)
            ps = res.scalar_one_or_none()
            overrides = (ps.settings.get("model_tier_overrides") if ps and ps.settings else None) or {}
            for tier_id, model_string in overrides.items():
                if tier_id in effective and model_string and str(model_string).strip():
                    effective[tier_id]["model_string"] = str(model_string).strip()
                    effective[tier_id]["is_overridden"] = True
        except Exception as e:
            print(f"[ModelRoutingService] get_effective_tiers notice: {e} -- repli sur les tiers par défaut.")
        return effective

    @staticmethod
    async def get_fallback_candidate(
        db: AsyncSession,
        exclude_provider: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Repli résilient (29/08, étendu 03/09) : quand l'appel LLM principal échoue (clé
        invalide, modèle indisponible, quota dépassé...), fournit UN fournisseur de
        secours pour un unique essai avant de retomber sur le moteur de gabarits.

        Deux modes, du plus spécifique au plus général :
          1. Repli explicitement configuré par un admin (03/09) : palier de repli du
             tenant (tenant.branding_config["llm_fallback_tier"], sauf "inherit") sinon
             palier de repli par défaut de la plateforme
             (platform_settings["default_fallback_tier"]). Si ce choix explicite pointe
             vers le même fournisseur que celui qui vient d'échouer (exclude_provider),
             ou n'a pas de clé réellement configurée, il est ignoré au profit du mode 2
             plutôt que de renvoyer un repli inutilisable.
          2. Comportement historique (29/08) si rien n'est configuré explicitement, ou
             si le choix explicite est inutilisable : le premier fournisseur activé et
             réellement doté d'une clé, différent du fournisseur en échec, dans l'ordre
             des fournisseurs. Volontairement simple : pas de file d'attente de N
             modèles, pas de scoring de coût.

        Ne lève jamais d'exception (retourne None si rien d'utilisable).
        """
        try:
            stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
            res = await db.execute(stmt)
            ps = res.scalar_one_or_none()
            settings_dict = (ps.settings if ps and ps.settings else {}) or {}
            providers = settings_dict.get("custom_providers") or DEFAULT_CUSTOM_PROVIDERS

            def _usable(prov: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                if not prov.get("enabled", True):
                    return None
                litellm_id = (prov.get("litellm_id") or "").strip()
                prov_id = (prov.get("id") or "").strip()
                if not litellm_id:
                    return None
                if exclude_provider and (exclude_provider in litellm_id or exclude_provider == prov_id or prov_id in exclude_provider):
                    return None
                encrypted_key = prov.get("api_key", "")
                if not encrypted_key:
                    return None
                key = decrypt_api_key(encrypted_key)
                if key and key.strip() and "sk-..." not in key:
                    return {
                        "model_string": litellm_id,
                        "provider": prov_id,
                        "api_key": key,
                        "api_base": prov.get("api_base") or None,
                    }
                return None

            # 1. Repli explicite : tenant d'abord, puis plateforme.
            explicit_tier_id = None
            if tenant_id:
                t_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
                tenant = t_res.scalar_one_or_none()
                tenant_fallback = (tenant.branding_config or {}).get("llm_fallback_tier") if tenant else None
                if tenant_fallback and tenant_fallback != "inherit":
                    explicit_tier_id = tenant_fallback
            if not explicit_tier_id:
                explicit_tier_id = await ModelRoutingService.get_platform_default_fallback_tier(db)

            if explicit_tier_id:
                effective_tiers = await ModelRoutingService.get_effective_tiers(db)
                tier_info = effective_tiers.get(explicit_tier_id)
                if tier_info:
                    target_model = tier_info["model_string"]
                    matched_prov = next(
                        (p for p in providers if (p.get("litellm_id") or "").strip() == target_model),
                        None,
                    )
                    if matched_prov:
                        candidate = _usable(matched_prov)
                        if candidate:
                            return candidate
                    # Palier de repli configuré mais inutilisable maintenant (pas de clé,
                    # ou même fournisseur que l'échec principal) -- on ne bloque pas, on
                    # retombe sur la recherche automatique ci-dessous.

            # 2. Comportement historique : premier fournisseur actif et doté d'une clé.
            for prov in providers:
                candidate = _usable(prov)
                if candidate:
                    return candidate
            return None
        except Exception as e:
            print(f"[ModelRoutingService] get_fallback_candidate notice: {e} -- pas de repli disponible.")
            return None

    @staticmethod
    async def resolve_model_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves the exact LLM model string for a given tenant.

        When `task_type` is passed (one of "extraction_gonogo", "redaction_memoire",
        "analyse_prix" -- the 3 tasks exposed by l'onglet admin "Routage IA par Tâche
        & Client"), a per-tenant per-task override takes priority over the tier
        system. Reads BOTH branding_config["model_routing"] (written by
        POST /admin/model-routing, the routing tab's own save action) AND the older
        branding_config["model_routing_config"] (written by the tenant create/detail
        forms) -- these were two different keys for the same concept, which is why
        the routing tab used to visibly "save" a change that a reload would never
        show back (list_tenants only ever surfaced the second key, and neither key
        was ever consulted here). Both are now read so whichever form an admin used,
        the saved choice is honoured.

        Bug fixed (30/08): this per-task override was previously saved by admin.py
        but never read anywhere -- the routing tab's 3 dropdowns changed a value with
        zero effect on which model actually ran. This is now the one place that reads
        it. Status as of 03/09, all 3 task types have a real LLM call site wired to
        this resolution: `redaction_memoire` (the long-form section generator in
        tasks.py), `extraction_gonogo` (DCE criteria extraction from OCR text --
        criteria_extraction_service.py, invoked from parse_dce_task in tasks.py on
        every document upload, wired 01/09; Go/No-Go's own scoring in
        go_no_go_service.py stays a deterministic rule-based engine with no LLM by
        design -- this task type routes the criteria-extraction step that feeds it,
        not the scoring itself), and `analyse_prix` (pricing risk analysis --
        api/pricing.py's POST /pricing-analysis, wired 02/09).

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
            "is_task_override": bool,
        }
        """
        t_stmt = select(Tenant).where(Tenant.id == tenant_id)
        t_res = await db.execute(t_stmt)
        tenant = t_res.scalar_one_or_none()

        # Case 0: per-tenant, per-task override -- most specific, checked first.
        if task_type and tenant and tenant.branding_config:
            task_routing = (
                tenant.branding_config.get("model_routing")
                or tenant.branding_config.get("model_routing_config")
                or {}
            )
            task_entry = task_routing.get(task_type) or {}
            task_model = str(task_entry.get("model") or "").strip()
            if task_model:
                providers = await ModelRoutingService.get_custom_providers(db)
                matched = next((p for p in providers if p.get("litellm_id") == task_model), None)
                zone = matched.get("zone") if matched else None
                is_non_eu = is_zone_non_eu_us(zone)
                return {
                    "tier_id": f"task_override:{task_type}",
                    "tier_name": f"Substitution par tâche ({task_type})",
                    "display_label": task_model,
                    "pricing": None,
                    "model_string": task_model,
                    "provider": task_entry.get("provider") or (matched.get("id") if matched else None),
                    "zone": zone or "non-verifie",
                    "is_non_eu": is_non_eu,
                    "warning_message": RGPD_NON_EU_WARNING if is_non_eu else None,
                    "is_override": True,
                    "is_task_override": True,
                }

        tenant_tier = None
        if tenant and tenant.branding_config:
            tenant_tier = tenant.branding_config.get("llm_model_tier")

        # 29/08 : model_string peut désormais être surchargé par admin (model_tier_overrides)
        # sans déploiement de code -- voir get_effective_tiers().
        effective_tiers = await ModelRoutingService.get_effective_tiers(db)

        # Case 1: Tenant has an explicit tier override
        if tenant_tier and tenant_tier != "inherit" and tenant_tier in effective_tiers:
            tier_info = effective_tiers[tenant_tier]
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
                "is_task_override": False,
            }

        # Case 2: Tenant inherits from platform default (tier or direct model)
        platform_tier = await ModelRoutingService.get_platform_default_tier(db)
        if platform_tier in effective_tiers:
            tier_info = effective_tiers[platform_tier]
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
                "is_task_override": False,
            }

        # Check if platform_tier is a direct model string from any configured provider
        providers = await ModelRoutingService.get_custom_providers(db)
        matched = next((p for p in providers if p.get("litellm_id") == platform_tier or p.get("id") == platform_tier), None)
        if matched:
            zone = matched.get("zone", "US")
            is_non_eu = is_zone_non_eu_us(zone)
            return {
                "tier_id": matched.get("id", "custom"),
                "tier_name": matched.get("name", "Modèle Master"),
                "display_label": f"{matched.get('name')} ({matched.get('litellm_id') or platform_tier})",
                "pricing": None,
                "model_string": matched.get("litellm_id") or platform_tier,
                "provider": matched.get("id"),
                "zone": zone,
                "is_non_eu": is_non_eu,
                "warning_message": RGPD_NON_EU_WARNING if is_non_eu else None,
                "is_override": False,
                "is_task_override": False,
            }

        tier_info = effective_tiers.get(DEFAULT_PLATFORM_TIER, list(effective_tiers.values())[0])
        return {
            "tier_id": DEFAULT_PLATFORM_TIER,
            "tier_name": tier_info["name"],
            "display_label": tier_info["display_label"],
            "pricing": tier_info["pricing"],
            "model_string": tier_info["model_string"],
            "provider": tier_info["provider"],
            "zone": tier_info.get("zone", "US"),
            "is_non_eu": tier_info.get("is_non_eu", False),
            "warning_message": tier_info.get("warning_message"),
            "is_override": False,
            "is_task_override": False,
        }

    @staticmethod
    async def get_current_month_spend_usd(db: AsyncSession, provider_id: str) -> float:
        """Somme des couts estimes (llm_usage_logs.estimated_cost_usd) pour ce fournisseur
        depuis le 1er du mois en cours (UTC). Ne leve jamais d'exception -- un plafond de
        budget ne doit jamais, lui-meme, faire echouer une generation (30/08)."""
        if not provider_id:
            return 0.0
        try:
            month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            stmt = select(func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0)).where(
                LlmUsageLog.provider_id == provider_id,
                LlmUsageLog.created_at >= month_start,
            )
            res = await db.execute(stmt)
            return float(res.scalar() or 0.0)
        except Exception as e:
            print(f"[ModelRoutingService] get_current_month_spend_usd notice: {e} -- 0.0 par defaut.")
            return 0.0

    @staticmethod
    async def get_credentials_for_model(
        db: AsyncSession,
        model_string: str,
    ) -> Dict[str, Any]:
        """
        Retrieves decrypted API key and optional api_base endpoint for a given model string.
        (30/08) Retourne aussi provider_id (pour le journal de consommation llm_usage_logs)
        et applique un plafond de budget mensuel optionnel par fournisseur
        (custom_providers[].monthly_budget_usd) : si la depense du mois en cours atteint ou
        depasse ce plafond, la cle n'est PAS retournee (comme si aucune cle n'etait
        configuree) -- declenche naturellement le repli resilient existant
        (get_fallback_candidate) plutot que de bloquer durement l'appelant.
        """
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()
        if not ps or not ps.settings:
            return {"api_key": None, "api_base": None, "provider_id": None}

        settings_dict = ps.settings
        custom_providers = settings_dict.get("custom_providers", [])

        # Match custom provider by litellm_id or id
        for prov in custom_providers:
            if prov.get("litellm_id") == model_string or prov.get("id") == model_string:
                prov_id = prov.get("id") or ""
                budget = prov.get("monthly_budget_usd")
                if budget is not None:
                    try:
                        budget_f = float(budget)
                    except (TypeError, ValueError):
                        budget_f = None
                    if budget_f is not None and budget_f > 0:
                        spend = await ModelRoutingService.get_current_month_spend_usd(db, prov_id)
                        if spend >= budget_f:
                            print(f"[ModelRoutingService] Plafond mensuel atteint pour '{prov_id}' ({spend:.2f}$/{budget_f:.2f}$) -- cle non fournie, repli attendu.")
                            return {"api_key": None, "api_base": None, "provider_id": prov_id, "budget_exceeded": True}
                encrypted_key = prov.get("api_key", "")
                return {
                    "api_key": decrypt_api_key(encrypted_key) if encrypted_key else None,
                    "api_base": prov.get("api_base") or None,
                    "provider_id": prov_id,
                }

        # Fallback to standard provider keys (champs legacy .env -- portee volontairement
        # limitee, pas de plafond de budget ici : voir la liste extensible custom_providers
        # ci-dessus pour un plafond parametrable).
        if "anthropic" in model_string or "claude" in model_string:
            key = settings_dict.get("anthropic_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None, "provider_id": "anthropic"}
        elif "openai" in model_string or "gpt" in model_string:
            key = settings_dict.get("openai_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None, "provider_id": "openai"}
        elif "mistral" in model_string or "ministral" in model_string:
            key = settings_dict.get("mistral_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None, "provider_id": "mistral"}
        elif "gemini" in model_string:
            key = settings_dict.get("gemini_api_key")
            return {"api_key": decrypt_api_key(key) if key else None, "api_base": None, "provider_id": "gemini"}
        elif "deepseek" in model_string:
            key = settings_dict.get("deepseek_api_key")
            return {
                "api_key": decrypt_api_key(key) if key else None,
                "api_base": "https://api.deepseek.com/v1",
                "provider_id": "deepseek",
            }

        return {"api_key": None, "api_base": None, "provider_id": None}


model_routing_service = ModelRoutingService()
