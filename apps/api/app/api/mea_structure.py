"""
MEA Regional Tender Structure, CSI MasterFormat, BoQ and Compliance API Endpoints.
"""
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import Tenant
from app.services.mea_structure_service import mea_structure_service

router = APIRouter(prefix="/mea-structure", tags=["MEA Technical Structure & Compliance"])


class ComplianceCheckRequest(BaseModel):
    country_code: str
    project_data: Optional[Dict[str, Any]] = None
    contractor_data: Optional[Dict[str, Any]] = None


@router.get("/csi-masterformat")
async def get_csi_divisions(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
):
    """
    Returns standard CSI MasterFormat (Divisions 01 to 48) breakdown and submittal requirements.
    """
    divisions = mea_structure_service.get_csi_masterformat_structure()
    return {
        "standard": "CSI MasterFormat (2020/2026 Edition)",
        "total_divisions": len(divisions),
        "divisions": divisions,
    }


@router.get("/boq-template")
async def get_boq_template(
    method: str = Query("POMI", description="Measurement standard (POMI, CESMM4, NRM2)"),
    currency: str = Query("SAR", description="Currency code (SAR, QAR, AED, USD)"),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
):
    """
    Returns standard Bill of Quantities (BoQ) structure for MEA tenders.
    """
    return mea_structure_service.generate_boq_template(method=method, currency=currency)


@router.get("/pqd-dossier")
async def download_pqd_dossier(
    country_code: str = Query("SA", description="Country code (SA, QA, AE, LB)"),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports official Contractor Prequalification Dossier (PQD) in Word (.docx) format.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant introuvable")

    from app.models.entities import CompanyAsset
    assets_res = await db.execute(
        select(CompanyAsset).where(
            CompanyAsset.tenant_id == t_uuid,
            CompanyAsset.validated_by_user == True,
        )
    )
    assets = assets_res.scalars().all()
    assets_list = [
        {"category": a.category, "title": a.title, "description": a.description, "metadata_json": a.metadata_json}
        for a in assets
    ]

    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "[À COMPLÉTER : SIRET / CR Number]",
        "country_code": country_code,
        "_company_assets": assets_list,
    }

    docx_bytes = mea_structure_service.generate_pqd_word_dossier(tenant_dict, country_code=country_code)
    filename = f"Contractor_PQD_Prequalification_{country_code.upper()}.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/validate-compliance")
async def validate_regional_compliance_endpoint(
    req: ComplianceCheckRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates contractor data and project scope against national building codes & statutory mandates.
    """
    t_uuid = uuid.UUID(current_user.tenant_id)
    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant = tenant_res.scalar_one_or_none()

    from app.models.entities import CompanyAsset
    assets_res = await db.execute(
        select(CompanyAsset).where(
            CompanyAsset.tenant_id == t_uuid,
            CompanyAsset.validated_by_user == True,
        )
    )
    assets = assets_res.scalars().all()
    assets_list = [
        {"category": a.category, "title": a.title, "description": a.description, "metadata_json": a.metadata_json}
        for a in assets
    ]

    contractor_data = req.contractor_data or {}
    if "_company_assets" not in contractor_data:
        contractor_data["_company_assets"] = assets_list
    if tenant and not contractor_data.get("name"):
        contractor_data["name"] = tenant.name
        contractor_data["siret"] = tenant.siret

    result = mea_structure_service.validate_regional_compliance(
        country_code=req.country_code,
        project_data=req.project_data or {},
        contractor_data=contractor_data,
    )
    return result
