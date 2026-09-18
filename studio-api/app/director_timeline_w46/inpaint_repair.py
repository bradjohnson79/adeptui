"""Timeline Mask/Repair → still inpaint → apply to the marked range only."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..db import Job
from ..image_product.edit_service import enqueue_edit
from ..image_product.masks import get_mask_path, save_mask
from . import orchestrator, store
from .capabilities import disclose_inpaint_strategy, get_generator
from .contracts import ExecutionSnapshot, RepairRange, SceneTimelineMaster
from .current_take import require_current_take
from .keyframe_repair import apply_keyframe_repair_to_asset
from .range_replacement import extract_cut_in_frame_asset

NATIVE_DISCLOSURE = (
    "Native video inpaint is unavailable. Adept repairs the painted area on this "
    "frame and applies that repair only to the selected time range. The rest of the shot stays as it is."
)


def _load_batch_repair(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((item for item in master.batchBlocks if item.id == batch_id), None)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "message": "That shot is missing.", "mock": False}
    repair = next((item for item in (batch.repairRanges or []) if item.id == repair_id), None)
    if not repair:
        return {"ok": False, "error": "REPAIR_NOT_FOUND", "message": "Select a Mask/Repair range first.", "mock": False}
    return {"ok": True, "master": master, "batch": batch, "repair": repair}


def _save_repair_metadata(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    patch: dict[str, Any],
    *,
    status: str | None = None,
    snapshot_id: str | None = None,
    candidate_id: str | None = None,
) -> RepairRange | None:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return None
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((item for item in master.batchBlocks if item.id == batch_id), None)
    if not batch:
        return None
    repair = next((item for item in (batch.repairRanges or []) if item.id == repair_id), None)
    if not repair:
        return None
    meta = dict(repair.metadata or {})
    inpaint = dict(meta.get("inpaint") or {}) if isinstance(meta.get("inpaint"), dict) else {}
    inpaint.update(patch)
    meta["inpaint"] = inpaint
    repair.metadata = meta
    if status:
        repair.status = status
    if snapshot_id:
        repair.executionSnapshotId = snapshot_id
    if candidate_id:
        repair.candidateId = candidate_id
    store.save_master(db, project_id, scene_id, master)
    return repair


def submit_video_retake(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    *,
    start: float,
    length: float,
    prompt: str,
    mask_png_base64: str | None = None,
    reference_frame_time: float | None = None,
    frame_asset_id: str | None = None,
    remove_background: bool = False,
) -> dict[str, Any]:
    """Masked / background-removal Re-Take. Reuses keyframe repair — no second backend."""
    note = str(prompt or "").strip()
    mask_b64 = str(mask_png_base64 or "").strip()
    if not note and not remove_background:
        return {
            "ok": False,
            "error": "REPAIR_PROMPT_REQUIRED",
            "message": "Describe what you want to change, or use Remove Background.",
            "mock": False,
        }
    if not note and remove_background:
        note = "Remove the background."
    if not mask_b64 and not remove_background:
        return {
            "ok": False,
            "error": "MASK_REQUIRED",
            "message": "Paint the area that needs repair, or use Remove Background.",
            "mock": False,
        }

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((item for item in master.batchBlocks if item.id == batch_id), None)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "message": "That shot is missing.", "mock": False}
    take_gate = require_current_take(batch, action="Inpaint")
    if not take_gate.get("ok"):
        return take_gate
    _current_take = take_gate["take"]

    start = max(0.0, float(start))
    length = max(0.15, float(length))
    at = start + min(0.15, length / 2.0) if reference_frame_time is None else float(reference_frame_time)
    at = max(start, min(start + length, at))

    repair = orchestrator.add_repair_range(
        db,
        project_id,
        scene_id,
        batch_id,
        {
            "start": start,
            "length": length,
            "mode": "range",
            "inPaintStrategy": "keyframe_repair",
            "label": "Re-Take",
            "status": "draft",
            "metadata": {"prompt": note, "sourceAssetId": _current_take["assetId"], "removeBackground": remove_background},
        },
        policy="stack_advanced",
    )
    if not repair.get("ok"):
        return {**repair, "mock": False}
    ranges = repair.get("ranges") or []
    repair_id = ranges[-1]["id"] if ranges else None
    if not repair_id:
        return {"ok": False, "error": "REPAIR_CREATE_FAILED", "message": "Could not mark this range.", "mock": False}

    frame_id = str(frame_asset_id or "").strip()
    if not frame_id:
        extracted = extract_repair_frame(
            db, project_id, scene_id, batch_id, repair_id, at_seconds=at
        )
        if not extracted.get("ok"):
            return extracted
        frame_id = str(extracted.get("frameAssetId") or "")
    if not frame_id:
        return {
            "ok": False,
            "error": "FRAME_MISSING",
            "message": "Could not take a still from this range to paint on.",
            "mock": False,
        }

    if remove_background and not mask_b64:
        from ..codirector.perception.selection_service import remove_background as run_remove_background
        from ..image_product.masks import get_mask_path

        rembg = run_remove_background(
            db,
            project_id,
            frame_id,
            save_to_library=False,
            tag="retake-background-mask",
        )
        if not rembg.get("ok"):
            return {
                "ok": False,
                "error": "BACKGROUND_REMOVAL_UNAVAILABLE",
                "message": str(rembg.get("message") or "Paint the region, or install intelligent selection."),
                "mock": False,
            }
        mask_id = str(rembg.get("maskAssetId") or "")
        mask_path = get_mask_path(project_id, mask_id) if mask_id else None
        if mask_path:
            from pathlib import Path
            import base64

            png = Path(mask_path)
            if png.is_file():
                mask_b64 = base64.b64encode(png.read_bytes()).decode("ascii")

    queued = submit_inpaint_repair(
        db,
        project_id,
        scene_id,
        batch_id,
        repair_id,
        prompt=note,
        mask_png_base64=mask_b64,
        at_seconds=at,
        frame_asset_id=frame_id,
    )
    if not queued.get("ok"):
        return queued
    queued["retakeMode"] = "keyframe_repair"
    queued["repairId"] = repair_id
    queued["rangeReplacement"] = {"start": start, "length": length, "repairId": repair_id}
    return queued


def extract_repair_frame(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    *,
    at_seconds: float | None = None,
) -> dict[str, Any]:
    ctx = _load_batch_repair(db, project_id, scene_id, batch_id, repair_id)
    if not ctx.get("ok"):
        return ctx
    batch = ctx["batch"]
    repair = ctx["repair"]
    take_gate = require_current_take(batch, action="Inpaint")
    if not take_gate.get("ok"):
        return take_gate
    _current_take = take_gate["take"]
    start = float(repair.start or 0.0)
    length = max(0.1, float(repair.length or 0.1))
    if at_seconds is None:
        at = start + min(0.15, length / 2.0)
    else:
        at = max(start, min(start + length, float(at_seconds)))
    frame = extract_cut_in_frame_asset(
        db,
        project_id=project_id,
        source_asset_id=_current_take["assetId"],
        at_seconds=at,
    )
    if not frame.get("ok"):
        return {**frame, "mock": False}
    _save_repair_metadata(
        db,
        project_id,
        scene_id,
        batch_id,
        repair_id,
        {
            "frameAssetId": frame.get("assetId"),
            "atSeconds": at,
            "sourceAssetId": _current_take["assetId"],
            "nativeDisclosure": NATIVE_DISCLOSURE,
        },
    )
    return {
        "ok": True,
        "frameAssetId": frame.get("assetId"),
        "atSeconds": at,
        "sourceAssetId": _current_take["assetId"],
        "start": start,
        "length": length,
        "disclosure": NATIVE_DISCLOSURE,
        "mock": False,
    }


def submit_inpaint_repair(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    *,
    prompt: str,
    mask_png_base64: str,
    at_seconds: float | None = None,
    frame_asset_id: str | None = None,
) -> dict[str, Any]:
    ctx = _load_batch_repair(db, project_id, scene_id, batch_id, repair_id)
    if not ctx.get("ok"):
        return ctx
    batch = ctx["batch"]
    repair = ctx["repair"]
    note = str(prompt or "").strip()
    if not note:
        return {
            "ok": False,
            "error": "REPAIR_PROMPT_REQUIRED",
            "message": "Write what should change in the painted area.",
            "mock": False,
        }
    mask_b64 = str(mask_png_base64 or "").strip()
    if not mask_b64:
        return {
            "ok": False,
            "error": "MASK_REQUIRED",
            "message": "Paint the area that needs repair first.",
            "mock": False,
        }
    take_gate = require_current_take(batch, action="Inpaint")
    if not take_gate.get("ok"):
        return take_gate
    _current_take = take_gate["take"]

    frame_id = str(frame_asset_id or "").strip()
    if not frame_id:
        extracted = extract_repair_frame(
            db, project_id, scene_id, batch_id, repair_id, at_seconds=at_seconds
        )
        if not extracted.get("ok"):
            return extracted
        frame_id = str(extracted.get("frameAssetId") or "")
    if not frame_id:
        return {
            "ok": False,
            "error": "FRAME_MISSING",
            "message": "Could not take a still from this range to paint on.",
            "mock": False,
        }

    try:
        mask_rec = save_mask(
            project_id,
            source_asset_id=frame_id,
            png_base64=mask_b64,
            role="include",
            creator="user",
            metadata={"repairId": repair_id, "batchId": batch_id, "purpose": "timeline_keyframe_repair"},
        )
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": "MASK_SAVE_FAILED", "message": str(exc)[:400], "mock": False}

    mask_id = str(mask_rec.get("maskId") or "")
    disclosure = disclose_inpaint_strategy(batch.generatorId or None, "keyframe_repair")
    try:
        queued = enqueue_edit(
            db,
            project_id,
            {
                "projectId": project_id,
                "sceneId": scene_id,
                "sourceAssetId": frame_id,
                "operation": "image.inpaint",
                "prompt": note,
                "masks": [{"maskId": mask_id, "maskAssetId": mask_id, "role": "include"}],
                "modelFamilyPreference": "zimage",
                "tag": "timeline-keyframe-repair",
                "purpose": "timeline_keyframe_repair",
                "quality": "standard",
            },
        )
    except (ValueError, RuntimeError) as exc:
        return {
            "ok": False,
            "error": "INPAINT_NOT_READY",
            "message": str(exc)[:400] or "Still inpaint is not ready for this repair.",
            "disclosure": NATIVE_DISCLOSURE,
            "mock": False,
        }

    job_id = str(queued.get("jobId") or "")
    if not job_id:
        return {
            "ok": False,
            "error": "INPAINT_QUEUE_FAILED",
            "message": "The repair job did not start.",
            "mock": False,
        }

    _save_repair_metadata(
        db,
        project_id,
        scene_id,
        batch_id,
        repair_id,
        {
            "prompt": note,
            "frameAssetId": frame_id,
            "maskId": mask_id,
            "jobId": job_id,
            "atSeconds": at_seconds,
            "sourceAssetId": _current_take["assetId"],
            "requestedStrategy": "keyframe_repair",
            "resolvedStrategy": disclosure.get("strategy") or "keyframe_repair",
            "strategyDisclosure": disclosure,
            "nativeDisclosure": NATIVE_DISCLOSURE,
            "workflowKey": queued.get("workflowKey"),
        },
        status="generating",
    )
    live = _load_batch_repair(db, project_id, scene_id, batch_id, repair_id)
    if live.get("ok"):
        live["repair"].inPaintStrategy = "keyframe_repair"  # type: ignore[assignment]
        store.save_master(db, project_id, scene_id, live["master"])

    return {
        "ok": True,
        "jobId": job_id,
        "frameAssetId": frame_id,
        "maskId": mask_id,
        "workflowKey": queued.get("workflowKey"),
        "disclosure": NATIVE_DISCLOSURE,
        "strategy": "keyframe_repair",
        "mock": False,
    }


def _job_output_asset_id(job: Job | None) -> str | None:
    if job is None:
        return None
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    if isinstance(params, dict) and params.get("output_asset_id"):
        return str(params["output_asset_id"])
    try:
        hist = json.loads(job.history_json or "{}")
    except Exception:
        hist = {}
    if isinstance(hist, dict) and hist.get("assetId"):
        return str(hist["assetId"])
    return None


def apply_inpaint_repair(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    repair_id: str,
    *,
    job_id: str | None = None,
    repaired_asset_id: str | None = None,
) -> dict[str, Any]:
    ctx = _load_batch_repair(db, project_id, scene_id, batch_id, repair_id)
    if not ctx.get("ok"):
        return ctx
    batch = ctx["batch"]
    repair = ctx["repair"]
    meta = repair.metadata.get("inpaint") if isinstance(repair.metadata, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    still_id = str(repaired_asset_id or meta.get("repairedAssetId") or "").strip()
    watch_job = str(job_id or meta.get("jobId") or "").strip()
    if not still_id and watch_job:
        job = db.get(Job, watch_job)
        if job is None:
            return {"ok": False, "error": "JOB_NOT_FOUND", "message": "The repair job is missing.", "mock": False}
        status = str(job.status or "")
        if status not in {"done", "completed"}:
            if status in {"failed", "error", "cancelled", "canceled", "timed_out"}:
                return {
                    "ok": False,
                    "error": "INPAINT_FAILED",
                    "message": job.message or "The painted repair did not finish.",
                    "jobId": watch_job,
                    "mock": False,
                }
            return {
                "ok": False,
                "error": "INPAINT_NOT_READY",
                "message": "Wait for the preview to finish before applying.",
                "jobId": watch_job,
                "status": status,
                "mock": False,
            }
        still_id = _job_output_asset_id(job) or ""
    if not still_id:
        return {
            "ok": False,
            "error": "REPAIRED_STILL_MISSING",
            "message": "Preview the repair first, then apply it.",
            "mock": False,
        }
    take_gate = require_current_take(batch, action="Inpaint")
    if not take_gate.get("ok"):
        return take_gate
    _current_take = take_gate["take"]
    mask_id = str(meta.get("maskId") or "").strip()
    mask_path = get_mask_path(project_id, mask_id) if mask_id else None
    if not mask_path:
        return {
            "ok": False,
            "error": "MASK_MISSING",
            "message": "The painted mask is missing. Paint the area again.",
            "mock": False,
        }

    source_id = str(_current_take["assetId"])
    composed = apply_keyframe_repair_to_asset(
        db,
        project_id=project_id,
        source_asset_id=source_id,
        repaired_still_asset_id=still_id,
        mask_path=mask_path,
        start=float(repair.start or 0.0),
        length=max(0.1, float(repair.length or 0.1)),
        planned_duration=float(batch.duration.plannedDuration or 0.0) or None,
    )
    if not composed.get("ok"):
        return {**composed, "mock": False}

    master = ctx["master"]
    snap = ExecutionSnapshot(
        batchBlockId=batch.id,
        compiledPrompts={"repairPrompt": str(meta.get("prompt") or "")},
        selectedGenerator=batch.generatorId,
        capabilityStrategy="keyframe_repair",
        runtime="local",
        inPaintStrategy="keyframe_repair",
        duration=batch.duration.model_copy(),
        continuityState={
            "reTakeReason": "keyframe_repair",
            "userCorrection": {"prompt": meta.get("prompt")},
            "keyframeRepair": {
                "start": repair.start,
                "length": repair.length,
                "repairId": repair.id,
                "sourceAssetId": source_id,
                "repairedStillAssetId": still_id,
                "maskId": mask_id,
            },
        },
    )
    master.executionSnapshots[snap.id] = snap
    store.save_master(db, project_id, scene_id, master)

    attached = orchestrator.complete_batch_candidate(
        db,
        project_id,
        scene_id,
        batch_id,
        asset_id=str(composed["assetId"]),
        generated_duration=float(composed.get("duration") or batch.duration.plannedDuration or 0.0),
        execution_snapshot_id=snap.id,
    )
    if not attached.get("ok"):
        return {**attached, "mock": False}

    # A new repair take is reviewable. The current approved take stays the
    # stitch / extension take until the creator chooses the new one.
    restored = store.load_master(db, project_id, scene_id)
    if restored.get("ok"):
        live_master = SceneTimelineMaster.model_validate(restored["master"])
        live_batch = next((item for item in live_master.batchBlocks if item.id == batch_id), None)
        if (
            live_batch
            and live_batch.approvedClip
            and str(live_batch.approvedClip.assetId) == source_id
        ):
            live_batch.status = "Approved"
            store.save_master(db, project_id, scene_id, live_master)

    candidate = attached.get("candidate") or {}
    live_repair = _save_repair_metadata(
        db,
        project_id,
        scene_id,
        batch_id,
        repair_id,
        {
            "repairedAssetId": still_id,
            "composedAssetId": composed.get("assetId"),
            "jobId": watch_job or meta.get("jobId"),
            "nativeDisclosure": NATIVE_DISCLOSURE,
        },
        status="ready",
        snapshot_id=snap.id,
        candidate_id=str(candidate.get("id") or "") or None,
    )
    if live_repair and not str(live_repair.label or "").strip():
        live = _load_batch_repair(db, project_id, scene_id, batch_id, repair_id)
        if live.get("ok"):
            live["repair"].label = "Repair"
            store.save_master(db, project_id, scene_id, live["master"])

    return {
        "ok": True,
        "assetId": composed.get("assetId"),
        "repairedStillAssetId": still_id,
        "candidate": candidate,
        "repairId": repair_id,
        "executionSnapshotId": snap.id,
        "disclosure": NATIVE_DISCLOSURE,
        "autoApproved": False,
        "mock": False,
    }
