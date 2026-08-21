"""
SQLAlchemy 2 Async Engine & Session Management with Multi-Tenant RLS Injection.
Enforces SET LOCAL app.current_tenant_id at transaction start.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from fastapi import Depends
from app.core.config import settings
from app.core.security import CurrentTenantUser, get_current_tenant_user


class Base(DeclarativeBase):
    pass


def get_async_database_url() -> str:
    """Formats DATABASE_URL for asyncpg driver."""
    raw_url = settings.DATABASE_URL or "postgresql://localhost:5432/postgres"
    if "<PASSWORD>" in raw_url:
        # Fallback to local default if remote placeholder password is not yet configured
        raw_url = "postgresql://localhost:5432/postgres"
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw_url


from sqlalchemy.pool import NullPool

ASYNC_DATABASE_URL = get_async_database_url()

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async session.
    1. Switches session to non-superuser application role 'btp_app_user' (strictly enforces Postgres RLS).
    2. Sets 'app.current_tenant_id' to the verified JWT tenant_id.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Switch to application role to enforce RLS (neither superuser nor bypassrls)
            await session.execute(text("SET ROLE btp_app_user;"))

            # 2. Inject verified JWT tenant_id into transaction context for Postgres RLS
            effective_tenant = current_user.tenant_id or ""
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true);"),
                {"tenant_id": effective_tenant},
            )
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true);"),
                {"tenant_id": effective_tenant},
            )

            try:
                yield session
            finally:
                try:
                    await session.execute(text("RESET ROLE;"))
                except Exception:
                    pass


async def get_public_auth_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for unauthenticated auth operations (forgot password, reset password token verification).
    Switches to application role 'btp_app_user' without tenant scoping.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET ROLE btp_app_user;"))
            try:
                yield session
            finally:
                try:
                    await session.execute(text("RESET ROLE;"))
                except Exception:
                    pass


async def get_system_db_unrestricted_INTERNAL_ONLY() -> AsyncGenerator[AsyncSession, None]:
    """
    CRITICAL SECURITY NOTICE (INTERNAL ONLY):
    Yields an unrestricted async session for system background workers (Celery) or
    cryptographically verified external webhooks (e.g. Stripe Webhook with verified HMAC signature).

    NEVER connect this dependency to any public HTTP route without prior cryptographic validation.
    Switches to application role 'btp_app_user'.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET ROLE btp_app_user;"))
            try:
                yield session
            finally:
                try:
                    await session.execute(text("RESET ROLE;"))
                except Exception:
                    pass



@asynccontextmanager
async def get_worker_db_session(tenant_id: str):
    """
    Context manager for background Celery workers.
    Switches session to non-superuser application role 'btp_app_user' and
    strictly injects 'app.current_tenant_id' to enforce Postgres RLS per tenant.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET ROLE btp_app_user;"))
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false);"),
            {"tenant_id": tenant_id},
        )
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, false);"),
            {"tenant_id": tenant_id},
        )
        try:
            yield session
        finally:
            try:
                await session.execute(text("SELECT set_config('app.current_tenant_id', '', false);"))
                await session.execute(text("SELECT set_config('app.tenant_id', '', false);"))
                await session.execute(text("RESET ROLE;"))
            except Exception:
                pass







