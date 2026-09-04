"""
Tenant Billing & Subscription Endpoints (Self-Service Stripe + Usage Tracking).
Strictly scoped to authenticated tenant via SQLAlchemy 2 Async + PostgreSQL RLS.
Stripe Webhooks are strictly authenticated via HMAC-SHA256 signature verification.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db, get_system_db_unrestricted_INTERNAL_ONLY
from app.core.security import CurrentTenantUser, get_current_tenant_user, require_tenant_owner
from app.models.entities import SubscriptionPlan, TenantSubscription, TenantUsageCounter
from app.services.billing_service import billing_service

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


class CheckoutSessionRequest(BaseModel):
    plan_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.get("/plans")
async def list_available_plans(db: AsyncSession = Depends(get_db)):
    """Returns active subscription plans available for self-service or enterprise."""
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.price_monthly_cents.asc())
    res = await db.execute(stmt)
    plans = res.scalars().all()

    if not plans:
        return [
            {
                "id": "starter",
                "name": "Forfait Artisan & PME",
                "price_monthly_cents": 19900,
                "included_dossiers_month": 3,
                "extra_dossier_price_cents": 9900,
                "features": ["Générateur IA & RAG", "Extraction DCE", "Export Word .docx"],
            },
            {
                "id": "pro",
                "name": "Forfait Entreprise Générale",
                "price_monthly_cents": 49900,
                "included_dossiers_month": 10,
                "extra_dossier_price_cents": 7900,
                "features": ["Tout Starter", "Organigrammes & Gantt", "Base de connaissances illimitée", "Support dédié"],
            },
            {
                "id": "enterprise",
                "name": "Grand Compte / Sur Devis",
                "price_monthly_cents": 0,
                "included_dossiers_month": 50,
                "extra_dossier_price_cents": 0,
                "features": ["Volume sur-mesure", "Facturation personnalisée", "Modèles IA dédiés", "SLA garanti"],
            },
        ]

    return [
        {
            "id": p.id,
            "name": p.name,
            "price_monthly_cents": p.price_monthly_cents,
            "included_dossiers_month": p.included_dossiers_month,
            "extra_dossier_price_cents": p.extra_dossier_price_cents,
            "features": p.features or [],
        }
        for p in plans
    ]


@router.get("/subscription")
async def get_tenant_subscription_status(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns current tenant's subscription plan, active status, consumption, and remaining quota.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    sub_stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == t_uuid)
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalar_one_or_none()

    usage = await billing_service.get_or_create_usage(t_uuid, db)

    if not sub:
        return {
            "has_subscription": False,
            "plan_id": "starter",
            "plan_name": "Essai Gratuit / Starter",
            "status": "active",
            "billing_mode": "free_trial",
            "quota_dossiers": 3,
            "dossiers_used": usage.dossiers_generated,
            "sections_used": usage.sections_generated,
            "exports_used": usage.exports_count,
            "allow_overage": True,
            "current_period_end": usage.period_end.isoformat(),
        }

    plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id)
    plan_res = await db.execute(plan_stmt)
    plan = plan_res.scalar_one_or_none()

    quota = sub.custom_quota_dossiers if sub.custom_quota_dossiers is not None else (plan.included_dossiers_month if plan else 3)
    plan_name = plan.name if plan else sub.plan_id.capitalize()

    return {
        "has_subscription": True,
        "subscription_id": str(sub.id),
        "plan_id": sub.plan_id,
        "plan_name": plan_name,
        "status": sub.status,
        "billing_mode": sub.billing_mode,
        "quota_dossiers": quota,
        "dossiers_used": usage.dossiers_generated,
        "sections_used": usage.sections_generated,
        "exports_used": usage.exports_count,
        "allow_overage": sub.allow_overage,
        "current_period_start": sub.current_period_start.isoformat(),
        "current_period_end": sub.current_period_end.isoformat(),
    }


@router.post("/create-checkout-session")
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    current_user: CurrentTenantUser = Depends(require_tenant_owner),
    db: AsyncSession = Depends(get_db),
):
    """
    Initializes a REAL Stripe Checkout Session for self-service subscription upgrade.
    Protected strictly by require_tenant_owner.

    01/09 : remplace l'implementation precedente qui fabriquait une fausse URL
    (/billing/checkout-success?session_id=cs_simulated_...) et un faux session_id
    SANS jamais appeler l'API Stripe -- l'utilisateur aurait ete rediriges vers une
    page inexistante et aucun paiement n'aurait jamais ete initie. Construit
    desormais un vrai stripe.checkout.Session via price_data dynamique (pas besoin
    de pre-creer des Price IDs dans le dashboard Stripe : le prix vient directement
    de subscription_plans.price_monthly_cents). Echoue honnetement (501) si
    STRIPE_SECRET_KEY n'est pas configuree, plutot que de simuler un succes.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Le paiement en ligne (Stripe) n'est pas configure sur ce serveur. "
                "STRIPE_SECRET_KEY est absente de la configuration. Contactez votre "
                "administrateur pour activer les paiements en self-service."
            ),
        )

    if not payload.success_url or not payload.cancel_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="success_url et cancel_url (URLs absolues) sont requis pour creer une session de paiement.",
        )

    plan_stmt = select(SubscriptionPlan).where(
        SubscriptionPlan.id == payload.plan_id,
        SubscriptionPlan.is_active == True,
    )
    plan_res = await db.execute(plan_stmt)
    plan = plan_res.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Palier '{payload.plan_id}' introuvable ou inactif.")

    if not plan.price_monthly_cents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce palier est a tarif negocie (sur devis) et ne peut pas etre souscrit en self-service. Contactez notre equipe commerciale.",
        )

    metadata = {"tenant_id": str(t_uuid), "plan_id": payload.plan_id}

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        session = stripe.checkout.Session.create(
            mode="subscription",
            client_reference_id=str(t_uuid),
            customer_email=current_user.email,
            metadata=metadata,
            subscription_data={"metadata": metadata},
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": f"btpAO - {plan.name}"},
                    "unit_amount": plan.price_monthly_cents,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Echec de la creation de la session Stripe : {e}",
        )

    return {
        "success": True,
        "checkout_url": session.url,
        "session_id": session.id,
        "plan_id": payload.plan_id,
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_system_db_unrestricted_INTERNAL_ONLY),
):
    """
    Stripe Webhook handler: strictly verifies cryptographic signature before processing.
    Rejects any unverified or forged request with 400 Bad Request before database access.
    """
    payload_bytes = await request.body()
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe webhook secret is not configured on the server."
        )

    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header."
        )

    try:
        import stripe
        event = stripe.Webhook.construct_event(
            payload=payload_bytes,
            sig_header=stripe_signature,
            secret=webhook_secret,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cryptographic Stripe signature verification failed: {e}",
        )

    event_type = event.get("type", "") if isinstance(event, dict) else getattr(event, "type", "")
    data_obj = (
        event.get("data", {}).get("object", {})
        if isinstance(event, dict)
        else getattr(getattr(event, "data", None), "object", {})
    )
    if hasattr(data_obj, "to_dict"):
        data_obj = data_obj.to_dict()

    if event_type in ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"):
        client_ref = data_obj.get("client_reference_id")
        meta = data_obj.get("metadata") or {}
        tenant_id_str = client_ref or meta.get("tenant_id")

        if tenant_id_str:
            try:
                t_uuid = uuid.UUID(tenant_id_str)
                plan_id = meta.get("plan_id", "pro")

                # Strictly set PostgreSQL session tenant_id for RLS enforcement
                from sqlalchemy import text
                await db.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
                    {"tenant_id": str(t_uuid)},
                )
                await db.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true);"),
                    {"tenant_id": str(t_uuid)},
                )

                sub_stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == t_uuid)
                sub_res = await db.execute(sub_stmt)
                sub = sub_res.scalar_one_or_none()


                now = datetime.utcnow()
                period_end = now + timedelta(days=30)

                if sub:
                    sub.plan_id = plan_id
                    sub.status = "active"
                    sub.billing_mode = "stripe"
                    sub.stripe_subscription_id = data_obj.get("subscription") or data_obj.get("id")
                    sub.stripe_customer_id = data_obj.get("customer") or sub.stripe_customer_id
                    sub.current_period_start = now
                    sub.current_period_end = period_end
                    sub.updated_at = now
                else:
                    new_sub = TenantSubscription(
                        id=uuid.uuid4(),
                        tenant_id=t_uuid,
                        plan_id=plan_id,
                        status="active",
                        billing_mode="stripe",
                        stripe_subscription_id=data_obj.get("subscription") or data_obj.get("id"),
                        stripe_customer_id=data_obj.get("customer"),
                        allow_overage=True,
                        current_period_start=now,
                        current_period_end=period_end,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(new_sub)
                await db.flush()
            except ValueError:
                pass

    return {"received": True, "event": event_type}
