"""
MEA Regional Tender Dossiers API Endpoints (Saudi Arabia, Qatar, UAE, Lebanon).
Supports bilingual English/Arabic generation with native OpenXML RTL rendering.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import Project, Tenant
from app.services.mea_dossier_service import mea_dossier_service

router = APIRouter(prefix="/dossiers", tags=["MEA Administrative Dossiers"])


@router.get("/{project_id}/mea")
async def export_mea_tender_dossier(
    project_id: str,
    country_code: Optional[str] = Query(None, description="Country code (SA, QA, AE, LB)"),
    language: str = Query("en", description="Output language (en, ar, fr)"),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports official Word (.docx) tender dossier for MEA countries.
    Automatically applies RTL OpenXML alignment when language='ar'.
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant introuvable")

    proj_res = await db.execute(select(Project).where(Project.id == p_uuid, Project.tenant_id == t_uuid))
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable ou accès refusé")

    target_country = (country_code or tenant.country_code or "SA").upper()

    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "CR-001",
        "cr_number": tenant.siret or "CR-001",
        "country_code": target_country,
    }
    project_dict = {
        "title": project.title,
        "client_name": project.client_name,
        "reference_code": project.reference_code,
        "lot_number": project.lot_number or "Main Contract Works",
    }

    if target_country == "SA":
        docx_bytes = mea_dossier_service.generate_saudi_tender_dossier(tenant_dict, project_dict, language=language)
        filename = f"Saudi_GTPL_FormOfTender_{project.reference_code or 'SA'}_{language}.docx"
    elif target_country == "QA":
        docx_bytes = mea_dossier_service.generate_qatar_tender_dossier(tenant_dict, project_dict, language=language)
        filename = f"Qatar_Ashghal_FormOfTender_{project.reference_code or 'QA'}_{language}.docx"
    elif target_country == "AE":
        docx_bytes = mea_dossier_service.generate_uae_tender_dossier(tenant_dict, project_dict, language=language)
        filename = f"UAE_Federal_FormOfTender_{project.reference_code or 'UAE'}_{language}.docx"
    elif target_country == "LB":
        docx_bytes = mea_dossier_service.generate_lebanon_tender_dossier(tenant_dict, project_dict, language=language)
        filename = f"Lebanon_PPA_Dossier_{project.reference_code or 'LB'}_{language}.docx"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Pays MEA '{target_country}' non supporté (disponibles: SA, QA, AE, LB)")

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
