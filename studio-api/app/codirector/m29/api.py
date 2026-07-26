"""FastAPI routes for Co-Director M2.9 Complete Native Production Suite."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from .audio.service import AudioService
from .control.service import ControlService
from .editing.service import EditingService
from .frames.service import FramesService
from .image.service import ImageService
from .lipsync.service import LipsyncService
from .render.service import RenderService
from .timeline.service import TimelineService
from .video.service import VideoService

router = APIRouter(prefix="/m29", tags=["codirector-m29"])


def _flag(name: str) -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, name, False))


def _require(*flag_names: str) -> None:
    if any(_flag(n) for n in flag_names):
        return
    raise HTTPException(status_code=404, detail="M2.9 production suite capability is not enabled.")


class ImageGenerateBody(BaseModel):
    projectId: str
    prompt: str = "M2.9 image"
    operation: str = "generate"
    sceneId: Optional[str] = None
    owner: str = "user"
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    negativePrompt: Optional[str] = None
    model: Optional[str] = None


class VersionActionBody(BaseModel):
    actor: str = "user"


class FrameGenerateBody(BaseModel):
    projectId: str
    frameType: str = "production_frame"
    shotId: Optional[str] = None
    count: int = 1
    sequence: bool = False
    sceneId: Optional[str] = None
    owner: str = "user"
    prompt: Optional[str] = None


class BindShotBody(BaseModel):
    shotId: str


class VideoGenerateBody(BaseModel):
    projectId: str
    prompt: str = "M2.9 video"
    mode: str = "text_to_video"
    sceneId: Optional[str] = None
    owner: str = "user"
    durationSec: Optional[float] = None
    fps: Optional[int] = None
    firstFrameAssetId: Optional[str] = None
    lastFrameAssetId: Optional[str] = None


class AudioGenerateBody(BaseModel):
    projectId: str
    kind: str = Field(default="dialogue", pattern="^(dialogue|sfx|music|ambience)$")
    prompt: str = "M2.9 audio"
    sceneId: Optional[str] = None
    owner: str = "user"
    startSec: float = 0.0
    durationSec: float = 2.0
    registryId: Optional[str] = None
    providerKey: Optional[str] = None


class AudioProcessBody(BaseModel):
    projectId: str
    assetId: str
    ops: list[dict[str, Any]] = Field(default_factory=list)
    sceneId: Optional[str] = None
    owner: str = "user"


class LipsyncBody(BaseModel):
    projectId: str
    audioAssetId: Optional[str] = None
    videoAssetId: Optional[str] = None
    sceneId: Optional[str] = None
    owner: str = "user"


class MouthTrackBody(BaseModel):
    projectId: str
    videoAssetId: Optional[str] = None
    sceneId: Optional[str] = None
    owner: str = "user"


class MouthRectBody(BaseModel):
    projectId: str
    rectangles: Optional[list[dict[str, Any]]] = None


class TimelineProposeBody(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    clips: Optional[list[dict[str, Any]]] = None
    notes: str = ""
    bibleMutations: Optional[dict[str, Any]] = None
    branch: Optional[str] = None


class AudioPlaceCueBody(BaseModel):
    projectId: str
    kind: str = "sfx"
    assetId: str
    startSec: float = 0.0
    durationSec: float = 2.0
    sceneId: Optional[str] = None
    volume: float = 1.0
    ducking: bool = False


class ActorBody(BaseModel):
    actor: str = "user"


class EditProposeBody(BaseModel):
    projectId: str
    ops: Optional[list[dict[str, Any]]] = None
    sceneId: Optional[str] = None


class EditApplyBody(BaseModel):
    projectId: str
    ops: list[dict[str, Any]]
    approved: bool = False
    sceneId: Optional[str] = None
    owner: str = "user"


class CueProposeBody(BaseModel):
    projectId: str
    prompt: str = "Cue"
    sceneId: Optional[str] = None
    owner: str = "user"
    startSec: float = 0.0
    durationSec: float = 2.0


class RenderBody(BaseModel):
    projectId: str
    kind: str = Field(default="timeline_render", pattern="^(timeline_render|scene_render)$")
    manifestId: Optional[str] = None
    sceneId: Optional[str] = None
    owner: str = "user"
    manifest: Optional[dict[str, Any]] = None


class ControlBody(BaseModel):
    projectId: str
    requestText: str
    enqueue: bool = False
    sceneId: Optional[str] = None
    owner: str = "user"


@router.get("/status")
def m29_status() -> dict[str, Any]:
    return {
        "imageProduction": _flag("image_production_v1"),
        "frameProduction": _flag("frame_production_v1"),
        "videoProduction": _flag("video_production_v1"),
        "directorTimeline": _flag("director_timeline_v1"),
        "lipsyncProduction": _flag("lipsync_production_v1"),
        "audioProduction": _flag("audio_production_v1"),
        "editingProduction": _flag("editing_production_v1"),
        "renderProduction": _flag("render_production_v1"),
        "codirectorProductionControl": _flag("codirector_production_control_v1"),
    }


@router.post("/image/generate")
def image_generate(body: ImageGenerateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("image_production_v1")
    params = {
        k: v
        for k, v in {
            "width": body.width,
            "height": body.height,
            "seed": body.seed,
            "negativePrompt": body.negativePrompt,
            "model": body.model,
        }.items()
        if v is not None
    }
    return ImageService.generate(
        db,
        project_id=body.projectId,
        prompt=body.prompt,
        operation=body.operation,
        scene_id=body.sceneId,
        owner=body.owner,
        **params,
    )


@router.post("/image/{version_id}/approve")
def image_approve(version_id: str, body: VersionActionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("image_production_v1")
    try:
        return ImageService.approve(db, version_id, actor=body.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="version not found") from None


@router.post("/image/{version_id}/reject")
def image_reject(version_id: str, body: VersionActionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("image_production_v1")
    try:
        return ImageService.reject(db, version_id, actor=body.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="version not found") from None


@router.post("/image/{version_id}/publish-reference")
def image_publish(version_id: str, body: VersionActionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("image_production_v1")
    try:
        return ImageService.publish_reference(db, version_id, actor=body.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="version not found") from None


@router.post("/frames/generate")
def frames_generate(body: FrameGenerateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("frame_production_v1")
    return FramesService.generate(
        db,
        project_id=body.projectId,
        frame_type=body.frameType,
        shot_id=body.shotId,
        count=body.count,
        sequence=body.sequence,
        scene_id=body.sceneId,
        owner=body.owner,
        prompt=body.prompt,
    )


@router.get("/frames")
def frames_list(projectId: str, shotId: Optional[str] = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("frame_production_v1")
    return {"frames": FramesService.list_frames(db, projectId, shot_id=shotId)}


@router.post("/frames/{frame_id}/bind")
def frames_bind(frame_id: str, body: BindShotBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("frame_production_v1")
    try:
        return FramesService.bind_to_shot(db, frame_id, body.shotId)
    except KeyError:
        raise HTTPException(status_code=404, detail="frame not found") from None


@router.post("/video/generate")
def video_generate(body: VideoGenerateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("video_production_v1")
    params: dict[str, Any] = {}
    if body.durationSec is not None:
        params["durationSec"] = body.durationSec
    if body.fps is not None:
        params["fps"] = body.fps
    if body.firstFrameAssetId:
        params["firstFrameAssetId"] = body.firstFrameAssetId
    if body.lastFrameAssetId:
        params["lastFrameAssetId"] = body.lastFrameAssetId
    return VideoService.generate(
        db,
        project_id=body.projectId,
        prompt=body.prompt,
        mode=body.mode,
        scene_id=body.sceneId,
        owner=body.owner,
        **params,
    )


@router.post("/audio/generate")
def audio_generate(body: AudioGenerateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("audio_production_v1")
    extra = {}
    if body.registryId:
        extra["registryId"] = body.registryId
    if body.providerKey:
        extra["providerKey"] = body.providerKey
    return AudioService.generate(
        db,
        project_id=body.projectId,
        kind=body.kind,
        prompt=body.prompt,
        scene_id=body.sceneId,
        owner=body.owner,
        start_sec=body.startSec,
        duration_sec=body.durationSec,
        **extra,
    )


@router.post("/audio/process")
def audio_process(body: AudioProcessBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("audio_production_v1")
    return AudioService.process(
        db,
        project_id=body.projectId,
        asset_id=body.assetId,
        ops=body.ops,
        scene_id=body.sceneId,
        owner=body.owner,
    )




class AudioPlanProposeBody(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    dialogue: list[dict[str, Any]] = Field(default_factory=list)
    sfx: list[dict[str, Any]] = Field(default_factory=list)
    ambience: list[dict[str, Any]] = Field(default_factory=list)
    music: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


@router.post("/audio/plan/propose")
def audio_plan_propose(body: AudioPlanProposeBody) -> dict[str, Any]:
    """Thin M2.10b helper: propose + validate an AudioPlan (no execution)."""
    _require("audio_production_v1", "m210b_audio_sandbox_v1")
    from ..m210b.scene_audio import propose_audio_plan, validate_audio_plan

    plan = propose_audio_plan(
        project_id=body.projectId,
        scene_id=body.sceneId,
        dialogue=body.dialogue,
        sfx=body.sfx,
        ambience=body.ambience,
        music=body.music,
        notes=body.notes,
    )
    return validate_audio_plan(plan)

@router.post("/audio/place-cue")
def audio_place_cue(body: AudioPlaceCueBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("audio_production_v1")
    return AudioService.place_cue(
        db,
        project_id=body.projectId,
        kind=body.kind,
        asset_id=body.assetId,
        start_sec=body.startSec,
        duration_sec=body.durationSec,
        scene_id=body.sceneId,
        volume=body.volume,
        ducking=body.ducking,
    )


@router.get("/audio/cues")
def audio_cues(projectId: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("audio_production_v1")
    return {"cues": AudioService.list_cues(db, projectId)}


@router.post("/lipsync/generate")
def lipsync_generate(body: LipsyncBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("lipsync_production_v1")
    return LipsyncService.generate(
        db,
        project_id=body.projectId,
        audio_asset_id=body.audioAssetId,
        video_asset_id=body.videoAssetId,
        scene_id=body.sceneId,
        owner=body.owner,
    )


@router.post("/lipsync/mouth-track")
def lipsync_mouth_track(body: MouthTrackBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("lipsync_production_v1")
    return LipsyncService.mouth_track(
        db,
        project_id=body.projectId,
        video_asset_id=body.videoAssetId,
        scene_id=body.sceneId,
        owner=body.owner,
    )


@router.post("/lipsync/mouth-rectangle")
def lipsync_mouth_rect(body: MouthRectBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("lipsync_production_v1")
    return LipsyncService.mouth_rectangle(
        db, project_id=body.projectId, rectangles=body.rectangles
    )


@router.post("/timeline/propose")
def timeline_propose(body: TimelineProposeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("director_timeline_v1")
    return TimelineService.propose(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        clips=body.clips,
        notes=body.notes,
        bible_mutations=body.bibleMutations,
        branch=body.branch,
    )


@router.post("/timeline/{proposal_id}/approve")
def timeline_approve(proposal_id: str, body: ActorBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("director_timeline_v1")
    try:
        return TimelineService.approve(db, proposal_id, actor=body.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="proposal not found") from None


@router.post("/timeline/{proposal_id}/reject")
def timeline_reject(proposal_id: str, body: ActorBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("director_timeline_v1")
    try:
        return TimelineService.reject(db, proposal_id, actor=body.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="proposal not found") from None


@router.post("/timeline/{proposal_id}/apply")
def timeline_apply(proposal_id: str, body: ActorBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("director_timeline_v1")
    try:
        return TimelineService.apply(db, proposal_id, actor=body.actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="proposal not found") from None


@router.post("/editing/propose")
def editing_propose(body: EditProposeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("editing_production_v1")
    return EditingService.propose_edit(
        db, project_id=body.projectId, ops=body.ops, scene_id=body.sceneId
    )


@router.post("/editing/apply")
def editing_apply(body: EditApplyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("editing_production_v1")
    try:
        return EditingService.apply_edit(
            db,
            project_id=body.projectId,
            ops=body.ops,
            approved=body.approved,
            scene_id=body.sceneId,
            owner=body.owner,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.post("/editing/sfx-cue")
def editing_sfx(body: CueProposeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("editing_production_v1", "audio_production_v1")
    return EditingService.propose_sfx_cue(
        db,
        project_id=body.projectId,
        prompt=body.prompt,
        scene_id=body.sceneId,
        owner=body.owner,
        start_sec=body.startSec,
        duration_sec=body.durationSec,
    )


@router.post("/editing/music-cue")
def editing_music(body: CueProposeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("editing_production_v1", "audio_production_v1")
    return EditingService.propose_music_cue(
        db,
        project_id=body.projectId,
        prompt=body.prompt,
        scene_id=body.sceneId,
        owner=body.owner,
        start_sec=body.startSec,
        duration_sec=body.durationSec,
    )


@router.post("/render")
def render(body: RenderBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("render_production_v1")
    return RenderService.render(
        db,
        project_id=body.projectId,
        kind=body.kind,
        manifest_id=body.manifestId,
        scene_id=body.sceneId,
        owner=body.owner,
        manifest=body.manifest,
    )


@router.get("/render/{manifest_id}")
def render_get(manifest_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("render_production_v1")
    out = RenderService.get_manifest(db, manifest_id)
    if not out:
        raise HTTPException(status_code=404, detail="manifest not found")
    return out


@router.post("/control/decompose")
def control_decompose(body: ControlBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("codirector_production_control_v1")
    return ControlService.decompose(
        db,
        project_id=body.projectId,
        request_text=body.requestText,
        enqueue=body.enqueue,
        owner=body.owner,
        scene_id=body.sceneId,
    )


@router.get("/control/{plan_id}")
def control_get(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("codirector_production_control_v1")
    out = ControlService.get_plan(db, plan_id)
    if not out:
        raise HTTPException(status_code=404, detail="plan not found")
    return out


@router.post("/control/plans/{plan_id}/resume")
def control_resume(plan_id: str, body: Optional[ActorBody] = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require("codirector_production_control_v1")
    actor = body.actor if body else "user"
    try:
        return ControlService.resume(db, plan_id, owner=actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="plan not found") from None
