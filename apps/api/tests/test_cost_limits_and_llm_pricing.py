"""
Plafonds de dépense IA et exactitude tarifaire.

Ces tests ne touchent ni la base ni le réseau : ils portent sur les règles pures
(conversion de devise, plafond conseillé, état d'une ligne, tarification d'un appel).
Le but est qu'une erreur de marge — la seule qui coûte de l'argent en silence — soit
détectée à chaque exécution de la suite, sans dépendre d'un environnement.
"""
import pytest

from app.services import cost_limits_service as cls
from app.services.billing_service import BillingService, _FALLBACK_MODEL_PRICING_USD_PER_MILLION
from app.services.llm_reference_catalog import (
    REFERENCE_AS_OF,
    REFERENCE_MODELS,
    free_tier_models,
    price_for,
)


# ── Socle tarifaire ───────────────────────────────────────────────────────────

def test_reference_catalog_is_complete_and_coherent():
    assert REFERENCE_MODELS, "socle tarifaire vide"
    seen = set()
    for entry in REFERENCE_MODELS:
        ext = entry["external_id"]
        assert ext not in seen, f"identifiant en double : {ext}"
        seen.add(ext)
        assert "/" in ext, f"identifiant sans préfixe fournisseur : {ext}"
        assert entry["display_name"], f"{ext} sans libellé"
        assert entry["pricing_prompt_per_million"] >= 0
        assert entry["pricing_completion_per_million"] >= 0
        # Un modèle payant coûte toujours plus cher en sortie qu'en entrée : l'inverse
        # signale presque toujours une inversion de colonnes au moment du relevé.
        if entry["pricing_prompt_per_million"] > 0:
            assert entry["pricing_completion_per_million"] >= entry["pricing_prompt_per_million"], ext


def test_reference_catalog_is_dated():
    assert len(REFERENCE_AS_OF) == 10 and REFERENCE_AS_OF.count("-") == 2


def test_free_tier_offers_at_least_one_option():
    free = free_tier_models()
    assert free, "aucun modèle gratuit référencé pour la recette"
    for entry in free:
        assert entry["provider_slug"] in {"gemini", "mistral"}


def test_price_lookup_tolerates_missing_provider_prefix():
    assert price_for("anthropic/claude-sonnet-5") == price_for("claude-sonnet-5")
    assert price_for("modele-qui-nexiste-pas") is None
    assert price_for(None) is None


# ── Estimation du coût d'un appel ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cost_estimation_falls_back_to_reference_catalog():
    """Sans catalogue en base, l'estimation doit quand même aboutir grâce au socle."""

    class _NoCatalogDb:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("base indisponible")

    cost = await BillingService.estimate_llm_cost_usd(
        _NoCatalogDb(), "anthropic/claude-sonnet-5", prompt_tokens=1_000_000, completion_tokens=100_000
    )
    # Sonnet 5 : 2 $ l'entrée, 10 $ la sortie, par million de tokens.
    assert cost == pytest.approx(2.0 + 1.0)


@pytest.mark.asyncio
async def test_cost_estimation_returns_none_for_unknown_model():
    class _NoCatalogDb:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("base indisponible")

    assert await BillingService.estimate_llm_cost_usd(_NoCatalogDb(), "inconnu/modele-x", 1000, 1000) is None


def test_fallback_pricing_table_is_ordered_from_specific_to_generic():
    """« gpt-5.6-luna » doit être trouvé avant « gpt-5.6-sol » ne puisse capter un préfixe
    plus court, sinon un modèle bon marché serait facturé au prix du haut de gamme."""
    needles = [n for n, _, _ in _FALLBACK_MODEL_PRICING_USD_PER_MILLION]
    for i, earlier in enumerate(needles):
        for later in needles[i + 1:]:
            # Un motif générique placé avant un motif plus précis capterait ce dernier :
            # « deepseek-v4 » avant « deepseek-v4-pro » facturerait le Pro au prix du Flash.
            assert not later.startswith(earlier), (
                f"'{earlier}' capterait '{later}' : le motif le plus précis doit venir en premier"
            )


# ── Conversion de devise ──────────────────────────────────────────────────────

def test_currency_conversion_round_trip():
    rate = 1.08
    assert cls.eur_to_usd(100.0, rate) == pytest.approx(108.0)
    assert cls.usd_to_eur(108.0, rate) == pytest.approx(100.0)
    assert cls.usd_to_eur(None, rate) is None
    assert cls.eur_to_usd(None, rate) is None


def test_conversion_refuses_an_impossible_rate():
    assert cls.usd_to_eur(100.0, 0) is None
    assert cls.eur_to_usd(100.0, -1) is None


def test_amount_is_normalised_to_dollars_whatever_the_input_currency():
    assert cls.to_usd(50.0, "USD", 1.08) == pytest.approx(50.0)
    assert cls.to_usd(50.0, "EUR", 1.08) == pytest.approx(54.0)
    assert cls.to_usd(None, "EUR", 1.08) is None


# ── Plafond conseillé ─────────────────────────────────────────────────────────

def test_recommended_cap_is_a_share_of_the_selling_price():
    # Forfait à 499 € HT, part cible 15 % → 499 × 1.08 × 0.15 ≈ 80.84 $
    cap = cls.recommended_cap_usd(49900, rate=1.08, target_share=0.15)
    assert cap == pytest.approx(80.84, abs=0.05)


def test_recommended_cap_never_falls_below_the_floor():
    # Un forfait gratuit ou sur devis ne doit pas produire un plafond de 0 $, qui
    # bloquerait toute génération dès le premier appel.
    assert cls.recommended_cap_usd(0, rate=1.08, target_share=0.15) == cls.MIN_RECOMMENDED_CAP_USD


def test_recommended_cap_grows_with_the_plan_price():
    small = cls.recommended_cap_usd(19900, 1.08, 0.15)
    big = cls.recommended_cap_usd(49900, 1.08, 0.15)
    assert big > small


# ── État d'une ligne ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "spend, cap, expected",
    [
        (0.0, None, "sans_plafond"),
        (0.0, 0.0, "sans_plafond"),
        (10.0, 100.0, "ok"),
        (79.0, 100.0, "ok"),
        (80.0, 100.0, "alerte"),
        (99.9, 100.0, "alerte"),
        (100.0, 100.0, "bloque"),
        (250.0, 100.0, "bloque"),
    ],
)
def test_usage_state_thresholds(spend, cap, expected):
    assert cls._usage_state(spend, cap, alert_pct=80) == expected


# ── Réglages ──────────────────────────────────────────────────────────────────

def test_settings_defaults_are_applied_when_nothing_is_stored():
    cfg = cls.get_settings(None)
    assert cfg["display_currency"] in ("EUR", "USD")
    assert cfg["eur_usd_rate"] > 0
    assert 0 < cfg["target_llm_share"] < 1
    assert 1 <= cfg["alert_threshold_pct"] <= 100


def test_stored_settings_override_defaults():
    cfg = cls.get_settings({"cost_limits": {"display_currency": "USD", "alert_threshold_pct": 90}})
    assert cfg["display_currency"] == "USD"
    assert cfg["alert_threshold_pct"] == 90
    # Les clés absentes retombent sur les valeurs par défaut plutôt que de disparaître.
    assert cfg["eur_usd_rate"] > 0
