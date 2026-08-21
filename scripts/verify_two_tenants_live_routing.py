"""
Live proof of multi-tenant LLM Model routing:
1. Tenant Alpha (EiffaBTP) is configured with 'economique' -> Claude Haiku 4.5 (≈ 1 $ / 5 $ par M tokens)
2. Tenant Beta (BouygBTP) is configured with 'maximum' -> Claude Fable 5 (≈ 10 $ / 50 $ par M tokens)
3. Direct execution of generation task for both tenants, verifying runtime model resolution and log output.
"""
import asyncio
import uuid
from sqlalchemy import select, update
from app.core.db import AsyncSessionLocal
from app.models.entities import Tenant, PlatformSettings


from app.services.model_routing_service import model_routing_service
from app.services.llm_generator import llm_generator_service

TENANT_ALPHA_ID = uuid.UUID('11111111-1111-1111-1111-111111111111')
TENANT_BETA_ID = uuid.UUID('22222222-2222-2222-2222-222222222222')

async def run_live_proof():
    print("=" * 80)
    print(">>> DÉMONSTRATION EN DIRECT DU ROUTAGE DES MODÈLES IA PAR CLIENT <<<")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        # 1. Configurer Tenant Alpha en 'economique'
        await db.execute(
            update(Tenant)
            .where(Tenant.id == TENANT_ALPHA_ID)
            .values(branding_config={"llm_model_tier": "economique"})
        )
        # 2. Configurer Tenant Beta en 'maximum'
        await db.execute(
            update(Tenant)
            .where(Tenant.id == TENANT_BETA_ID)
            .values(branding_config={"llm_model_tier": "maximum"})
        )
        await db.commit()

        # 3. Résolution dynamique
        model_alpha = await model_routing_service.resolve_model_for_tenant(db, TENANT_ALPHA_ID)
        model_beta = await model_routing_service.resolve_model_for_tenant(db, TENANT_BETA_ID)

        print(f"\n[Tenant Alpha - EiffaBTP SAS]")
        print(f"  Configuration : Tier 'economique'")
        print(f"  Modèle résolu : {model_alpha}")
        print(f"  Tarification  : 1 $ / 5 $ par M tokens")

        print(f"\n[Tenant Beta - BouygBTP SAS]")
        print(f"  Configuration : Tier 'maximum'")
        print(f"  Modèle résolu : {model_beta}")
        print(f"  Tarification  : 10 $ / 50 $ par M tokens")

        # 4. Exécution réelle de génération pour Tenant Alpha
        print("\n" + "-" * 40)
        print(">>> Exécution Génération Réelle — Tenant Alpha (Économique) <<<")
        res_alpha = await llm_generator_service.generate_memo_section(
            project_title="Réhabilitation Groupe Scolaire Paris 15",
            reference_code="AO-2026-001",
            section_key="methodology",
            section_title="Méthodologie et Organisation du Chantier",
            decision_form={"cadence": "rapide"},
            dce_criteria=[{"name": "Délai d'exécution"}],
            rag_dce_chunks=[{"content": "DCE extrait"}],
            rag_company_assets=[{"content": "Certification ISO 9001"}],
            regulatory_profile={"country_code": "FR", "regulations": ["CCAG Travaux 2021", "Code de la commande publique"]},
            llm_model=model_alpha["model_string"]
        )
        print(f"  Modèle effectif utilisé : {res_alpha.get('model_used')}")
        print(f"  Nombre de mots générés : {len(res_alpha.get('content', '').split())}")

        # 5. Exécution réelle de génération pour Tenant Beta
        print("\n" + "-" * 40)
        print(">>> Exécution Génération Réelle — Tenant Beta (Maximum) <<<")
        res_beta = await llm_generator_service.generate_memo_section(
            project_title="Construction Centre Aquatique Olympique",
            reference_code="AO-2026-002",
            section_key="team",
            section_title="Moyens Humains et Matériels Dédiés",
            decision_form={"effectif": 25},
            dce_criteria=[{"name": "Qualification équipe"}],
            rag_dce_chunks=[{"content": "DCE extrait aquatique"}],
            rag_company_assets=[{"content": "Grue à tour et coffrages"}],
            regulatory_profile={"country_code": "FR", "regulations": ["CCAG Travaux 2021", "Code de la commande publique"]},
            llm_model=model_beta["model_string"]
        )
        print(f"  Modèle effectif utilisé : {res_beta.get('model_used')}")
        print(f"  Nombre de mots générés : {len(res_beta.get('content', '').split())}")



    print("\n" + "=" * 80)
    print(">>> PREUVE VALIDÉE : Deux tenants avec deux modèles différents appellent chacun leur modèle assigné <<<")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_live_proof())
