"""
BT01 — Chiffreur & Ajustement Inflation.
Avant ce fichier (01/09), cette fonctionnalité n'avait aucune implémentation serveur
(confirmé par grep sur tout le dépôt) -- seul un intitulé d'onglet UI et une note honnête
"pas encore développée côté serveur" existaient. Implémentation volontairement simple et
réelle plutôt qu'un moteur de métré exhaustif : lignes de prix (désignation/unité/quantité/
PU HT), agrégées en un total HT réel, puis ajustées par les taux économiques RÉELS du tenant
(TenantSettings -- déjà stockés en base mais jamais réellement lus/écrits jusqu'ici, voir
economic_settings.py) : inflation, marge cible, aléas chantier.

Complété par un vrai point d'appel LLM pour la tâche "analyse_prix" (routage IA par tâche),
qui produit une lecture qualitative du chiffrage (cohérence des prix unitaires, postes
manquants au regard des critères DCE) -- en complément du calcul déterministe ci-dessus,
jamais à sa place : les totaux HT/TTC restent un calcul arithmétique vérifiable, pas une
sortie de modèle de langage.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import litellm
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import DCECriterionEntity, Project, ProjectPricingLine, TenantSettings
from app.services.billing_service import billing_service
from app.services.model_routing_service import model_routing_service

router = APIRouter(tags=["Chiffrage (BT01)"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PricingLineIn(BaseModel):
    lot: Optional[str] = None
    designation: str
    unite: str = "u"
    quantite: float
    prix_unitaire_ht: float


class PricingLineOut(PricingLineIn):
    id: str
    project_id: str
    total_ht: float
    created_at: datetime
    updated_at: datetime


class EconomicSettingsIn(BaseModel):
    taux_inflation_pct: Optional[float] = None
    marge_cible_pct: Optional[float] = None
    risk_contingency_pct: Optional[float] = None
    taux_horaires: Optional[Dict[str, float]] = None


async def _get_or_create_settings(db: AsyncSession, tenant_uuid: uuid.UUID) -> TenantSettings:
    res = await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_uuid))
    settings = res.scalar_one_or_none()
    if not settings:
        settings = TenantSettings(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            taux_inflation_pct=3.5,
            marge_cible_pct=12.0,
            taux_horaires={},
            economic_settings={},
        )
        db.add(settings)
        await db.flush()
    return settings


# ---------------------------------------------------------------------------
# Réglages économiques du tenant (03/09 : corrige dashboard/settings/page.tsx dont le
# bouton "Enregistrer" ne faisait qu'un setTimeout(400ms) puis affichait un faux message
# de succès -- aucun appel réseau, aucune donnée jamais persistée nulle part).
# ---------------------------------------------------------------------------
@router.get("/company/economic-settings")
async def get_economic_settings(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_uuid = uuid.UUID(current_user.tenant_id)
    settings = await _get_or_create_settings(db, tenant_uuid)
    await db.commit()
    return {
        "taux_inflation_pct": float(settings.taux_inflation_pct) if settings.taux_inflation_pct is not None else 3.5,
        "marge_cible_pct": float(settings.marge_cible_pct) if settings.marge_cible_pct is not None else 12.0,
        "risk_contingency_pct": float((settings.economic_settings or {}).get("risk_contingency_pct", 4.5)),
        "taux_horaires": settings.taux_horaires or {},
    }


@router.put("/company/economic-settings")
async def update_economic_settings(
    payload: EconomicSettingsIn,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_uuid = uuid.UUID(current_user.tenant_id)
    settings = await _get_or_create_settings(db, tenant_uuid)

    if payload.taux_inflation_pct is not None:
        settings.taux_inflation_pct = payload.taux_inflation_pct
    if payload.marge_cible_pct is not None:
        settings.marge_cible_pct = payload.marge_cible_pct
    if payload.taux_horaires is not None:
        settings.taux_horaires = payload.taux_horaires
    if payload.risk_contingency_pct is not None:
        econ = dict(settings.economic_settings or {})
        econ["risk_contingency_pct"] = payload.risk_contingency_pct
        settings.economic_settings = econ

    settings.mis_a_jour_le = datetime.utcnow()
    await db.commit()
    return {"status": "saved"}


# ---------------------------------------------------------------------------
# Lignes de chiffrage (métré simplifié : désignation / unité / quantité / PU HT)
# ---------------------------------------------------------------------------
def _serialize_line(line: ProjectPricingLine) -> Dict[str, Any]:
    qty = float(line.quantite)
    pu = float(line.prix_unitaire_ht)
    return {
        "id": str(line.id),
        "project_id": str(line.project_id),
        "lot": line.lot,
        "designation": line.designation,
        "unite": line.unite,
        "quantite": qty,
        "prix_unitaire_ht": pu,
        "total_ht": round(qty * pu, 2),
        "created_at": line.created_at,
        "updated_at": line.updated_at,
    }


@router.get("/projects/{project_id}/pricing-lines")
async def list_pricing_lines(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    proj_uuid = uuid.UUID(project_id)
    tenant_uuid = uuid.UUID(current_user.tenant_id)
    res = await db.execute(
        select(ProjectPricingLine)
        .where(ProjectPricingLine.project_id == proj_uuid, ProjectPricingLine.tenant_id == tenant_uuid)
        .order_by(ProjectPricingLine.created_at.asc())
    )
    return [_serialize_line(l) for l in res.scalars().all()]


@router.post("/projects/{project_id}/pricing-lines")
async def create_pricing_line(
    project_id: str,
    payload: PricingLineIn,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    proj_uuid = uuid.UUID(project_id)
    tenant_uuid = uuid.UUID(current_user.tenant_id)

    proj = await db.execute(select(Project.id).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")

    line = ProjectPricingLine(
        id=uuid.uuid4(),
        tenant_id=tenant_uuid,
        project_id=proj_uuid,
        lot=payload.lot,
        designation=payload.designation,
        unite=payload.unite,
        quantite=payload.quantite,
        prix_unitaire_ht=payload.prix_unitaire_ht,
    )
    db.add(line)
    await db.commit()
    await db.refresh(line)
    return _serialize_line(line)


@router.put("/pricing-lines/{line_id}")
async def update_pricing_line(
    line_id: str,
    payload: PricingLineIn,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_uuid = uuid.UUID(current_user.tenant_id)
    res = await db.execute(
        select(ProjectPricingLine).where(
            ProjectPricingLine.id == uuid.UUID(line_id), ProjectPricingLine.tenant_id == tenant_uuid,
        )
    )
    line = res.scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ligne de chiffrage introuvable")

    line.lot = payload.lot
    line.designation = payload.designation
    line.unite = payload.unite
    line.quantite = payload.quantite
    line.prix_unitaire_ht = payload.prix_unitaire_ht
    line.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(line)
    return _serialize_line(line)


@router.delete("/pricing-lines/{line_id}")
async def delete_pricing_line(
    line_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_uuid = uuid.UUID(current_user.tenant_id)
    res = await db.execute(
        select(ProjectPricingLine).where(
            ProjectPricingLine.id == uuid.UUID(line_id), ProjectPricingLine.tenant_id == tenant_uuid,
        )
    )
    line = res.scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ligne de chiffrage introuvable")
    await db.delete(line)
    await db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Synthèse chiffrée : total HT réel + ajustements inflation/marge/aléas RÉELS du tenant
# (calcul arithmétique vérifiable, pas une estimation de modèle de langage).
# ---------------------------------------------------------------------------
@router.get("/projects/{project_id}/pricing-summary")
async def get_pricing_summary(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    proj_uuid = uuid.UUID(project_id)
    tenant_uuid = uuid.UUID(current_user.tenant_id)

    res = await db.execute(
        select(ProjectPricingLine).where(
            ProjectPricingLine.project_id == proj_uuid, ProjectPricingLine.tenant_id == tenant_uuid,
        )
    )
    lines = res.scalars().all()
    total_ht = sum(float(l.quantite) * float(l.prix_unitaire_ht) for l in lines)

    settings = await _get_or_create_settings(db, tenant_uuid)
    await db.commit()
    inflation_pct = float(settings.taux_inflation_pct) if settings.taux_inflation_pct is not None else 3.5
    marge_pct = float(settings.marge_cible_pct) if settings.marge_cible_pct is not None else 12.0
    risk_pct = float((settings.economic_settings or {}).get("risk_contingency_pct", 4.5))

    total_apres_inflation = total_ht * (1 + inflation_pct / 100.0)
    total_apres_alea = total_apres_inflation * (1 + risk_pct / 100.0)
    total_avec_marge = total_apres_alea * (1 + marge_pct / 100.0)
    tva_pct = 20.0
    total_ttc = total_avec_marge * (1 + tva_pct / 100.0)

    return {
        "lines_count": len(lines),
        "total_ht_brut": round(total_ht, 2),
        "taux_inflation_pct": inflation_pct,
        "risk_contingency_pct": risk_pct,
        "marge_cible_pct": marge_pct,
        "total_apres_inflation_ht": round(total_apres_inflation, 2),
        "total_apres_alea_ht": round(total_apres_alea, 2),
        "total_avec_marge_ht": round(total_avec_marge, 2),
        "tva_pct": tva_pct,
        "total_ttc": round(total_ttc, 2),
        "formule": (
            "total_ht_brut × (1 + inflation%) × (1 + aléas%) × (1 + marge%) × (1 + TVA%) "
            "— chaque taux vient de vos Réglages économiques (Espace Entreprise)."
        ),
    }


# ---------------------------------------------------------------------------
# Analyse qualitative LLM réelle du chiffrage (task_type="analyse_prix" -- même clé de
# routage exposée sur l'onglet admin "Routage IA par Tâche & Client", auparavant sans
# aucun point d'appel réel dans le pipeline).
# ---------------------------------------------------------------------------
@router.post("/projects/{project_id}/pricing-analysis")
async def analyze_pricing(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    proj_uuid = uuid.UUID(project_id)
    tenant_uuid = uuid.UUID(current_user.tenant_id)

    proj_res = await db.execute(select(Project).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid))
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")

    # 02/09 : plafond de cout LLM mensuel reel (protection de marge, parametrable par
    # forfait/tenant) -- verifie avant tout appel LLM facturable.
    await billing_service.check_and_enforce_cost_cap(current_user.tenant_id, db=db)

    lines_res = await db.execute(
        select(ProjectPricingLine).where(
            ProjectPricingLine.project_id == proj_uuid, ProjectPricingLine.tenant_id == tenant_uuid,
        )
    )
    lines = lines_res.scalars().all()
    if not lines:
        return {
            "status": "no_data",
            "message": "Aucune ligne de chiffrage saisie -- ajoutez des lignes avant de lancer l'analyse.",
        }

    crit_res = await db.execute(
        select(DCECriterionEntity.criterion_title).where(
            DCECriterionEntity.project_id == proj_uuid, DCECriterionEntity.tenant_id == tenant_uuid,
        )
    )
    criteria_titles = [c for (c,) in crit_res.all()]

    lines_text = "\n".join(
        f"- {l.designation} ({l.lot or 'sans lot'}) : {float(l.quantite)} {l.unite} x {float(l.prix_unitaire_ht)}€ HT/u = {round(float(l.quantite) * float(l.prix_unitaire_ht), 2)}€ HT"
        for l in lines
    )

    resolved = await model_routing_service.resolve_model_for_tenant(
        db=db, tenant_id=tenant_uuid, task_type="analyse_prix",
    )
    model_string = resolved["model_string"]
    credentials = await model_routing_service.get_credentials_for_model(db=db, model_string=model_string)
    api_key = credentials.get("api_key")

    if not api_key:
        return {
            "status": "no_api_key",
            "message": "Aucune clé LLM configurée pour la tâche 'analyse_prix' -- configurez-en une dans l'administration.",
        }

    try:
        kwargs: Dict[str, Any] = {
            "model": model_string,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu es un chiffreur BTP expérimenté. Tu analyses un chiffrage (bordereau de prix) "
                        "de façon critique et concrète : prix unitaires anormalement bas ou hauts pour le marché "
                        "français du BTP, postes probablement manquants au regard des critères du DCE fournis, "
                        "cohérence globale. Réponds en JSON strict."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""LIGNES DE CHIFFRAGE ({project.title}) :
{lines_text}

CRITÈRES DU DCE POUR CE PROJET :
{chr(10).join('- ' + c for c in criteria_titles) or 'Aucun critère DCE extrait pour ce projet.'}

Réponds en JSON strict : {{"risk_level": "low"|"medium"|"high", "summary": "synthèse en 2-3 phrases",
"flagged_lines": ["désignations de lignes au prix suspect, si any"],
"missing_items_suggestions": ["postes probablement manquants, si any"]}}""",
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 1200,
            "api_key": api_key,
        }
        if credentials.get("api_base"):
            kwargs["api_base"] = credentials["api_base"]

        response = litellm.completion(**kwargs)

        # 02/09 : journal de consommation LLM (tokens + cout estime) -- absent jusqu'ici sur
        # ce point d'appel, rendant tout plafond de cout par tenant invisible pour l'analyse
        # de chiffrage. Ne doit jamais faire echouer la reponse : erreurs absorbees en interne.
        _usage = getattr(response, "usage", None)
        await billing_service.log_llm_usage(
            db=db,
            tenant_id=tenant_uuid,
            project_id=proj_uuid,
            provider_id=credentials.get("provider_id"),
            model_string=model_string,
            prompt_tokens=getattr(_usage, "prompt_tokens", None) if _usage else None,
            completion_tokens=getattr(_usage, "completion_tokens", None) if _usage else None,
            total_tokens=getattr(_usage, "total_tokens", None) if _usage else None,
        )

        import json as _json
        parsed = _json.loads(response.choices[0].message.content)
        parsed["status"] = "ok"
        parsed["model_used"] = model_string
        return parsed
    except Exception as e:
        return {"status": "error", "message": f"Analyse indisponible pour le moment : {e}"}
