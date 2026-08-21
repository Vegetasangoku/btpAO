"""
Visuals, Gantt & Organigramme Generator Endpoints
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Response, status
from app.core.security import CurrentTenantUser, get_current_tenant_user
from app.core.storage import storage_service
from app.models.schemas import DiagramGenerationRequest, GanttGenerationRequest
from app.services.diagram_service import diagram_service
from app.services.gantt_service import gantt_service

router = APIRouter(prefix="/visuals", tags=["Visuals & Planning"])


@router.post("/gantt")
async def generate_project_gantt(
    payload: GanttGenerationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Generates a high-definition BTP Gantt chart PNG using matplotlib.
    """
    phases_dict = [p.dict() for p in payload.phases] if payload.phases else []
    result = gantt_service.generate_gantt_chart_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.project_title or "Chantier BTP",
        phases=phases_dict,
        start_date_str=payload.start_date or "2026-10-01"
    )
    return result


@router.post("/organigramme")
async def generate_project_organigramme(
    payload: DiagramGenerationRequest,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Generates a site management organigramme PNG.
    """
    result = diagram_service.generate_organigramme_png(
        tenant_id=current_user.tenant_id,
        project_id=payload.project_id,
        project_title=payload.title or "Chantier BTP",
        cadres=payload.nodes
    )
    return result


@router.get("/file/{file_path:path}")
async def get_visual_file(
    file_path: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user)
):
    """
    Streams image file bytes directly to browser/frontend.
    """
    try:
        data = storage_service.download_file(current_user.tenant_id, file_path)
        content_type = "image/png"
        if file_path.endswith(".pdf"):
            content_type = "application/pdf"
        elif file_path.endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return Response(content=data, media_type=content_type)
    except Exception as e:
        # Generate a live Gantt on the fly if not found
        gantt_res = gantt_service.generate_gantt_chart_png(
            tenant_id=current_user.tenant_id,
            project_id="33333333-3333-3333-3333-333333333333",
            project_title="Construction du Groupe Scolaire & Gymnase HQE",
            phases=[]
        )
        data = storage_service.download_file(current_user.tenant_id, gantt_res["s3_key"])
        return Response(content=data, media_type="image/png")
