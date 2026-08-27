"""
Tenant Continuous Learning & Experience Capitalization Engine.
Extracts actionable lessons from buyer debriefs / tender outcomes (won/lost)
and feeds them back into the memo generation loop.
Strictly isolated per tenant under Postgres RLS.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import TenantLearning


import difflib
import re
from app.models.entities import CompanyAsset, GeneratedSection, ProjectDecision


class LearningService:
    @staticmethod
    def calculate_diff_significance(
        old_text: Optional[str],
        new_text: str,
        threshold_pct: float = 15.0
    ) -> tuple[bool, float, str]:
        """
        Calculates whether a user modification is significant enough to warrant
        learning retention (> 15% modification or major content addition).
        """
        if not old_text or not old_text.strip():
            summary = "Ajout initial d'un contenu complet pour cette section."
            return True, 100.0, summary

        # Strip HTML tags for clean semantic comparison
        clean_old = re.sub(r'<[^>]+>', ' ', old_text).strip()
        clean_new = re.sub(r'<[^>]+>', ' ', new_text).strip()

        seq = difflib.SequenceMatcher(None, clean_old, clean_new)
        similarity = seq.ratio()
        diff_pct = round((1.0 - similarity) * 100, 1)

        char_diff = len(clean_new) - len(clean_old)
        is_significant = (diff_pct >= threshold_pct) or (char_diff > 80)

        summary = ""
        if is_significant:
            added_fragments = [
                line[2:].strip()
                for line in difflib.ndiff(clean_old.splitlines(), clean_new.splitlines())
                if line.startswith('+ ') and len(line[2:].strip()) > 10
            ]
            if added_fragments:
                summary = f"Ajustement ({diff_pct}% modifié) : " + "; ".join(added_fragments[:2])
            else:
                summary = f"Réécriture technique majeure ({diff_pct}% de modification du contenu)."

        return is_significant, diff_pct, summary[:250]

    async def aggregate_prefill_knowledge(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        section_key: str,
        section_title: str,
        project_id: Optional[uuid.UUID] = None,
        min_chars_threshold: int = 150,
    ) -> tuple[List[Dict[str, Any]], str, bool, Optional[str]]:
        """
        Phase B - Aggregates all known tenant data for initial tender prefill:
        1. Historical validated sections from past projects.
        2. Validated company knowledge assets.
        3. Continuous tenant learnings.
        """
        sources_used: List[Dict[str, Any]] = []
        chunks: List[str] = []

        # 1. Past projects history (all countries)
        stmt_past = (
            select(GeneratedSection)
            .where(
                GeneratedSection.tenant_id == tenant_id,
                GeneratedSection.section_key == section_key,
                GeneratedSection.status.in_(["validated", "user_edited", "completed"]),
            )
        )
        if project_id:
            stmt_past = stmt_past.where(GeneratedSection.project_id != project_id)

        stmt_past = stmt_past.order_by(GeneratedSection.updated_at.desc()).limit(3)
        res_past = await db.execute(stmt_past)
        past_sections = res_past.scalars().all()

        for ps in past_sections:
            if ps.content_html:
                clean_txt = re.sub(r'<[^>]+>', ' ', ps.content_html).strip()
                if clean_txt:
                    chunks.append(f"--- Précédente rédaction validée ({ps.title}) ---\n{clean_txt[:1200]}")
                    sources_used.append({
                        "type": "past_project_section",
                        "id": str(ps.id),
                        "title": ps.title,
                        "date": ps.updated_at.isoformat() if ps.updated_at else None,
                    })

        # 2. Validated Company Assets
        stmt_assets = (
            select(CompanyAsset)
            .where(
                CompanyAsset.tenant_id == tenant_id,
                CompanyAsset.validated_by_user == True,
                CompanyAsset.status != "obsolete",
            )
            .order_by(CompanyAsset.created_at.desc())
            .limit(5)
        )
        res_assets = await db.execute(stmt_assets)
        assets = res_assets.scalars().all()

        for a in assets:
            desc = a.description or ""
            if desc:
                chunks.append(f"--- Savoir-faire ({a.category}: {a.title}) ---\n{desc}")
                sources_used.append({
                    "type": "company_asset",
                    "id": str(a.id),
                    "title": a.title,
                    "category": a.category,
                    "date": a.updated_at.isoformat() if a.updated_at else None,
                })

        # 3. Active Tenant Learnings (scoped to this project + section per the
        # 3-portees learning loop -- a tenant-wide learning still applies, a
        # project/section-scoped one only applies where the user chose it to)
        learnings = await self.get_active_tenant_learnings(
            db=db, tenant_id=tenant_id, project_id=project_id, section_type=section_key, limit=5
        )
        for l in learnings:
            content = l.learned_content or l.actionable_directive or l.learning_insight
            if content:
                chunks.append(f"--- Ajustement appris ({l.title}) ---\n{content}")
                sources_used.append({
                    "type": "tenant_learning",
                    "id": str(l.id),
                    "title": l.title,
                    "date": l.created_at.isoformat() if l.created_at else None,
                })

        combined_text = "\n\n".join(chunks)
        total_len = len(combined_text)
        is_sufficient = total_len >= min_chars_threshold
        missing_label = None if is_sufficient else section_title

        return sources_used, combined_text, is_sufficient, missing_label

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
        project_id: Optional[uuid.UUID] = None,
        section_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[TenantLearning]:
        """
        Retrieves active continuous learnings for LLM context injection or UI view.

        project_id / section_type implement the "boucle d'apprentissage 3
        portees" scoping: a learning with project_id=NULL (resp.
        section_type=NULL) was saved as "AOs similaires" / "tous les futurs
        dossiers" and applies regardless of the caller's project_id (resp.
        section_type); a learning with a concrete project_id (resp.
        section_type) was saved as "cette reponse AO uniquement" and only
        matches when the caller's value equals it. Passing project_id=None /
        section_type=None here (the default) preserves the original
        unrestricted behavior for any caller that doesn't scope its query.
        """
        stmt = (
            select(TenantLearning)
            .where(TenantLearning.tenant_id == tenant_id, TenantLearning.is_active == True)
        )
        if category:
            stmt = stmt.where(TenantLearning.category == category)
        if project_id:
            stmt = stmt.where(
                or_(TenantLearning.project_id.is_(None), TenantLearning.project_id == project_id)
            )
        if section_type:
            stmt = stmt.where(
                or_(TenantLearning.section_type.is_(None), TenantLearning.section_type == section_type)
            )

        stmt = stmt.order_by(TenantLearning.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())


learning_service = LearningService()
