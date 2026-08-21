"""
Security, Multi-Tenancy & Supabase JWT Authentication
Strict tenant isolation: tenant_id is extracted exclusively from verified JWT claims.
Live Database RBAC verification for sensitive tenant operations.
"""
import uuid
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select, text
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


class CurrentTenantUser(BaseModel):
    user_id: str
    tenant_id: Optional[str] = None
    email: str
    role: str = "member"
    is_platform_admin: bool = False
    is_authenticated: bool = True


async def get_current_tenant_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> CurrentTenantUser:
    """
    Validates Supabase JWT and extracts user_id, tenant_id, and platform_admin role.
    1. Returns 401 Unauthorized if no Bearer token is provided or if token is invalid.
    2. Platform admins have is_platform_admin=True and do not require a tenant_id.
    3. Regular tenant users must have tenant_id derived strictly from verified JWT claims.
    """
    # 1. Reject immediately if no Bearer token is provided
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    secret_key = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )

        user_id = payload.get("sub") or payload.get("user_id")
        email = payload.get("email", "")

        app_metadata = payload.get("app_metadata", {})
        user_metadata = payload.get("user_metadata", {})
        
        raw_role = app_metadata.get("role") or user_metadata.get("role") or payload.get("role") or "member"
        is_platform_admin = (
            raw_role == "platform_admin"
            or app_metadata.get("is_platform_admin") is True
            or user_metadata.get("is_platform_admin") is True
            or payload.get("is_platform_admin") is True
        )
        
        tenant_id = app_metadata.get("tenant_id") or user_metadata.get("tenant_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing sub/user_id",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Platform admins don't belong to any client tenant
        if not is_platform_admin and not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing tenant_id in JWT claims",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return CurrentTenantUser(
            user_id=str(user_id),
            tenant_id=str(tenant_id) if tenant_id else None,
            email=email,
            role="platform_admin" if is_platform_admin else raw_role,
            is_platform_admin=is_platform_admin,
            is_authenticated=True,
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_platform_admin(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
) -> CurrentTenantUser:
    """
    FastAPI security dependency: verifies the user has the 'platform_admin' role.
    Rejects any regular tenant user or unauthorized entity with 403 Forbidden.
    """
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator privileges required (role 'platform_admin')",
        )
    return current_user


async def require_tenant_owner(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
) -> CurrentTenantUser:
    """
    FastAPI security dependency: live-verifies against Postgres database that the user
    actively holds the 'owner' role within their tenant, or has global platform_admin privileges.
    Any demoted or removed user loses privileges on their very next request even if JWT is still valid.
    """
    if current_user.is_platform_admin:
        return current_user

    from app.core.db import AsyncSessionLocal
    from app.models.entities import User

    try:
        u_uuid = uuid.UUID(current_user.user_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user or tenant identifier in token",
        )

    # Perform fresh check directly against PostgreSQL under application role and tenant context
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET ROLE btp_app_user;"))
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
            {"tenant_id": str(t_uuid)},
        )
        stmt = select(User.role).where(User.id == u_uuid, User.tenant_id == t_uuid)
        result = await session.execute(stmt)
        active_role = result.scalar_one_or_none()

    if not active_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account does not exist or has been removed from this tenant",
        )

    if active_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant owner privileges required (live role in database is '{active_role}')",
        )

    current_user.role = active_role
    return current_user
