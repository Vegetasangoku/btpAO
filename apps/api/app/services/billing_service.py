"""
Hybrid Billing & Quota Enforcement Service.
Handles Self-Service Stripe subscriptions, Enterprise manual quotas, and consumption tracking.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import SubscriptionPlan, TenantSubscription, TenantUsageCounter


class BillingService:
    @staticmethod
    def get_current_period_bounds() -> tuple[datetime, datetime]:
        """Returns the start and end of the current calendar month in UTC."""
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            end = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        return start, end

    async def get_or_create_usage(self, tenant_id: uuid.UUID, db: AsyncSession) -> TenantUsageCounter:
        """Fetches or creates the usage counter for the current month."""
        start, end = self.get_current_period_bounds()

        stmt = (
            select(TenantUsageCounter)
            .where(
                TenantUsageCounter.tenant_id == tenant_id,
                TenantUsageCounter.period_start >= start,
                TenantUsageCounter.period_start < end,
            )
            .order_by(TenantUsageCounter.period_start.desc())
        )
        res = await db.execute(stmt)
        usage = res.scalars().first()

        if not usage:
            usage = TenantUsageCounter(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                period_start=start,
                period_end=end,
                dossiers_generated=0,
                sections_generated=0,
                exports_count=0,
                web_searches_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(usage)
            await db.flush()

        return usage


    async def get_tenant_subscription(self, tenant_id: uuid.UUID, db: AsyncSession) -> Optional[TenantSubscription]:
        """Fetches active subscription record for tenant."""
        stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def check_and_enforce_quota(
        self,
        tenant_id_str: str,
        action: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Enforces tenant subscription status and monthly dossier quotas before generation/export.
        Raises 402 Payment Required if subscription is suspended or quota exceeded without overage.
        """
        try:
            t_uuid = uuid.UUID(tenant_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

        sub = await self.get_tenant_subscription(t_uuid, db)
        if not sub:
            # Default to active starter trial if no record exists yet
            return {"status": "active", "quota": 3, "used": 0, "allow_overage": True}

        if sub.status != "active":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Abonnement inactif ou suspendu (statut: {sub.status}). Veuillez régulariser votre compte pour générer des dossiers.",
            )

        # Determine effective quota
        if sub.custom_quota_dossiers is not None:
            effective_quota = sub.custom_quota_dossiers
        else:
            plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id)
            plan_res = await db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()
            effective_quota = plan.included_dossiers_month if plan else 3

        usage = await self.get_or_create_usage(t_uuid, db)

        # Check quota limit
        if usage.dossiers_generated >= effective_quota and not sub.allow_overage:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Quota mensuel de dossiers atteint ({usage.dossiers_generated}/{effective_quota}). "
                    f"Le dépassement n'est pas activé sur ce compte. Veuillez contacter votre administrateur ou passer au forfait supérieur."
                ),
            )

        return {
            "status": sub.status,
            "billing_mode": sub.billing_mode,
            "quota": effective_quota,
            "used": usage.dossiers_generated,
            "sections_generated": usage.sections_generated,
            "exports_count": usage.exports_count,
            "allow_overage": sub.allow_overage,
        }

    async def increment_usage(
        self,
        tenant_id_str: str,
        action: str,
        db: AsyncSession,
    ):
        """Increments usage counter for current month."""
        try:
            t_uuid = uuid.UUID(tenant_id_str)
        except ValueError:
            return

        usage = await self.get_or_create_usage(t_uuid, db)
        if action == "dossier":
            usage.dossiers_generated += 1
        elif action == "section":
            usage.sections_generated += 1
        elif action == "export":
            usage.exports_count += 1
        usage.updated_at = datetime.utcnow()
        await db.flush()

    async def check_and_enforce_knowledge_quota(
        self,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Enforces tenant document quota in knowledge base:
        - starter: 20 documents max
        - pro: 100 documents max
        - enterprise: unlimited
        Raises 403 FORBIDDEN if quota is reached.
        """
        from app.models.entities import CompanyAsset, Tenant
        from sqlalchemy import func

        # 1. Determine tenant plan
        sub = await self.get_tenant_subscription(tenant_id, db)
        plan_id = sub.plan_id if sub else "starter"

        if not sub:
            t_stmt = select(Tenant).where(Tenant.id == tenant_id)
            t_res = await db.execute(t_stmt)
            t = t_res.scalar_one_or_none()
            if t and t.plan:
                plan_id = t.plan

        plan_id = plan_id.lower()
        quotas = {
            "starter": 20,
            "pro": 100,
            "enterprise": None,  # Unlimited
        }
        max_allowed = quotas.get(plan_id, 20)

        # 2. Count existing assets for this tenant
        count_stmt = select(func.count(CompanyAsset.id)).where(CompanyAsset.tenant_id == tenant_id)
        count_res = await db.execute(count_stmt)
        current_count = count_res.scalar() or 0

        if max_allowed is not None and current_count >= max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Quota de documents atteint pour votre plan {plan_id.upper()} ({current_count}/{max_allowed} max). "
                    f"Mettez à niveau votre forfait vers le plan supérieur pour indexer plus de documents dans votre base de connaissances."
                ),
            )

        return {
            "plan": plan_id,
            "current_count": current_count,
            "max_allowed": max_allowed,
        }


billing_service = BillingService()

