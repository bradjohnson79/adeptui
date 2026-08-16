"""LTX local adapter — shared Timeline interface over studio Job queue."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ....db import Asset, Job, SessionLocal
from ..adapter import validate_against_capabilities
from ..contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
    ValidationResult,
    VideoGeneratorCapabilities,
)

GENERATOR_ID = "ltx-local"
ALIASES = frozenset({
    "ltx-local",
    "ltx-2.5-full",
    "ltx-2.5-distilled",
    "ltx-2.5-comfy",
})


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="LTX 2.5 (Local)",
        executionType="local",
        supportsTextToVideo=True,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=True,
        supportsMultipleImageReferences=False,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        maximumReferenceImages=0,
        maximumReferenceVideos=0,
        maximumReferenceAudio=0,
        supportedDurations=[5.0, 8.0, 10.0, 15.0, 20.0],
        supportedResolutions=["1280x720", "768x432", "672x288", "1344x576", "512x512", "1024x1024", "512x384", "1024x768"],
        supportedAspectRatios=["1:1", "4:3", "16:9", "21:9", "9:16"],
        supportedFps=[24, 30, 48, 50],
        supportsSeed=True,
        supportsNegativePrompt=True,
        supportsCameraControls=False,
        native_multishot=True,
        audio_generation=True,
        auto_duration=True,
        fast_generation=True,
        audio={
            "generation": True,
            "synchronized": True,
            "native": True,
        },
        executable=True,
        notes="Local Comfy LTX path via studio render_scene jobs. Supports LTX 2.3 and 2.5 variants.",
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        finalRequiresNewGeneration=True,
        draftResolution="768x432",
        finalResolution="1280x720",
        supportsImageAndVideoTogether=False,
    )


class LtxLocalAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        result = validate_against_capabilities(self.capabilities, request)
        if not result.ok:
            return result
        gen_id = request.generatorId or ""
        if gen_id in ("ltx-2.5-full", "ltx-2.5-distilled", "ltx-2.5-comfy"):
            errors: list[str] = []
            from ....setup.diagnostics import verify_component
            required_components = ["ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"]
            if gen_id in ("ltx-2.5-full", "ltx-2.5-distilled"):
                required_components.append("ltx_2_5_audio_vae")
            missing = [cid for cid in required_components if not verify_component(cid).healthy]
            if missing:
                errors.append(f"LTX 2.5 model components not found: {', '.join(missing)}. Use Source Manager to install required models.")
            if errors:
                return ValidationResult(ok=False, errors=errors)
        return result

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        job_id = str(uuid4())
        gen_id = request.generatorId or GENERATOR_ID
        params = {
            "engine": "ltx",
            "generatorId": gen_id,
            "prompt": request.prompt,
            "negativePrompt": request.negativePrompt,
            "startImageAssetId": request.startImageAssetId,
            "endImageAssetId": request.endImageAssetId,
            "duration": request.duration,
            "seed": request.seed,
            "batchBlockId": request.batchBlockId,
            "executionSnapshotId": request.executionSnapshotId,
            "generationMode": request.generationMode,
            "timelineGeneration": True,
            "fallbackAllowed": bool(request.fallbackAllowed),
            "continuityBridgeId": request.continuityBridgeId,
            "lastFrameAssetId": request.lastFrameAssetId,
            "tailAssetId": request.tailAssetId,
            "aspectRatio": request.aspectRatio,
            "resolution": request.resolution,
            "draftMode": bool(request.providerOptions.get("draftMode")),
            "continuityStrategy": request.continuityStrategy
            if request.continuityStrategy not in ("native_tail", "native_extend")
            else "last_frame_i2v",
        }

        if gen_id in ("ltx-2.5-full", "ltx-2.5-distilled", "ltx-2.5-comfy"):
            params["fast_mode"] = bool(request.providerOptions.get("fast_generation", True))
            params["generate_audio"] = bool(request.providerOptions.get("audio_generation", True))
            params["variant"] = gen_id
        elif request.providerOptions.get("fast_generation"):
            params["fast_mode"] = True

        res = str(request.resolution or "")
        if "x" in res:
            try:
                w_s, h_s = res.lower().split("x", 1)
                params["width"] = int(w_s)
                params["height"] = int(h_s)
            except ValueError:
                pass

        db: Session = SessionLocal()
        try:
            row = Job(
                id=job_id,
                project_id=request.projectId,
                scene_id=request.sceneId,
                kind="render_scene",
                status="queued",
                progress=0.0,
                message=(
                    "Timeline batch LTX draft queued"
                    if params.get("draftMode")
                    else "Timeline batch LTX job queued"
                ),
                stage="queued",
                params_json=json.dumps(params),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        # Enqueue into the in-process JobQueue. The Timeline generate route is
        # sync (threadpool), so hop onto the worker event loop — never silently
        # skip because `worker` is not an exported alias.
        try:
            import asyncio

            from ....queue_worker import job_queue

            if job_queue is not None and hasattr(job_queue, "enqueue"):
                task = getattr(job_queue, "_task", None)
                worker_loop = task.get_loop() if task is not None else None
                if worker_loop is not None and worker_loop.is_running():
                    asyncio.run_coroutine_threadsafe(job_queue.enqueue(job_id), worker_loop)
                else:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        loop.create_task(job_queue.enqueue(job_id))
                    else:
                        asyncio.run(job_queue.enqueue(job_id))
        except Exception:
            pass

        return NormalizedJobSubmission(
            internalJobId=job_id,
            providerJobId=job_id,
            queueJobId=job_id,
            generatorId=gen_id,
            status="queued",
            apiUsed=False,
            providerMetadata={
                "projectId": request.projectId,
                "sceneId": request.sceneId,
                "engine": "ltx",
                "generatorId": gen_id,
                "executionSnapshotId": request.executionSnapshotId,
                "batchBlockId": request.batchBlockId,
                "continuityStrategy": params.get("continuityStrategy") or "none",
                "lastFrameAssetId": request.lastFrameAssetId,
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        db = SessionLocal()
        try:
            row = db.get(Job, job.queueJobId or job.internalJobId)
            if not row:
                return NormalizedJobStatus(
                    internalJobId=job.internalJobId,
                    generatorId=job.generatorId,
                    status="failed",
                    errorCode="LTX_JOB_MISSING",
                    errorMessage="LTX queue job not found.",
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
            if mapped == "completed" and not output_ids:
                output_ids = _ensure_output_asset_ids(db, row, params)
            return NormalizedJobStatus(
                internalJobId=job.internalJobId,
                providerJobId=row.comfy_prompt_id or job.providerJobId,
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
                },
            )
        finally:
            db.close()

    def cancel(self, job: NormalizedJobSubmission) -> None:
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
                row.message = "Cancelled from Timeline batch (halt fallback)"
                db.add(row)
                db.commit()
        finally:
            db.close()

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        status = self.get_status(job)
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
                errorCode=status.errorCode or "LTX_NOT_COMPLETE",
                errorMessage=status.errorMessage or "LTX job is not complete.",
            )
        # Asset import is owned by queue_worker; surface output path for completion bridge.
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
            errorCode=None
            if status.providerMetadata.get("outputPath") or status.providerMetadata.get("outputAssetIds")
            else "LTX_OUTPUT_PENDING",
            errorMessage=None,
        )


def _ensure_output_asset_ids(db: Session, row: Job, params: dict[str, Any]) -> list[str]:
    """Bind a Library asset for a finished LTX render if queue_worker did not."""
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

            tag = "ltx-draft" if params.get("draftMode") else "ltx"
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
        db.add(row)
        try:
            db.commit()
        except Exception:
            db.rollback()
    return ids


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
