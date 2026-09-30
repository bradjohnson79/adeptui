"""HTTP API for M42 W46 Director Timeline Master."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from . import orchestrator, service
from .contracts import CancelRequest
from .production_gate import evaluate_director_timeline_gate
from .creator_batch_surface import INTERNAL_RUNTIME_ONLY

router = APIRouter(prefix="/director-timeline", tags=["director-timeline-w46"])


@router.get("/gate")
def get_gate():
    return evaluate_director_timeline_gate()


@router.get("/generators")
def get_generators():
    return service.generators()


@router.get("/camera-catalog")
def get_camera_catalog():
    return service.camera_catalog()


@router.get("/projects/{project_id}/scenes/{scene_id}/master")
def get_master(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    result = service.workspace(db, project_id, scene_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


class LibraryAssetsBody(BaseModel):
    libraryAssetIds: list[str] = Field(default_factory=list)


@router.put("/projects/{project_id}/scenes/{scene_id}/library-assets")
def put_library_assets(
    project_id: str,
    scene_id: str,
    body: LibraryAssetsBody,
    db: Session = Depends(get_db),
):
    result = service.set_library_asset_ids(db, project_id, scene_id, body.libraryAssetIds)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


class MasterBody(BaseModel):
    master: dict[str, Any]


@router.put("/projects/{project_id}/scenes/{scene_id}/master")
def put_master(project_id: str, scene_id: str, body: MasterBody, db: Session = Depends(get_db)):
    result = service.put_master(db, project_id, scene_id, body.master)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "Update failed")
    return result


class SceneMetadataBody(BaseModel):
    promptIntelligence: dict[str, Any] | None = None


@router.patch("/projects/{project_id}/scenes/{scene_id}/metadata")
def patch_scene_metadata(
    project_id: str,
    scene_id: str,
    body: SceneMetadataBody,
    db: Session = Depends(get_db),
):
    payload = body.model_dump(exclude_none=True)
    result = service.patch_scene_metadata(db, project_id, scene_id, payload)
    if not result.get("ok"):
        status = 404 if result.get("error") == "SCENE_NOT_FOUND" else 400
        raise HTTPException(status, result.get("error") or "Metadata update failed")
    return result


class DismissFailureBody(BaseModel):
    jobId: str


@router.post("/projects/{project_id}/scenes/{scene_id}/dismiss-failure")
def dismiss_failure(project_id: str, scene_id: str, body: DismissFailureBody, db: Session = Depends(get_db)):
    result = service.dismiss_failure(db, project_id, scene_id, body.jobId)
    if not result.get("ok"):
        status = 404 if result.get("error") in {"NOT_FOUND", "SCENE_NOT_FOUND"} else 400
        raise HTTPException(status, result.get("error") or "Dismiss failed")
    return result


class AddBatchBody(BaseModel):
    label: Optional[str] = None
    #: None = caller did not choose -> service seeds by generator law
    #: (MiniMax H3 / blank / "auto" -> 15.0s, other generators -> 5.0s).
    plannedDuration: Optional[float] = None
    generatorId: Optional[str] = None
    atOrder: Optional[int] = None


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def add_batch(project_id: str, scene_id: str, body: AddBatchBody, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/duplicate",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def duplicate_batch(project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, batch_id, db)
    _film_timeline_only()


@router.delete(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def delete_batch(project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, batch_id, db)
    _film_timeline_only()



class RematerializeExecutionWindowsBody(BaseModel):
    windows: list[dict[str, float]] | None = None
    plan: dict[str, Any] | None = None
    generatorId: str | None = None
    durationSeconds: float | None = None
    allowSceneTakeId: str | None = None
    allowRevision: int | None = None
    previousSceneTakeId: str | None = None
    force: bool = False


class PatchBatchBody(BaseModel):
    label: Optional[str] = None
    generatorId: Optional[str] = None
    # Shared LoRA registry selection ({loraId, name, strength}); None = baseline.
    lora: Optional[dict[str, Any]] = None
    plannedDuration: Optional[float] = None
    promptSegments: Optional[list[dict[str, Any]]] = None
    sourceAnchors: Optional[list[dict[str, Any]]] = None
    references: Optional[list[dict[str, Any]]] = None
    repairRanges: Optional[list[dict[str, Any]]] = None
    visualClips: Optional[list[dict[str, Any]]] = None
    audioClips: Optional[list[dict[str, Any]]] = None
    sfxClips: Optional[list[dict[str, Any]]] = None
    cameraInstructions: Optional[list[dict[str, Any]]] = None
    # MiniMax H3 megapixel resolution intent ({mode: auto|manual, megapixels}).
    h3Resolution: Optional[dict[str, Any]] = None
    # LTX 2.5 Timeline QUALITY tier ("720p"|"1080p"|"2K"|"4K"); independent of H3.
    ltxQuality: Optional[str] = None


class AddClipBody(BaseModel):
    kind: Literal["image", "video", "audio", "sfx", "camera"]
    assetId: Optional[str] = None
    start: float = 0.0
    length: float = 5.0
    trimStart: float = 0.0
    label: str = ""
    role: Optional[str] = None
    volume: float = 1.0
    muted: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    motion_type: Optional[str] = None
    rig: Optional[str] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/clips")
def add_clip_to_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: AddClipBody,
    db: Session = Depends(get_db),
):
    """Retired. Add to Timeline is the production insertion path."""
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()




@router.post("/projects/{project_id}/scenes/{scene_id}/execution-windows/rematerialize")
def rematerialize_execution_windows_route(
    project_id: str,
    scene_id: str,
    body: RematerializeExecutionWindowsBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()


@router.patch(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def patch_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: PatchBatchBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()
class ModeBody(BaseModel):
    mode: Literal["image_planning", "video_finishing"]


@router.post("/projects/{project_id}/scenes/{scene_id}/mode")
def set_mode(project_id: str, scene_id: str, body: ModeBody, db: Session = Depends(get_db)):
    return service.set_mode(db, project_id, scene_id, body.mode)


@router.post("/projects/{project_id}/scenes/{scene_id}/stitch")
def stitch_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, db)
    _film_timeline_only()


class ExtendBody(BaseModel):
    prompt: Optional[str] = None
    durationSec: Optional[float] = None
    force: bool = False


def _film_timeline_only() -> None:
    raise HTTPException(
        410,
        {
            "error": "FILM_TIMELINE_REQUIRED",
            "message": "This Timeline action now runs through Film Timeline. Use Generate Shot, Continue Shot, or Add to Timeline.",
        },
    )


@router.post("/projects/{project_id}/scenes/{scene_id}/extend")
def extend_scene(project_id: str, scene_id: str, body: ExtendBody, db: Session = Depends(get_db)):
    """Retired. Continue Shot is the production continuation path."""
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()


class ExtendRetakeBody(BaseModel):
    prompt: Optional[str] = None
    durationSec: Optional[float] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/extend-segments/{segment_id}/retake")
def retake_extend_segment(
    project_id: str, scene_id: str, segment_id: str, body: ExtendRetakeBody, db: Session = Depends(get_db)
):
    """Retired. Regenerate the Film Timeline segment instead."""
    _ = (project_id, scene_id, segment_id, body, db)
    _film_timeline_only()


class GenerateBody(BaseModel):
    scope: Literal["current", "selected", "ready", "full"] = "full"
    batchBlockIds: list[str] = Field(default_factory=list)
    draftMode: Optional[bool] = None


class GenerateBatchBody(BaseModel):
    draftMode: Optional[bool] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/generate")
def generate_scene(project_id: str, scene_id: str, body: GenerateBody, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()


@router.get("/projects/{project_id}/scenes/{scene_id}/scene-takes")
def list_scene_takes(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    result = service.workspace(db, project_id, scene_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    from .contracts import SceneTimelineMaster
    from .scene_takes import list_scene_takes_payload

    master = SceneTimelineMaster.model_validate(result["master"])
    return list_scene_takes_payload(master)


class CreateSceneTakeBody(BaseModel):
    intent: str | None = None
    reason: str | None = None


@router.post("/projects/{project_id}/scenes/{scene_id}/scene-takes")
def create_scene_take(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
    body: CreateSceneTakeBody = Body(default_factory=CreateSceneTakeBody),
    intent: str | None = None,
):
    """Mint a SceneTake. intent=execution_revision = lightweight (no generate)."""
    intent = str(intent or body.intent or "").strip().lower()
    if intent in {"execution_revision", "begin_execution_revision", "mint_only"}:
        from .scene_takes import begin_execution_revision_for_scene

        result = begin_execution_revision_for_scene(
            db,
            project_id,
            scene_id,
            reason=str(body.reason or "generator_switch_window_topology_change"),
        )
    else:
        from .scene_takes import start_new_take

        result = start_new_take(db, project_id, scene_id)
    if not result.get("ok"):
        raise HTTPException(400, {"error": result.get("error"), "message": result.get("message")})
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/scene-takes/{take_id}/make-current")
def make_scene_take_current(project_id: str, scene_id: str, take_id: str, db: Session = Depends(get_db)):
    from .scene_takes import make_current_take

    result = make_current_take(db, project_id, scene_id, take_id)
    if not result.get("ok"):
        raise HTTPException(400, {"error": result.get("error"), "message": result.get("message")})
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/scene-takes/{take_id}/resume")
def resume_scene_take_route(project_id: str, scene_id: str, take_id: str, db: Session = Depends(get_db)):
    from .scene_takes import resume_scene_take

    result = resume_scene_take(db, project_id, scene_id, take_id)
    if not result.get("ok"):
        raise HTTPException(400, {"error": result.get("error"), "message": result.get("message")})
    return result


@router.delete("/projects/{project_id}/scenes/{scene_id}/scene-takes/{take_id}")
def delete_scene_take_route(project_id: str, scene_id: str, take_id: str, db: Session = Depends(get_db)):
    from .scene_takes import delete_scene_take

    result = delete_scene_take(db, project_id, scene_id, take_id)
    if not result.get("ok"):
        raise HTTPException(400, {"error": result.get("error"), "message": result.get("message")})
    return result


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/generate",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def generate_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: GenerateBatchBody | None = Body(default=None),
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/qc-retry")
def qc_retry_batch(project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, batch_id, db)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/reconcile-generation")
def reconcile_generation(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, db)
    _film_timeline_only()
@router.get("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/reference-transport")
def inspect_reference_transport(
    project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)
):
    """Diagnostic: Timeline References → Direct Transport → intended Comfy sockets."""
    from . import store
    from .contracts import SceneTimelineMaster
    from .generation.direct_reference import inspect_direct_reference

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        raise HTTPException(404, payload.get("error") or "Not found")
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((item for item in master.batchBlocks if item.id == batch_id), None)
    if batch is None:
        raise HTTPException(404, "BATCH_NOT_FOUND")
    return inspect_direct_reference(
        db,
        project_id=project_id,
        scene_id=scene_id,
        batch=batch,
        generator_id=batch.generatorId,
    )


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/workflow-export")
def export_batch_workflow_route(
    project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)
):
    """Developer-only inspection export (Phase 4). Builds the real request +
    ComfyUI graph for the batch without queueing/executing anything, and
    writes workflow/api/bindings/fingerprints artifacts under
    data/runtime/exports/. Env-gated by ADEPT_TIMELINE_WORKFLOW_EXPORT=1.
    """
    from .workflow_export import WorkflowExportError, export_batch_workflow, export_enabled

    if not export_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return export_batch_workflow(db, project_id, scene_id, batch_id)
    except WorkflowExportError as exc:
        status = 404 if exc.code in {"NOT_FOUND", "BATCH_NOT_FOUND"} else 422
        raise HTTPException(status_code=status, detail={"error": exc.code, "message": str(exc)}) from exc


class CompleteBody(BaseModel):
    assetId: str
    generatedDuration: float
    executionSnapshotId: str


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/complete",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def complete_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: CompleteBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()
class ApproveBody(BaseModel):
    candidateId: str


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/approve",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def approve_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: ApproveBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()
class RejectBody(BaseModel):
    candidateId: str


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/reject",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def reject_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RejectBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/cancel")
def cancel(project_id: str, scene_id: str, body: CancelRequest, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()
class RepairBody(BaseModel):
    start: float = 0.0
    length: float = 1.0
    mode: str = "range"
    inPaintStrategy: str = "range_replacement"
    label: str = ""
    policy: Optional[str] = None


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/repair-ranges",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def add_repair(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RepairBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()
@router.get("/projects/{project_id}/scenes/{scene_id}/preflight")
def preflight(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, db)
    _film_timeline_only()
@router.get("/projects/{project_id}/scenes/{scene_id}/snapshots/{snapshot_id}")
def get_snapshot(project_id: str, scene_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    result = service.snapshot_get(db, project_id, scene_id, snapshot_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


class DurationBody(BaseModel):
    """Duration-check request. plannedDuration is required - no silent 5.0 steal."""

    generatorId: Optional[str] = None
    plannedDuration: float  # required; omit => 422 (do not default to 5.0)


@router.post("/duration-check")
def duration_check(body: DurationBody):
    return service.duration_check(body.generatorId, body.plannedDuration)


@router.get("/tools")
def timeline_tools():
    from .timeline_tools import tool_catalog

    return tool_catalog()


class TimelineToolBody(BaseModel):
    toolId: str
    projectId: str
    sceneId: str
    args: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False


@router.post("/tools/dispatch")
def timeline_tools_dispatch(body: TimelineToolBody, db: Session = Depends(get_db)):
    from .timeline_tools import dispatch

    return dispatch(
        db,
        tool_id=body.toolId,
        project_id=body.projectId,
        scene_id=body.sceneId,
        args=body.args,
        approved=body.approved,
    )


class RetakeBody(BaseModel):
    mode: str = "directed"
    userCorrection: dict[str, Any] = Field(default_factory=dict)
    continuityAware: Optional[bool] = None


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/retake",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def retake_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RetakeBody,
    db: Session = Depends(get_db),
):
    """Retired. Regenerate the Film Timeline segment."""
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()


class RetakeRangeBody(BaseModel):
    start: float
    length: float
    prompt: str = ""
    spendApiCredits: bool = False
    maskPngBase64: Optional[str] = None
    referenceFrameTime: Optional[float] = None
    frameAssetId: Optional[str] = None
    removeBackground: bool = False


class RepairFrameBody(BaseModel):
    atSeconds: Optional[float] = None


class RepairInpaintSubmitBody(BaseModel):
    prompt: str
    maskPngBase64: str
    atSeconds: Optional[float] = None
    frameAssetId: Optional[str] = None


class RepairInpaintApplyBody(BaseModel):
    jobId: Optional[str] = None
    repairedAssetId: Optional[str] = None


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/retake-range",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def retake_range(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RetakeRangeBody,
    db: Session = Depends(get_db),
):
    """Retired. Regenerate the Film Timeline segment."""
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()


class PlaceVisualImageRangeBody(BaseModel):
    markIn: float
    markOut: float
    imageAssetId: str
    placementId: Optional[str] = None
    batchId: Optional[str] = None
    sourceAssetId: Optional[str] = None
    label: Optional[str] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/place-visual-image-range")
def place_visual_image_range(
    project_id: str,
    scene_id: str,
    body: PlaceVisualImageRangeBody,
    db: Session = Depends(get_db),
):
    """Retired. Add to Timeline places an image as a reference or still."""
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/repair-ranges/{repair_id}/extract-frame"
)
def extract_repair_frame(
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    body: RepairFrameBody = Body(default_factory=RepairFrameBody),
    db: Session = Depends(get_db),
):
    from .inpaint_repair import extract_repair_frame as extract_frame

    return extract_frame(
        db,
        project_id,
        scene_id,
        batch_id,
        repair_id,
        at_seconds=body.atSeconds,
    )


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/repair-ranges/{repair_id}/inpaint"
)
def submit_inpaint_repair(
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    body: RepairInpaintSubmitBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, repair_id, body, db)
    _film_timeline_only()


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/repair-ranges/{repair_id}/apply-inpaint"
)
def apply_inpaint_repair(
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    body: RepairInpaintApplyBody = Body(default_factory=RepairInpaintApplyBody),
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, repair_id, body, db)
    _film_timeline_only()


class ContinuityPolicyBody(BaseModel):
    configuredTailDuration: float = 0.0


class CoDirectorContinuityPolicyBody(BaseModel):
    enabled: bool | None = None
    reviewCadence: str | None = None
    protection: str | None = None
    fastVisionModel: str | None = None
    deepReview: str | None = None
    showDebugState: bool | None = None
    creatorNextBatchNote: str | None = None


class RejectTemporalBody(BaseModel):
    packetId: str
    manualNote: str | None = None


@router.post("/projects/{project_id}/scenes/{scene_id}/continuity-policy")
def set_continuity_policy(
    project_id: str,
    scene_id: str,
    body: ContinuityPolicyBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/codirector-continuity-policy")
def set_codirector_continuity_policy(
    project_id: str,
    scene_id: str,
    body: CoDirectorContinuityPolicyBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/temporal-continuity/reject")
def reject_temporal_continuation(
    project_id: str,
    scene_id: str,
    body: RejectTemporalBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()
@router.get("/projects/{project_id}/scenes/{scene_id}/temporal-continuity")
def get_temporal_continuity(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    from .store import load_master

    result = load_master(db, project_id, scene_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Scene not found")
    master = result.get("master") or {}
    return {
        "ok": True,
        "coDirectorContinuityPolicy": master.get("coDirectorContinuityPolicy"),
        "temporalPackets": master.get("temporalPackets") or [],
        "mock": False,
    }


class ActivateTakeBody(BaseModel):
    candidateId: str


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/activate-take",
    deprecated=True,
    summary=INTERNAL_RUNTIME_ONLY,
)
def activate_take(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: ActivateTakeBody,
    db: Session = Depends(get_db),
):
    _ = (project_id, scene_id, batch_id, body, db)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/bridges/{bridge_id}/retry")
def retry_bridge(project_id: str, scene_id: str, bridge_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, db, bridge_id)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/bridges/{bridge_id}/continue-without")
def continue_without_bridge(
    project_id: str, scene_id: str, bridge_id: str, db: Session = Depends(get_db)
):
    _ = (project_id, scene_id, db, bridge_id)
    _film_timeline_only()
class ReconcileBody(BaseModel):
    spendApiCredits: bool = False


@router.post("/projects/{project_id}/scenes/{scene_id}/reconcile-downstream")
def reconcile_downstream(
    project_id: str, scene_id: str, body: ReconcileBody, db: Session = Depends(get_db)
):
    _ = (project_id, scene_id, body, db)
    _film_timeline_only()
@router.post("/projects/{project_id}/scenes/{scene_id}/keep-existing-downstream")
def keep_existing_downstream(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    _ = (project_id, scene_id, db)
    _film_timeline_only()
def _require_stub():
    from .generation.adapters.stub_cert import stub_enabled

    if not stub_enabled():
        raise HTTPException(404, "Not found")


class StubJobStateBody(BaseModel):
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    outputAssetIds: Optional[list[str]] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None


@router.post("/cert/stub-jobs/{job_id}/state")
def cert_set_stub_job_state(job_id: str, body: StubJobStateBody):
    _require_stub()
    from .generation.adapters.stub_cert import set_stub_job_state

    return set_stub_job_state(
        job_id,
        body.state,
        output_asset_ids=body.outputAssetIds,
        error_code=body.errorCode,
        error_message=body.errorMessage,
    )


@router.get("/cert/stub-jobs/{job_id}/state")
def cert_get_stub_job_state(job_id: str):
    _require_stub()
    from .generation.adapters.stub_cert import get_stub_job_state

    entry = get_stub_job_state(job_id)
    if entry is None:
        raise HTTPException(404, "Stub job not found")
    return {"ok": True, "jobId": job_id, **entry}


@router.get("/cert/requests")
def cert_read_requests():
    _require_stub()
    from .generation.adapters.stub_cert import read_request_sink

    return {"ok": True, "requests": read_request_sink()}


@router.post("/cert/reset")
def cert_reset():
    _require_stub()
    from .generation.adapters.stub_cert import clear_cert_sink

    clear_cert_sink()
    return {"ok": True}


class CertSeedFailedJobBody(BaseModel):
    projectId: str
    sceneId: str
    message: str = "simulated failure (cert seed)"


@router.post("/cert/seed-failed-job")
def cert_seed_failed_job(body: CertSeedFailedJobBody, db: Session = Depends(get_db)):
    """Cert-only: insert a terminal failed render_scene Job row so UI tests can
    exercise the REAL Preview Monitor failure path (jobs table → overlay). The
    stub adapter deliberately never creates Job rows (queue_worker would execute
    them for real), so monitor-level failure UX cannot be certified through
    stub generation alone. Only mounted when ADEPT_TIMELINE_CERT_STUB=1."""
    _require_stub()
    import json as _json
    import uuid as _uuid

    from ..db import Job

    job_id = str(_uuid.uuid4())
    db.add(
        Job(
            id=job_id,
            project_id=body.projectId,
            scene_id=body.sceneId,
            kind="render_scene",
            status="failed",
            progress=0.0,
            message=body.message,
            stage="failed",
            params_json=_json.dumps({"engine": "ltx", "timelineGeneration": True, "certSeed": True}),
        )
    )
    db.commit()
    return {"ok": True, "jobId": job_id}


class OmniExportVideoBody(BaseModel):
    assetId: str
    label: str | None = None
    sourceSurface: str | None = Field(default=None, description="one-frame | three-frame | omni")


@router.post("/projects/{project_id}/scenes/{scene_id}/export-video-to-timeline")
def export_video_to_timeline(
    project_id: str,
    scene_id: str,
    body: OmniExportVideoBody,
    db: Session = Depends(get_db),
):
    """Wave 2B: deposit a completed Library VIDEO onto Timeline Visual.

    No regeneration. Rejects non-video assets (image = reference under Omni law).
    """
    from .generation.omni_visual_export import export_completed_video_to_timeline

    result = export_completed_video_to_timeline(
        db,
        project_id,
        scene_id,
        body.assetId,
        label=body.label,
        source_surface=body.sourceSurface,
    )
    if not result.get("ok"):
        code = str(result.get("error") or "EXPORT_FAILED")
        status = 404 if code in {"SCENE_NOT_FOUND", "ASSET_OWNERSHIP", "BATCH_NOT_FOUND"} else 400
        raise HTTPException(status_code=status, detail=result)
    return result


class SpokenLanguageBody(BaseModel):
    """Explicit project spoken language (NOT UI locale)."""

    language: str = Field(..., description="BCP-47 / registry code, e.g. en")
    source: str = Field(default="explicit", description="writer attribution")


@router.get("/projects/{project_id}/spoken-language")
def get_spoken_language(project_id: str, db: Session = Depends(get_db)):
    """Read project spokenLanguage authority (UI-isolated)."""
    from .generation.dialogue_authority import (
        ensure_spoken_language_authority,
        load_project_settings_json,
        read_project_spoken_language,
        read_ui_language_blob,
    )

    raw = load_project_settings_json(db, project_id)
    spoken = read_project_spoken_language(raw)
    ui = read_ui_language_blob(raw)
    auth = ensure_spoken_language_authority(db, project_id, master=None, persist_promote=False)
    return {
        "ok": True,
        "projectId": project_id,
        "spokenLanguage": {"projectLanguage": spoken} if spoken else None,
        "uiLanguage": ui,
        "authority": auth,
        "mock": False,
    }


@router.put("/projects/{project_id}/spoken-language")
def put_spoken_language(
    project_id: str,
    body: SpokenLanguageBody,
    db: Session = Depends(get_db),
):
    """Persist explicit project spokenLanguage. Never writes UI locale fields."""
    from .generation.dialogue_authority import (
        load_project_settings_json,
        read_project_spoken_language,
        save_project_settings_json,
        write_project_spoken_language,
    )

    try:
        raw = load_project_settings_json(db, project_id)
        new_settings = write_project_spoken_language(raw or "{}", body.language, source=body.source)
        save_project_settings_json(db, project_id, new_settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "error": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=404 if "PROJECT_NOT_FOUND" in str(exc) else 400,
            detail={"ok": False, "error": str(exc)},
        ) from exc
    return {
        "ok": True,
        "projectId": project_id,
        "spokenLanguage": {"projectLanguage": read_project_spoken_language(new_settings)},
        "mock": False,
    }


class SceneSpokenLanguageBody(BaseModel):
    language: str = Field(..., description="Scene spoken language override")


@router.put("/projects/{project_id}/scenes/{scene_id}/spoken-language")
def put_scene_spoken_language(
    project_id: str,
    scene_id: str,
    body: SceneSpokenLanguageBody,
    db: Session = Depends(get_db),
):
    """Persist sceneLanguage on SceneTimelineMaster (line→scene→project ladder)."""
    from . import store
    from .contracts import SceneTimelineMaster
    from .generation.dialogue_authority import (
        read_scene_spoken_language,
        write_scene_spoken_language,
        _norm_lang,
    )

    lang = _norm_lang(body.language)
    if not lang:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "SPOKEN_LANGUAGE_REQUIRED"})
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        raise HTTPException(status_code=404, detail=payload)
    try:
        master = SceneTimelineMaster.model_validate(payload["master"])
        write_scene_spoken_language(master, lang, source="explicit")
        from .generation.dialogue_authority import drop_dialogue_manifests

        drop_dialogue_manifests(master)
        # save_master returns SceneTimelineMaster, not {ok: True}.
        # The Scene 12B residual 500 was saved.get("ok") after persist.
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
    except ValueError as exc:
        code = 404 if "NOT_FOUND" in str(exc) else 400
        raise HTTPException(status_code=code, detail={"ok": False, "error": str(exc)}) from exc
    persisted = read_scene_spoken_language(master) or lang
    spoken_blob = getattr(master, "spokenLanguage", None)
    if not isinstance(spoken_blob, dict):
        spoken_blob = {"sceneLanguage": persisted, "source": "explicit"}
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "sceneLanguage": persisted,
        "spokenLanguage": spoken_blob,
        "mock": False,
    }


class FinalCheckDecisionBody(BaseModel):
    decision: Literal[
        "repair_automatically",
        "review_first",
        "keep_current",
        "decline",
        "dismiss",
        "auto_retake",
    ]
    runtimeKind: Optional[Literal["local", "api"]] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/final-check/open")
def open_final_check(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    result = service.open_or_refresh_final_check(db, project_id, scene_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/final-check/decision")
def final_check_decision(
    project_id: str,
    scene_id: str,
    body: FinalCheckDecisionBody,
    db: Session = Depends(get_db),
):
    result = service.final_check_decision(
        db, project_id, scene_id, body.decision, runtime_kind=body.runtimeKind
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "Decision failed")
    return result



class PublishBody(BaseModel):
    update: bool = False
    expectedVersion: Optional[int] = None
    source: Literal["stitch", "upscaled", "published"] = "stitch"


class MagiUpscaleBody(BaseModel):
    engine: str = "ffmpeg-scale"
    model: str = "lanczos"
    targetResolution: str = ""
    assetId: Optional[str] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/publish")
def publish_scene(project_id: str, scene_id: str, body: PublishBody = Body(default=PublishBody()), db: Session = Depends(get_db)):
    """Explicit Video Published Master register. Never auto-called from stitch/pass."""
    result = service.publish_scene(
        db,
        project_id,
        scene_id,
        update=bool(body.update),
        expected_version=body.expectedVersion,
        source=body.source,
    )
    if not result.get("ok"):
        code = 400
        if result.get("error") == "SCENE_NOT_FOUND":
            code = 404
        raise HTTPException(
            status_code=code,
            detail={
                "ok": False,
                "error": result.get("error"),
                "creatorMessage": result.get("creatorMessage")
                or result.get("error")
                or "Publish failed",
                "detail": result.get("detail"),
            },
        )
    return result


@router.get("/projects/{project_id}/scenes/{scene_id}/magi-upscale/options")
def magi_upscale_options(project_id: str, scene_id: str, assetId: Optional[str] = None, db: Session = Depends(get_db)):
    result = service.magi_upscale_options(db, project_id, scene_id, asset_id=assetId)
    if not result.get("ok"):
        code = 404 if result.get("error") == "SCENE_NOT_FOUND" else 400
        raise HTTPException(
            status_code=code,
            detail={
                "ok": False,
                "error": result.get("error"),
                "creatorMessage": result.get("creatorMessage") or result.get("error") or "MAGI options failed",
                "detail": result.get("detail"),
            },
        )
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/magi-upscale")
def magi_upscale_scene(project_id: str, scene_id: str, body: MagiUpscaleBody = Body(default=MagiUpscaleBody()), db: Session = Depends(get_db)):
    """Timeline MAGI entry: full stitch / published master only. No auto-publish."""
    result = service.magi_upscale_full_stitch(
        db,
        project_id,
        scene_id,
        engine=body.engine,
        model=body.model,
        target_resolution=body.targetResolution,
        asset_id=body.assetId,
    )
    if not result.get("ok"):
        code = 400
        if result.get("error") == "SCENE_NOT_FOUND":
            code = 404
        raise HTTPException(
            status_code=code,
            detail={
                "ok": False,
                "error": result.get("error"),
                "creatorMessage": result.get("creatorMessage")
                or result.get("error")
                or "MAGI upscale failed",
                "detail": result.get("detail"),
            },
        )
    return result


def _reference_http(err: Any) -> HTTPException:
    status = 404
    if err.code == "feature_disabled":
        status = 404
    elif err.code in ("version_conflict", "reference_cycle_detected"):
        status = 409
    elif err.code in ("invalid_reference_role", "invalid_influence"):
        status = 400
    return HTTPException(status_code=status, detail=err.to_dict())


@router.get("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/references")
def get_item_references(project_id: str, scene_id: str, item_id: str, db: Session = Depends(get_db)):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    try:
        return TimelineReferenceService(db).get_references(project_id, scene_id, item_id)
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.post("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/references")
def add_item_reference(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    try:
        return TimelineReferenceService(db).add_binding(
            project_id,
            scene_id,
            item_id,
            reference_asset_id=str(body.get("referenceAssetId") or ""),
            role=str(body.get("role") or "other"),
            influence=str(body.get("influence") or "moderate"),
            source=str(body.get("source") or "project_asset"),
            bible_entity_stable_id=body.get("bibleEntityStableId"),
            bible_version_id=body.get("bibleVersionId"),
            source_timeline_item_id=body.get("sourceTimelineItemId"),
            label=str(body.get("label") or ""),
            notes=str(body.get("notes") or ""),
        )
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.patch("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/references/{binding_id}")
def patch_item_reference(
    project_id: str,
    scene_id: str,
    item_id: str,
    binding_id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    try:
        return TimelineReferenceService(db).patch_binding(
            project_id,
            scene_id,
            item_id,
            binding_id,
            role=body.get("role"),
            influence=body.get("influence"),
            label=body.get("label"),
            notes=body.get("notes"),
            sort_order=body.get("sortOrder"),
            expected_version=body.get("expectedVersion"),
        )
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.delete("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/references/{binding_id}")
def delete_item_reference(
    project_id: str,
    scene_id: str,
    item_id: str,
    binding_id: str,
    db: Session = Depends(get_db),
):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    try:
        return TimelineReferenceService(db).delete_binding(project_id, scene_id, item_id, binding_id)
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.post("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/references/clear")
def clear_item_references(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    body = body or {}
    try:
        return TimelineReferenceService(db).clear(
            project_id,
            scene_id,
            item_id,
            expected_version=body.get("expectedVersion"),
        )
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.get("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/reference-package")
def get_item_reference_package(project_id: str, scene_id: str, item_id: str, db: Session = Depends(get_db)):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.package import ReferencePackageBuilder

    try:
        return ReferencePackageBuilder(db).build(project_id, scene_id, item_id)
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.post("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/references/continuity-previous")
def continuity_previous_item(project_id: str, scene_id: str, item_id: str, db: Session = Depends(get_db)):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    try:
        return TimelineReferenceService(db).continuity_previous(project_id, scene_id, item_id)
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc


@router.post("/projects/{project_id}/scenes/{scene_id}/items/{item_id}/reference-presets/apply")
def apply_item_reference_preset(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    from ..director_references.errors import DirectorReferenceError
    from ..director_references.service import TimelineReferenceService

    try:
        return TimelineReferenceService(db).apply_preset(
            project_id,
            scene_id,
            item_id,
            str(body.get("presetId") or ""),
            mode=str(body.get("mode") or "replace"),
            expected_version=body.get("expectedVersion"),
        )
    except DirectorReferenceError as exc:
        raise _reference_http(exc) from exc
