"""
Tenant Continuous Learning & Experience Capitalization Engine.
Extracts actionable lessons from buyer debriefs / tender outcomes (won/lost)
and feeds them back into the memo generation loop.
Strictly isolated per tenant under Postgres RLS.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import TenantLearning


class LearningService:
    async def extract_and_store_learnings_from_feedback(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        project_title: str,
        outcome_status: str,
        buyer_feedback: Dict[str, Any],
    ) -> List[TenantLearning]:
        """
        Analyzes buyer feedback points and distills actionable directives.
        Persists them into public.tenant_learnings.
        """
        points_faibles = buyer_feedback.get("points_faibles", [])
        points_forts = buyer_feedback.get("points_forts", [])
        comments = buyer_feedback.get("general_comments") or ""

        new_learnings: List[TenantLearning] = []
        now = datetime.now(timezone.utc)

        # 1. Process points faibles (critical lessons learned from lost/debated tenders)
        for idx, pf in enumerate(points_faibles, start=1):
            pf_str = str(pf).strip()
            if not pf_str:
                continue

            pf_lower = pf_str.lower()
            category = "general"
            if any(k in pf_lower for k in ["délai", "planning", "phasage", "cadencement", "retard"]):
                category = "planning"
            elif any(k in pf_lower for k in ["méthodologie", "pic", "grue", "banche", "béton", "technique"]):
                category = "methodology"
            elif any(k in pf_lower for k in ["déchet", "rse", "carbone", "environnement", "inies"]):
                category = "qse"
            elif any(k in pf_lower for k in ["sécurité", "ppsps", "accident", "coactivité", "gardiennage"]):
                category = "safety"
            elif any(k in pf_lower for k in ["prix", "dpgf", "chiffrage", "cout", "coût"]):
                category = "pricing"

            learning = TenantLearning(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=project_id,
                category=category,
                title=f"Enseignement suite retour acheteur sur {project_title[:40]}",
                learning_insight=f"Point d'amélioration signalé par le pouvoir adjudicateur : {pf_str}",
                actionable_directive=f"Directive obligatoire : Intégrer des justifications techniques et preuves concrètes sur l'aspect '{pf_str}'.",
                source_outcome=outcome_status,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(learning)
            new_learnings.append(learning)

        # 2. Process points forts (best practices to systematize)
        for pf in points_forts:
            pf_str = str(pf).strip()
            if not pf_str:
                continue

            learning = TenantLearning(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=project_id,
                category="methodology",
                title=f"Bonne pratique valorisée sur {project_title[:40]}",
                learning_insight=f"Point fort particulièrement apprécié par l'acheteur : {pf_str}",
                actionable_directive=f"Standardiser et réutiliser l'argumentaire validé sur : {pf_str}.",
                source_outcome=outcome_status,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(learning)
            new_learnings.append(learning)

        if new_learnings:
            await db.flush()

        return new_learnings

    async def get_active_tenant_learnings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[TenantLearning]:
        """
        Retrieves active continuous learnings for LLM context injection or UI view.
        """
        stmt = (
            select(TenantLearning)
            .where(TenantLearning.tenant_id == tenant_id, TenantLearning.is_active == True)
        )
        if category:
            stmt = stmt.where(TenantLearning.category == category)

        stmt = stmt.order_by(TenantLearning.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())


learning_service = LearningService()
