"""
Auth & Tenancy Management Endpoints.
Includes password reset flow with branded transactional btpAO emails.
"""
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from app.core.config import settings
from app.core.db import get_db, get_public_auth_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import AuditLog, PasswordResetToken, Tenant, User

from app.models.schemas import TenantBranding, TenantOut, UserProfileOut
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Auth & Tenancy"])


class ForgotPasswordPayload(BaseModel):
    email: str


class VerifyResetTokenPayload(BaseModel):
    token: str


class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str


@router.get("/me", response_model=UserProfileOut)
async def get_my_profile(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db)
):
    # Lookup real user record from database
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    db_user = result.scalars().first()

    full_name = db_user.full_name if (db_user and db_user.full_name) else (current_user.email.split("@")[0] if current_user.email else "Utilisateur")
    avatar_url = db_user.avatar_url if db_user else None
    role = db_user.role if db_user else current_user.role

    return UserProfileOut(
        id=str(current_user.user_id),
        tenant_id=str(current_user.tenant_id) if current_user.tenant_id else "",
        email=current_user.email,
        full_name=full_name,
        role=role,
        avatar_url=avatar_url
    )


@router.get("/tenant", response_model=TenantOut)
async def get_tenant_info(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune entreprise cliente rattachée à cet utilisateur."
        )

    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalars().first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation tenant introuvable."
        )

    branding = tenant.branding_config or {}
    branding_obj = TenantBranding(
        primary_color=branding.get("primary_color", "#0284c7"),
        secondary_color=branding.get("secondary_color", "#0f172a"),
        font_family=branding.get("font_family", "Inter"),
        company_name=branding.get("company_name", tenant.name),
        header_text=branding.get("header_text", f"{tenant.name} — Mémoire Technique Justificatif"),
        footer_text=branding.get("footer_text", "Document confidentiel — Réponse Appel d'Offres BTP")
    )

    return TenantOut(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan or "pro",
        branding_config=branding_obj,
        created_at=tenant.created_at or datetime.utcnow()
    )



@router.post("/forgot-password")
async def request_password_reset(
    payload: ForgotPasswordPayload,
    db: AsyncSession = Depends(get_public_auth_db)
):
    """
    Initiates password reset flow.
    Sends a high-end, branded btpAO HTML email with a secure, 1-hour expiration single-use token.
    Always returns 200 OK to prevent user enumeration.
    """
    clean_email = payload.email.strip().lower()
    
    # 1. Lookup user in database
    result = await db.execute(
        select(User).where(User.email.ilike(clean_email))
    )
    user = result.scalars().first()

    reset_url_dev: Optional[str] = None

    if user:
        # 2. Generate secure token
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        # 3. Store in password_reset_tokens
        reset_entry = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=user.id,
            email=user.email,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=now,
        )
        db.add(reset_entry)
        await db.commit()

        # 4. Construct URL and send branded email
        frontend_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
        reset_url = f"{frontend_url}/reset-password?token={raw_token}"
        reset_url_dev = reset_url

        send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
            user_name=user.full_name or user.email.split("@")[0]
        )

    response_data = {
        "success": True,
        "message": "Si cette adresse est associée à un compte, un e-mail de réinitialisation vient d'être envoyé.",
    }
    
    # In development/test mode, expose dev reset URL for easy testing
    if settings.DEBUG or os.getenv("APP_ENV") == "development":
        response_data["reset_url_dev"] = reset_url_dev

    return response_data


@router.post("/verify-reset-token")
async def verify_reset_token(
    payload: VerifyResetTokenPayload,
    db: AsyncSession = Depends(get_public_auth_db)
):
    """
    Validates if a password reset token is active, unused, and not expired.
    """
    token_hash = hashlib.sha256(payload.token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now
        )
    )
    record = result.scalars().first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce lien de réinitialisation est invalide ou a expiré. Veuillez refaire une demande."
        )

    return {
        "valid": True,
        "email": record.email
    }


@router.post("/reset-password")

async def reset_password(
    payload: ResetPasswordPayload,
    db: AsyncSession = Depends(get_public_auth_db)
):

    """
    Applies new password using valid reset token.
    Updates hashed password in PostgreSQL auth schema and marks token as used.
    """
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le mot de passe doit contenir au moins 8 caractères."
        )

    token_hash = hashlib.sha256(payload.token.strip().encode("utf-8")).hexdigest()

    # 1. Hash new password with bcrypt
    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(payload.new_password.encode("utf-8"), salt).decode("utf-8")

    # 2. Call SECURITY DEFINER function to atomically validate token and update auth password
    result = await db.execute(
        text("SELECT public.apply_password_reset(:token_hash, :hashed_pw);"),
        {"token_hash": token_hash, "hashed_pw": hashed_pw}
    )
    success = result.scalar()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le lien de réinitialisation est invalide ou a déjà été utilisé."
        )

    await db.commit()

    return {
        "success": True,
        "message": "Votre mot de passe a été modifié avec succès. Vous pouvez maintenant vous connecter avec vos nouveaux identifiants."
    }


# ── RGPD / Droit à l'effacement & Suppression de Compte ────────────────────────

class DeleteAccountResponse(BaseModel):
    success: bool
    status: str
    deletion_requested_at: str
    scheduled_purge_at: str
    message: str
    legal_notice: str


@router.post("/account/delete-request", response_model=DeleteAccountResponse)
async def request_account_deletion(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    RGPD Article 17 - Droit à l'effacement.
    Initiates a 30-day soft deletion period allowing grace cancellation before irreversible hard purge.
    """
    try:
        user_uuid = uuid.UUID(current_user.user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID utilisateur invalide")

    res = await db.execute(select(User).where(User.id == user_uuid))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    now = datetime.now(timezone.utc)
    purge_date = now + timedelta(days=30)

    user.status = "pending_deletion"
    user.deletion_requested_at = now
    user.scheduled_purge_at = purge_date

    # Record Audit Trail
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(current_user.tenant_id) if current_user.tenant_id else None,
        user_id=user_uuid,
        action="gdpr_account_deletion_requested",
        entity_type="user",
        entity_id=user_uuid,
        details={
            "email": user.email,
            "deletion_requested_at": now.isoformat(),
            "scheduled_purge_at": purge_date.isoformat(),
            "retention_days": 30,
        },
        created_at=now,
    )
    db.add(audit_entry)
    await db.flush()

    return DeleteAccountResponse(
        success=True,
        status="pending_deletion",
        deletion_requested_at=now.isoformat(),
        scheduled_purge_at=purge_date.isoformat(),
        message="Votre demande de suppression a été enregistrée. Votre compte sera désactivé pendant 30 jours, puis l'ensemble de vos données personnelles sera définitivement effacé.",
        legal_notice="Conformément au RGPD et aux obligations légales BTP relatives aux marchés publics (délai de recours et garantie décennale), les pièces contractuelles et journaux d'audit anonymisés sont conservés selon les durées légales applicables.",
    )


@router.post("/account/cancel-deletion")
async def cancel_account_deletion(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancels an active account deletion request within the 30-day grace period.
    """
    try:
        user_uuid = uuid.UUID(current_user.user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID utilisateur invalide")

    res = await db.execute(select(User).where(User.id == user_uuid))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    user.status = "active"
    user.deletion_requested_at = None
    user.scheduled_purge_at = None

    audit_entry = AuditLog(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(current_user.tenant_id) if current_user.tenant_id else None,
        user_id=user_uuid,
        action="gdpr_account_deletion_cancelled",
        entity_type="user",
        entity_id=user_uuid,
        details={"email": user.email, "cancelled_at": datetime.now(timezone.utc).isoformat()},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit_entry)
    await db.flush()

    return {
        "success": True,
        "status": "active",
        "message": "La demande de suppression de compte a été annulée avec succès. Votre compte reste actif."
    }


@router.post("/account/execute-purge")
async def execute_expired_accounts_purge(
    db: AsyncSession = Depends(get_public_auth_db),
):
    """
    Automated / Cron execution of expired account purges (scheduled_purge_at <= NOW()).
    Permanently erases user identity and personal records, anonymizing audit logs.
    """
    now = datetime.now(timezone.utc)
    expired_users_res = await db.execute(
        select(User).where(
            User.status == "pending_deletion",
            User.scheduled_purge_at.isnot(None),
            User.scheduled_purge_at <= now,
        )
    )
    expired_users = expired_users_res.scalars().all()
    purged_count = 0

    for u in expired_users:
        u_id = u.id
        u_email = u.email

        # 1. Anonymize Audit Logs for this user (remove personal identity link)
        await db.execute(
            text("UPDATE public.audit_logs SET user_id = NULL, details = jsonb_set(details, '{anonymized}', 'true'::jsonb) WHERE user_id = :uid;"),
            {"uid": u_id}
        )

        # 2. Hard delete user personal record
        await db.delete(u)
        purged_count += 1

    await db.commit()

    return {
        "success": True,
        "purged_accounts_count": purged_count,
        "executed_at": now.isoformat(),
    }


