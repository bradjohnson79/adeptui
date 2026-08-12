"""PoseCraft REST router — project-scoped scene API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .schemas import PoseCraftCustomPose, PoseCraftDocument, PoseCraftExportPreview, PoseCraftRevision, PoseCraftScene, PoseCraftSnapshot

router = APIRouter(prefix="/api/posecraft", tags=["posecraft"])


def _to_http(exc: service.PoseCraftError) -> HTTPException:
    code = getattr(exc, "args", (None,))
    code_val = code[1] if len(code) > 1 and isinstance(code[1], int) else 400
    return HTTPException(status_code=code_val, detail=str(exc.args[0]) if exc.args else "PoseCraft error")


@router.get("/projects/{project_id}/scene", response_model=PoseCraftDocument)
def get_scene(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.load_scene(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.put("/projects/{project_id}/scene", response_model=PoseCraftDocument)
def put_scene(project_id: str, body: PoseCraftDocument, db: Session = Depends(get_db)):
    try:
        return service.save_scene(project_id, body, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/revisions", response_model=list[PoseCraftRevision])
def get_revisions(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.list_revisions(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/revisions", response_model=PoseCraftRevision)
def post_revision(project_id: str, body: PoseCraftRevision, db: Session = Depends(get_db)):
    try:
        return service.save_revision(project_id, body.label, body.scene, db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/revisions/{revision_id}/restore", response_model=PoseCraftDocument)
def restore_revision(project_id: str, revision_id: str, db: Session = Depends(get_db)):
    try:
        return service.restore_revision(project_id, revision_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/export-preview", response_model=PoseCraftExportPreview)
def get_export_preview(project_id: str, snapshot_id: str | None = None, db: Session = Depends(get_db)):
    try:
        return service.build_export_preview(project_id, db, snapshot_id=snapshot_id)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


# --------------------------------------------------------------------------
# Snapshot CRUD — frozen camera-composition handoff artifacts. Snapshots are
# persisted on the PoseCraftDocument via the existing scene PUT (the client
# appends the frozen snapshot and flushes). These endpoints expose rename /
# duplicate / delete / select and a snapshot-aware export preview so Co-
# Director / Image Gen / Storyboard can read a frozen composition by id.
# --------------------------------------------------------------------------
@router.get("/projects/{project_id}/snapshots", response_model=list[PoseCraftSnapshot])
def list_snapshots_route(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.list_snapshots(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.get("/projects/{project_id}/snapshots/{snapshot_id}", response_model=PoseCraftSnapshot)
def get_snapshot_route(project_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    try:
        return service.get_snapshot(project_id, snapshot_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


class SnapshotRenameBody(BaseModel):
    name: str


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/rename", response_model=PoseCraftDocument)
def rename_snapshot_route(project_id: str, snapshot_id: str, body: SnapshotRenameBody, db: Session = Depends(get_db)):
    try:
        return service.rename_snapshot(project_id, snapshot_id, body.name, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/duplicate", response_model=PoseCraftDocument)
def duplicate_snapshot_route(project_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    try:
        return service.duplicate_snapshot(project_id, snapshot_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.delete("/projects/{project_id}/snapshots/{snapshot_id}", response_model=PoseCraftDocument)
def delete_snapshot_route(project_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    try:
        return service.delete_snapshot(project_id, snapshot_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


class SnapshotSelectBody(BaseModel):
    snapshotId: str | None = None


@router.post("/projects/{project_id}/snapshots/select", response_model=PoseCraftDocument)
def select_snapshot_route(project_id: str, body: SnapshotSelectBody, db: Session = Depends(get_db)):
    try:
        return service.select_snapshot(project_id, body.snapshotId, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


# Master Program Phase 15–20: project-scoped custom pose CRUD.
@router.get("/projects/{project_id}/poses", response_model=list[PoseCraftCustomPose])
def list_custom_poses(project_id: str, db: Session = Depends(get_db)):
    try:
        return service.list_custom_poses(project_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.post("/projects/{project_id}/poses", response_model=PoseCraftCustomPose, status_code=201)
def create_custom_pose(project_id: str, body: PoseCraftCustomPose, db: Session = Depends(get_db)):
    try:
        return service.create_custom_pose(project_id, body.model_dump(), db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.put("/projects/{project_id}/poses/{pose_id}", response_model=PoseCraftCustomPose)
def update_custom_pose(project_id: str, pose_id: str, body: PoseCraftCustomPose, db: Session = Depends(get_db)):
    try:
        return service.update_custom_pose(project_id, pose_id, body.model_dump(), db, saved_by="creator")
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc


@router.delete("/projects/{project_id}/poses/{pose_id}", status_code=204)
def delete_custom_pose(project_id: str, pose_id: str, db: Session = Depends(get_db)):
    try:
        service.delete_custom_pose(project_id, pose_id, db)
    except service.PoseCraftError as exc:
        raise _to_http(exc) from exc
