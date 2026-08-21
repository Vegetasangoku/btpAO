"""
Unit and Integration Tests for btpAO Services (Gantt, Organigramme, Chunking, Exporter, LLM)
"""
import pytest
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.gantt_service import gantt_service
from app.services.diagram_service import diagram_service
from app.services.exporter_service import exporter_service
from app.services.llm_generator import llm_generator_service


def test_chunking_service():
    pages = [
        {
            "page_number": 1,
            "text": "Article 1.1 Objet de la consultation\nLe présent marché concerne les travaux de gros oeuvre.\n\nArticle 1.2 Délai d'exécution\nLe délai global est fixé à 6 mois."
        }
    ]
    chunks = chunking_service.chunk_document_pages(pages)
    assert len(chunks) >= 1
    assert "gros oeuvre" in chunks[0]["content"]


def test_embedding_service_dimension():
    text = "Grue à tour Potain MDT 219 pour le chantier de Saint-Denis"
    vec = embedding_service.generate_embedding(text)
    assert len(vec) == 1536
    # Vector should be normalized
    import math
    norm = math.sqrt(sum(x * x for x in vec))
    assert pytest.approx(norm, 0.01) == 1.0


def test_gantt_chart_generation():
    tenant_id = "11111111-1111-1111-1111-111111111111"
    project_id = "test-project-123"
    phases = [
        {"phase": "1. Terrassement & PIC", "duree_semaines": 4, "jalon": "Plateforme prête"},
        {"phase": "2. Gros Œuvre Superstructure", "duree_semaines": 12, "jalon": "Hors d'eau"},
    ]
    result = gantt_service.generate_gantt_chart_png(
        tenant_id=tenant_id,
        project_id=project_id,
        project_title="Test Groupe Scolaire",
        phases=phases,
        start_date_str="2026-10-01"
    )
    assert "s3_key" in result
    assert result["bytes_length"] > 1000
    assert result["total_weeks"] == 16


def test_diagram_generation():
    tenant_id = "11111111-1111-1111-1111-111111111111"
    project_id = "test-project-123"
    cadres = [
        {"nom": "Jean-Marc Alibert", "role": "Directeur de Projet", "experience_ans": 15, "presence_hebdo_pct": 100},
        {"nom": "Sébastien Vasseur", "role": "Chef de Chantier", "experience_ans": 12, "presence_hebdo_pct": 100},
    ]
    result = diagram_service.generate_organigramme_png(
        tenant_id=tenant_id,
        project_id=project_id,
        project_title="Test Groupe Scolaire",
        cadres=cadres
    )
    assert "s3_key" in result
    assert result["bytes_length"] > 1000


def test_exporter_service_docx_build():
    tenant_id = "11111111-1111-1111-1111-111111111111"
    project_id = "test-project-123"
    project_data = {
        "title": "Construction Groupe Scolaire",
        "reference_code": "AO-2026-001",
        "client_name": "Ville de Saint-Denis",
        "budget_estimate": 3000000.0,
    }
    sections = [
        {
            "section_key": "moyens_humains",
            "title": "1. Moyens Humains",
            "content_html": "<p>Direction par Jean-Marc Alibert. Taux d'encadrement garanti 18.5%.</p>"
        }
    ]
    decision_form = {
        "delai_mois": 6,
        "materiel_principal": "Grue Potain MDT 219",
        "equipe_cadres": [{"nom": "Jean-Marc Alibert", "role": "Directeur", "experience_ans": 15}],
        "phasage_travaux": [{"phase": "Terrassement", "duree_semaines": 4, "jalon": "Livré"}]
    }

    res = exporter_service.build_memo_docx(
        tenant_id=tenant_id,
        project_id=project_id,
        project_data=project_data,
        sections=sections,
        decision_form=decision_form,
        include_visuals=False
    )
    assert "s3_docx_key" in res
    assert len(res["docx_bytes"]) > 5000
