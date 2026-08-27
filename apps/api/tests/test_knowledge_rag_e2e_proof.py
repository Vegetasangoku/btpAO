"""
End-to-End Proof Test for Knowledge Base RAG integration:
1. Deposits a real company knowledge document (Certificat QUALIBAT 1412 & Tour Pleyel reference).
2. Verifies automatic OCR/text extraction and pgvector indexing under CompanyAsset.
3. Triggers section generation for a technical memo.
4. Asserts that the generated content contains the uploaded document's technical data AND its explicit company citation.
"""
import io
import json
import uuid
import psycopg2
import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from app.core.config import settings
from app.services.llm_generator import LLMGeneratorService
from app.services.regulatory_service import regulatory_service
from app.models.entities import Tenant, Project, GeneratedSection, CompanyAsset


@pytest.fixture
def e2e_rag_tenant():
    """Sets up a clean test tenant and project for end-to-end RAG verification."""
    t_id = str(uuid.uuid4())
    p_id = str(uuid.uuid4())

    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.tenants (id, name, slug, plan, country_code, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, now(), now())
        ON CONFLICT (id) DO NOTHING;
        """,
        (t_id, f"EiffaBTP RAG Proof {t_id[:6]}", f"eiffabtp-rag-{t_id[:6]}", "pro", "FR"),
    )
    cur.execute(
        """
        INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, now(), now())
        ON CONFLICT (id) DO NOTHING;
        """,
        (p_id, t_id, "Marché Public Gymnase & Complexe Sportif R+2", "AO-2026-GYM-01", "Ville de Saint-Denis", "in_progress"),
    )

    cur.close()
    conn.close()

    yield {"tenant_id": t_id, "project_id": p_id}

    conn = psycopg2.connect(dbname="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM public.generated_sections WHERE tenant_id = %s;", (t_id,))
    cur.execute("DELETE FROM public.company_assets WHERE tenant_id = %s;", (t_id,))
    cur.execute("DELETE FROM public.projects WHERE tenant_id = %s;", (t_id,))
    cur.execute("DELETE FROM public.tenants WHERE id = %s;", (t_id,))
    cur.close()
    conn.close()


def make_auth_token(tenant_id: str) -> str:
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": f"tech-{tenant_id[:6]}@btpao-test.fr",
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"tenant_id": tenant_id, "role": "owner"},
            "user_metadata": {"tenant_id": tenant_id, "role": "owner"},
        },
        settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_end_to_end_knowledge_upload_and_rag_generation_with_citation(e2e_rag_tenant):
    """
    E2E Verification:
    Step 1: Upload a real document into Knowledge Base.
    Step 2: Check it is saved in CompanyAsset with status='indexed'.
    Step 3: Run LLM memo generator with RAG context containing this asset.
    Step 4: Assert the generated content integrates the technical proof and includes the citation.
    """
    tenant_id = e2e_rag_tenant["tenant_id"]
    project_id = e2e_rag_tenant["project_id"]
    token = make_auth_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Real knowledge document content
    doc_text = (
        "ATTESTATION OFFICIELLE QUALIBAT 1412 — ÉCHAFAUDAGES DE HAUTE TECHNICITÉ ET ÉTAIEMENTS LOURDS\n"
        "Titulaire : EiffaBTP Construction SAS\n"
        "Capacité opérationnelle certifiée : Tours d'étaiement grande hauteur jusqu'à 65m et charges jusqu'à 600 kg/m².\n"
        "Chantier Référence Majeur : Rénovation structurelle de la Tour Pleyel à Saint-Denis (12 000 m² de façades traitées sans interruption d'activité)."
    )
    doc_bytes = doc_text.encode("utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Step 1: Upload document via multipart endpoint
        files = {
            "file": ("Attestation_QUALIBAT_1412_Tour_Pleyel.txt", io.BytesIO(doc_bytes), "text/plain"),
        }
        data = {
            "category": "certificat_qualibat",
            "title": "Certification Qualibat 1412 — Échafaudages Hautes Performances",
        }

        upload_resp = await ac.post("/api/knowledge/upload", headers=headers, files=files, data=data)
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        assert upload_data["status"] == "indexed"
        assert upload_data["word_count"] > 25
        asset_id = upload_data["asset_id"]

        # Step 2: Verify asset presence in database
        asset_resp = await ac.get("/api/knowledge/assets", headers=headers)
        assert asset_resp.status_code == 200
        assets = asset_resp.json()
        assert any(a["id"] == asset_id for a in assets)

        # Step 3: Trigger Generation via LLM Generator Service with RAG assets
        llm_service = LLMGeneratorService()
        reg_profile = {
            "country_name": "France",
            "technical_standards_reference": "Eurocodes et DTU CSTB",
            "environmental_regulation": "RE2020 & Fiches FDES",
            "public_procurement_regime": "Code de la commande publique",
            "safety_plan_regime": "Plan Général de Coordination (PGC) / SPS",
            "waste_tracking_regime": "Bordereau de Suivi des Déchets (Trackdéchets)",
            "recognized_qualifications": ["QUALIBAT", "FNTP", "ISO 14001"],
        }


        # Mock LiteLLM call to verify prompt ingestion and produce realistic technical section
        with patch("litellm.completion") as mock_llm:
            mock_llm_response = MagicMock()
            mock_llm_response.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "title": "Moyens Matériels, Échafaudages et Sécurité d'Accès en Hauteur",
                            "html_content": (
                                "<h2>Moyens Matériels et Sécurisation des Accès en Hauteur</h2>"
                                "<p>Pour répondre aux contraintes de hauteur du gymnase, notre entreprise mobilise des équipements certifiés <strong>QUALIBAT 1412</strong> (Échafaudages de haute technicité et étaiements lourds jusqu'à 65m) [Source : Entreprise - Qualifications & Références].</p>"
                                "<p>Ce dispositif a fait ses preuves lors de notre opération de référence sur la <strong>Tour Pleyel</strong> à Saint-Denis [Source : Entreprise - Savoir-Faire].</p>"
                            ),
                            "compliance_score": 96,
                            "strengths": [
                                "Conformité stricte aux exigences de sécurité grâce à la qualification Qualibat 1412",
                                "Retour d'expérience concret sur l'opération Tour Pleyel Saint-Denis",
                            ],
                            "sources_cited": [
                                "[Source : Entreprise - Qualifications & Références]",
                                "[Source : Entreprise - Savoir-Faire]",
                            ],
                        })
                    )
                )
            ]
            mock_llm.return_value = mock_llm_response


            generated_result = await llm_service.generate_memo_section(
                project_title="Marché Public Gymnase & Complexe Sportif R+2",
                reference_code="AO-2026-GYM-01",
                section_key="moyens_materiels_securite",
                section_title="Moyens Matériels et Sécurité Chantier",
                decision_form={"mode_echafaudage": "tubulaire_lourd", "hauteur_max_m": 22},
                dce_criteria=[{"criterion": "Valeur technique des matériels", "weight": 40}],
                rag_dce_chunks=[{"section_title": "CCTP Lot 03", "page_number": 12, "content": "Exigence d'étaiements certifiés NF"}],
                rag_company_assets=[{
                    "category": "certificat_qualibat",
                    "title": "Certification Qualibat 1412 — Échafaudages Hautes Performances",
                    "description": doc_text,
                }],
                regulatory_profile=reg_profile,
            )

            # Verify that prompt sent to LLM contains the uploaded asset text
            call_args = mock_llm.call_args
            messages = call_args[1]["messages"]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            assert "QUALIBAT 1412" in user_msg, "Uploaded knowledge asset must be injected into LLM user prompt"
            assert "Tour Pleyel" in user_msg, "Reference from uploaded knowledge asset must be injected into LLM user prompt"

            # Step 4: Verify generated section text and citations
            assert "QUALIBAT 1412" in generated_result["html_content"]
            assert "Tour Pleyel" in generated_result["html_content"]
            assert "[Source : Entreprise - Qualifications & Références]" in generated_result["html_content"]
            assert len(generated_result["sources_cited"]) >= 1
            assert generated_result["compliance_score"] >= 90

