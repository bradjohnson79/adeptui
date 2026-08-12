"""LTX local adapter — shared Timeline interface over studio Job queue."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ....db import Job, SessionLocal
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
        supportedResolutions=["1280x720", "768x512", "3840x2160"],
        supportedAspectRatios=["16:9", "9:16"],
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
        params = {
            "engine": "ltx",
            "generatorId": GENERATOR_ID,
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
        }
        db: Session = SessionLocal()
        try:
            row = Job(
                id=job_id,
                project_id=request.projectId,
                scene_id=request.sceneId,
                kind="render_scene",
                status="queued",
                progress=0.0,
                message="Timeline batch LTX job queued",
                stage="queued",
                params_json=json.dumps(params),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        # Best-effort enqueue into async worker when available.
        try:
            from ....queue_worker import worker

            if worker is not None and hasattr(worker, "enqueue"):
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(worker.enqueue(job_id))
                    else:
                        loop.run_until_complete(worker.enqueue(job_id))
                except Exception:
                    pass
        except Exception:
            pass

        return NormalizedJobSubmission(
            internalJobId=job_id,
            providerJobId=job_id,
            queueJobId=job_id,
            generatorId=GENERATOR_ID,
            status="queued",
            apiUsed=False,
            providerMetadata={
                "projectId": request.projectId,
                "sceneId": request.sceneId,
                "engine": "ltx",
                "executionSnapshotId": request.executionSnapshotId,
                "batchBlockId": request.batchBlockId,
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
                },
            )
        finally:
            db.close()

    def cancel(self, job: NormalizedJobSubmission) -> None:
        db = SessionLocal()
        try:
            row = db.get(Job, job.queueJobId or job.internalJobId)
            if row and row.status in ("queued", "running"):
                row.status = "cancelled"
                row.message = "Cancelled from Timeline batch"
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
