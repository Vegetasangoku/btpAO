"""
Administrative Tender Dossiers API Endpoints (DC1, DC2, DUME, Country Regulatory Profiles).
Strictly scoped by tenant_id under Postgres RLS.
"""
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.models.entities import CountryRegulatoryProfile, Project, Tenant
from app.services.admin_dossier_service import admin_dossier_service

router = APIRouter(prefix="/dossiers", tags=["Administrative Dossiers (DC1/DC2/DUME)"])


async def _get_project_and_tenant(
    project_id: str,
    current_user: CurrentTenantUser,
    db: AsyncSession,
) -> tuple[Tenant, Project]:
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

    return tenant, project


@router.get("/{project_id}/dc1")
async def export_dc1_dossier(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports official Word (.docx) DC1 candidature letter.
    """
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)

    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "Non renseigné",
        "country_code": tenant.country_code or "FR",
        "city": "Paris",
    }
    project_dict = {
        "title": project.title,
        "client_name": project.client_name,
        "reference_code": project.reference_code,
        "lot_number": project.lot_number or "Lot unique / Tous corps d'état",
    }

    docx_bytes = admin_dossier_service.generate_dc1_docx(tenant_dict, project_dict)

    filename = f"DC1_Candidature_{project.reference_code or 'AO'}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/dc2")
async def export_dc2_dossier(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports official Word (.docx) DC2 candidate declaration.
    All fields are sourced from real tenant data (CompanyAsset metadata_json) validated by the user.
    Missing fields appear as explicit [À COMPLÉTER : field] placeholders — never fabricated.
    """
    from app.models.entities import CompanyAsset
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    t_uuid = tenant.id

    # Load all validated company assets to extract real field values
    assets_res = await db.execute(
        select(CompanyAsset).where(
            CompanyAsset.tenant_id == t_uuid,
            CompanyAsset.validated_by_user == True,
        )
    )
    assets = assets_res.scalars().all()

    # Merge metadata_json from all validated assets into a single dict
    asset_meta: dict = {}
    for a in assets:
        if a.metadata_json:
            asset_meta.update(a.metadata_json)

    def real_or_placeholder(key: str, label: str) -> str:
        """Returns real value from tenant/assets, or a visible red-flag placeholder."""
        # Check tenant columns first
        tenant_val = getattr(tenant, key, None)
        if tenant_val:
            return str(tenant_val)
        # Then merged asset metadata
        asset_val = asset_meta.get(key)
        if asset_val:
            return str(asset_val)
        return f"[À COMPLÉTER : {label}]"

    # Financial history from assets (category='financial') or placeholder rows
    financial_assets = [a for a in assets if (a.category or "").lower() in ("financial", "finance", "chiffres")]
    financial_history = None
    if financial_assets:
        financial_history = []
        for fa in financial_assets[:3]:
            m = fa.metadata_json or {}
            financial_history.append({
                "annee": m.get("annee") or fa.title or "Exercice",
                "ca_global": m.get("ca_global") or m.get("chiffre_affaires") or "[À COMPLÉTER : CA global €]",
                "ca_specifique": m.get("ca_specifique") or "[À COMPLÉTER : CA marchés publics €]",
            })

    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "[À COMPLÉTER : numéro SIRET]",
        "country_code": tenant.country_code or "FR",
        "naf": real_or_placeholder("naf_code", "code NAF / APE"),
        "legal_form": real_or_placeholder("legal_form", "forme juridique (ex: SAS, SARL, SA)"),
        "headcount": real_or_placeholder("headcount", "effectif moyen annuel permanent"),
        "equipment": real_or_placeholder("equipment_list", "outillage et matériel lourd détenu en propre"),
        "insurance_company": real_or_placeholder("insurance_company", "nom de la compagnie d'assurance RC décennale"),
        "insurance_policy_number": real_or_placeholder("insurance_policy_number", "numéro de police d'assurance"),
    }
    project_dict = {
        "title": project.title,
        "client_name": project.client_name,
        "reference_code": project.reference_code,
    }

    docx_bytes = admin_dossier_service.generate_dc2_docx(tenant_dict, project_dict, financial_history)

    filename = f"DC2_Declaration_{project.reference_code or 'AO'}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/dume")
async def export_dume_summary_endpoint(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates structured European Single Procurement Document (DUME / ESPD) summary.
    """
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)

    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "N/A",
        "country_code": tenant.country_code or "FR",
        "contact_email": current_user.email,
    }
    project_dict = {
        "title": project.title,
        "client_name": project.client_name,
        "reference_code": project.reference_code,
    }

    return admin_dossier_service.generate_dume_summary(tenant_dict, project_dict)


@router.get("/{project_id}/regulatory-profile")
async def get_project_regulatory_profile_endpoint(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches the applicable Country Regulatory Profile for the project.
    """
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    country_code = tenant.country_code or "FR"

    stmt = select(CountryRegulatoryProfile).where(CountryRegulatoryProfile.country_code == country_code)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        # Fallback to France profile
        stmt_fr = select(CountryRegulatoryProfile).where(CountryRegulatoryProfile.country_code == "FR")
        res_fr = await db.execute(stmt_fr)
        profile = res_fr.scalar_one_or_none()

    if not profile:
        return {
            "country_code": country_code,
            "country_name": "France",
            "procurement_framework": "Code de la commande publique",
            "currency": "EUR",
        }

    return {
        "country_code": profile.country_code,
        "country_name": profile.country_name,
        "procurement_framework": profile.procurement_framework,
        "currency": profile.currency,
        "key_regulations": profile.key_regulations or [],
        "standard_requirements": profile.standard_requirements or [],
        "mandatory_certifications": profile.mandatory_certifications or [],
        "tender_document_structure": profile.tender_document_structure or {},
    }
