"""HTTP API for Timeline Re-take take registry."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import store

router = APIRouter(prefix="/timeline-retakes", tags=["timeline-retakes"])


class BaselineBody(BaseModel):
    shotId: str
    sceneId: Optional[str] = None
    assetId: Optional[str] = None
    jobId: Optional[str] = None
    prompt: str = ""
    durationSec: float = 5.0
    provenance: Optional[dict[str, Any]] = None


class AlternateBody(BaseModel):
    shotId: str
    sourceTakeId: str
    assetId: Optional[str] = None
    jobId: Optional[str] = None
    prompt: str = ""
    deltaInstruction: str = Field(..., min_length=1)
    durationSec: float = 5.0
    provenance: Optional[dict[str, Any]] = None
    activate: bool = False


class ActiveBody(BaseModel):
    takeId: str


@router.get("/projects/{project_id}")
def list_takes(project_id: str):
    return {"ok": True, **store.list_project_takes(project_id), "mock": False}


@router.get("/projects/{project_id}/shots/{shot_id}")
def get_shot(project_id: str, shot_id: str):
    return store.get_shot_takes(project_id, shot_id)


@router.post("/projects/{project_id}/baseline")
def baseline(project_id: str, body: BaselineBody):
    shot = store.ensure_baseline_take(
        project_id,
        shot_id=body.shotId,
        scene_id=body.sceneId,
        asset_id=body.assetId,
        job_id=body.jobId,
        prompt=body.prompt,
        duration_sec=body.durationSec,
        provenance=body.provenance,
    )
    return {"ok": True, "shot": shot, "mock": False}


@router.post("/projects/{project_id}/alternate")
def alternate(project_id: str, body: AlternateBody):
    try:
        shot = store.add_alternate_take(
            project_id,
            shot_id=body.shotId,
            source_take_id=body.sourceTakeId,
            asset_id=body.assetId,
            job_id=body.jobId,
            prompt=body.prompt,
            delta_instruction=body.deltaInstruction,
            duration_sec=body.durationSec,
            provenance=body.provenance,
            activate=body.activate,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "shot": shot, "mock": False}


@router.put("/projects/{project_id}/shots/{shot_id}/active")
def active(project_id: str, shot_id: str, body: ActiveBody):
    try:
        shot = store.set_active_take(project_id, shot_id, body.takeId)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True, "shot": shot, "mock": False}
