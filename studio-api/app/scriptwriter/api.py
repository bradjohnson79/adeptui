"""HTTP API for M4.7 Professional Scriptwriter Studio."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .errors import ScriptwriterError
from .migration import preview_migration, run_migration

router = APIRouter(prefix="/projects/{project_id}/scriptwriter", tags=["scriptwriter-m47"])


def _err(exc: ScriptwriterError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.to_dict())


class AutosaveBody(BaseModel):
    elements: Optional[list[dict[str, Any]]] = None
    html: Optional[str] = None
    expectedRevision: Optional[int] = None


class InsertSceneBody(BaseModel):
    afterOrder: int = -1
    heading: str = "INT. LOCATION - DAY"


class DeleteSceneBody(BaseModel):
    sceneHeadingId: str


class MoveSceneBody(BaseModel):
    sceneHeadingId: str
    toIndex: int = 0


class RevisionBody(BaseModel):
    name: str = "Blue Draft"
    color: str = "Blue"
    note: str = ""


class CompareBody(BaseModel):
    revisionA: str
    revisionB: str


class RestoreBody(BaseModel):
    revisionId: str


class ImportBody(BaseModel):
    text: str
    format: str = "fountain"


class ProposalApplyBody(BaseModel):
    proposal: dict[str, Any]


class OutlineBody(BaseModel):
    beats: list[dict[str, Any]] = Field(default_factory=list)


class LinkSceneBody(BaseModel):
    sceneHeadingId: str
    projectSceneId: str


class TimelinePrepBody(BaseModel):
    sceneHeadingId: str


class TimelineApplyBody(BaseModel):
    sceneHeadingId: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyzeBody(BaseModel):
    sceneHeadingId: str


class LockBody(BaseModel):
    locked: bool = True


class SearchReplaceBody(BaseModel):
    find: str
    replace: str = ""
    elementTypes: list[str] = Field(default_factory=list)


@router.get("")
def get_studio(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        doc = service.get_or_create_document(db, project_id)
        return service.document_bundle(db, doc.id)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.get("/documents")
def list_docs(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from .store import list_documents

    service.ensure_ready()
    return {"ok": True, "documents": [d.model_dump(mode="json") for d in list_documents(db, project_id)]}


@router.get("/documents/{document_id}")
def get_doc(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.document_bundle(db, document_id)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/autosave")
def autosave(project_id: str, document_id: str, body: AutosaveBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        if body.html is not None:
            return service.autosave_html(db, document_id, body.html, expected_revision=body.expectedRevision)
        return service.autosave_elements(db, document_id, body.elements or [], expected_revision=body.expectedRevision)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/scenes/insert")
def insert_scene(project_id: str, document_id: str, body: InsertSceneBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.insert_scene(db, document_id, after_order=body.afterOrder, heading=body.heading)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/scenes/delete")
def delete_scene(project_id: str, document_id: str, body: DeleteSceneBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.delete_scene(db, document_id, body.sceneHeadingId)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/scenes/move")
def move_scene(project_id: str, document_id: str, body: MoveSceneBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.move_scene(db, document_id, body.sceneHeadingId, to_index=body.toIndex)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/revisions")
def create_revision(project_id: str, document_id: str, body: RevisionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.create_revision_set(db, document_id, name=body.name, color=body.color, note=body.note)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/revisions/compare")
def compare(project_id: str, document_id: str, body: CompareBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.compare_revisions(db, document_id, body.revisionA, body.revisionB)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/revisions/restore")
def restore(project_id: str, document_id: str, body: RestoreBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.restore_revision(db, document_id, body.revisionId)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/import")
def import_doc(project_id: str, document_id: str, body: ImportBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.import_text(db, document_id, body.text, fmt=body.format)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.get("/documents/{document_id}/export/fountain")
def export_fountain(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.export_fountain(db, document_id)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/export/pdf")
def export_pdf(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        root = Path(__file__).resolve().parents[3]
        out = root / "artifacts" / "m47" / "pdf"
        return service.export_pdf_file(db, document_id, out)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/proposals/apply")
def apply_proposal(project_id: str, document_id: str, body: ProposalApplyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.apply_codirector_proposal(db, document_id, body.proposal)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/outline/convert")
def convert_outline(project_id: str, document_id: str, body: OutlineBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.convert_outline_to_scenes(db, document_id, body.beats)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/scenes/link")
def link_scene(project_id: str, document_id: str, body: LinkSceneBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.link_scene(db, document_id, body.sceneHeadingId, body.projectSceneId)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/timeline/prepare")
def timeline_prepare(project_id: str, document_id: str, body: TimelinePrepBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.prepare_timeline(db, document_id, body.sceneHeadingId)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/timeline/apply-metadata")
def timeline_apply(project_id: str, document_id: str, body: TimelineApplyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.apply_timeline_prep_metadata(db, document_id, body.sceneHeadingId, body.metadata)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/analyze/scene")
def analyze_scene(project_id: str, document_id: str, body: AnalyzeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.analyze_scene(db, document_id, body.sceneHeadingId)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/production-lock")
def production_lock(project_id: str, document_id: str, body: LockBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.lock_production_numbers(db, document_id, locked=body.locked)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/undo")
def undo_tx(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.undo(db, document_id)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/search-replace")
def search_replace(project_id: str, document_id: str, body: SearchReplaceBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.search_replace(
            db, document_id, find=body.find, replace=body.replace, element_types=body.elementTypes or None
        )
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.post("/documents/{document_id}/bible/propose")
def bible_propose(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return service.propose_bible_entities(db, project_id, document_id)
    except ScriptwriterError as exc:
        raise _err(exc) from exc


@router.get("/migration/preview")
def mig_preview(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return preview_migration(db, project_id)


@router.post("/migration/run")
def mig_run(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return run_migration(db, project_id)
