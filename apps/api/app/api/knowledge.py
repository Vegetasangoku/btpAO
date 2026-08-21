"""
Company Knowledge Base & RAG Asset Management Endpoints.
Strictly scoped by tenant_id via SQLAlchemy 2 Async and Postgres RLS.
Zero mock fallbacks, zero local memory cache.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.core.storage import storage_service
from app.models.entities import CompanyAsset, ExportTemplate
from app.models.schemas import CompanyAssetCreate, CompanyAssetOut

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & Assets"])


@router.get("/assets", response_model=List[CompanyAssetOut])
async def list_company_assets(
    category: Optional[str] = None,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns company references, certifications, equipment sheets, and CVs.
    Strictly scoped to the authenticated tenant via PostgreSQL RLS.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(CompanyAsset).where(CompanyAsset.tenant_id == t_uuid)
    if category:
        stmt = stmt.where(CompanyAsset.category == category)
    stmt = stmt.order_by(CompanyAsset.created_at.desc())

    result = await db.execute(stmt)
    assets = result.scalars().all()

    return [
        CompanyAssetOut(
            id=str(a.id),
            tenant_id=str(a.tenant_id),
            category=a.category,
            title=a.title,
            description=a.description or "",
            s3_url=a.s3_url,
            tags=a.metadata_json.get("tags", []) if isinstance(a.metadata_json, dict) else [],
            metadata_json=a.metadata_json or {},
            created_at=a.created_at,
        )
        for a in assets
    ]


@router.post("/assets", response_model=CompanyAssetOut, status_code=status.HTTP_201_CREATED)
async def create_company_asset(
    payload: CompanyAssetCreate,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new company knowledge asset stored in PostgreSQL under the authenticated tenant.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    asset_id = uuid.uuid4()
    now = datetime.utcnow()

    metadata = payload.metadata_json or {}
    if payload.tags:
        metadata["tags"] = payload.tags

    new_asset = CompanyAsset(
        id=asset_id,
        tenant_id=t_uuid,
        category=payload.category,
        title=payload.title,
        description=payload.description,
        s3_url=None,
        metadata_json=metadata,
        created_at=now,
        updated_at=now,
    )

    db.add(new_asset)
    await db.flush()
    await db.refresh(new_asset)

    return CompanyAssetOut(
        id=str(new_asset.id),
        tenant_id=str(new_asset.tenant_id),
        category=new_asset.category,
        title=new_asset.title,
        description=new_asset.description or "",
        s3_url=new_asset.s3_url,
        tags=payload.tags or [],
        metadata_json=new_asset.metadata_json or {},
        created_at=new_asset.created_at,
    )


@router.get("/search")
async def search_knowledge(
    query: str,
    category: Optional[str] = None,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Searches company knowledge base strictly within the authenticated tenant's data.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(CompanyAsset).where(CompanyAsset.tenant_id == t_uuid)
    if category:
        stmt = stmt.where(CompanyAsset.category == category)
    stmt = stmt.order_by(CompanyAsset.created_at.desc())

    result = await db.execute(stmt)
    assets = result.scalars().all()

    # Simple semantic/keyword relevance match
    q_lower = query.lower()
    matched = []
    for a in assets:
        score = 0.5
        if q_lower in a.title.lower():
            score = 0.95
        elif a.description and q_lower in a.description.lower():
            score = 0.85
        matched.append({
            "id": str(a.id),
            "category": a.category,
            "title": a.title,
            "description": a.description,
            "score": score,
        })

    matched.sort(key=lambda x: x["score"], reverse=True)

    return {"query": query, "results": matched[:10]}


@router.post("/template/word")
async def upload_word_template(
    file: UploadFile = File(...),
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Uploads the client's branded Word template (.docx with header, logo, footer).
    Saves to tenant-scoped storage and records it in export_templates table in PostgreSQL.
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les fichiers .docx sont acceptés comme template Word."
        )

    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    file_bytes = await file.read()
    subpath = f"templates/word_template_{current_user.tenant_id}.docx"

    s3_key = storage_service.upload_file(
        tenant_id=current_user.tenant_id,
        subpath=subpath,
        file_obj=file_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    # Save S3 key reference in export_templates table
    stmt = select(ExportTemplate).where(
        ExportTemplate.tenant_id == t_uuid,
        ExportTemplate.is_default == True,
    )
    result = await db.execute(stmt)
    existing_template = result.scalar_one_or_none()

    if existing_template:
        existing_template.name = file.filename
        existing_template.s3_docx_key = s3_key
    else:
        new_template = ExportTemplate(
            id=uuid.uuid4(),
            tenant_id=t_uuid,
            name=file.filename,
            description="Template Word officiel client",
            s3_docx_key=s3_key,
            is_default=True,
            created_at=datetime.utcnow(),
        )
        db.add(new_template)

    await db.flush()

    return {
        "success": True,
        "message": f"Template Word '{file.filename}' enregistré avec succès.",
        "s3_key": s3_key,
        "filename": file.filename,
    }


@router.get("/template/word")
async def get_word_template_info(
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns metadata about the current Word template for this tenant from PostgreSQL.
    """
    try:
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

    stmt = select(ExportTemplate).where(
        ExportTemplate.tenant_id == t_uuid,
        ExportTemplate.is_default == True,
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if template:
        return {
            "has_template": True,
            "filename": template.name,
            "updated_at": template.created_at.isoformat(),
        }

    return {"has_template": False, "filename": None, "updated_at": None}
