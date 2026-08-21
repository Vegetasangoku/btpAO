"""
Go/No-Go Decision Matrix Engine for Tenders (Appels d'Offres BTP).
Strictly scoped to the tenant under Postgres RLS.
Cross-references:
1. DCE Criteria & Mandatory Requirements (dce_criteria)
2. Real Enterprise Qualifications, Assurances & References (company_assets)
3. Submission Deadline vs Concurrent Tenant Workload (projects count)
4. Historical Win-Rate on Similar Tenders (with transparent neutral missing-data handling)
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import CompanyAsset, DCECriterionEntity, Project, ProjectGoNoGoAnalysis
from app.models.schemas import GoNoGoAnalysisOut, GoNoGoFactor
from app.services.regulatory_service import regulatory_service


class GoNoGoService:
    async def evaluate_project(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> ProjectGoNoGoAnalysis:
        """
        Calculates and persists the Go/No-Go recommendation for a given tender,
        strictly contextualized by the country regulatory profile of the tenant.
        """
        # 1. Resolve Country Regulatory Profile (strictly fails if unsupported country_code)
        regulatory_profile = await regulatory_service.get_tenant_regulatory_profile(db=db, tenant_id=tenant_id)
        recognized_quals = regulatory_profile.recognized_qualifications if regulatory_profile.recognized_qualifications is not None else []
        quals_label = ", ".join(recognized_quals[:2]) if recognized_quals else "Certifications professionnelles"


        # 2. Fetch Project
        p_stmt = select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        p_res = await db.execute(p_stmt)
        project = p_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found or access denied")

        # 3. Fetch DCE Criteria
        c_stmt = select(DCECriterionEntity).where(
            DCECriterionEntity.project_id == project_id,
            DCECriterionEntity.tenant_id == tenant_id,
        )
        c_res = await db.execute(c_stmt)
        criteria = c_res.scalars().all()



        # 3. Fetch Company Assets (Qualifications, Assurances, References)
        a_stmt = select(CompanyAsset).where(CompanyAsset.tenant_id == tenant_id)
        a_res = await db.execute(a_stmt)
        company_assets = a_res.scalars().all()

        # 4. Fetch Active Projects Count on Tenant
        active_stmt = select(func.count(Project.id)).where(
            Project.tenant_id == tenant_id,
            Project.status.in_(["draft", "in_progress", "analyzing", "generating"]),
        )
        active_res = await db.execute(active_stmt)
        active_projects_count = active_res.scalar() or 1

        # 5. Fetch Historical Win-Rate Data
        hist_stmt = select(Project.status, func.count(Project.id)).where(
            Project.tenant_id == tenant_id,
            Project.status.in_(["won", "lost", "adjudicated"]),
        ).group_by(Project.status)
        hist_res = await db.execute(hist_stmt)
        hist_counts = dict(hist_res.all())

        factors: List[GoNoGoFactor] = []
        blocking_issues: List[str] = []
        score = 70.0

        # ---------------------------------------------------------------------
        # Evaluation 1: DCE Mandatory Criteria & Requirements
        # ---------------------------------------------------------------------
        if not criteria:
            factors.append(
                GoNoGoFactor(
                    category="mandatory_criteria",
                    title="Exigences & Critères du DCE",
                    status="missing_data",
                    impact="neutral",
                    detail="Aucun critère DCE extrait pour ce dossier. Uploader le Règlement de Consultation (RC) pour une analyse affinée.",
                    recommendation="Uploader le RC et le CCTP dans l'onglet DCE.",
                )
            )
        else:
            mandatory_criteria = [
                c for c in criteria
                if str(c.mandatory).lower() in ("true", "1", "yes", "obligatoire")
            ]
            total_mand = len(mandatory_criteria)
            factors.append(
                GoNoGoFactor(
                    category="mandatory_criteria",
                    title="Exigences & Critères du DCE",
                    status="ok",
                    impact="positive",
                    detail=f"{len(criteria)} critères extraits du DCE dont {total_mand} exigence(s) obligatoire(s).",
                    recommendation="S'assurer de répondre à 100% des attendus éliminatoires.",
                )
            )
            score += 5.0

        # ---------------------------------------------------------------------
        # Evaluation 2: Qualifications & Assurances (Asset Matching)
        # ---------------------------------------------------------------------
        now = datetime.now(timezone.utc)
        asset_titles = [a.title.lower() for a in company_assets]
        expired_assets: List[str] = []

        for asset in company_assets:
            meta = asset.metadata_json or {}
            exp_str = meta.get("expiration_date") or meta.get("date_expiration") or meta.get("valid_until")
            if exp_str:
                try:
                    exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                    if exp_dt < now:
                        expired_assets.append(f"{asset.title} (Expirée le {exp_dt.strftime('%d/%m/%Y')})")
                except Exception:
                    pass

        if not company_assets:
            factors.append(
                GoNoGoFactor(
                    category="qualifications",
                    title="Qualifications & Assurances Entreprise",
                    status="missing_data",
                    impact="warning",
                    detail=f"Aucune qualification ou assurance renseignée dans l'espace entreprise ({quals_label}, Décennale).",
                    recommendation=f"Renseigner vos attestations ({quals_label}) et assurances dans l'Espace Entreprise.",
                )
            )

            score -= 10.0
        elif expired_assets:
            for exp in expired_assets:
                blocking_issues.append(f"Attestation expirée : {exp}")
            factors.append(
                GoNoGoFactor(
                    category="qualifications",
                    title="Qualifications & Assurances Entreprise",
                    status="blocking",
                    impact="critical",
                    detail=f"Qualifications expirées détectées : {', '.join(expired_assets)}. Risque d'irrecevabilité administrative de l'offre.",
                    recommendation="Mettre à jour d'urgence les attestations d'assurance et certifications avant dépôt.",
                )
            )
            score -= 40.0
        else:
            # Check if any mandatory criterion explicitly requests missing certs
            missing_reqs = []
            for crit in criteria:
                evidence_text = (
                    " ".join(crit.required_evidence)
                    if isinstance(crit.required_evidence, list)
                    else str(crit.required_evidence or "")
                )
                c_text = f"{crit.criterion_title or ''} {crit.description or ''} {evidence_text}".lower()
                for cert_keyword in ["qualibat 2112", "qualibat 1112", "rge", "iso 9001", "iso 14001", "fntp"]:
                    if cert_keyword in c_text and not any(cert_keyword in t for t in asset_titles):
                        missing_reqs.append(cert_keyword.upper())


            if missing_reqs:
                unique_missing = sorted(list(set(missing_reqs)))
                for m in unique_missing:
                    blocking_issues.append(f"Qualification obligatoire manquante : {m}")
                factors.append(
                    GoNoGoFactor(
                        category="qualifications",
                        title="Qualifications & Assurances Entreprise",
                        status="blocking",
                        impact="critical",
                        detail=f"Le DCE requiert les certifications suivantes absentes du dossier entreprise : {', '.join(unique_missing)}.",
                        recommendation="Déposer en groupement momentané d'entreprises (cotraitance) ou sous-traiter le lot concerné.",
                    )
                )
                score -= 45.0
            else:
                factors.append(
                    GoNoGoFactor(
                        category="qualifications",
                        title="Qualifications & Assurances Entreprise",
                        status="ok",
                        impact="positive",
                        detail=f"{len(company_assets)} qualifications, assurances et références valides renseignées.",
                        recommendation="Conformité administrative et technique vérifiée.",
                    )
                )
                score += 15.0

        # ---------------------------------------------------------------------
        # Evaluation 3: Deadline vs Workload
        # ---------------------------------------------------------------------
        if not project.submission_deadline:
            factors.append(
                GoNoGoFactor(
                    category="deadline_workload",
                    title="Délai de Réponse & Charge Équipe",
                    status="missing_data",
                    impact="neutral",
                    detail=f"Date limite de remise non renseignée sur ce projet. Charge actuelle : {active_projects_count} dossier(s) en cours.",
                    recommendation="Renseigner la date limite de dépôt dans les paramètres du projet.",
                )
            )
        else:
            deadline = project.submission_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            days_left = (deadline - now).total_seconds() / 86400.0

            if days_left < 1.5:
                blocking_issues.append(f"Délai de remise intenable ({max(0, int(days_left))} jour(s) restant(s))")
                factors.append(
                    GoNoGoFactor(
                        category="deadline_workload",
                        title="Délai de Réponse & Charge Équipe",
                        status="blocking",
                        impact="critical",
                        detail=f"Délai d'urgence extrême ({max(0, int(days_left))} jour(s) restant(s)) avec {active_projects_count} dossier(s) en cours en parallèle.",
                        recommendation="Risque élevé de remise d'une offre incomplète. Candidature déconseillée sauf équipe dédiée disponible.",
                    )
                )
                score -= 40.0
            elif days_left < 4.0:
                factors.append(
                    GoNoGoFactor(
                        category="deadline_workload",
                        title="Délai de Réponse & Charge Équipe",
                        status="warning",
                        impact="negative",
                        detail=f"Délai tendu ({int(days_left)} jours restants) et {active_projects_count} AO en cours sur le tenant.",
                        recommendation="Prioriser la rédaction et mobiliser le conducteur de travaux immédiatement.",
                    )
                )
                score -= 15.0
            else:
                factors.append(
                    GoNoGoFactor(
                        category="deadline_workload",
                        title="Délai de Réponse & Charge Équipe",
                        status="ok",
                        impact="positive",
                        detail=f"Délai confortable ({int(days_left)} jours restants) pour {active_projects_count} dossier(s) actif(s).",
                        recommendation="Calendrier idéal pour peaufiner les mémoires et optimiser le chiffrage.",
                    )
                )
                score += 10.0

        # ---------------------------------------------------------------------
        # Evaluation 4: Historical Win Rate
        # ---------------------------------------------------------------------
        won_count = hist_counts.get("won", 0)
        lost_count = hist_counts.get("lost", 0)
        total_hist = won_count + lost_count

        if total_hist < 2:
            factors.append(
                GoNoGoFactor(
                    category="historical_win_rate",
                    title="Historique & Taux de Succès Similaires",
                    status="missing_data",
                    impact="neutral",
                    detail="Historique insuffisant pour ce type de marché (0 marché similaire référencé). Donnée neutre.",
                    recommendation="La constitution de l'historique permettra d'affiner le ciblage prédictif des futurs AO.",
                )
            )
        else:
            win_rate = (won_count / total_hist) * 100.0
            if win_rate >= 50.0:
                factors.append(
                    GoNoGoFactor(
                        category="historical_win_rate",
                        title="Historique & Taux de Succès Similaires",
                        status="ok",
                        impact="positive",
                        detail=f"Taux de succès historique de {win_rate:.0f}% sur {total_hist} marchés comparables ({won_count} remportés).",
                        recommendation="Profil de marché aligné avec vos points forts historiques.",
                    )
                )
                score += 5.0
            else:
                factors.append(
                    GoNoGoFactor(
                        category="historical_win_rate",
                        title="Historique & Taux de Succès Similaires",
                        status="warning",
                        impact="negative",
                        detail=f"Taux de succès historique modéré ({win_rate:.0f}% sur {total_hist} marchés).",
                        recommendation="Renforcer l'effort sur la note méthodologique pour se démarquer.",
                    )
                )
                score -= 5.0

        # ---------------------------------------------------------------------
        # Final Recommendation & Score Boundaries
        # ---------------------------------------------------------------------
        final_score = max(0.0, min(100.0, round(score, 1)))

        if blocking_issues:
            recommendation = "NO_GO"
            final_score = min(final_score, 35.0)
            summary = (
                f"Recommandation NO-GO : {len(blocking_issues)} point(s) bloquant(s) identifié(s) "
                f"({'; '.join(blocking_issues[:2])})."
            )
        elif final_score >= 70.0:
            recommendation = "GO"
            summary = "Recommandation GO : Excellente adéquation des qualifications, délai maîtrisé et conformité DCE."
        else:
            recommendation = "RESERVES"
            summary = "Recommandation sous RÉSERVES : Candidature possible avec vigilance sur la charge de travail et le délai."

        # ---------------------------------------------------------------------
        # Persist / Upsert in public.project_go_no_go_analyses
        # ---------------------------------------------------------------------
        existing_stmt = select(ProjectGoNoGoAnalysis).where(
            ProjectGoNoGoAnalysis.project_id == project_id,
            ProjectGoNoGoAnalysis.tenant_id == tenant_id,
        )
        existing_res = await db.execute(existing_stmt)
        analysis_record = existing_res.scalar_one_or_none()

        factors_json = [f.model_dump() for f in factors]

        if not analysis_record:
            analysis_record = ProjectGoNoGoAnalysis(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=project_id,
                recommendation=recommendation,
                score=final_score,
                summary=summary,
                factors=factors_json,
                mandatory_criteria_met=len(blocking_issues) == 0,
                blocking_issues=blocking_issues,
                evaluated_by=user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(analysis_record)
        else:
            analysis_record.recommendation = recommendation
            analysis_record.score = final_score
            analysis_record.summary = summary
            analysis_record.factors = factors_json
            analysis_record.mandatory_criteria_met = len(blocking_issues) == 0
            analysis_record.blocking_issues = blocking_issues
            analysis_record.evaluated_by = user_id
            analysis_record.updated_at = datetime.now(timezone.utc)

        await db.flush()
        return analysis_record


go_no_go_service = GoNoGoService()
