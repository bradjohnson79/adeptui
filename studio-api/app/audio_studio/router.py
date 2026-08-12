"""Audio Studio HTTP API — M42 W45."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .production_gate import evaluate_m42_audio_studio_gate
from .provider_resolver import resolve_execution

router = APIRouter(prefix="/audio-studio", tags=["audio-studio"])


@router.get("/gate/w45")
def gate_w45():
    return evaluate_m42_audio_studio_gate()


@router.get("/projects/{project_id}/workspace")
def get_workspace(project_id: str, db: Session = Depends(get_db)):
    return service.workspace(db, project_id)


class GenerateBody(BaseModel):
    kind: str = "music"
    brief: Optional[dict[str, Any]] = None
    prompt: Optional[str] = None
    durationSeconds: Optional[float] = None
    mood: Optional[list[str]] = None
    genre: Optional[str] = None
    energy: Optional[str] = None
    instrumentation: Optional[list[str]] = None
    category: Optional[str] = None
    intensity: Optional[str] = None
    loopRequired: Optional[bool] = None
    candidateCount: int = Field(default=3, ge=1, le=6)
    preferredProvider: Optional[str] = None
    allowProviderSwitch: bool = False
    allowCpuFallback: bool = False
    asyncMode: bool = True


def _brief_from_body(body: GenerateBody) -> dict[str, Any]:
    brief = dict(body.brief or {})
    if body.prompt is not None:
        brief["prompt"] = body.prompt
    if body.durationSeconds is not None:
        brief["duration_seconds"] = body.durationSeconds
    if body.mood is not None:
        brief["mood"] = body.mood
    if body.genre is not None:
        brief["genre"] = body.genre
    if body.energy is not None:
        brief["energy"] = body.energy
    if body.instrumentation is not None:
        brief["instrumentation"] = body.instrumentation
    if body.category is not None:
        brief["category"] = body.category
    if body.intensity is not None:
        brief["intensity"] = body.intensity
    if body.loopRequired is not None:
        brief["loop_required"] = body.loopRequired
    return brief


@router.post("/projects/{project_id}/generate")
def generate(
    project_id: str,
    body: GenerateBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    brief = _brief_from_body(body)
    if body.asyncMode:
        batch = service.begin_generate_batch(
            project_id,
            kind=body.kind,
            brief=brief,
            candidate_count=body.candidateCount,
            preferred_provider=body.preferredProvider,
            allow_provider_switch=body.allowProviderSwitch,
            allow_cpu_fallback=body.allowCpuFallback,
        )
        background_tasks.add_task(service.run_generate_batch_job, project_id, batch["id"])
        return batch
    return service.generate_batch(
        db,
        project_id,
        kind=body.kind,
        brief=brief,
        candidate_count=body.candidateCount,
        preferred_provider=body.preferredProvider,
        allow_provider_switch=body.allowProviderSwitch,
        allow_cpu_fallback=body.allowCpuFallback,
    )


@router.get("/projects/{project_id}/batches/{batch_id}")
def get_batch(project_id: str, batch_id: str):
    return service.get_batch(project_id, batch_id)


@router.post("/projects/{project_id}/batches/{batch_id}/cancel")
def cancel_batch(project_id: str, batch_id: str):
    """Certified cancel-to-source — terminates ACE-Step/MMAudio worker process trees."""
    return service.cancel_batch(project_id, batch_id)


@router.post("/projects/{project_id}/cancel-generations")
def cancel_project_generations(project_id: str):
    """Cancel all in-flight Audio Studio batches for the project (GPU/RAM safety)."""
    return service.cancel_project_generations(project_id)


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/select")
def select_candidate(project_id: str, batch_id: str, candidate_id: str):
    return service.select_candidate(project_id, batch_id, candidate_id)


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/approve")
def approve_candidate(project_id: str, batch_id: str, candidate_id: str):
    return service.approve_candidate(project_id, batch_id, candidate_id)


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/retry")
def retry_candidate(project_id: str, batch_id: str, candidate_id: str, db: Session = Depends(get_db)):
    return service.retry_candidate(db, project_id, batch_id, candidate_id)


class PlaceBody(BaseModel):
    assetId: str
    category: str = "music"
    startMs: int = 0
    loop: bool = False
    sceneId: Optional[str] = None


@router.post("/projects/{project_id}/place")
def place(project_id: str, body: PlaceBody, db: Session = Depends(get_db)):
    return service.place_on_timeline(
        db,
        project_id,
        asset_id=body.assetId,
        category=body.category,
        start_ms=body.startMs,
        loop=body.loop,
        scene_id=body.sceneId,
    )


@router.get("/projects/{project_id}/mix")
def get_mix(project_id: str):
    from . import store

    return {"ok": True, "mix": store.get_mix(project_id), "mock": False}


class MixBody(BaseModel):
    master: Optional[dict[str, Any]] = None
    clips: Optional[dict[str, Any]] = None
    clip: Optional[dict[str, Any]] = None


@router.put("/projects/{project_id}/mix")
def put_mix(project_id: str, body: MixBody):
    return {"ok": True, "mix": service.update_mix(project_id, body.model_dump(exclude_none=True)), "mock": False}


@router.get("/projects/{project_id}/providers")
def providers(project_id: str, kind: str = "music"):
    return resolve_execution(kind if kind in ("music", "sfx", "ambience") else "music")
