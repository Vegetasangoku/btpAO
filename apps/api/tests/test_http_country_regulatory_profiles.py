"""
Integration Tests for Extensible Multi-Country Regulatory Profiles.
Tests:
1. France (FR) tenants work seamlessly with full localized regulatory framework.
2. Tenants with unconfigured country_code are cleanly blocked (HTTP 400 / task failure) without silent fallback to French norms.
3. Extensibility: Adding a new country profile (e.g. Belgium 'BE') activates without rewriting core logic.
"""
import uuid
import psycopg2
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from app.core.config import settings
from app.main import app
from app.workers.tasks import generate_section_task

TENANT_FR_ID = "aaaaaaaa-1111-1111-1111-111111111111"
TENANT_UNCONFIGURED_ID = "bbbbbbbb-2222-2222-2222-222222222222"
TENANT_BE_ID = "cccccccc-3333-3333-3333-333333333333"

USER_FR_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_UNCONF_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
USER_BE_ID = "33333333-cccc-cccc-cccc-cccccccccccc"

PROJ_FR_ID = "aaaaaaaa-aaaa-1111-1111-111111111111"
PROJ_UNCONF_ID = "bbbbbbbb-bbbb-2222-2222-222222222222"
PROJ_BE_ID = "cccccccc-cccc-3333-3333-333333333333"

SECRET_KEY = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_jwt(user_id: str, tenant_id: str, email: str, role: str = "owner") -> str:
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "app_metadata": {"tenant_id": tenant_id, "role": role},
        "user_metadata": {"tenant_id": tenant_id, "role": role},
    }
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_postgres_country_tenants():
    """Initializes tenants with FR, unconfigured ('XX') and newly added ('BE') country codes."""
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("RESET ROLE;")

        # Seed Belgium regulatory profile to test extensibility
        cur.execute("""
            INSERT INTO public.country_regulatory_profiles (
                country_code, country_name, technical_standards_reference,
                environmental_regulation, public_procurement_regime,
                recognized_qualifications, waste_tracking_regime,
                safety_plan_regime, is_active
            ) VALUES (
                'BE', 'Belgique', 'CCTB 2022 / NBN / Eurocodes Belgique',
                'PEB Région Wallonne & Bruxelles', 'Loi du 17 juin 2016 sur les marchés publics',
                '["Enregistrement Entrepreneur SPF", "VCA", "BCCA"]'::jsonb,
                'Formulaire de transport et valorisation des déchets de construction (Région)',
                'Plan Général de Sécurité et de Santé (PGSS) & Plan Particulier (PPSS)',
                true
            ) ON CONFLICT (country_code) DO NOTHING;
        """)

        # Clean existing test data
        cur.execute("DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s, %s);", (TENANT_FR_ID, TENANT_UNCONFIGURED_ID, TENANT_BE_ID))
        cur.execute("DELETE FROM public.projects WHERE tenant_id IN (%s, %s, %s);", (TENANT_FR_ID, TENANT_UNCONFIGURED_ID, TENANT_BE_ID))
        cur.execute("DELETE FROM public.users WHERE tenant_id IN (%s, %s, %s) OR id IN (%s, %s, %s);", (TENANT_FR_ID, TENANT_UNCONFIGURED_ID, TENANT_BE_ID, USER_FR_ID, USER_UNCONF_ID, USER_BE_ID))
        cur.execute("DELETE FROM public.tenants WHERE id IN (%s, %s, %s);", (TENANT_FR_ID, TENANT_UNCONFIGURED_ID, TENANT_BE_ID))


        # Seed Tenants
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug, country_code)
            VALUES 
            (%s, 'EiffaBTP France', 'eiffabtp-fr', 'FR'),
            (%s, 'GlobalBTP International Unconfigured', 'globalbtp-unconf', 'XX'),
            (%s, 'Bespix BTP Bruxelles', 'bespix-be', 'BE');
        """, (TENANT_FR_ID, TENANT_UNCONFIGURED_ID, TENANT_BE_ID))

        # Seed Users
        cur.execute("""
            INSERT INTO public.users (id, tenant_id, email, full_name, role)
            VALUES
            (%s, %s, 'owner.fr@eiffabtp.fr', 'Directeur FR', 'owner'),
            (%s, %s, 'owner.xx@globalbtp.com', 'Directeur XX', 'owner'),
            (%s, %s, 'owner.be@bespix.be', 'Directeur BE', 'owner');
        """, (
            USER_FR_ID, TENANT_FR_ID,
            USER_UNCONF_ID, TENANT_UNCONFIGURED_ID,
            USER_BE_ID, TENANT_BE_ID,
        ))

        # Seed Projects
        cur.execute("""
            INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, status, outcome_status, created_by)
            VALUES
            (%s, %s, 'Collège HQE Paris', 'AO-2026-FR-01', 'Département 75', 'draft', 'pending', %s),
            (%s, %s, 'Unconfigured Tower Project', 'AO-2026-XX-01', 'Global Dev', 'draft', 'pending', %s),
            (%s, %s, 'Rénovation Énergétique Bâtiment Public Namur', 'AO-2026-BE-01', 'SPW Wallonie', 'draft', 'pending', %s);
        """, (
            PROJ_FR_ID, TENANT_FR_ID, USER_FR_ID,
            PROJ_UNCONF_ID, TENANT_UNCONFIGURED_ID, USER_UNCONF_ID,
            PROJ_BE_ID, TENANT_BE_ID, USER_BE_ID,
        ))

    finally:
        cur.close()
        conn.close()


def test_http_france_tenant_runs_with_full_french_regulatory_profile():
    """FR tenant uses localized French regulatory framework in Go/No-Go and generation without issue."""
    client = TestClient(app)
    token_fr = create_jwt(user_id=USER_FR_ID, tenant_id=TENANT_FR_ID, email="owner.fr@eiffabtp.fr")

    # 1. Run Go/No-Go for French project
    res_gng = client.post(f"/api/dce/go-no-go/{PROJ_FR_ID}", headers={"Authorization": f"Bearer {token_fr}"})
    assert res_gng.status_code == 200
    gng_data = res_gng.json()
    assert gng_data["recommendation"] in ("GO", "RESERVES", "RÉSERVES", "NO-GO")

    # 2. Run section generation task for French tenant
    res_gen = generate_section_task(
        tenant_id=TENANT_FR_ID,
        project_id=PROJ_FR_ID,
        section_key="qse_environnement",
    )
    assert res_gen["status"] == "completed"

    # Verify Trackdéchets / BSD mention is present
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SELECT content_html FROM public.generated_sections WHERE project_id = %s;", (PROJ_FR_ID,))
        row = cur.fetchone()
        assert row is not None
        assert "Trackdéchets / BSD" in row[0]
    finally:
        cur.close()
        conn.close()


def test_http_unconfigured_country_code_blocks_cleanly_without_silent_fallback():
    """A tenant with an unconfigured country code ('XX') is cleanly blocked with 400 Bad Request."""
    client = TestClient(app)
    token_unconf = create_jwt(user_id=USER_UNCONF_ID, tenant_id=TENANT_UNCONFIGURED_ID, email="owner.xx@globalbtp.com")

    # 1. HTTP Go/No-Go is blocked with explicit 400 error message
    res_gng = client.post(f"/api/dce/go-no-go/{PROJ_UNCONF_ID}", headers={"Authorization": f"Bearer {token_unconf}"})
    assert res_gng.status_code == 400
    err_detail = res_gng.json()["detail"]
    assert "Profil réglementaire non configuré pour le pays 'XX'" in err_detail

    # 2. Celery Worker task fails explicitly and refuses silent execution
    with pytest.raises(Exception) as exc_info:
        generate_section_task(
            tenant_id=TENANT_UNCONFIGURED_ID,
            project_id=PROJ_UNCONF_ID,
            section_key="planning_phasage",
        )
    assert "Profil réglementaire non configuré pour le pays 'XX'" in str(exc_info.value)



def test_http_belgium_tenant_applies_belgian_regulatory_profile_without_rewriting_core_logic():
    """Adding a new country profile ('BE') seamlessly activates Belgian public procurement and technical standards."""
    client = TestClient(app)
    token_be = create_jwt(user_id=USER_BE_ID, tenant_id=TENANT_BE_ID, email="owner.be@bespix.be")

    # 1. Run Go/No-Go for Belgian project
    res_gng = client.post(f"/api/dce/go-no-go/{PROJ_BE_ID}", headers={"Authorization": f"Bearer {token_be}"})
    assert res_gng.status_code == 200

    # 2. Run section generation task for Belgian tenant
    res_gen = generate_section_task(
        tenant_id=TENANT_BE_ID,
        project_id=PROJ_BE_ID,
        section_key="securite_ppsps",
    )
    assert res_gen["status"] == "completed"

    # Verify Belgian PGSS / PPSS safety plan regime is applied
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SELECT content_html FROM public.generated_sections WHERE project_id = %s;", (PROJ_BE_ID,))
        row = cur.fetchone()
        assert row is not None
        assert "Plan Général de Sécurité et de Santé (PGSS)" in row[0]
    finally:
        cur.close()
        conn.close()


@pytest.mark.anyio
async def test_llm_generator_refuses_none_regulatory_profile_without_silent_fallback():
    """llm_generator_service.generate_memo_section explicitly raises ValueError if regulatory_profile is None."""
    from app.services.llm_generator import llm_generator_service

    with pytest.raises(ValueError) as exc_info:
        await llm_generator_service.generate_memo_section(
            project_title="Projet Test",
            reference_code="REF-01",
            section_key="qse_environnement",
            section_title="QSE",
            decision_form={},
            dce_criteria=[],
            rag_dce_chunks=[],
            rag_company_assets=[],
            regulatory_profile=None,  # Explicitly None
        )

    assert "regulatory_profile est requis" in str(exc_info.value)
    assert "aucun défaut silencieux autorisé" in str(exc_info.value)


def test_build_btp_system_prompt_dynamic_localization_belgium():
    """build_btp_system_prompt dynamically generates localized prompt for Belgium with zero hardcoded French norms."""
    from app.services.llm_generator import build_btp_system_prompt

    reg_be = {
        "country_code": "BE",
        "country_name": "Belgique",
        "technical_standards_reference": "CCTB 2022 / NBN / Eurocodes Belgique",
        "environmental_regulation": "PEB Région Wallonne & Bruxelles",
        "public_procurement_regime": "Loi du 17 juin 2016 sur les marchés publics",
        "recognized_qualifications": ["Enregistrement Entrepreneur SPF", "VCA", "BCCA"],
        "waste_tracking_regime": "Formulaire de transport et valorisation des déchets de construction (Région)",
        "safety_plan_regime": "Plan Général de Sécurité et de Santé (PGSS) & Plan Particulier (PPSS)",
    }

    prompt = build_btp_system_prompt(reg_be)

    # 1. Must contain Belgian specifications
    assert "pour les Appels d'Offres de marchés publics et privés en Belgique" in prompt
    assert "CCTB 2022 / NBN / Eurocodes Belgique" in prompt
    assert "PEB Région Wallonne & Bruxelles" in prompt
    assert "Loi du 17 juin 2016 sur les marchés publics" in prompt
    assert "Plan Général de Sécurité et de Santé (PGSS)" in prompt
    assert "Enregistrement Entrepreneur SPF" in prompt

    # 2. Must NEVER contain hardcoded French references
    assert "en France" not in prompt
    assert "RE2020" not in prompt
    assert "QUALIBAT" not in prompt
    assert "CCAG Travaux" not in prompt

