"""
RGPD Right to Erasure Service.
Handles account soft-deletion grace period and hard-purge routine with audit log anonymization.
"""
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import User, AuditLog


async def execute_expired_accounts_purge_db(db: AsyncSession) -> Dict[str, Any]:
    """
    Executes the irreversible hard-purge of accounts whose 30-day grace period has passed (scheduled_purge_at <= NOW()).
    - Removes all personal records (users).
    - Anonymizes any remaining audit log entries (user_id = NULL, details.anonymized = true).
    """
    now = datetime.now(timezone.utc)
    stmt = select(User).where(
        User.status == "pending_deletion",
        User.scheduled_purge_at.isnot(None),
        User.scheduled_purge_at <= now,
    )
    result = await db.execute(stmt)
    expired_users = result.scalars().all()
    purged_count = 0

    for u in expired_users:
        u_id = u.id

        # 1. Anonymize Audit Logs linked to this user
        await db.execute(
            text("UPDATE public.audit_logs SET user_id = NULL, details = jsonb_set(COALESCE(details, '{}'::jsonb), '{anonymized}', 'true'::jsonb) WHERE user_id = :uid;"),
            {"uid": u_id}
        )

        # 2. Hard delete user record
        await db.delete(u)
        purged_count += 1

    await db.commit()

    return {
        "success": True,
        "purged_accounts_count": purged_count,
        "executed_at": now.isoformat(),
    }
