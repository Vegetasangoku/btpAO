"""
Plafond de cout OCR (Azure Document Intelligence) -- miroir exact du mecanisme deja en
place pour le cout LLM (app/services/billing_service.py : get_effective_cost_cap_usd,
check_and_enforce_cost_cap, log_llm_usage). Avant ce service (03/09), aucun cout OCR
n'etait journalise ni plafonne nulle part : app/services/ocr_service.py appelait Azure
Document Intelligence directement des qu'une cle etait configuree, sans aucune limite
independante du plafond LLM. Combine au triage local->Azure de ocr_service.py (qui
reduit deja fortement le nombre de pages envoyees a Azure), ce plafond est le filet de
securite qui garantit qu'un client ne peut jamais faire deraper la facture Azure au-dela
de ce que son forfait tolere, quel que soit le volume de documents scannes qu'il depose.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import OcrUsageLog, SubscriptionPlan, TenantSubscription

# Tarif Azure Document Intelligence "Layout" (prebuilt-layout, celui utilise par
# ocr_service.py) au 03/09 : ~10 USD / 1000 pages = 0.01 USD/page. Valeur de repli
# utilisee pour estimer le cout reel ; ne remplace pas une verification periodique
# du tarif officiel Azure si le modele ou la region change.
AZURE_LAYOUT_PRICE_USD_PER_PAGE = 0.01


def estimate_ocr_cost_usd(pages_azure: int) -> float:
    return round(max(pages_azure, 0) * AZURE_LAYOUT_PRICE_USD_PER_PAGE, 6)


async def get_tenant_subscription(tenant_id: uuid.UUID, db: AsyncSession) -> Optional[TenantSubscription]:
    res = await db.execute(select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id))
    return res.scalar_one_or_none()


async def get_effective_ocr_cap_usd(tenant_id: uuid.UUID, db: AsyncSession) -> Optional[float]:
    """Plafond mensuel de cout OCR effectif : surcharge tenant si definie, sinon valeur
    du forfait, sinon None (aucun plafond -- jamais bloquant tant qu'un admin n'a pas
    choisi une valeur explicitement, meme convention que get_effective_cost_cap_usd)."""
    sub = await get_tenant_subscription(tenant_id, db)
    if sub and sub.custom_ocr_cost_cap_usd is not None:
        return float(sub.custom_ocr_cost_cap_usd)

    plan_id = sub.plan_id if sub else "starter"
    plan_res = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    plan = plan_res.scalar_one_or_none()
    if plan and plan.monthly_ocr_cost_cap_usd is not None:
        return float(plan.monthly_ocr_cost_cap_usd)
    return None


async def get_tenant_current_month_ocr_spend_usd(tenant_id: uuid.UUID, db: AsyncSession) -> float:
    try:
        from app.services.billing_service import billing_service

        month_start, _ = billing_service.get_current_period_bounds()
        stmt = select(func.coalesce(func.sum(OcrUsageLog.estimated_cost_usd), 0)).where(
            OcrUsageLog.tenant_id == tenant_id,
            OcrUsageLog.created_at >= month_start,
        )
        res = await db.execute(stmt)
        return float(res.scalar() or 0.0)
    except Exception as e:
        print(f"[OcrCostService] get_tenant_current_month_ocr_spend_usd notice: {e} -- 0.0 par defaut.")
        return 0.0


async def is_ocr_cap_exceeded(tenant_id: uuid.UUID, db: AsyncSession) -> tuple[bool, Optional[float], float]:
    """Ne leve jamais d'exception -- destine aux points d'appel qui doivent degrader
    silencieusement (ex. conserver le texte pdfplumber local et ne pas escalader vers
    Azure) plutot que de faire echouer tout l'upload."""
    cap = await get_effective_ocr_cap_usd(tenant_id, db)
    if cap is None or cap <= 0:
        return False, cap, 0.0
    spend = await get_tenant_current_month_ocr_spend_usd(tenant_id, db)
    return spend >= cap, cap, spend


async def log_ocr_usage(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: Optional[uuid.UUID],
    source: str,
    ocr_stats: dict,
) -> float:
    """Journalise un cycle OCR reel (pages locales + pages escaladees vers Azure) et
    retourne le cout USD estime. N'echoue jamais l'appelant (meme garantie que
    billing_service.log_llm_usage)."""
    pages_local = int(ocr_stats.get("pages_local", 0) or 0)
    pages_azure = int(ocr_stats.get("pages_azure", 0) or 0)
    estimated_cost = estimate_ocr_cost_usd(pages_azure)
    try:
        db.add(OcrUsageLog(
            tenant_id=tenant_id,
            document_id=document_id,
            source=source,
            provider="hybrid_local_azure" if pages_azure else "local_pdf_parser",
            pages_local=pages_local,
            pages_azure=pages_azure,
            estimated_cost_usd=estimated_cost,
            created_at=datetime.now(timezone.utc),
        ))
    except Exception as e:
        print(f"[OcrCostService] log_ocr_usage notice: {e} -- traitement du document non affecte.")
    return estimated_cost


async def check_and_enforce_ocr_cap(tenant_id_str: str, db: AsyncSession) -> dict:
    """Bloque (402) toute nouvelle ingestion de document si le plafond mensuel de cout
    OCR reel configure pour ce tenant est atteint -- miroir exact de
    billing_service.check_and_enforce_cost_cap, sur l'axe OCR plutot que LLM."""
    try:
        t_uuid = uuid.UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    exceeded, cap, spend = await is_ocr_cap_exceeded(t_uuid, db)
    if exceeded:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Plafond mensuel de cout OCR atteint ({spend:.2f} $ US / {cap:.2f} $ US configures). "
                f"Ce plafond protege la marge de votre forfait face aux documents scannes volumineux -- "
                f"contactez votre administrateur pour l'ajuster, ou reessayez le mois prochain."
            ),
        )
    return {"ocr_cost_cap_usd": cap, "current_ocr_spend_usd": spend, "cap_enforced": cap is not None}
