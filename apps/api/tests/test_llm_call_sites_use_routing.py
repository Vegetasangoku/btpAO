"""
Garde-fou : tout appel à un modèle passe par le routage commun.

Le bug qui a motivé ces tests : l'assistant de projet et le chat sur le dossier
appelaient LiteLLM en lisant directement les variables d'environnement
(ANTHROPIC_API_KEY, OPENAI_API_KEY…) et en forçant un modèle Claude. Le
fournisseur choisi dans l'administration — Gemini, en l'occurrence — n'était donc
jamais utilisé, et l'écran annonçait un « service temporairement indisponible »
alors que le service n'avait simplement jamais été appelé.

Ces tests lisent le code source plutôt que d'exécuter les routes : ils n'ont
besoin ni de base ni de réseau, et ils échouent dès qu'un nouveau point d'appel
recommence à court-circuiter le routage.
"""
import pathlib
import re

import pytest

APP = pathlib.Path(__file__).resolve().parent.parent / "app"

# Modules qui appellent réellement un modèle. config.py importe litellm sans
# jamais l'appeler ; llm_generator reçoit ses identifiants de son appelant.
CALL_SITES = [
    "api/projects.py",
    "api/dce.py",
    "api/pricing.py",
    "api/company_bootstrap.py",
    "services/criteria_extraction_service.py",
]


def _source(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", CALL_SITES)
def test_call_site_resolves_credentials_through_routing(rel):
    src = _source(rel)
    if "litellm.completion" not in src and "acompletion" not in src:
        pytest.skip(f"{rel} n'appelle plus de modèle")
    assert "get_credentials_for_model" in src or "model_routing_service" in src, (
        f"{rel} appelle un modèle sans passer par model_routing_service : "
        "le fournisseur configuré dans l'administration serait ignoré."
    )


@pytest.mark.parametrize("rel", CALL_SITES)
def test_call_site_does_not_read_env_keys_directly(rel):
    """Une clé lue dans l'environnement contourne les clés saisies dans l'admin
    et le plafond de dépense qui les accompagne."""
    src = _source(rel)
    forbidden = re.findall(
        r"api_key\s*=\s*[^\n]*settings\.(?:ANTHROPIC|OPENAI|MISTRAL|GEMINI|DEEPSEEK)_API_KEY", src
    )
    forbidden += re.findall(
        r"api_key_to_use\s*=\s*[^\n]*settings\.(?:ANTHROPIC|OPENAI|MISTRAL|GEMINI|DEEPSEEK)_API_KEY", src
    )
    assert not forbidden, f"{rel} lit une clé d'API dans l'environnement : {forbidden}"


@pytest.mark.parametrize("rel", CALL_SITES)
def test_call_site_does_not_hardcode_a_model(rel):
    """Un identifiant de modèle figé dans un appel réapparaît en production des
    mois après que le fournisseur l'a retiré."""
    src = _source(rel)
    hardcoded = re.findall(r'model\s*=\s*"(anthropic/[^"]+|openai/[^"]+|mistral/[^"]+)"', src)
    assert not hardcoded, f"{rel} fige un modèle dans l'appel : {hardcoded}"


def test_builtin_providers_ship_a_model_that_exists():
    """Les fournisseurs livrés d'origine doivent viser un modèle du socle de
    référence, sinon le premier appel échoue sur un identifiant inconnu."""
    from app.services.model_routing_service import DEFAULT_CUSTOM_PROVIDERS
    from app.services.llm_reference_catalog import REFERENCE_BY_ID

    for prov in DEFAULT_CUSTOM_PROVIDERS:
        assert prov["litellm_id"] in REFERENCE_BY_ID, (
            f"Fournisseur « {prov['id']} » : modèle par défaut inconnu du socle "
            f"({prov['litellm_id']})."
        )


def test_key_test_endpoint_persists_a_validated_key():
    """Le test de connexion doit conserver la clé qui vient de répondre.

    Sans cela, l'écran affiche « Connecté » et la base reste vide : c'est ce qui
    a fait perdre la clé Gemini saisie le 3 septembre."""
    src = (APP / "api" / "admin.py").read_text(encoding="utf-8")
    block = src[src.index("async def test_llm_provider_connection"):]
    block = block[: block.index("@router.get(\"/llm-catalog\")")]
    assert "key_persisted" in block, "le test de clé ne rapporte pas s'il a enregistré la clé"
    assert "encrypt_api_key(raw_key)" in block, "le test de clé n'enregistre pas la clé validée"
