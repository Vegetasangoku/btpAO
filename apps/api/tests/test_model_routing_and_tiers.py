import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.model_routing_service import (
    model_routing_service,
    LLM_MODEL_TIERS,
    DEFAULT_PLATFORM_TIER,
)
from app.models.entities import Tenant, PlatformSettings
from app.services.llm_generator import llm_generator_service


@pytest.mark.asyncio
async def test_model_routing_hierarchy():
    """Tests the resolution of model tiers between platform default and tenant override."""
    db_mock = AsyncMock()

    # 1. Test fallback when no platform setting exists (Inherits default 'equilibre')
    tenant_id_a = uuid4()
    tenant_a = Tenant(
        id=tenant_id_a,
        name="Entreprise Alpha (Hérité)",
        slug="entreprise-alpha",
        plan="pro",
        branding_config={},
    )

    result_mock = MagicMock()
    # First call: select(Tenant), second call: select(PlatformSettings)
    result_mock.scalar_one_or_none.side_effect = [tenant_a, None]
    db_mock.execute.return_value = result_mock

    res_a = await model_routing_service.resolve_model_for_tenant(
        db=db_mock,
        tenant_id=tenant_id_a,
    )
    assert res_a["tier_id"] == "equilibre"
    assert res_a["model_string"] == "anthropic/claude-sonnet-5"
    assert res_a["is_override"] is False

    # 2. Test when super-admin changed platform default to 'avance'
    ps_mock = PlatformSettings(
        id="global",
        settings={"default_llm_tier": "avance"},
    )
    result_mock.scalar_one_or_none.side_effect = [tenant_a, ps_mock]

    res_platform_changed = await model_routing_service.resolve_model_for_tenant(
        db=db_mock,
        tenant_id=tenant_id_a,
    )
    assert res_platform_changed["tier_id"] == "avance"
    assert res_platform_changed["model_string"] == "anthropic/claude-opus-5"
    assert res_platform_changed["is_override"] is False

    # 3. Test tenant specific override (e.g. 'economique')
    tenant_id_b = uuid4()
    tenant_b = Tenant(
        id=tenant_id_b,
        name="Entreprise Beta (Économique)",
        slug="entreprise-beta",
        plan="starter",
        branding_config={"llm_model_tier": "economique"},
    )
    result_mock.scalar_one_or_none.side_effect = [tenant_b, ps_mock]

    res_b = await model_routing_service.resolve_model_for_tenant(
        db=db_mock,
        tenant_id=tenant_id_b,
    )
    assert res_b["tier_id"] == "economique"
    assert res_b["model_string"] == "anthropic/claude-haiku-4-5-20251001"
    assert res_b["is_override"] is True

    # 4. Test tenant specific override (e.g. 'maximum')
    tenant_id_c = uuid4()
    tenant_c = Tenant(
        id=tenant_id_c,
        name="Entreprise Gamma (Maximum)",
        slug="entreprise-gamma",
        plan="enterprise",
        branding_config={"llm_model_tier": "maximum"},
    )
    result_mock.scalar_one_or_none.side_effect = [tenant_c, ps_mock]

    res_c = await model_routing_service.resolve_model_for_tenant(
        db=db_mock,
        tenant_id=tenant_id_c,
    )
    assert res_c["tier_id"] == "maximum"
    assert res_c["model_string"] == "anthropic/claude-fable-5"
    assert res_c["is_override"] is True



@pytest.mark.asyncio
async def test_all_tiers_pricing_and_names():
    """Verifies that all 4 required tiers have exact labels and valid model identifiers."""
    expected_tiers = ["economique", "equilibre", "avance", "maximum"]
    for tier in expected_tiers:
        assert tier in LLM_MODEL_TIERS
        tier_info = LLM_MODEL_TIERS[tier]
        assert "name" in tier_info
        assert "pricing" in tier_info
        assert "model_string" in tier_info
        assert "$" in tier_info["pricing"]
        assert len(tier_info["display_label"]) > 10


@pytest.mark.asyncio
async def test_llm_generator_logs_and_returns_model():
    """Verifies that LLMGenerator uses the provided model and returns model_used in output."""
    sample_reg_profile = {
        "country_code": "FR",
        "country_name": "France",
        "technical_standards_reference": "DTU et Eurocodes",
        "environmental_regulation": "RE2020",
        "public_procurement_regime": "Code de la commande publique",
        "safety_plan_regime": "PPSPS",
        "waste_tracking_regime": "Trackdéchets",
        "recognized_qualifications": ["Qualibat"],
    }

    mock_completion_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "title": "Méthodologie d'exécution",
        "content_html": "<p>Contenu généré par Claude Haiku 4.5.</p>",
        "compliance_score": 98.0,
        "compliance_notes": "Conforme",
        "visual_placeholders": [],
        "web_sources_used": [],
    })
    mock_completion_response.choices = [mock_choice]

    with patch("app.core.config.settings.ANTHROPIC_API_KEY", "sk-ant-test-12345"), \
         patch("litellm.completion", return_value=mock_completion_response) as mock_litellm:
        
        res = await llm_generator_service.generate_memo_section(
            section_key="methodologie_phasage",
            section_title="Méthodologie d'exécution",
            project_title="Construction Centre Hospitalier",
            reference_code="AO-2026-004",
            decision_form={"delai_mois": 12},
            dce_criteria=[{"name": "Méthodologie", "weight_pct": 40}],
            rag_dce_chunks=[{"section_title": "CCTP Lot Gros Oeuvre", "page_number": 12, "content": "Fondations spéciales"}],
            rag_company_assets=[{"category": "Matériel", "description": "Grues à tour Potain"}],
            regulatory_profile=sample_reg_profile,
            llm_model="anthropic/claude-3-5-haiku-20241022",
        )


        assert res["model_used"] == "anthropic/claude-3-5-haiku-20241022"
        assert "Claude Haiku 4.5" in res["content_html"]
        mock_litellm.assert_called_once()
        call_kwargs = mock_litellm.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-3-5-haiku-20241022"
