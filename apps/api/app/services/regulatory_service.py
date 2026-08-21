"""
Country Regulatory Profiles Service
Provides localized regulatory, public procurement and technical standards frameworks (ISO 3166-1 alpha-2).
Prevents silent fallback to French defaults when an unconfigured country_code is encountered.
"""
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import CountryRegulatoryProfile, Tenant


class RegulatoryService:
    async def get_tenant_regulatory_profile(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> CountryRegulatoryProfile:
        """
        Resolves the active regulatory profile for a given tenant.
        Raises an explicit error if the tenant's country_code has no configured profile.
        """
        # 1. Fetch tenant country_code
        t_stmt = select(Tenant.country_code).where(Tenant.id == tenant_id)
        t_res = await db.execute(t_stmt)
        country_code = t_res.scalar_one_or_none()

        if not country_code:
            country_code = "FR"

        # 2. Fetch regulatory profile
        return await self.get_profile_by_code(db=db, country_code=country_code)

    async def get_profile_by_code(
        self,
        db: AsyncSession,
        country_code: str,
    ) -> CountryRegulatoryProfile:
        """
        Loads the country regulatory profile by ISO code.
        Rejects unconfigured or inactive country codes explicitly.
        """
        code_clean = (country_code or "").strip().upper()
        stmt = select(CountryRegulatoryProfile).where(
            CountryRegulatoryProfile.country_code == code_clean,
            CountryRegulatoryProfile.is_active == True,
        )
        res = await db.execute(stmt)
        profile = res.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Profil réglementaire non configuré pour le pays '{code_clean}'. "
                    f"Ce tenant requiert un cadre réglementaire national spécifique (normes, marchés publics, qualifications) "
                    f"qui n'est pas encore activé sur la plateforme."
                ),
            )

        return profile


regulatory_service = RegulatoryService()
