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


class MasterBody(BaseModel):
    master: dict[str, Any]


@router.put("/projects/{project_id}/scenes/{scene_id}/master")
def put_master(project_id: str, scene_id: str, body: MasterBody, db: Session = Depends(get_db)):
    result = service.put_master(db, project_id, scene_id, body.master)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "Update failed")
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
    plannedDuration: float = 5.0
    generatorId: Optional[str] = None
    atOrder: Optional[int] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/batches")
def add_batch(project_id: str, scene_id: str, body: AddBatchBody, db: Session = Depends(get_db)):
    return service.add_batch(
        db,
        project_id,
        scene_id,
        label=body.label,
        planned_duration=body.plannedDuration,
        generator_id=body.generatorId,
        at_order=body.atOrder,
    )


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/duplicate")
def duplicate_batch(project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)):
    result = service.duplicate_batch(db, project_id, scene_id, batch_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


@router.delete("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}")
def delete_batch(project_id: str, scene_id: str, batch_id: str, db: Session = Depends(get_db)):
    result = service.delete_batch(db, project_id, scene_id, batch_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


class PatchBatchBody(BaseModel):
    label: Optional[str] = None
    generatorId: Optional[str] = None
    plannedDuration: Optional[float] = None
    promptSegments: Optional[list[dict[str, Any]]] = None
    sourceAnchors: Optional[list[dict[str, Any]]] = None
    references: Optional[list[dict[str, Any]]] = None
    repairRanges: Optional[list[dict[str, Any]]] = None
    visualClips: Optional[list[dict[str, Any]]] = None
    audioClips: Optional[list[dict[str, Any]]] = None
    sfxClips: Optional[list[dict[str, Any]]] = None
    cameraInstructions: Optional[list[dict[str, Any]]] = None


class AddClipBody(BaseModel):
    kind: Literal["image", "video", "audio", "sfx", "camera"]
    assetId: Optional[str] = None
    start: float = 0.0
    length: float = 5.0
    trimStart: float = 0.0
    label: str = ""
    role: Optional[str] = None
    volume: float = 1.0
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
    """Append a clip to a specific batch's owned clip array (BATCH_OWNED_CLIPS).

    Adding media to one batch never mutates or deletes another batch's clips.
    """
    return orchestrator.add_clip_to_batch(db, project_id, scene_id, batch_id, body.model_dump())


@router.patch("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}")
def patch_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: PatchBatchBody,
    db: Session = Depends(get_db),
):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    # Map camelCase plannedDuration already in body
    if "plannedDuration" in patch:
        pass
    return orchestrator.touch_batch_config(db, project_id, scene_id, batch_id, patch)


class ModeBody(BaseModel):
    mode: Literal["image_planning", "video_finishing"]


@router.post("/projects/{project_id}/scenes/{scene_id}/mode")
def set_mode(project_id: str, scene_id: str, body: ModeBody, db: Session = Depends(get_db)):
    return service.set_mode(db, project_id, scene_id, body.mode)


class GenerateBody(BaseModel):
    scope: Literal["current", "selected", "ready", "full"] = "full"
    batchBlockIds: list[str] = Field(default_factory=list)
    draftMode: Optional[bool] = None


class GenerateBatchBody(BaseModel):
    draftMode: Optional[bool] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/generate")
def generate_scene(project_id: str, scene_id: str, body: GenerateBody, db: Session = Depends(get_db)):
    return orchestrator.generate_scene(
        db,
        project_id,
        scene_id,
        scope=body.scope,
        batch_ids=body.batchBlockIds or None,
        draft_mode=body.draftMode,
    )


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/generate")
def generate_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: GenerateBatchBody | None = Body(default=None),
    db: Session = Depends(get_db),
):
    draft_mode = body.draftMode if body else None
    return orchestrator.submit_batch_generation(
        db, project_id, scene_id, batch_id, draft_mode=draft_mode
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


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/complete")
def complete_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: CompleteBody,
    db: Session = Depends(get_db),
):
    return orchestrator.complete_batch_candidate(
        db,
        project_id,
        scene_id,
        batch_id,
        asset_id=body.assetId,
        generated_duration=body.generatedDuration,
        execution_snapshot_id=body.executionSnapshotId,
    )


class ApproveBody(BaseModel):
    candidateId: str


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/approve")
def approve_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: ApproveBody,
    db: Session = Depends(get_db),
):
    return orchestrator.approve_candidate(db, project_id, scene_id, batch_id, body.candidateId)


class RejectBody(BaseModel):
    candidateId: str


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/reject")
def reject_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RejectBody,
    db: Session = Depends(get_db),
):
    return orchestrator.reject_candidate(db, project_id, scene_id, batch_id, body.candidateId)


@router.post("/projects/{project_id}/scenes/{scene_id}/cancel")
def cancel(project_id: str, scene_id: str, body: CancelRequest, db: Session = Depends(get_db)):
    return orchestrator.cancel_scene(db, project_id, scene_id, body)


class RepairBody(BaseModel):
    start: float = 0.0
    length: float = 1.0
    mode: str = "range"
    inPaintStrategy: str = "range_replacement"
    label: str = ""
    policy: Optional[str] = None


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/repair-ranges")
def add_repair(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RepairBody,
    db: Session = Depends(get_db),
):
    payload = body.model_dump()
    policy = payload.pop("policy", None)
    return orchestrator.add_repair_range(
        db, project_id, scene_id, batch_id, payload, policy=policy
    )


@router.get("/projects/{project_id}/scenes/{scene_id}/preflight")
def preflight(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    bundle = service.load_timeline_bundle(db, project_id, scene_id)
    if not bundle.get("ok"):
        raise HTTPException(404, bundle.get("error") or "Not found")
    master = bundle["master"]
    director_timeline = bundle["directorTimeline"]
    return {"ok": True, "findings": orchestrator.run_preflight(master, director_timeline=director_timeline), "mock": False}


@router.get("/projects/{project_id}/scenes/{scene_id}/snapshots/{snapshot_id}")
def get_snapshot(project_id: str, scene_id: str, snapshot_id: str, db: Session = Depends(get_db)):
    result = service.snapshot_get(db, project_id, scene_id, snapshot_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Not found")
    return result


class DurationBody(BaseModel):
    generatorId: Optional[str] = None
    plannedDuration: float = 5.0


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


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/retake")
def retake_batch(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: RetakeBody,
    db: Session = Depends(get_db),
):
    """Re-Take creates a new job + immutable snapshot; never mutates prior snapshots."""
    return orchestrator.retake_batch(
        db,
        project_id,
        scene_id,
        batch_id,
        user_correction=body.userCorrection,
        continuity_aware=body.continuityAware,
        mode=body.mode,
    )


class ContinuityPolicyBody(BaseModel):
    configuredTailDuration: float = 0.0


@router.post("/projects/{project_id}/scenes/{scene_id}/continuity-policy")
def set_continuity_policy(
    project_id: str,
    scene_id: str,
    body: ContinuityPolicyBody,
    db: Session = Depends(get_db),
):
    result = orchestrator.set_scene_continuity_policy(
        db, project_id, scene_id, body.configuredTailDuration
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("message") or result.get("error") or "Policy update failed")
    return result


class ActivateTakeBody(BaseModel):
    candidateId: str


@router.post("/projects/{project_id}/scenes/{scene_id}/batches/{batch_id}/activate-take")
def activate_take(
    project_id: str,
    scene_id: str,
    batch_id: str,
    body: ActivateTakeBody,
    db: Session = Depends(get_db),
):
    return orchestrator.activate_take(db, project_id, scene_id, batch_id, body.candidateId)


@router.post("/projects/{project_id}/scenes/{scene_id}/bridges/{bridge_id}/retry")
def retry_bridge(project_id: str, scene_id: str, bridge_id: str, db: Session = Depends(get_db)):
    result = orchestrator.retry_continuity_bridge(db, project_id, scene_id, bridge_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Bridge not found")
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/bridges/{bridge_id}/continue-without")
def continue_without_bridge(
    project_id: str, scene_id: str, bridge_id: str, db: Session = Depends(get_db)
):
    result = orchestrator.continue_without_continuity_bridge(db, project_id, scene_id, bridge_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Bridge not found")
    return result


class ReconcileBody(BaseModel):
    spendApiCredits: bool = False


@router.post("/projects/{project_id}/scenes/{scene_id}/reconcile-downstream")
def reconcile_downstream(
    project_id: str, scene_id: str, body: ReconcileBody, db: Session = Depends(get_db)
):
    result = orchestrator.reconcile_downstream(
        db, project_id, scene_id, spend_api_credits=body.spendApiCredits
    )
    if not result.get("ok") and result.get("error") in {
        "API_CREDIT_CONFIRMATION_REQUIRED",
        "API_CONTINUITY_OFF",
    }:
        raise HTTPException(400, result.get("message") or result.get("error"))
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/keep-existing-downstream")
def keep_existing_downstream(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    return orchestrator.keep_existing_downstream(db, project_id, scene_id)


# ---------------------------------------------------------------------------
# Certification stub control endpoints (CERT_STUB_ENV_GATED)
#
# Registered routes always exist, but every handler returns 404 unless
# ADEPT_TIMELINE_CERT_STUB=1 — invisible in production. These endpoints give
# tests deterministic control over stub job lifecycle states and read access
# to the JSONL request sink. No provider code ever runs through them.
# ---------------------------------------------------------------------------


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
