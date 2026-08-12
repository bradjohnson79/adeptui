"""HTTP API for Voice Environment — /api/voice-environment/*"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .contracts import (
    ApproveRenderRequest,
    ApplyToSceneRequest,
    LipSyncHandoffRequest,
    PreviewRenderRequest,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    RecommendRequest,
    TimelineHandoffRequest,
)
from .errors import VoiceEnvironmentError, http_error
from .presets import (
    DEVICE_PRESETS,
    DIRECTION_PRESETS,
    DISTANCE_PRESETS,
    SPACE_PRESETS,
    TONE_PRESETS,
    WALLA_PRESETS,
)

router = APIRouter(prefix="/voice-environment", tags=["voice-environment"])


def _handle(fn):
    try:
        return fn()
    except VoiceEnvironmentError as exc:
        raise http_error(exc) from exc


@router.get("/runtime/status")
def get_runtime_status():
    return service.runtime_status()


@router.get("/presets")
def get_presets():
    def pack(d):
        return [{"id": k, "label": v.get("label", k), **{kk: vv for kk, vv in v.items() if kk != "label"}} for k, v in d.items()]

    return {
        "space": pack(SPACE_PRESETS),
        "distance": pack(DISTANCE_PRESETS),
        "direction": pack(DIRECTION_PRESETS),
        "tone": pack(TONE_PRESETS),
        "device": pack(DEVICE_PRESETS),
        "walla": pack(WALLA_PRESETS),
    }


@router.post("/profiles")
def create_profile(body: ProfileCreateRequest, db: Session = Depends(get_db)):
    return _handle(lambda: service.create_profile(db, body).model_dump())


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfileUpdateRequest, db: Session = Depends(get_db)):
    return _handle(lambda: service.update_profile(db, profile_id, body).model_dump())


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    return _handle(lambda: service.get_profile(db, profile_id).model_dump())


@router.get("/projects/{project_id}/profiles")
def list_profiles(project_id: str, characterId: Optional[str] = None, db: Session = Depends(get_db)):
    return _handle(lambda: [p.model_dump() for p in service.list_profiles(db, project_id, characterId)])


@router.post("/preview")
def create_preview(body: PreviewRenderRequest, db: Session = Depends(get_db)):
    return _handle(
        lambda: service.create_render(
            db,
            project_id=body.projectId,
            character_id=body.characterId,
            performance_record_id=body.performanceRecordId,
            performance_take_id=body.performanceTakeId,
            environment_profile_id=body.environmentProfileId,
            preview=True,
        ).model_dump()
    )


@router.post("/render")
def create_render(body: PreviewRenderRequest, db: Session = Depends(get_db)):
    return _handle(
        lambda: service.create_render(
            db,
            project_id=body.projectId,
            character_id=body.characterId,
            performance_record_id=body.performanceRecordId,
            performance_take_id=body.performanceTakeId,
            environment_profile_id=body.environmentProfileId,
            preview=False,
        ).model_dump()
    )


@router.get("/renders/{render_id}")
def get_render(render_id: str, db: Session = Depends(get_db)):
    return _handle(lambda: service.get_render(db, render_id).model_dump())


@router.get("/projects/{project_id}/renders")
def list_renders(
    project_id: str,
    characterId: Optional[str] = None,
    performanceTakeId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return _handle(
        lambda: [
            r.model_dump()
            for r in service.list_renders(
                db, project_id, character_id=characterId, performance_take_id=performanceTakeId
            )
        ]
    )


@router.post("/renders/{render_id}/approve")
def approve_render(render_id: str, body: ApproveRenderRequest, db: Session = Depends(get_db)):
    return _handle(lambda: service.approve_render(db, render_id, body.approved).model_dump())


@router.post("/renders/{render_id}/apply-to-scene")
def apply_to_scene(render_id: str, body: ApplyToSceneRequest, db: Session = Depends(get_db)):
    return _handle(lambda: service.apply_to_scene(db, render_id, body.sceneId))


@router.post("/renders/{render_id}/timeline/prepare")
def timeline_prepare(render_id: str, body: TimelineHandoffRequest, db: Session = Depends(get_db)):
    return _handle(
        lambda: service.prepare_timeline(
            db, render_id, scene_id=body.sceneId, use_processed=body.useProcessedMix
        )
    )


@router.post("/renders/{render_id}/timeline")
def timeline_place(render_id: str, body: TimelineHandoffRequest, db: Session = Depends(get_db)):
    return _handle(
        lambda: service.place_timeline(
            db, render_id, scene_id=body.sceneId, use_processed=body.useProcessedMix
        )
    )


@router.post("/renders/{render_id}/lipsync")
def lipsync_prepare(render_id: str, body: LipSyncHandoffRequest, db: Session = Depends(get_db)):
    return _handle(lambda: service.prepare_lipsync(db, render_id, scene_id=body.sceneId))


@router.post("/renders/{render_id}/audio-studio")
def audio_studio_open(render_id: str, db: Session = Depends(get_db)):
    return _handle(lambda: service.open_audio_studio_payload(db, render_id))


@router.post("/recommend")
def recommend(body: RecommendRequest, db: Session = Depends(get_db)):
    return _handle(
        lambda: service.recommend(
            db,
            project_id=body.projectId,
            character_id=body.characterId,
            scene_id=body.sceneId,
            location_id=body.locationId,
        ).model_dump()
    )
