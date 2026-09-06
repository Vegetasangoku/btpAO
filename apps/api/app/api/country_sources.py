"""
Country Official Sources & Regulatory Watch API Endpoints.
Provides certified public procurement, building codes and legal portals per country.
"""
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import CountryOfficialSource
from app.services.regulatory_watch_service import regulatory_watch_service

router = APIRouter(prefix="/country-sources", tags=["Country Official Sources & Regulatory Watch"])


@router.get("")
async def list_country_official_sources(
    country_code: Optional[str] = Query(None, description="Filter by 2-letter country code (FR, SA, QA, AE, LB)"),
    portal_type: Optional[str] = Query(None, description="Filter by type (procurement_portal, building_code, qualification_board)"),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all verified official public sources and regulatory portals.
    """
    stmt = select(CountryOfficialSource).where(CountryOfficialSource.status == "active")
    if country_code:
        stmt = stmt.where(CountryOfficialSource.country_code == country_code.upper())
    if portal_type:
        stmt = stmt.where(CountryOfficialSource.portal_type == portal_type)

    stmt = stmt.order_by(CountryOfficialSource.country_code, CountryOfficialSource.portal_name)
    res = await db.execute(stmt)
    sources = res.scalars().all()

    return [
        {
            "id": str(s.id),
            "country_code": s.country_code,
            "portal_name": s.portal_name,
            "portal_url": s.portal_url,
            "portal_type": s.portal_type,
            "reference_law": s.reference_law,
            "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
            "last_known_hash": s.last_known_hash,
            "last_summary": s.last_summary,
            "status": s.status,
        }
        for s in sources
    ]


@router.post("/check-updates")
async def check_official_sources_updates(
    country_code: Optional[str] = Query(None, description="Optional country code filter"),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers SHA-256 integrity checks and regulatory change detection across official sources.
    """
    stmt = select(CountryOfficialSource).where(CountryOfficialSource.status == "active")
    if country_code:
        stmt = stmt.where(CountryOfficialSource.country_code == country_code.upper())

    res = await db.execute(stmt)
    sources = res.scalars().all()

    # La veille NE s'execute PLUS dans la requete HTTP (04/09). Deux raisons :
    #   1. `country_official_sources` reserve l'ecriture a is_superadmin() par RLS : lancee
    #      depuis la session d'un utilisateur normal, la veille lisait les sources mais son
    #      UPDATE ne matchait aucune ligne (StaleDataError) -- aucun resultat n'a jamais pu
    #      etre enregistre.
    #   2. 55 sources a 12 s de timeout, c'est jusqu'a 11 minutes : intenable en HTTP.
    # Le travail part donc dans la tache planifiee tasks.regulatory_watch_daily_task, qui
    # tourne sur une session non soumise au role tenant. Ici on se contente de la declencher
    # et de rendre l'etat connu des sources.
    from app.workers.tasks import regulatory_watch_daily_task

    task = regulatory_watch_daily_task.delay()

    return {
        "status": "scheduled",
        "task_id": str(task.id),
        "sources_count": len(sources),
        "message": (
            "Veille lancee en arriere-plan sur les sources officielles. "
            "Les resultats apparaitront au fur et a mesure sur chaque source."
        ),
        "sources": [
            {
                "country_code": s.country_code,
                "portal_name": s.portal_name,
                "portal_url": s.portal_url,
                "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
                "has_verified_content": s.last_known_hash is not None,
            }
            for s in sources
        ],
    }


@router.get("/{country_code}/brief")
async def get_country_regulatory_brief_endpoint(
    country_code: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the certified regulatory brief for a country, backed by verified official sources.
    """
    return await regulatory_watch_service.get_country_regulatory_brief(db, country_code=country_code)
