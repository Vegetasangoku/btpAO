"""
Integration Tests for Web Search Enrichment (Serper API), Double Citations, Anti-Hallucination & Tenant Isolation.
"""
import pytest
import psycopg2
from app.services.web_search_service import web_search_service, SERPER_COST_PER_QUERY_USD
from app.services.llm_generator import llm_generator_service
from app.workers.tasks import generate_section_task

TENANT_A_ID = "11111111-1111-1111-1111-111111111111"
TENANT_B_ID = "22222222-2222-2222-2222-222222222222"
PROJ_A_ID = "33333333-3333-3333-3333-333333333333"

FRENCH_REGULATORY_PROFILE = {
    "country_code": "FR",
    "country_name": "France",
    "technical_standards_reference": "DTU / Eurocodes / Normes NF BTP",
    "environmental_regulation": "RE2020 / FDES / Base INIES",
    "public_procurement_regime": "Code de la Commande Publique & CCAG Travaux",
    "recognized_qualifications": ["QUALIBAT", "FNTP", "QUALIFELEC"],
    "waste_tracking_regime": "Trackdéchets / BSD dématérialisé (Bordereau de Suivi des Déchets)",
    "safety_plan_regime": "PPSPS (Plan Particulier de Sécurité et de Protection de la Santé) & PAQ",
}



@pytest.fixture(autouse=True)
def setup_postgres_web_search():
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("RESET ROLE;")
        cur.execute("""
            INSERT INTO public.tenants (id, name, slug)
            VALUES 
            (%s, 'EiffaBTP Construction', 'eiffabtp-web'),
            (%s, 'BouygBTP Bâtiment', 'bouygbtp-web')
            ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug;


            INSERT INTO public.projects (id, tenant_id, reference_code, title, client_name, location)
            VALUES 
            (%s, %s, 'AO-HQE-PARIS', 'Construction Centre Aquatique HQE', 'Métropole Grand Paris', 'Saint-Denis')
            ON CONFLICT (id) DO NOTHING;

            INSERT INTO public.tenant_subscriptions (id, tenant_id, plan_id, status, billing_mode, allow_overage)
            VALUES (gen_random_uuid(), %s, 'pro', 'active', 'stripe', true)
            ON CONFLICT (tenant_id) DO UPDATE SET status = 'active';

            DELETE FROM public.generated_sections WHERE tenant_id IN (%s, %s);
        """, (TENANT_A_ID, TENANT_B_ID, PROJ_A_ID, TENANT_A_ID, TENANT_A_ID, TENANT_A_ID, TENANT_B_ID))
    finally:
        cur.close()
        conn.close()


@pytest.mark.anyio
async def test_web_search_service_scoping_and_cost_logging(caplog):
    """Web search is strictly scoped to calling tenant, logs estimated cost, and returns structured results."""
    import logging
    caplog.set_level(logging.INFO)
    results = await web_search_service.search(

        tenant_id=TENANT_A_ID,
        query="RE2020 seuil carbone béton CEM III",
        num_results=2,
        project_id=PROJ_A_ID,
    )
    assert len(results) >= 1
    assert results[0].url.startswith("http")
    assert results[0].title is not None
    assert results[0].snippet is not None

    # Verify cost logging in caplog
    log_text = caplog.text
    assert f"Tenant {TENANT_A_ID}" in log_text
    assert "Estimated Cost" in log_text


@pytest.mark.anyio
async def test_llm_generator_includes_internal_and_web_citations():
    """Generated section contains both [Source : DCE ...] and [Source web : Titre — URL] citations."""
    rag_dce_chunks = [
        {"section_title": "CCTP Lot 01 Gros Œuvre", "page_number": 14, "content": "Mise en œuvre obligatoire de bétons bas carbone."}
    ]
    rag_web_sources = [
        {
            "title": "NF DTU 13.3 - Dallages Béton",
            "url": "https://www.afnor.org/normes/nf-dtu-13-3-dallages-beton",
            "snippet": "Prescriptions techniques pour le dallage industriel et tertiaire.",
        }
    ]

    res = await llm_generator_service.generate_memo_section(
        project_title="Centre Aquatique HQE",
        reference_code="AO-HQE-PARIS",
        section_key="qse_environnement",
        section_title="Démarche Environnementale & Déchets",
        decision_form={"demarche_rse_environnement": "Béton CEM III bas carbone"},
        dce_criteria=[],
        rag_dce_chunks=rag_dce_chunks,
        rag_company_assets=[],
        rag_web_sources=rag_web_sources,
        regulatory_profile=FRENCH_REGULATORY_PROFILE,
        custom_instructions=None,
    )

    html = res["content_html"]
    assert "[Source : DCE CCTP Lot 01 Gros Œuvre, Page 14]" in html
    assert "Source web :" in html
    assert "NF DTU 13.3" in html
    assert "https://www.afnor.org/normes/nf-dtu-13-3-dallages-beton" in html
    assert res["compliance_score"] >= 90.0


@pytest.mark.anyio
async def test_llm_generator_flags_missing_data_anti_hallucination():
    """When a specific technical requirement has no internal or web source, an explicit alert is raised instead of inventing."""
    res = await llm_generator_service.generate_memo_section(
        project_title="Centre Aquatique HQE",
        reference_code="AO-HQE-PARIS",
        section_key="moyens_materiels",
        section_title="Moyens Matériels",
        decision_form={"materiel_principal": "Grue Potain MDT 219"},
        dce_criteria=[],
        rag_dce_chunks=[],
        rag_company_assets=[],
        rag_web_sources=[],
        regulatory_profile=FRENCH_REGULATORY_PROFILE,
        custom_instructions="Exigence introuvable concernant un procédé de pompage cryogénique non documenté",
    )


    html = res["content_html"]
    # Check that anti-hallucination alert is explicitly rendered
    assert "[Information requise de l'entreprise :" in html


def test_celery_generate_section_task_integrates_web_enrichment():
    """generate_section_task queries web search, integrates sources, and stores section in DB under RLS."""
    task_res = generate_section_task(
        tenant_id=TENANT_A_ID,
        project_id=PROJ_A_ID,
        section_key="qse_environnement",
        custom_instructions="Intégrer les seuils RE2020 et traçabilité Trackdéchets",
    )
    assert task_res["status"] == "completed"

    # Verify directly in PostgreSQL with Tenant A role
    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SET ROLE btp_app_user;")
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false);", (TENANT_A_ID,))
        cur.execute("""
            SELECT section_key, status, compliance_score, content_html 
            FROM public.generated_sections 
            WHERE project_id = %s;
        """, (PROJ_A_ID,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "qse_environnement"
        assert row[1] == "generated"
        assert "Source web :" in row[3]
    finally:
        cur.close()
        conn.close()


@pytest.mark.anyio
async def test_web_search_multi_tenant_isolation(caplog):
    """Tenant A and Tenant B web search calls remain strictly segregated."""
    import logging
    caplog.set_level(logging.INFO)
    await web_search_service.search(

        tenant_id=TENANT_A_ID,
        query="Norme NF DTU 13.3 Dallage pour Tenant A",
        project_id=PROJ_A_ID,
    )
    await web_search_service.search(
        tenant_id=TENANT_B_ID,
        query="FDES CEM III Bas Carbone pour Tenant B",
        project_id=None,
    )

    log_text = caplog.text
    assert f"Tenant {TENANT_A_ID}" in log_text
    assert f"Tenant {TENANT_B_ID}" in log_text


@pytest.mark.anyio
async def test_web_search_service_returns_empty_in_production_without_api_key(monkeypatch, caplog):
    """In production mode without an API key, search() strictly returns [] without fabricating results."""
    import logging
    from app.core.config import settings

    caplog.set_level(logging.WARNING)
    # Simulate production environment without Serper API key
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SERPER_API_KEY", None)

    results = await web_search_service.search(
        tenant_id=TENANT_A_ID,
        query="NF DTU 13.3 Dallage Béton",
        num_results=4,
        project_id=PROJ_A_ID,
    )

    # Must return empty list, zero fabricated items
    assert results == []
    assert len(results) == 0
    assert "Returning 0 web results to prevent fake/hallucinated citations" in caplog.text


@pytest.mark.anyio
async def test_llm_generation_with_empty_web_results_renders_missing_data_marker_and_no_fake_citations():
    """When web search returns 0 results and internal context is empty, the LLM generator displays missing info marker and ZERO fake citations."""
    res = await llm_generator_service.generate_memo_section(
        project_title="Centre Aquatique HQE",
        reference_code="AO-HQE-PARIS",
        section_key="qse_environnement",
        section_title="Démarche Environnementale & Déchets",
        decision_form={"demarche_rse_environnement": "Béton CEM III bas carbone"},
        dce_criteria=[],
        rag_dce_chunks=[],
        rag_company_assets=[],
        rag_web_sources=[], # 0 web search results (due to missing key or empty search)
        regulatory_profile=FRENCH_REGULATORY_PROFILE,
        custom_instructions=None,
    )


    html = res["content_html"]

    # 1. Missing information alert is present
    assert "[Information requise de l'entreprise :" in html

    # 2. Absolutely ZERO fake web sources or URLs are fabricated
    assert "<h3>Sources Réglementaires & Techniques Externes</h3>" not in html
    assert "Source web :" not in html
    assert "ecologie.gouv.fr" not in html
    assert "inies.fr" not in html
    assert "afnor.org" not in html

