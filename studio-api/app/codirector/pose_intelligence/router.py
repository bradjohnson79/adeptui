"""Pose intelligence API — project-scoped, advisory, never mutates poses."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db import get_db
from ..world_intelligence.service import is_available as world_is_available
from .service import (
    analyze_project_scene,
    compare_project_poses,
    handoff_scene_creator,
    handoff_timeline,
    latest,
)

router = APIRouter(tags=["posecraft-pose-intelligence"])


class AnalyzeBody(BaseModel):
    snapshotId: str = ""
    figureId: str = ""


class CompareBody(BaseModel):
    fromSnapshotId: str
    toSnapshotId: str


class HandoffBody(BaseModel):
    snapshotId: str = ""


def _guard_project(project_id: str) -> None:
    if not project_id:
        raise HTTPException(status_code=400, detail="projectId is required.")


@router.get("/projects/{project_id}/intelligence")
def api_latest(project_id: str, snapshotId: str = "", db: Session = Depends(get_db)) -> dict[str, Any]:
    _guard_project(project_id)
    return latest(db, project_id, snapshot_id=snapshotId)


@router.post("/projects/{project_id}/intelligence/analyze")
def api_analyze(project_id: str, body: AnalyzeBody | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    _guard_project(project_id)
    payload = body or AnalyzeBody()
    packet = analyze_project_scene(
        db,
        project_id,
        snapshot_id=payload.snapshotId,
        figure_id=payload.figureId,
    )
    if packet.projectId and packet.projectId != project_id:
        raise HTTPException(status_code=403, detail="Pose intelligence is project-scoped.")
    return {"packet": packet.model_dump(mode="json"), "worldAvailable": bool(world_is_available(probe=False).get("available"))}


@router.post("/projects/{project_id}/intelligence/compare")
def api_compare(project_id: str, body: CompareBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _guard_project(project_id)
    if not body.fromSnapshotId or not body.toSnapshotId:
        raise HTTPException(status_code=400, detail="fromSnapshotId and toSnapshotId are required.")
    return compare_project_poses(
        db,
        project_id,
        from_snapshot_id=body.fromSnapshotId,
        to_snapshot_id=body.toSnapshotId,
    )


@router.post("/projects/{project_id}/intelligence/handoff/scene-creator")
def api_handoff_scene(project_id: str, body: HandoffBody | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    _guard_project(project_id)
    payload = body or HandoffBody()
    return handoff_scene_creator(db, project_id, snapshot_id=payload.snapshotId)


@router.post("/projects/{project_id}/intelligence/handoff/timeline")
def api_handoff_timeline(project_id: str, body: HandoffBody | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    _guard_project(project_id)
    payload = body or HandoffBody()
    return handoff_timeline(db, project_id, snapshot_id=payload.snapshotId)
