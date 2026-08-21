"""
Team & User Management Endpoints with Multi-User Support and RBAC (owner, member, read_only).
Strictly isolated by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db, get_system_db_unrestricted_INTERNAL_ONLY
from app.core.security import (
    CurrentTenantUser,
    get_current_tenant_user,
    require_tenant_owner,
)

from app.models.entities import TenantInvitation, User
from app.models.schemas import (
    TeamInvitationAccept,
    TeamInvitationCreate,
    TeamInvitationOut,
    TeamMemberOut,
    TeamMemberUpdateRole,
)

router = APIRouter(prefix="/team", tags=["Team & User Management"])


@router.get("/members", response_model=List[TeamMemberOut])
async def list_team_members(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all members within the authenticated user's tenant.
    Accessible to all members of the tenant under Postgres RLS.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(User).where(User.tenant_id == t_uuid).order_by(User.created_at.asc())
    result = await db.execute(stmt)
    members = result.scalars().all()

    return [
        TeamMemberOut(
            id=str(m.id),
            tenant_id=str(m.tenant_id),
            email=m.email,
            full_name=m.full_name,
            role=m.role,
            avatar_url=m.avatar_url,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.post("/invitations", response_model=TeamInvitationOut)
async def invite_team_member(
    payload: TeamInvitationCreate,
    current_user: CurrentTenantUser = Depends(require_tenant_owner),
    db: AsyncSession = Depends(get_db),
):
    """
    Invites a user to join the tenant with a specific role.
    Protected strictly by require_tenant_owner.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(current_user.user_id) if current_user.user_id else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant or user UUID")

    email_clean = payload.email.strip().lower()
    role_clean = payload.role.strip().lower() if payload.role else "member"

    if role_clean not in ("owner", "member", "read_only", "conducteur_travaux", "chiffreur"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role '{role_clean}'")

    # 1. Check if user is already a member
    exist_stmt = select(User).where(User.tenant_id == t_uuid, func.lower(User.email) == email_clean)
    exist_res = await db.execute(exist_stmt)
    if exist_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member of this tenant")

    # 2. Revoke any previous pending invitations for this email
    prev_stmt = select(TenantInvitation).where(
        TenantInvitation.tenant_id == t_uuid,
        func.lower(TenantInvitation.email) == email_clean,
        TenantInvitation.status == "pending",
    )
    prev_res = await db.execute(prev_stmt)
    for prev in prev_res.scalars().all():
        prev.status = "revoked"

    # 3. Create new secure invitation
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=7)

    invitation = TenantInvitation(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        email=email_clean,
        role=role_clean,
        invitation_token=token,
        status="pending",
        invited_by=u_uuid,
        expires_at=expires,
        created_at=now,
        updated_at=now,
    )
    db.add(invitation)
    await db.flush()

    return TeamInvitationOut(
        id=str(invitation.id),
        tenant_id=str(invitation.tenant_id),
        email=invitation.email,
        role=invitation.role,
        invitation_token=invitation.invitation_token,
        status=invitation.status,
        invited_by=str(invitation.invited_by) if invitation.invited_by else None,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get("/invitations", response_model=List[TeamInvitationOut])
async def list_pending_invitations(
    current_user: CurrentTenantUser = Depends(require_tenant_owner),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all pending invitations for this tenant.
    Protected strictly by require_tenant_owner.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = (
        select(TenantInvitation)
        .where(TenantInvitation.tenant_id == t_uuid, TenantInvitation.status == "pending")
        .order_by(TenantInvitation.created_at.desc())
    )
    res = await db.execute(stmt)
    invites = res.scalars().all()

    return [
        TeamInvitationOut(
            id=str(i.id),
            tenant_id=str(i.tenant_id),
            email=i.email,
            role=i.role,
            invitation_token=i.invitation_token,
            status=i.status,
            invited_by=str(i.invited_by) if i.invited_by else None,
            expires_at=i.expires_at,
            created_at=i.created_at,
        )
        for i in invites
    ]


@router.post("/invitations/accept", response_model=TeamMemberOut)
async def accept_invitation(
    payload: TeamInvitationAccept,
    db: AsyncSession = Depends(get_system_db_unrestricted_INTERNAL_ONLY),
):
    """
    Accepts an invitation token and binds the new user account strictly to the invitation's tenant_id.
    Never creates a new tenant based on email domain.
    """
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing invitation token")

    now = datetime.now(timezone.utc)

    # Fetch invitation
    stmt = select(TenantInvitation).where(
        TenantInvitation.invitation_token == token,
        TenantInvitation.status == "pending",
    )
    res = await db.execute(stmt)
    invitation = res.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or non-existent invitation token")

    exp = invitation.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    if exp < now:
        invitation.status = "expired"
        await db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation token has expired")

    # Explicitly set app.current_tenant_id to the verified invitation tenant
    tenant_str = str(invitation.tenant_id)
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
        {"tenant_id": tenant_str},
    )
    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true);"),
        {"tenant_id": tenant_str},
    )

    # Check if user already exists in that tenant
    u_stmt = select(User).where(
        User.tenant_id == invitation.tenant_id,
        func.lower(User.email) == func.lower(invitation.email),
    )
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            full_name=payload.full_name or invitation.email.split("@")[0].capitalize(),
            role=invitation.role,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
    else:
        user.role = invitation.role
        if payload.full_name:
            user.full_name = payload.full_name
        user.updated_at = now

    invitation.status = "accepted"
    invitation.updated_at = now
    await db.flush()

    return TeamMemberOut(
        id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )



@router.put("/members/{user_id}/role", response_model=TeamMemberOut)
async def update_member_role(
    user_id: str,
    payload: TeamMemberUpdateRole,
    current_user: CurrentTenantUser = Depends(require_tenant_owner),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates the role of a team member within the tenant.
    Protected strictly by require_tenant_owner.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user or tenant UUID")

    role_clean = payload.role.strip().lower()
    if role_clean not in ("owner", "member", "read_only", "conducteur_travaux", "chiffreur"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role '{role_clean}'")

    stmt = select(User).where(User.id == u_uuid, User.tenant_id == t_uuid)
    res = await db.execute(stmt)
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found or access denied")

    member.role = role_clean
    member.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return TeamMemberOut(
        id=str(member.id),
        tenant_id=str(member.tenant_id),
        email=member.email,
        full_name=member.full_name,
        role=member.role,
        avatar_url=member.avatar_url,
        created_at=member.created_at,
    )


@router.delete("/members/{user_id}")
async def remove_team_member(
    user_id: str,
    current_user: CurrentTenantUser = Depends(require_tenant_owner),
    db: AsyncSession = Depends(get_db),
):
    """
    Removes a member from the tenant.
    Protected strictly by require_tenant_owner. Cannot delete the only owner.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
        u_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user or tenant UUID")

    stmt = select(User).where(User.id == u_uuid, User.tenant_id == t_uuid)
    res = await db.execute(stmt)
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found or access denied")

    if member.role == "owner":
        # Check if there are other owners
        owner_count_stmt = select(func.count(User.id)).where(User.tenant_id == t_uuid, User.role == "owner")
        owner_count_res = await db.execute(owner_count_stmt)
        if (owner_count_res.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last owner of the tenant",
            )

    await db.delete(member)
    await db.flush()

    return {"status": "success", "message": f"Member {member.email} removed from tenant"}
