"""
Test Suite for Tenant Custom System Prompt Integration in llm_generator.py.
Verifies that:
1. build_btp_system_prompt accepts tenant_system_prompt and includes it under dedicated section.
2. When tenant_system_prompt is None or empty, base localized prompt is unmodified.
"""
import pytest
from app.services.llm_generator import build_btp_system_prompt

SAMPLE_REG_PROFILE = {
    "country_code": "FR",
    "country_name": "France",
    "technical_standards_reference": "DTU (Documents Techniques Unifiés) et Eurocodes",
    "environmental_regulation": "RE2020 (Réglementation Environnementale 2020)",
    "public_procurement_regime": "Code de la commande publique et CCAG Travaux 2021",
    "recognized_qualifications": ["Qualibat", "Qualifelec", "FNTP"],
    "waste_tracking_regime": "Bordereau de Suivi des Déchets (Trackdéchets)",
    "safety_plan_regime": "Plan Particulier de Sécurité et de Protection de la Santé (PPSPS)",
}


def test_build_btp_system_prompt_without_tenant_custom_prompt():
    prompt = build_btp_system_prompt(SAMPLE_REG_PROFILE)
    assert "Tu es un Ingénieur Principal Méthodes" in prompt
    assert "RE2020" in prompt
    assert "PROMPT SYSTÈME PERSONNALISÉ" not in prompt


def test_build_btp_system_prompt_with_tenant_custom_prompt():
    custom_directive = "Toujours valoriser notre parc de grues à tour 100% électriques et notre béton bas carbone certifié CEM III/A."
    prompt = build_btp_system_prompt(SAMPLE_REG_PROFILE, tenant_system_prompt=custom_directive)
    
    assert "Tu es un Ingénieur Principal Méthodes" in prompt
    assert "DIRECTIVES ET POSITIONNEMENT SPÉCIFIQUES DE L'ENTREPRISE (PROMPT SYSTÈME PERSONNALISÉ) :" in prompt
    assert custom_directive in prompt


def test_build_btp_system_prompt_with_empty_or_whitespace_prompt():
    prompt_none = build_btp_system_prompt(SAMPLE_REG_PROFILE, tenant_system_prompt=None)
    prompt_empty = build_btp_system_prompt(SAMPLE_REG_PROFILE, tenant_system_prompt="   ")
    
    assert prompt_none == prompt_empty
    assert "PROMPT SYSTÈME PERSONNALISÉ" not in prompt_none
