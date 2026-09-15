"""
Administrative Tender Dossiers API Endpoints (DC1, DC2, DUME, Country Regulatory Profiles).
Strictly scoped by tenant_id under Postgres RLS.
"""
import re
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
        "siret": tenant.siret or "[à compléter]",
        "country_code": tenant.country_code or "FR",
        "city": (tenant.branding_config or {}).get("city") or "[à compléter]",  # 11/09 : plus de ville inventée
    }
    project_dict = {
        "title": project.title,
        "client_name": _reel(project.client_name),
        "reference_code": project.reference_code,
        "lot_number": _reel(project.lot_number) if project.lot_number else "Lot unique / Tous corps d'état",
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
        "client_name": _reel(project.client_name),
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
        "client_name": _reel(project.client_name),
        "reference_code": project.reference_code,
    }

    return admin_dossier_service.generate_dume_summary(tenant_dict, project_dict)


_DEFAUTS_APPLI = {"acheteur public détecté", "acheteur public detecte", "lot 01 - gros œuvre", "lot 01 - gros oeuvre"}


def _reel(v):
    """Une valeur par defaut de l'assistant n'est pas une donnee : « [à compléter] »."""
    return v if v and str(v).strip().lower() not in _DEFAUTS_APPLI else "[à compléter]"


@router.get("/{project_id}/dume.docx")
async def export_dume_docx(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """DUME pré-rempli en Word (11/09) : jusqu'ici uniquement un JSON, introuvable dans l'interface."""
    from app.models.entities import CompanyAsset
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    certifs = (await db.execute(
        select(CompanyAsset.title).where(CompanyAsset.tenant_id == tenant.id,
                                         CompanyAsset.category.in_(("certification", "certificat_qualibat")),
                                         CompanyAsset.obsolete_at.is_(None))
    )).scalars().all()
    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret or "[à compléter]",
        "country_code": tenant.country_code or "FR",
        "contact_email": current_user.email,
        "certifications": list(certifs),
    }
    project_dict = {
        "title": project.title,
        "client_name": _reel(project.client_name),
        "reference_code": project.reference_code or "[à compléter]",
    }
    docx_bytes = admin_dossier_service.generate_dume_docx(tenant_dict, project_dict)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="DUME_{project.reference_code or "AO"}.docx"'},
    )


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


@router.get("/{project_id}/piece-declaration")
async def export_piece_declaration(
    project_id: str,
    piece: str,
    citation: Optional[str] = None,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Projet de déclaration/lettre rédigé par l'IA pour une pièce administrative exigée par le
    dossier de consultation de ce projet, quand aucun formulaire national fixe n'existe pour ce
    pays (voir pieces_service.GENERABLES, aujourd'hui France/Belgique/Luxembourg seulement) --
    15/09, en réponse directe au constat que pour les autres pays (ex. Liban) l'application
    identifiait la pièce manquante et cherchait un lien, sans jamais la rédiger elle-même.

    piece/citation sont les valeurs déjà renvoyées par POST /{project_id}/pieces pour cette même
    ligne (l'utilisateur les a déjà vues à l'écran avant de cliquer) -- pas ré-analysées ici, au
    même niveau de confiance que project_id (scopé au tenant de l'utilisateur authentifié).

    TOUJOURS un PROJET à vérifier, compléter et signer -- jamais présenté comme final : voir
    l'avertissement inséré directement dans le document par generate_declaration_docx, et sa
    discipline anti-invention (aucun fait non fourni n'est inventé ; aucune déclaration sur
    l'honneur n'est pré-affirmée comme vraie pour l'entreprise).
    """
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    piece = (piece or "").strip()
    if not piece:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pièce manquante")

    tenant_dict = {
        "name": tenant.name,
        "siret": tenant.siret,
        "country_code": tenant.country_code or "FR",
        "city": (tenant.branding_config or {}).get("city"),
    }
    project_dict = {
        "title": project.title,
        "client_name": _reel(project.client_name),
        "reference_code": project.reference_code,
    }
    langue = getattr(project, "output_language", None) or "fr"

    docx_bytes = await admin_dossier_service.generate_declaration_docx(
        db, tenant.id, tenant_dict, project_dict,
        piece[:200], (citation or "").strip()[:400] or None, langue,
    )
    if not docx_bytes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le brouillon n'a pas pu être rédigé pour l'instant (service IA indisponible) — réessayez dans un instant.",
        )

    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", piece)[:60].strip("_") or "Piece"
    filename = f"Declaration_{safe_name}_{project.reference_code or 'AO'}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/pieces")
async def verifier_pieces_et_formulaires(
    project_id: str,
    request: Request,
    chercher: bool = True,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """Pièces exigées (DCE + pays du marché), ce qui est déjà disponible, et pour ce qui
    manque, lien vers le formulaire sur les portails officiels du pays (11/09).
    15/09 : accepte en option un corps JSON {"pieces_confirmees": [...]} -- libellés de
    recommandations (historique tenant+pays) que l'utilisateur vient de confirmer pour ce
    dossier ; corps absent ou vide = comportement inchangé (rétrocompatible)."""
    from app.services.pieces_service import analyser_pieces
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    pieces_confirmees = None
    try:
        corps = await request.json()
        if isinstance(corps, dict):
            brut = corps.get("pieces_confirmees")
            if isinstance(brut, list):
                pieces_confirmees = [str(x)[:250] for x in brut if str(x or "").strip()][:30] or None
    except Exception:
        pieces_confirmees = None
    return await analyser_pieces(db, tenant.id, project, chercher=chercher,
                                 langue=request.headers.get("x-ui-language") or "fr",
                                 pieces_confirmees=pieces_confirmees)
