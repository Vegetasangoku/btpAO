"""
Socle tarifaire de référence — modèles LLM réellement commercialisés.

Pourquoi ce fichier existe
--------------------------
Le catalogue dynamique (`llm_catalog_service.sync_catalog`) lit la base embarquée de
LiteLLM puis, si le réseau le permet, l'API publique OpenRouter. Ces deux sources
retardent toujours un peu sur les annonces des fournisseurs, et la base LiteLLM est
figée à la version du paquet installé : sans socle, une installation dont les
dépendances datent affiche des modèles retirés depuis des mois et des tarifs faux.

Ce module est donc la source de vérité de dernier recours : une table relevée à la
main sur les pages tarifaires officielles, datée et sourcée. Elle sert à trois
endroits :
  1. amorcer / corriger `llm_catalog_models` à chaque synchronisation (priorité la
     plus haute : ce qui est ici écrase ce que dit LiteLLM pour le même identifiant) ;
  2. définir les paliers de qualité exposés dans l'admin (`LLM_MODEL_TIERS`) ;
  3. estimer le coût d'un appel quand le modèle n'est pas encore en base
     (`billing_service.estimate_llm_cost_usd`).

Mise à jour : relever les pages ci-dessous, corriger les lignes, incrémenter
`REFERENCE_AS_OF`. La synchronisation nocturne (4h00, Europe/Paris) réapplique
automatiquement ce socle en base — aucun déploiement n'est nécessaire pour un simple
changement de prix côté fournisseur tant que le modèle est déjà listé ici.

Sources relevées le 2026-09-02 :
  - Anthropic : https://platform.claude.com/docs/en/models/overview
  - OpenAI    : https://developers.openai.com/api/docs/pricing
  - Mistral   : https://docs.mistral.ai/inference/pricing
  - Google    : https://ai.google.dev/gemini-api/docs/pricing
  - DeepSeek  : https://api-docs.deepseek.com/quick_start/pricing
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

REFERENCE_AS_OF = "2026-09-02"

# Zones d'hébergement déclarées par les fournisseurs (voir model_routing_service pour
# l'avertissement RGPD attaché aux zones hors UE/US).
PROVIDER_ZONES: Dict[str, str] = {
    "anthropic": "US",
    "openai": "US",
    "mistral": "UE",
    "gemini": "US",
    "deepseek": "Chine",
}

PROVIDER_LABELS: Dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "mistral": "Mistral AI",
    "gemini": "Google Gemini",
    "deepseek": "DeepSeek",
}


def _m(
    external_id: str,
    display_name: str,
    provider: str,
    prompt: float,
    completion: float,
    context: Optional[int] = None,
    free_tier: bool = False,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "external_id": external_id,
        "display_name": display_name,
        "provider_slug": provider,
        "pricing_prompt_per_million": prompt,
        "pricing_completion_per_million": completion,
        "context_length": context,
        "free_tier": free_tier,
        "note": note,
    }


# Prix en dollars US par million de tokens, tarif standard (hors mise en cache, hors lot).
REFERENCE_MODELS: List[Dict[str, Any]] = [
    # ── Anthropic ────────────────────────────────────────────────────────────
    _m("anthropic/claude-fable-5-1", "Claude Fable 5.1", "anthropic", 10.0, 50.0, 1_000_000,
       note="Raisonnement long et travail agentique de bout en bout."),
    _m("anthropic/claude-opus-5", "Claude Opus 5", "anthropic", 5.0, 25.0, 1_000_000,
       note="Analyse juridique et pièces de marché complexes."),
    _m("anthropic/claude-sonnet-5", "Claude Sonnet 5", "anthropic", 2.0, 10.0, 1_000_000,
       note="Meilleur rapport vitesse / qualité rédactionnelle."),
    _m("anthropic/claude-haiku-4-5-20251001", "Claude Haiku 4.5", "anthropic", 1.0, 5.0, 200_000,
       note="Extraction rapide des pièces du DCE."),

    # ── OpenAI ───────────────────────────────────────────────────────────────
    _m("openai/gpt-5.6-sol", "GPT-5.6 Sol", "openai", 2.0, 10.0),
    _m("openai/gpt-5.6-terra", "GPT-5.6 Terra", "openai", 1.0, 6.0),
    _m("openai/gpt-5.6-luna", "GPT-5.6 Luna", "openai", 0.10, 0.60,
       note="Tarif plancher, adapté aux traitements de masse."),
    _m("openai/gpt-5.3-codex", "GPT-5.3 Codex", "openai", 1.75, 14.0),

    # ── Mistral AI (hébergement UE) ──────────────────────────────────────────
    _m("mistral/mistral-large-3-25-12", "Mistral Large 3", "mistral", 0.50, 1.50,
       note="Modèle haut de gamme européen, poids ouverts (Apache 2.0)."),
    _m("mistral/mistral-medium-3.5-26.04", "Mistral Medium 3.5", "mistral", 1.50, 7.50),
    _m("mistral/mistral-small-4-0-26-03", "Mistral Small 4", "mistral", 0.15, 0.60),
    _m("mistral/ministral-3-14b-25-12", "Ministral 3 14B", "mistral", 0.20, 0.20),
    _m("mistral/ministral-3-8b-25-12", "Ministral 3 8B", "mistral", 0.15, 0.15),
    _m("mistral/ministral-3-3b-25-12", "Ministral 3 3B", "mistral", 0.10, 0.10),
    _m("mistral/leanstral-1.5", "Leanstral 1.5 (Labs)", "mistral", 0.0, 0.0, free_tier=True,
       note="Gratuit sur La Plateforme, périmètre expérimental — hébergement UE."),

    # ── Google Gemini ────────────────────────────────────────────────────────
    _m("gemini/gemini-3.8-flash", "Gemini 3.8 Flash", "gemini", 0.75, 3.75, free_tier=True,
       note="Palier gratuit sur Google AI Studio ; tarif payant applicable au-delà des quotas."),
    _m("gemini/gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", "gemini", 0.30, 2.50, free_tier=True),
    _m("gemini/gemini-2.5-pro", "Gemini 2.5 Pro", "gemini", 1.25, 10.0, free_tier=True),

    # ── DeepSeek (hors UE/US) ────────────────────────────────────────────────
    # Tarif heures pleines retenu volontairement : majore l'estimation plutôt que de
    # la sous-évaluer (les heures creuses sont à 50 %).
    _m("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash", "deepseek", 0.44, 1.32, 1_000_000),
    _m("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro", "deepseek", 1.32, 3.96, 1_000_000),
]

REFERENCE_BY_ID: Dict[str, Dict[str, Any]] = {m["external_id"]: m for m in REFERENCE_MODELS}


def price_for(external_id: Optional[str]) -> Optional[tuple[float, float]]:
    """Tarif (prompt, completion) par million de tokens pour un identifiant exact."""
    if not external_id:
        return None
    entry = REFERENCE_BY_ID.get(external_id)
    if entry is None:
        # Tolère l'absence de préfixe fournisseur ("claude-sonnet-5" == "anthropic/claude-sonnet-5").
        suffix = external_id.split("/")[-1]
        for candidate_id, candidate in REFERENCE_BY_ID.items():
            if candidate_id.split("/")[-1] == suffix:
                entry = candidate
                break
    if entry is None:
        return None
    return float(entry["pricing_prompt_per_million"]), float(entry["pricing_completion_per_million"])


def free_tier_models() -> List[Dict[str, Any]]:
    return [m for m in REFERENCE_MODELS if m["free_tier"]]
