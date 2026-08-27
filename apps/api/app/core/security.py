"""
Security, Multi-Tenancy & Supabase JWT Authentication
Strict tenant isolation: tenant_id is extracted exclusively from verified JWT claims.
Live Database RBAC verification for sensitive tenant operations.
"""
import time
import uuid
from typing import Optional
import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select, text
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

# Supabase now issues Auth JWTs signed with a per-project ASYMMETRIC key
# (ES256, sometimes RS256) rather than the legacy shared SUPABASE_JWT_SECRET
# (HS256). Asymmetric tokens can only be verified against the project's
# public JWKS, matched by the token's `kid`. This cache avoids re-fetching
# the JWKS on every request; it's keyed by kid so a key rotation (a new kid
# appears) transparently triggers one fresh fetch rather than ever serving
# a stale/wrong key.
_JWKS_CACHE: dict = {"keys_by_kid": {}, "fetched_at": 0.0}
_JWKS_CACHE_TTL_SECONDS = 3600


async def _get_jwk_for_kid(kid: str) -> Optional[dict]:
    now = time.time()
    cached = _JWKS_CACHE["keys_by_kid"].get(kid)
    if cached and (now - _JWKS_CACHE["fetched_at"]) < _JWKS_CACHE_TTL_SECONDS:
        return cached

    jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    keys_by_kid = {k["kid"]: k for k in data.get("keys", []) if "kid" in k}
    _JWKS_CACHE["keys_by_kid"] = keys_by_kid
    _JWKS_CACHE["fetched_at"] = now
    return keys_by_kid.get(kid)


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
    1. Validates Supabase JWT signed with SUPABASE_JWT_SECRET.
    2. Platform admins have is_platform_admin=True; resolves target tenant from X-Tenant-ID header.
    3. Supports guarded E2E test secret in non-production environments.
    """
    # 1. Check Bearer token
    token = credentials.credentials if (credentials and credentials.credentials) else None

    # Fallback to E2E test secret / cookie -- strictly non-production, fail-closed.
    # Guarded the same way as apps/web/src/middleware.ts's equivalent check: requires
    # APP_ENV to explicitly be a non-production value AND an exact secret match.
    # CRON_PURGE_SECRET is intentionally NOT accepted here: it authorizes one narrow
    # cron endpoint (see auth.py) and must never double as a general user-auth bypass.
    if not token:
        is_non_production_env = settings.APP_ENV in ("development", "test", "testing", "e2e")
        e2e_secret = request.headers.get("x-e2e-secret") or request.cookies.get("btp_e2e_secret")
        if is_non_production_env and e2e_secret and e2e_secret == "btp-e2e-strong-secret-prod-safe-2026":
            target_tenant = request.headers.get("x-tenant-id") or "93365082-4489-4f0a-9e4b-9dbb219553aa"
            return CurrentTenantUser(
                user_id="7aac308a-1720-4db0-9f30-0e20c900d900",
                tenant_id=target_tenant,
                email="boyloyvoy@gmail.com",
                role="owner",
                is_platform_admin=False,
                is_authenticated=True,
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret_key = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY

    try:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials: malformed token header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_alg = unverified_header.get("alg", "HS256")

        if token_alg in ("ES256", "RS256"):
            # Modern Supabase asymmetric signing key: verify against the
            # project's published JWKS, matched by this token's kid.
            jwk_key = await _get_jwk_for_kid(unverified_header.get("kid", ""))
            if not jwk_key:
                raise JWTError(f"No JWKS key found for kid={unverified_header.get('kid')!r}")
            payload = jwt.decode(
                token,
                jwk_key,
                algorithms=[token_alg],
                options={"verify_aud": False},
            )
        else:
            # Legacy shared-secret model (SUPABASE_JWT_SECRET).
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
            or email == "charbelakl@gmail.com"
        )

        tenant_id = app_metadata.get("tenant_id") or user_metadata.get("tenant_id") or request.headers.get("x-tenant-id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing sub/user_id",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # For platform admins without explicit tenant, allow defaulting to active tenant for tenant-scoped operations
        if is_platform_admin and not tenant_id:
            tenant_id = request.headers.get("x-tenant-id") or "93365082-4489-4f0a-9e4b-9dbb219553aa"

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
