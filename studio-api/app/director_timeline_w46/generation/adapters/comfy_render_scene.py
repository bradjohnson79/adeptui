"""Shared Timeline → studio render_scene queue hop for local Comfy engines."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ....db import Asset, Job, SessionLocal
from ..contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
)


def submit_render_scene(
    request: TimelineGenerationRequest,
    *,
    engine: str,
    generator_id: str,
    queue_message: str,
) -> NormalizedJobSubmission:
    job_id = str(uuid4())
    gen_id = request.generatorId or generator_id
    timeline_model = str(
        request.providerOptions.get("originalGeneratorId")
        or request.providerOptions.get("selectedGenerator")
        or request.generatorId
        or generator_id
    )
    params: dict[str, Any] = {
        "engine": engine,
        "generatorId": timeline_model,
        "adapterId": gen_id,
        "prompt": request.prompt,
        "negativePrompt": request.negativePrompt,
        "startImageAssetId": request.startImageAssetId,
        "endImageAssetId": request.endImageAssetId,
        "duration": request.duration,
        "seed": request.seed,
        "batchBlockId": request.batchBlockId,
        "executionSnapshotId": request.executionSnapshotId,
        "sceneTakeId": str(request.providerOptions.get("sceneTakeId") or ""),
        "generationMode": request.generationMode,
        "timelineGeneration": True,
        "fallbackAllowed": bool(request.fallbackAllowed),
        "continuityBridgeId": request.continuityBridgeId,
        "lastFrameAssetId": request.lastFrameAssetId,
        "tailAssetId": request.tailAssetId,
        "aspectRatio": request.aspectRatio,
        "resolution": request.resolution,
        "lora": request.lora or request.providerOptions.get("lora"),
        "draftMode": bool(request.providerOptions.get("draftMode")),
        "continuityStrategy": request.continuityStrategy
        if request.continuityStrategy not in ("native_tail", "native_extend")
        else "last_frame_i2v",
        "temporalContinuityPacketId": request.temporalContinuityPacketId,
        "temporalContinuation": request.providerOptions.get("temporalContinuation"),
    }
    from ..r2v import copy_r2v_into_job_params

    copy_r2v_into_job_params(params, request)
    # Film Timeline Continue continuity packet (priorAssetId/prompt/duration + frames).
    # Required by queue_worker H3 Director native continue (2-group + cache seed).
    continuity = (
        request.providerOptions.get("continuity")
        if isinstance(request.providerOptions, dict)
        else None
    )
    if isinstance(continuity, dict) and continuity:
        params["continuity"] = dict(continuity)
    # Director bridge flag — routes to h3_director_bridge in queue_worker.
    # Fail-closed: local MiniMax H3 Timeline always gets useDirector=True so
    # queue_worker cannot silently fall back to legacy ref2v.
    _gen_tok = str(timeline_model or gen_id or "").strip().lower()
    _is_local_h3 = "minimax-h3" in _gen_tok and "local" in _gen_tok
    if _is_local_h3 or request.providerOptions.get("useDirector"):
        params["useDirector"] = True
    # Whole-second duration authority for Director (also via copy_r2v).
    if params.get("useDirector") and params.get("requestedDurationSec") is None:
        try:
            params["requestedDurationSec"] = int(request.duration)
        except (TypeError, ValueError):
            pass
    res = str(request.resolution or "")
    if "x" in res:
        try:
            w_s, h_s = res.lower().split("x", 1)
            params["width"] = int(w_s)
            params["height"] = int(h_s)
        except ValueError:
            pass
    # Carry the single resolvedGeneration object (H3 table authority) onto the job.
    resolved = request.providerOptions.get("resolvedGeneration") if isinstance(request.providerOptions, dict) else None
    if isinstance(resolved, dict) and resolved.get("width") and resolved.get("height"):
        params["resolvedGeneration"] = dict(resolved)
        params["width"] = int(resolved["width"])
        params["height"] = int(resolved["height"])
        params["resolution"] = f"{int(resolved['width'])}x{int(resolved['height'])}"

    db: Session = SessionLocal()
    try:
        row = Job(
            id=job_id,
            project_id=request.projectId,
            scene_id=request.sceneId,
            kind="render_scene",
            status="queued",
            progress=0.0,
            message=queue_message,
            stage="queued",
            params_json=json.dumps(params),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    from ....codirector.executive.imagegen_adapter import schedule_job_queue_enqueue
    from ....video_runtime.job_model import merge_video_runtime_history

    enqueue_at = datetime.now(timezone.utc).isoformat()
    try:
        schedule_job_queue_enqueue(job_id)
    except Exception as exc:
        db = SessionLocal()
        try:
            row = db.get(Job, job_id)
            if row:
                row.status = "failed"
                row.stage = "failed"
                row.message = (
                    f"Failed to enqueue Timeline {engine} job onto the studio queue: {exc}"
                )[:4000]
                row.history_json = merge_video_runtime_history(
                    row.history_json,
                    {
                        "queueHops": {
                            "enqueueAt": enqueue_at,
                            "enqueueOk": False,
                            "enqueueError": str(exc)[:400],
                        }
                    },
                )
                db.add(row)
                db.commit()
        finally:
            db.close()
        raise

    db = SessionLocal()
    try:
        row = db.get(Job, job_id)
        if row:
            row.history_json = merge_video_runtime_history(
                row.history_json,
                {"queueHops": {"enqueueAt": enqueue_at, "enqueueOk": True}},
            )
            db.add(row)
            db.commit()
    finally:
        db.close()

    return NormalizedJobSubmission(
        internalJobId=job_id,
        providerJobId=None,
        queueJobId=job_id,
        generatorId=gen_id,
        status="queued",
        apiUsed=False,
        providerMetadata={
            "projectId": request.projectId,
            "sceneId": request.sceneId,
            "engine": engine,
            "generatorId": timeline_model,
            "requestedModel": timeline_model,
            "executionSnapshotId": request.executionSnapshotId,
            "batchBlockId": request.batchBlockId,
            "continuityStrategy": params.get("continuityStrategy") or "none",
            "lastFrameAssetId": request.lastFrameAssetId,
            "providerAccepted": False,
        },
    )


def _map(raw: str) -> Any:
    s = (raw or "").lower()
    if s in ("completed", "done", "success"):
        return "completed"
    if s in ("failed", "error"):
        return "failed"
    if s in ("cancelled", "canceled"):
        return "cancelled"
    if s in ("running", "processing"):
        return "running"
    return "queued"


def _extract_gate_duration(row: Job) -> float | None:
    if row.status != "done":
        return None
    try:
        history = json.loads(row.history_json or "{}")
        gate = history.get("outputGate") or {}
        dur = float(gate.get("durationSec") or 0)
        return dur if dur > 0 else None
    except Exception:
        return None


def _ensure_output_asset_ids(db: Session, row: Job, params: dict[str, Any], engine: str) -> list[str]:
    from pathlib import Path

    path = str(row.output_path or "").strip()
    if not path or not Path(path).is_file():
        return []
    existing = db.query(Asset).filter(Asset.project_id == row.project_id, Asset.path == path).first()
    if existing:
        ids = [existing.id]
    else:
        try:
            from ....minimax_h3.route_a_adapter import import_output_to_project_library

            tag = f"{engine}-draft" if params.get("draftMode") else engine
            receipt = import_output_to_project_library(
                project_id=str(row.project_id),
                source_mp4=Path(path),
                tag=tag,
                db=db,
            )
            ids = [str(receipt.get("assetId") or receipt.get("id") or "")]
            ids = [x for x in ids if x]
        except Exception:
            return []
    if ids:
        params["outputAssetIds"] = ids
        row.params_json = json.dumps(params)
        try:
            for aid in ids:
                asset = db.get(Asset, str(aid)) if aid else None
                if asset is None:
                    continue
                try:
                    raw = asset.prompt_meta_json or "{}"
                    meta = json.loads(raw) if isinstance(raw, str) else (raw or {})
                except Exception:
                    meta = {}
                if isinstance(meta, dict):
                    meta["lora"] = params.get("lora_provenance")
                    meta.setdefault("engine", engine)
                    asset.prompt_meta_json = json.dumps(meta)
                    db.add(asset)
        except Exception:
            pass
        db.add(row)
        try:
            db.commit()
        except Exception:
            db.rollback()
    return ids


def get_render_status(job: NormalizedJobSubmission, *, engine: str) -> NormalizedJobStatus:
    db = SessionLocal()
    try:
        row = db.get(Job, job.queueJobId or job.internalJobId)
        if not row:
            return NormalizedJobStatus(
                internalJobId=job.internalJobId,
                generatorId=job.generatorId,
                status="failed",
                errorCode=f"{engine.upper()}_JOB_MISSING",
                errorMessage=f"{engine} queue job not found.",
            )
        mapped = _map(row.status)
        params: dict[str, Any] = {}
        try:
            parsed = json.loads(row.params_json or "{}")
            if isinstance(parsed, dict):
                params = parsed
        except Exception:
            params = {}
        output_ids = [str(x) for x in (params.get("outputAssetIds") or []) if x]
        if mapped == "completed":
            live_ids = [aid for aid in output_ids if db.get(Asset, aid) is not None]
            if not live_ids:
                live_ids = _ensure_output_asset_ids(db, row, params, engine)
            output_ids = live_ids
        prompt_id = row.comfy_prompt_id or None
        from ....video_runtime.progress_telemetry import telemetry_from_job_row

        tel = telemetry_from_job_row(row)
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=prompt_id,
            queueJobId=row.id,
            generatorId=job.generatorId,
            status=mapped,
            progress=float(row.progress or 0.0),
            errorMessage=row.message if mapped == "failed" else None,
            apiUsed=False,
            providerMetadata={
                **job.providerMetadata,
                "outputPath": row.output_path,
                "stage": row.stage,
                "outputAssetIds": output_ids,
                "draftMode": bool(params.get("draftMode")),
                "aspectRatio": params.get("aspectRatio"),
                "resolution": params.get("resolution"),
                "providerAccepted": bool(prompt_id),
                "requestedModel": params.get("generatorId") or job.generatorId,
                "resolvedRuntimeModel": params.get("resolvedRuntimeModel"),
                "generatedDuration": _extract_gate_duration(row),
                "startImageAssetId": params.get("startImageAssetId"),
                "engine": engine,
                "progressTelemetry": tel,
            },
        )
    finally:
        db.close()


def cancel_render_job(job: NormalizedJobSubmission) -> None:
    job_id = job.queueJobId or job.internalJobId
    if not job_id:
        return
    try:
        from ....codirector.execution.cancel import _cancel_job

        _cancel_job(str(job_id))
        return
    except Exception:
        pass
    db = SessionLocal()
    try:
        row = db.get(Job, job_id)
        if row and row.status in ("queued", "running", "cancelling"):
            row.status = "cancelled"
            row.message = "Cancelled from Timeline batch"
            db.add(row)
            db.commit()
    finally:
        db.close()


def collect_render_result(job: NormalizedJobSubmission, *, engine: str) -> TimelineGenerationResult:
    status = get_render_status(job, engine=engine)
    if status.status != "completed":
        return TimelineGenerationResult(
            internalJobId=job.internalJobId,
            providerJobId=status.providerJobId,
            queueJobId=status.queueJobId,
            generatorId=job.generatorId,
            status=status.status,
            progress=status.progress,
            apiUsed=False,
            providerMetadata=status.providerMetadata,
            errorCode=status.errorCode or f"{engine.upper()}_NOT_COMPLETE",
            errorMessage=status.errorMessage or f"{engine} job is not complete.",
        )
    return TimelineGenerationResult(
        internalJobId=job.internalJobId,
        providerJobId=status.providerJobId,
        queueJobId=status.queueJobId,
        generatorId=job.generatorId,
        status="completed",
        progress=1.0,
        outputAssetIds=list(status.providerMetadata.get("outputAssetIds") or []),
        apiUsed=False,
        providerMetadata=status.providerMetadata,
        duration=(
            float(status.providerMetadata["generatedDuration"])
            if status.providerMetadata.get("generatedDuration")
            else None
        ),
        errorCode=None
        if status.providerMetadata.get("outputPath") or status.providerMetadata.get("outputAssetIds")
        else f"{engine.upper()}_OUTPUT_PENDING",
        errorMessage=None,
    )
