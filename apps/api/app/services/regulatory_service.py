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

    async def get_project_regulatory_profile(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> CountryRegulatoryProfile:
        """
        Resout le cadre reglementaire d'un DOSSIER (04/09).

        Le pays qui compte est celui du MARCHE, pas celui de l'entreprise : une entreprise
        francaise qui repond a un marche au Qatar doit se voir appliquer les normes, le
        regime de commande publique et la whitelist de sources qataris. On lit donc en
        priorite Project.country_code (renseigne par la detection sur les pieces du DCE, ou
        corrige a la main), et on ne retombe sur le pays du tenant que s'il est absent.
        """
        from app.models.entities import Project

        p_res = await db.execute(
            select(Project.country_code).where(
                Project.id == project_id, Project.tenant_id == tenant_id
            )
        )
        project_country = p_res.scalar_one_or_none()
        if project_country:
            return await self.get_profile_by_code(db=db, country_code=project_country)
        return await self.get_tenant_regulatory_profile(db=db, tenant_id=tenant_id)

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
