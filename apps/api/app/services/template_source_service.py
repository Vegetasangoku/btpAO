"""
Choix du modele Word de base d'un export (11/09).

Demande Charbel : « a terme on devra se caler sur les exemples les plus fournis du
client et prendre ses couleurs et template ». Jusqu'ici, sans modele Word explicite,
l'export reprenait le PLUS RECENT EXPORT de l'application comme modele : la plateforme
se copiait elle-meme (et, avant le correctif du meme jour, en embarquait les images).
Les memoires de reference deposes par le client -- ses vrais documents, avec son
en-tete, son logo, ses styles et ses couleurs -- n'etaient jamais utilises.

Ordre retenu :
  1. le modele Word configure explicitement (Modeles & mise en forme) ;
  2. le memoire de reference .docx le plus fourni du client ;
  3. le plus recent export (comportement historique) ;
  4. aucun : document vierge.
Le corps du modele est toujours vide avant remplissage (exporter_service) : seuls
l'en-tete, le pied de page, les marges, les styles et le theme de couleurs sont repris.
"""
import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_service
from app.models.entities import CompanyAsset, ExportJob, ExportTemplate

logger = logging.getLogger(__name__)

CATEGORIES_MEMOIRES = ("memoire_reference", "memoire", "dossier_reference", "reference_chantier")


async def memoire_client_le_plus_fourni(db: AsyncSession, tenant_uuid: uuid.UUID) -> Optional[CompanyAsset]:
    res = await db.execute(
        select(CompanyAsset)
        .where(
            CompanyAsset.tenant_id == tenant_uuid,
            CompanyAsset.category.in_(CATEGORIES_MEMOIRES),
            CompanyAsset.obsolete_at.is_(None),
            CompanyAsset.s3_url.isnot(None),
            func.lower(CompanyAsset.s3_url).like("%.docx"),
        )
        .order_by(func.length(func.coalesce(CompanyAsset.description, "")).desc())
        .limit(1)
    )
    return res.scalars().first()


async def choisir_modele(db: AsyncSession, tenant_uuid: uuid.UUID, tenant_id: str) -> Tuple[Optional[bytes], Dict[str, Any]]:
    """Renvoie (octets du modele ou None, description de la source retenue)."""
    tmpl = (await db.execute(
        select(ExportTemplate).where(ExportTemplate.tenant_id == tenant_uuid, ExportTemplate.is_default == True)  # noqa: E712
    )).scalars().first()
    if tmpl and tmpl.s3_docx_key:
        try:
            return storage_service.download_file(tenant_id, tmpl.s3_docx_key), {"source": "export_template", "nom": tmpl.name}
        except Exception as exc:
            logger.warning("[TemplateSource] Modele configure illisible : %s", exc)

    asset = await memoire_client_le_plus_fourni(db, tenant_uuid)
    if asset:
        try:
            return storage_service.download_file(tenant_id, asset.s3_url), {"source": "memoire_client", "nom": asset.title}
        except Exception as exc:
            logger.warning("[TemplateSource] Memoire de reference illisible (%s) : %s", asset.title, exc)

    job = (await db.execute(
        select(ExportJob).where(
            ExportJob.tenant_id == tenant_uuid, ExportJob.status == "completed", ExportJob.s3_docx_url.isnot(None)
        ).order_by(ExportJob.completed_at.desc()).limit(1)
    )).scalars().first()
    if job:
        try:
            return storage_service.download_file(tenant_id, job.s3_docx_url), {"source": "export_precedent", "nom": str(job.id)}
        except Exception:
            pass
    return None, {"source": None}
