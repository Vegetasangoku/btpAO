"""
Plafonds de dépense IA — une seule source de vérité pour trois niveaux de garde-fou.

Le problème auquel ce service répond : la consommation LLM est un coût variable adossé
à un revenu fixe (l'abonnement). Sans plafond, un seul client bavard suffit à effacer
la marge d'un forfait. Trois verrous indépendants, du plus large au plus fin :

  1. Fournisseur  — plafond mensuel par fournisseur d'API (Anthropic, OpenAI, …).
                    Protège la facture globale de la plateforme. Vérifié dans
                    model_routing_service.get_credentials_for_model() : au-delà, la clé
                    n'est plus servie et le repli vers un autre fournisseur s'enclenche.
  2. Forfait      — plafond par défaut appliqué à tout client d'un forfait donné
                    (subscription_plans.monthly_llm_cost_cap_usd).
  3. Client       — surcharge nominative, prioritaire sur le forfait
                    (tenant_subscriptions.custom_llm_cost_cap_usd).

Les montants sont stockés en dollars US, parce que c'est la devise de facturation de
tous les fournisseurs et celle des journaux de consommation (llm_usage_logs). L'admin
peut saisir et lire en euros : la conversion utilise un taux saisi par l'administrateur
(aucune source de change n'est interrogée), horodaté et affiché tel quel.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.entities import (
    LlmUsageLog,
    PlatformSettings,
    SubscriptionPlan,
    Tenant,
    TenantSubscription,
)

SETTINGS_KEY = "cost_limits"

# Part du prix de l'abonnement que l'opérateur accepte de dépenser en appels LLM.
# 15 % laisse 85 % pour couvrir hébergement, support et marge. C'est la valeur retenue
# par défaut pour calculer les plafonds recommandés affichés dans la console.
DEFAULT_TARGET_LLM_SHARE = 0.15

# Plancher : en dessous, un plafond bloquerait un usage normal avant même la fin du mois.
MIN_RECOMMENDED_CAP_USD = 25.0

DEFAULT_SETTINGS: Dict[str, Any] = {
    "display_currency": "EUR",
    "eur_usd_rate": 1.08,
    "eur_usd_rate_updated_at": None,
    "target_llm_share": DEFAULT_TARGET_LLM_SHARE,
    "alert_threshold_pct": 80,
    "provider_budgets": {},
}


def get_settings(platform_settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (platform_settings or {}).get(SETTINGS_KEY) or {}
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in raw.items() if v is not None})
    return merged


def usd_to_eur(amount_usd: Optional[float], rate: float) -> Optional[float]:
    if amount_usd is None:
        return None
    if not rate or rate <= 0:
        return None
    return round(float(amount_usd) / float(rate), 2)


def eur_to_usd(amount_eur: Optional[float], rate: float) -> Optional[float]:
    if amount_eur is None:
        return None
    if not rate or rate <= 0:
        return None
    return round(float(amount_eur) * float(rate), 2)


def to_usd(amount: Optional[float], currency: str, rate: float) -> Optional[float]:
    """Normalise un montant saisi par l'admin vers la devise de stockage (USD)."""
    if amount is None:
        return None
    if (currency or "USD").upper() == "EUR":
        return eur_to_usd(amount, rate)
    return round(float(amount), 2)


def recommended_cap_usd(price_monthly_cents: int, rate: float, target_share: float) -> float:
    """Plafond conseillé pour un forfait : une part fixe du prix de vente, avec plancher.

    Le prix des forfaits est libellé en euros HT ; on le convertit en dollars pour rester
    homogène avec les journaux de consommation avant d'appliquer la part cible.
    """
    price_eur = (price_monthly_cents or 0) / 100.0
    price_usd = eur_to_usd(price_eur, rate) or 0.0
    return round(max(price_usd * float(target_share), MIN_RECOMMENDED_CAP_USD), 2)


async def _spend_by_tenant(db: AsyncSession, month_start: datetime) -> Dict[uuid.UUID, float]:
    stmt = (
        select(LlmUsageLog.tenant_id, func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0))
        .where(LlmUsageLog.created_at >= month_start)
        .group_by(LlmUsageLog.tenant_id)
    )
    res = await db.execute(stmt)
    return {row[0]: float(row[1] or 0.0) for row in res.all()}


async def _spend_by_provider(db: AsyncSession, month_start: datetime) -> Dict[str, float]:
    stmt = (
        select(LlmUsageLog.provider_id, func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0))
        .where(LlmUsageLog.created_at >= month_start)
        .group_by(LlmUsageLog.provider_id)
    )
    res = await db.execute(stmt)
    return {(row[0] or "inconnu"): float(row[1] or 0.0) for row in res.all()}


def current_month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _usage_state(spend_usd: float, cap_usd: Optional[float], alert_pct: int) -> str:
    """« ok » / « alerte » / « bloque » — l'état que la console affiche sur chaque ligne."""
    if cap_usd is None or cap_usd <= 0:
        return "sans_plafond"
    ratio = spend_usd / cap_usd * 100.0
    if ratio >= 100.0:
        return "bloque"
    if ratio >= alert_pct:
        return "alerte"
    return "ok"


async def build_overview(db: AsyncSession) -> Dict[str, Any]:
    """Vue consolidée des trois niveaux de plafond, avec la consommation du mois en cours."""
    from app.services.model_routing_service import ModelRoutingService

    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps = ps_res.scalar_one_or_none()
    cfg = get_settings(ps.settings if ps else None)
    rate = float(cfg["eur_usd_rate"])
    alert_pct = int(cfg["alert_threshold_pct"])
    target_share = float(cfg["target_llm_share"])

    month_start = current_month_start()
    tenant_spend = await _spend_by_tenant(db, month_start)
    provider_spend = await _spend_by_provider(db, month_start)

    # ── Niveau 1 : fournisseurs ──────────────────────────────────────────────
    providers_raw = await ModelRoutingService.get_custom_providers(db, mask_keys=True)
    providers: List[Dict[str, Any]] = []
    for prov in providers_raw:
        cap = prov.get("monthly_budget_usd")
        cap = float(cap) if cap is not None else None
        spend = provider_spend.get(prov["id"], 0.0)
        providers.append({
            "id": prov["id"],
            "name": prov["name"],
            "litellm_id": prov.get("litellm_id"),
            "zone": prov.get("zone"),
            "is_non_eu": prov.get("is_non_eu"),
            "enabled": prov.get("enabled", True),
            "has_api_key": bool(prov.get("api_key")),
            "cap_usd": cap,
            "cap_eur": usd_to_eur(cap, rate),
            "spend_usd": round(spend, 4),
            "spend_eur": usd_to_eur(spend, rate),
            "state": _usage_state(spend, cap, alert_pct),
        })

    # ── Niveau 2 : forfaits ──────────────────────────────────────────────────
    plans_res = await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.price_monthly_cents))
    plans_rows = plans_res.scalars().all()
    plan_spend: Dict[str, float] = {}
    plan_tenant_count: Dict[str, int] = {}

    subs_res = await db.execute(select(TenantSubscription))
    subs = subs_res.scalars().all()
    subs_by_tenant = {s.tenant_id: s for s in subs}
    for sub in subs:
        plan_spend[sub.plan_id] = plan_spend.get(sub.plan_id, 0.0) + tenant_spend.get(sub.tenant_id, 0.0)
        plan_tenant_count[sub.plan_id] = plan_tenant_count.get(sub.plan_id, 0) + 1

    plans: List[Dict[str, Any]] = []
    for plan in plans_rows:
        cap = float(plan.monthly_llm_cost_cap_usd) if plan.monthly_llm_cost_cap_usd is not None else None
        suggested = recommended_cap_usd(plan.price_monthly_cents, rate, target_share)
        plans.append({
            "id": plan.id,
            "name": plan.name,
            "price_monthly_eur": (plan.price_monthly_cents or 0) / 100.0,
            "included_dossiers_month": plan.included_dossiers_month,
            "tenant_count": plan_tenant_count.get(plan.id, 0),
            "cap_usd": cap,
            "cap_eur": usd_to_eur(cap, rate),
            "recommended_cap_usd": suggested,
            "recommended_cap_eur": usd_to_eur(suggested, rate),
            "spend_usd": round(plan_spend.get(plan.id, 0.0), 4),
            "is_configured": cap is not None,
        })

    # ── Niveau 3 : clients ───────────────────────────────────────────────────
    plan_cap_by_id = {p["id"]: p["cap_usd"] for p in plans}
    tenants_res = await db.execute(select(Tenant).order_by(Tenant.name))
    tenants: List[Dict[str, Any]] = []
    for tenant in tenants_res.scalars().all():
        sub = subs_by_tenant.get(tenant.id)
        plan_id = sub.plan_id if sub else (tenant.plan or "starter")
        own_cap = (
            float(sub.custom_llm_cost_cap_usd)
            if sub and sub.custom_llm_cost_cap_usd is not None
            else None
        )
        inherited_cap = plan_cap_by_id.get(plan_id)
        effective = own_cap if own_cap is not None else inherited_cap
        spend = tenant_spend.get(tenant.id, 0.0)
        tenants.append({
            "id": str(tenant.id),
            "name": tenant.name,
            "plan_id": plan_id,
            "status": sub.status if sub else "active",
            "custom_cap_usd": own_cap,
            "custom_cap_eur": usd_to_eur(own_cap, rate),
            "inherited_cap_usd": inherited_cap,
            "effective_cap_usd": effective,
            "effective_cap_eur": usd_to_eur(effective, rate),
            "source": "client" if own_cap is not None else ("forfait" if inherited_cap is not None else "aucun"),
            "spend_usd": round(spend, 4),
            "spend_eur": usd_to_eur(spend, rate),
            "state": _usage_state(spend, effective, alert_pct),
        })

    total_spend = round(sum(tenant_spend.values()), 4)
    return {
        "settings": {
            "display_currency": cfg["display_currency"],
            "eur_usd_rate": rate,
            "eur_usd_rate_updated_at": cfg["eur_usd_rate_updated_at"],
            "target_llm_share": target_share,
            "alert_threshold_pct": alert_pct,
            "rate_source": "Taux saisi par l'administrateur — aucune source de change n'est interrogée automatiquement.",
        },
        "period_start": month_start.isoformat(),
        "totals": {
            "spend_usd": total_spend,
            "spend_eur": usd_to_eur(total_spend, rate),
            "providers_without_cap": sum(1 for p in providers if p["cap_usd"] is None),
            "plans_without_cap": sum(1 for p in plans if p["cap_usd"] is None),
            "tenants_without_cap": sum(1 for t in tenants if t["effective_cap_usd"] is None),
            "tenants_blocked": sum(1 for t in tenants if t["state"] == "bloque"),
        },
        "providers": providers,
        "plans": plans,
        "tenants": tenants,
    }


async def save_settings(db: AsyncSession, patch: Dict[str, Any]) -> Dict[str, Any]:
    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps = ps_res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    current = dict(ps.settings) if ps and ps.settings else {}
    cfg = get_settings(current)

    if patch.get("display_currency") in ("EUR", "USD"):
        cfg["display_currency"] = patch["display_currency"]
    if patch.get("eur_usd_rate") is not None:
        rate = float(patch["eur_usd_rate"])
        if rate <= 0:
            raise ValueError("Le taux de conversion doit être strictement positif.")
        cfg["eur_usd_rate"] = rate
        cfg["eur_usd_rate_updated_at"] = now.isoformat()
    if patch.get("target_llm_share") is not None:
        share = float(patch["target_llm_share"])
        if not 0 < share < 1:
            raise ValueError("La part cible doit être comprise entre 0 et 1 (ex. 0.15 pour 15 %).")
        cfg["target_llm_share"] = share
    if patch.get("alert_threshold_pct") is not None:
        pct = int(patch["alert_threshold_pct"])
        if not 1 <= pct <= 100:
            raise ValueError("Le seuil d'alerte doit être compris entre 1 et 100 %.")
        cfg["alert_threshold_pct"] = pct

    current[SETTINGS_KEY] = cfg
    if ps:
        ps.settings = current
        ps.updated_at = now
        flag_modified(ps, "settings")
    else:
        db.add(PlatformSettings(id="global", settings=current, updated_at=now))
    return cfg


async def set_provider_cap(
    db: AsyncSession, provider_id: str, amount: Optional[float], currency: str
) -> Dict[str, Any]:
    """Écrit le plafond d'un fournisseur dans platform_settings.custom_providers.

    Le montant est converti en dollars avant stockage ; la devise de saisie est conservée
    pour réafficher à l'admin exactement ce qu'il a tapé.
    """
    from app.services.model_routing_service import DEFAULT_CUSTOM_PROVIDERS

    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps = ps_res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    current = dict(ps.settings) if ps and ps.settings else {}
    cfg = get_settings(current)
    rate = float(cfg["eur_usd_rate"])

    amount_usd = to_usd(amount, currency, rate)
    if amount_usd is not None and amount_usd < 0:
        raise ValueError("Un plafond ne peut pas être négatif.")

    providers = list(current.get("custom_providers") or [])
    if not providers:
        providers = [dict(p) for p in DEFAULT_CUSTOM_PROVIDERS]

    found = False
    for prov in providers:
        if prov.get("id") == provider_id:
            prov["monthly_budget_usd"] = amount_usd
            prov["budget_currency"] = (currency or "USD").upper()
            prov["budget_input_amount"] = amount
            found = True
            break
    if not found:
        raise KeyError(f"Fournisseur inconnu : {provider_id}")

    current["custom_providers"] = providers
    if ps:
        ps.settings = current
        ps.updated_at = now
        flag_modified(ps, "settings")
    else:
        db.add(PlatformSettings(id="global", settings=current, updated_at=now))

    return {"provider_id": provider_id, "cap_usd": amount_usd, "cap_eur": usd_to_eur(amount_usd, rate)}


async def set_plan_cap(
    db: AsyncSession, plan_id: str, amount: Optional[float], currency: str
) -> Dict[str, Any]:
    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps = ps_res.scalar_one_or_none()
    cfg = get_settings(ps.settings if ps else None)
    rate = float(cfg["eur_usd_rate"])

    amount_usd = to_usd(amount, currency, rate)
    if amount_usd is not None and amount_usd < 0:
        raise ValueError("Un plafond ne peut pas être négatif.")

    plan_res = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    plan = plan_res.scalar_one_or_none()
    if plan is None:
        raise KeyError(f"Forfait inconnu : {plan_id}")
    plan.monthly_llm_cost_cap_usd = amount_usd
    return {"plan_id": plan_id, "cap_usd": amount_usd, "cap_eur": usd_to_eur(amount_usd, rate)}


async def set_tenant_cap(
    db: AsyncSession, tenant_id: uuid.UUID, amount: Optional[float], currency: str
) -> Dict[str, Any]:
    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps = ps_res.scalar_one_or_none()
    cfg = get_settings(ps.settings if ps else None)
    rate = float(cfg["eur_usd_rate"])

    amount_usd = to_usd(amount, currency, rate)
    if amount_usd is not None and amount_usd < 0:
        raise ValueError("Un plafond ne peut pas être négatif.")

    sub_res = await db.execute(select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id))
    sub = sub_res.scalar_one_or_none()
    if sub is None:
        raise KeyError(
            "Ce client n'a pas encore d'abonnement enregistré — configurez son forfait avant de fixer un plafond nominatif."
        )
    sub.custom_llm_cost_cap_usd = amount_usd
    sub.updated_at = datetime.now(timezone.utc)
    return {"tenant_id": str(tenant_id), "cap_usd": amount_usd, "cap_eur": usd_to_eur(amount_usd, rate)}


async def apply_recommended_plan_caps(db: AsyncSession) -> List[Dict[str, Any]]:
    """Applique à chaque forfait le plafond conseillé (part cible du prix de vente).
    Utilisé par l'action « Appliquer les plafonds conseillés » de la console."""
    ps_res = await db.execute(select(PlatformSettings).where(PlatformSettings.id == "global"))
    ps = ps_res.scalar_one_or_none()
    cfg = get_settings(ps.settings if ps else None)
    rate = float(cfg["eur_usd_rate"])
    target_share = float(cfg["target_llm_share"])

    plans_res = await db.execute(select(SubscriptionPlan))
    applied = []
    for plan in plans_res.scalars().all():
        suggested = recommended_cap_usd(plan.price_monthly_cents, rate, target_share)
        plan.monthly_llm_cost_cap_usd = suggested
        applied.append({"plan_id": plan.id, "cap_usd": suggested})
    return applied
