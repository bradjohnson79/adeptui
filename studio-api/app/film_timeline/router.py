"""Film Timeline HTTP API. This is the production Timeline surface."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..db import get_db
from .contracts import AddToTimelineRequest
from .duration import _WHOLE_SECOND_EPSILON
from .orchestrator import FilmTimelineError


def _validate_whole_seconds(v):
    """Reject fractional duration at the HTTP edge with a creator-readable 4xx."""
    if v is None:
        return v
    try:
        sec = float(v)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Duration {v!r} is not a number.")
    if not (sec > 0):
        raise HTTPException(status_code=422, detail="Duration must be greater than zero.")
    nearest = round(sec)
    if abs(sec - nearest) > _WHOLE_SECOND_EPSILON:
        raise HTTPException(
            status_code=422,
            detail=f"{sec:g}s is not a whole second. Duration must be a whole number (e.g. 5, 10, 15). "
                   f"The closest whole second is {nearest}s.",
        )
    return float(nearest)

router = APIRouter(prefix="/film-timeline", tags=["film-timeline"])


class ShotBody(BaseModel):
    name: Optional[str] = None
    durationSec: float = 10
    timedPrompt: str = ""
    generatorId: Optional[str] = None

    @field_validator("durationSec", mode="before")
    @classmethod
    def _whole(cls, v):
        return _validate_whole_seconds(v)


class ShotModelBody(BaseModel):
    generatorId: str


class PromptBody(BaseModel):
    timedPrompt: str
    modelPrompt: Optional[str] = None


class GenerateBody(BaseModel):
    durationSec: Optional[float] = None
    timedPrompt: Optional[str] = None
    generatorId: Optional[str] = None
    providerOptions: Optional[dict] = None

    @field_validator("durationSec", mode="before")
    @classmethod
    def _whole(cls, v):
        return _validate_whole_seconds(v) if v is not None else None


class ContinueBody(BaseModel):
    durationSec: float
    timedPrompt: str
    generatorId: Optional[str] = None
    providerOptions: Optional[dict] = None

    @field_validator("durationSec", mode="before")
    @classmethod
    def _whole(cls, v):
        return _validate_whole_seconds(v)


class ReferenceBody(BaseModel):
    assetId: str = ""
    type: str = "image"
    label: str = ""
    tag: str = ""
    sceneLevel: bool = False
    referenceId: str = ""


class RetakeBody(BaseModel):
    markIn: Optional[float] = None
    markOut: Optional[float] = None
    timedPrompt: Optional[str] = None


class PublishBody(BaseModel):
    assetId: str
    update: bool = False


class MagiBody(BaseModel):
    assetId: str
    engine: str = "ffmpeg-scale"
    model: str = "lanczos"
    targetResolution: str = ""


class ClipPatch(BaseModel):
    startSec: Optional[float] = None
    durationSec: Optional[float] = None
    trimInSec: Optional[float] = None
    trimOutSec: Optional[float] = None
    volume: Optional[float] = None
    fadeInSec: Optional[float] = None
    fadeOutSec: Optional[float] = None
    muted: Optional[bool] = None
    label: Optional[str] = None


def _fail(exc: FilmTimelineError, status: int = 400) -> None:
    raise HTTPException(status, {"error": exc.code, "message": exc.message})


@router.get("/projects/{project_id}/scenes/{scene_id}")
def get_film(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    from .store import load_film

    loaded = load_film(db, project_id, scene_id)
    if not loaded.get("ok"):
        raise HTTPException(404, {"error": loaded.get("error") or "SCENE_NOT_FOUND"})
    film = loaded["film"]
    return {"ok": True, "film": film.model_dump(), "projectId": project_id, "sceneId": scene_id}


@router.get("/capabilities")
def capabilities():
    from .availability import list_generator_status

    return {"ok": True, "capabilities": list_generator_status()}


@router.post("/projects/{project_id}/scenes/{scene_id}/shots")
def post_shot(project_id: str, scene_id: str, body: ShotBody, db: Session = Depends(get_db)):
    from .orchestrator import create_shot

    try:
        return create_shot(
            db,
            project_id,
            scene_id,
            name=body.name,
            duration_sec=body.durationSec,
            timed_prompt=body.timedPrompt,
            generator_id=body.generatorId,
        )
    except FilmTimelineError as exc:
        _fail(exc)


@router.patch("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}")
def patch_shot_model(project_id: str, scene_id: str, shot_id: str, body: ShotModelBody, db: Session = Depends(get_db)):
    from .orchestrator import set_shot_generator

    try:
        return set_shot_generator(db, project_id, scene_id, shot_id, body.generatorId)
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/new")
def post_new_shot(project_id: str, scene_id: str, body: ShotBody, db: Session = Depends(get_db)):
    from .orchestrator import new_shot

    try:
        return new_shot(db, project_id, scene_id, name=body.name)
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/prompt")
def post_prompt(project_id: str, scene_id: str, shot_id: str, body: PromptBody, db: Session = Depends(get_db)):
    from .orchestrator import update_timed_prompt

    try:
        return update_timed_prompt(
            db, project_id, scene_id, shot_id, body.timedPrompt, model_prompt=body.modelPrompt
        )
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/references")
def post_reference(project_id: str, scene_id: str, shot_id: str, body: ReferenceBody, db: Session = Depends(get_db)):
    from .orchestrator import attach_reference

    try:
        return attach_reference(
            db,
            project_id,
            scene_id,
            shot_id,
            asset_id=body.assetId,
            ref_type=body.type,
            label=body.label,
            tag=body.tag,
            scene_level=body.sceneLevel,
            reference_id=body.referenceId,
        )
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/generate")
def post_generate(project_id: str, scene_id: str, shot_id: str, body: GenerateBody, db: Session = Depends(get_db)):
    from .orchestrator import generate_shot

    try:
        return generate_shot(
            db,
            project_id,
            scene_id,
            shot_id,
            duration_sec=body.durationSec,
            timed_prompt=body.timedPrompt,
            generator_id=body.generatorId,
            provider_options=body.providerOptions,
        )
    except FilmTimelineError as exc:
        _fail(exc, 409 if exc.code == "CONTINUITY_MISSING" else 400)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/continue")
def post_continue(project_id: str, scene_id: str, shot_id: str, body: ContinueBody, db: Session = Depends(get_db)):
    from .orchestrator import continue_shot

    try:
        return continue_shot(
            db,
            project_id,
            scene_id,
            shot_id,
            duration_sec=body.durationSec,
            timed_prompt=body.timedPrompt,
            generator_id=body.generatorId,
            provider_options=body.providerOptions,
        )
    except FilmTimelineError as exc:
        _fail(exc, 409 if exc.code == "CONTINUITY_MISSING" else 400)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/cancel")
async def post_cancel(project_id: str, scene_id: str, shot_id: str, db: Session = Depends(get_db)):
    from .orchestrator import cancel_shot

    try:
        return await cancel_shot(db, project_id, scene_id, shot_id)
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/retake")
def post_retake(project_id: str, scene_id: str, shot_id: str, body: RetakeBody, db: Session = Depends(get_db)):
    from .orchestrator import retake_shot

    try:
        return retake_shot(
            db,
            project_id,
            scene_id,
            shot_id,
            mark_in=body.markIn,
            mark_out=body.markOut,
            timed_prompt=body.timedPrompt,
        )
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/references/remove")
def post_detach_reference(project_id: str, scene_id: str, shot_id: str, body: ReferenceBody, db: Session = Depends(get_db)):
    from .orchestrator import detach_reference

    try:
        return detach_reference(db, project_id, scene_id, shot_id, asset_id=body.assetId)
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/publish")
def post_publish(project_id: str, scene_id: str, body: PublishBody, db: Session = Depends(get_db)):
    from .publish_media import publish_film_media

    return publish_film_media(db, project_id, scene_id, asset_id=body.assetId, update=body.update)


@router.post("/projects/{project_id}/scenes/{scene_id}/magi/options")
def post_magi_options(project_id: str, scene_id: str, body: PublishBody, db: Session = Depends(get_db)):
    from .publish_media import magi_options_for_asset

    return magi_options_for_asset(db, project_id, scene_id, asset_id=body.assetId)


@router.post("/projects/{project_id}/scenes/{scene_id}/magi")
def post_magi(project_id: str, scene_id: str, body: MagiBody, db: Session = Depends(get_db)):
    from .publish_media import magi_upscale_film

    return magi_upscale_film(
        db,
        project_id,
        scene_id,
        asset_id=body.assetId,
        engine=body.engine,
        model=body.model,
        target_resolution=body.targetResolution,
    )


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/segments/{segment_id}/regenerate")
def post_regenerate(
    project_id: str,
    scene_id: str,
    shot_id: str,
    segment_id: str,
    body: PromptBody | None = None,
    db: Session = Depends(get_db),
):
    from .orchestrator import regenerate_segment

    try:
        return regenerate_segment(
            db,
            project_id,
            scene_id,
            shot_id,
            segment_id,
            timed_prompt=body.timedPrompt if body else None,
        )
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/sync")
def post_sync(project_id: str, scene_id: str, shot_id: str, db: Session = Depends(get_db)):
    from .orchestrator import sync_shot

    try:
        return sync_shot(db, project_id, scene_id, shot_id)
    except FilmTimelineError as exc:
        _fail(exc)


@router.post("/projects/{project_id}/scenes/{scene_id}/shots/{shot_id}/stitch")
def post_stitch(project_id: str, scene_id: str, shot_id: str, db: Session = Depends(get_db)):
    from .stitch import stitch_shot

    return stitch_shot(db, project_id, scene_id, shot_id)


@router.post("/projects/{project_id}/scenes/{scene_id}/media")
def post_media(project_id: str, scene_id: str, body: AddToTimelineRequest, db: Session = Depends(get_db)):
    from .insertion import add_to_timeline

    return add_to_timeline(
        db,
        project_id,
        scene_id,
        media_type=body.mediaType,
        asset_id=body.assetId,
        target_track_type=body.targetTrackType,
        start_time=body.startTime,
        duration_sec=body.durationSec,
        shot_id=body.shotId,
        label=body.label,
        metadata=body.metadata,
    )


@router.patch("/projects/{project_id}/scenes/{scene_id}/clips/{clip_id}")
def patch_clip(project_id: str, scene_id: str, clip_id: str, body: ClipPatch, db: Session = Depends(get_db)):
    from .insertion import update_clip

    return update_clip(db, project_id, scene_id, clip_id, body.model_dump(exclude_none=True))


@router.delete("/projects/{project_id}/scenes/{scene_id}/clips/{clip_id}")
def remove_clip(project_id: str, scene_id: str, clip_id: str, db: Session = Depends(get_db)):
    from .insertion import delete_clip

    return delete_clip(db, project_id, scene_id, clip_id)
