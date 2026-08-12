"""HTTP surface for M4.9 Storyboard Studio documents / sync / timeline prep."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .add_from_image import (
    add_image_to_next_panel,
    replace_panel_image,
    undo_add_image,
    undo_replace_panel,
)
from .documents import (
    append_panel,
    ensure_document,
    get_document,
    hydrate_panels,
    list_documents,
    next_free_slot,
    reorder_panels,
    set_page_size,
)
from .export import export_adept_json, export_contact_sheet_html, export_pdf_bytes
from .timeline_prep import confirm_timeline_proposal, get_proposal, prepare_timeline_from_storyboard

router = APIRouter(prefix="/storyboard-studio", tags=["storyboard-studio-m49"])

PageSize = Literal[6, 9, 12]


class PageSizeBody(BaseModel):
    pageSize: PageSize = 9


class ReorderBody(BaseModel):
    panelOrder: list[str] = Field(default_factory=list)


class AppendPanelBody(BaseModel):
    panelId: str


class PrepBody(BaseModel):
    documentId: Optional[str] = None
    panelIds: Optional[list[str]] = None
    approvedOnly: bool = True


class ConfirmBody(BaseModel):
    panelIds: Optional[list[str]] = None


class AddImageBody(BaseModel):
    assetId: str
    prompt: str = ""
    label: str = ""
    lens: str = ""
    shotSize: str = ""
    continuitySessionId: Optional[str] = None
    spatialMapId: Optional[str] = None
    spatialMapVersion: Optional[str] = None
    sceneId: Optional[str] = None
    documentId: Optional[str] = None
    scriptwriterSceneId: Optional[str] = None


class ReplacePanelBody(BaseModel):
    panelId: str
    assetId: str
    prompt: str = ""
    label: str = ""
    lens: str = ""
    shotSize: str = ""
    continuitySessionId: Optional[str] = None
    spatialMapId: Optional[str] = None
    spatialMapVersion: Optional[str] = None
    sceneId: Optional[str] = None
    scriptwriterSceneId: Optional[str] = None


class UndoAddBody(BaseModel):
    panelId: str


@router.get("/projects/{project_id}/documents")
def api_list_docs(project_id: str) -> dict[str, Any]:
    return {"documents": [d.model_dump() for d in list_documents(project_id)]}


@router.post("/projects/{project_id}/documents/ensure")
def api_ensure_doc(project_id: str, body: PageSizeBody | None = None) -> dict[str, Any]:
    page_size = (body.pageSize if body else 9) or 9
    doc = ensure_document(project_id, page_size=page_size)  # type: ignore[arg-type]
    return {"document": doc.model_dump()}


@router.get("/projects/{project_id}/workspace")
def api_workspace(project_id: str, documentId: Optional[str] = None) -> dict[str, Any]:
    return hydrate_panels(project_id, documentId)


@router.patch("/projects/{project_id}/documents/{document_id}/page-size")
def api_page_size(project_id: str, document_id: str, body: PageSizeBody) -> dict[str, Any]:
    doc = set_page_size(project_id, document_id, body.pageSize)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document": doc.model_dump()}


@router.patch("/projects/{project_id}/documents/{document_id}/reorder")
def api_reorder(project_id: str, document_id: str, body: ReorderBody) -> dict[str, Any]:
    doc = reorder_panels(project_id, document_id, body.panelOrder)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document": doc.model_dump()}


@router.post("/projects/{project_id}/documents/{document_id}/append-panel")
def api_append(project_id: str, document_id: str, body: AppendPanelBody) -> dict[str, Any]:
    doc = append_panel(project_id, document_id, body.panelId)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document": doc.model_dump(), "slot": next_free_slot(project_id, doc.id)}


@router.get("/projects/{project_id}/next-free-slot")
def api_next_slot(project_id: str, documentId: Optional[str] = None) -> dict[str, Any]:
    return next_free_slot(project_id, documentId)


@router.post("/projects/{project_id}/add-image")
def api_add_image(project_id: str, body: AddImageBody) -> dict[str, Any]:
    if not body.assetId:
        raise HTTPException(status_code=400, detail="assetId required")
    return add_image_to_next_panel(
        project_id,
        asset_id=body.assetId,
        prompt=body.prompt,
        label=body.label,
        lens=body.lens,
        shot_size=body.shotSize,
        continuity_session_id=body.continuitySessionId,
        spatial_map_id=body.spatialMapId,
        spatial_map_version=body.spatialMapVersion,
        scene_id=body.sceneId,
        document_id=body.documentId,
        scriptwriter_scene_id=body.scriptwriterSceneId,
    )


@router.post("/projects/{project_id}/replace-panel")
def api_replace_panel(project_id: str, body: ReplacePanelBody) -> dict[str, Any]:
    result = replace_panel_image(
        project_id,
        panel_id=body.panelId,
        asset_id=body.assetId,
        prompt=body.prompt,
        label=body.label,
        lens=body.lens,
        shot_size=body.shotSize,
        continuity_session_id=body.continuitySessionId,
        spatial_map_id=body.spatialMapId,
        spatial_map_version=body.spatialMapVersion,
        scene_id=body.sceneId,
        scriptwriter_scene_id=body.scriptwriterSceneId,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error") or "replace failed")
    return result


@router.post("/projects/{project_id}/undo-add-image")
def api_undo_add(project_id: str, body: UndoAddBody) -> dict[str, Any]:
    result = undo_add_image(project_id, body.panelId)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error") or "undo failed")
    return result


@router.post("/projects/{project_id}/undo-replace-panel")
def api_undo_replace(project_id: str, body: UndoAddBody) -> dict[str, Any]:
    result = undo_replace_panel(project_id, body.panelId)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error") or "undo failed")
    return result


@router.post("/projects/{project_id}/prepare-timeline")
def api_prepare_timeline(project_id: str, body: PrepBody | None = None) -> dict[str, Any]:
    body = body or PrepBody()
    proposal = prepare_timeline_from_storyboard(
        project_id,
        document_id=body.documentId,
        panel_ids=body.panelIds,
        approved_only=body.approvedOnly,
    )
    return {"proposal": proposal.model_dump()}


@router.post("/projects/{project_id}/timeline-proposals/{proposal_id}/confirm")
def api_confirm_proposal(
    project_id: str, proposal_id: str, body: ConfirmBody | None = None
) -> dict[str, Any]:
    body = body or ConfirmBody()
    result = confirm_timeline_proposal(project_id, proposal_id, panel_ids=body.panelIds)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error") or "confirm failed")
    return result


@router.get("/projects/{project_id}/timeline-proposals/{proposal_id}")
def api_get_proposal(project_id: str, proposal_id: str) -> dict[str, Any]:
    proposal = get_proposal(project_id, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="proposal not found")
    return {"proposal": proposal.model_dump()}


@router.get("/projects/{project_id}/documents/{document_id}")
def api_get_doc(project_id: str, document_id: str) -> dict[str, Any]:
    doc = get_document(project_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document": doc.model_dump()}


@router.get("/projects/{project_id}/export.json")
def api_export_json(project_id: str, documentId: Optional[str] = None) -> JSONResponse:
    return JSONResponse(export_adept_json(project_id, documentId))


@router.get("/projects/{project_id}/export/contact-sheet", response_class=HTMLResponse)
def api_export_contact_sheet(project_id: str, documentId: Optional[str] = None) -> HTMLResponse:
    return HTMLResponse(export_contact_sheet_html(project_id, documentId))


@router.get("/projects/{project_id}/export.pdf")
def api_export_pdf(project_id: str, documentId: Optional[str] = None) -> Response:
    pdf_bytes, filename = export_pdf_bytes(project_id, documentId)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
