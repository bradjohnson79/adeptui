"""MiniMax H3 local adapter — reuses Route A /api/minimax-h3 path."""

from __future__ import annotations

from typing import Any

from ....minimax_h3.contracts import AdeptMiniMaxH3Request, H3TimelineContext
from ....minimax_h3.service import cancel as h3_cancel
from ....minimax_h3.service import create_job_or_block, get_job, prepare_plan
from ..adapter import validate_against_capabilities
from ..contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
    ValidationResult,
    VideoGeneratorCapabilities,
)

GENERATOR_ID = "minimax-h3-t2v-local"
ALIASES = frozenset({"minimax-h3-t2v-local", "minimax-h3-local", "minimax-h3"})


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="MiniMax H3 Text-to-Video (Local)",
        executionType="local",
        supportsTextToVideo=True,
        supportsImageToVideo=False,
        supportsStartFrame=False,
        supportsEndFrame=False,
        supportsMultipleImageReferences=False,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        maximumReferenceImages=0,
        maximumReferenceVideos=0,
        maximumReferenceAudio=0,
        supportedDurations=[5.0],
        supportedResolutions=["480x256"],
        supportedAspectRatios=["≈16:9"],
        supportsSeed=True,
        supportsNegativePrompt=False,
        supportsCameraControls=False,
        executable=True,
        notes=(
            "Experimental Private Profile — text-to-video with native audio. "
            "Image-to-video is not supported; batch start images remain Timeline planning anchors. "
            "Continuity uses prompt_context only — never native video extend or last-frame I2V. "
            "Draft Mode is unavailable — this profile only generates at 480x256."
        ),
        draftPathway="none",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        finalRequiresNewGeneration=True,
        draftResolution=None,
        finalResolution="480x256",
        supportsImageAndVideoTogether=False,
    )


class MiniMaxH3LocalAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        # Planning anchors may be present in providerOptions; generation refs must match caps.
        return validate_against_capabilities(self.capabilities, request)

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        if request.fallbackAllowed:
            raise ValueError("MiniMax H3 adapter refuses fallbackAllowed=true without explicit LTX accept API.")

        mode = "text-to-video"
        if request.generationMode == "image_to_video":
            raise ValueError("MiniMax H3 local profile does not support image-to-video.")

        strategy = request.continuityStrategy or "none"
        if strategy in ("native_tail", "native_extend", "last_frame_i2v", "multi_frame"):
            strategy = "prompt_context"
        if request.lastFrameAssetId and strategy == "none":
            strategy = "prompt_context"

        notes = [
            f"batchBlockId={request.batchBlockId}",
            f"executionSnapshotId={request.executionSnapshotId}",
            f"continuityStrategy={strategy}",
        ]
        if request.lastFrameAssetId:
            notes.append(f"continuityLastFrameAssetId={request.lastFrameAssetId}")
            notes.append("Continue the same scene, characters, wardrobe, lighting, and location from the previous shot.")

        prompt = request.prompt
        if strategy == "prompt_context" and request.lastFrameAssetId:
            prompt = (
                "Continue this scene from the previous shot. Keep the same characters, wardrobe, "
                "lighting, and location.\n"
                + (prompt or "")
            ).strip()

        h3_req = AdeptMiniMaxH3Request(
            projectId=request.projectId,
            prompt=prompt,
            territory=str(request.providerOptions.get("territory") or "PRIVATE"),
            sourceSurface="timeline",
            mode=mode,  # type: ignore[arg-type]
            deployment="local_weights",
            durationSec=float(request.duration or 5.0),
            timelineContext=H3TimelineContext(
                sceneId=request.sceneId,
                shotId=request.batchBlockId,
                notes=notes,
            ),
            creatorNotes=(
                f"timeline-batch generatorId={request.generatorId} "
                f"planningAnchor={request.providerOptions.get('planningStartImageAssetId') or ''} "
                f"continuityStrategy={strategy}"
            ),
        )
        plan = prepare_plan(h3_req)
        created = create_job_or_block(request.projectId, plan.planId, approval_id=None)
        if not created.get("ok"):
            raise RuntimeError(
                str(created.get("message") or created.get("status") or "MiniMax H3 submit failed")
            )

        job_id = str(created.get("jobId") or "")
        prov = created.get("provenance") if isinstance(created.get("provenance"), dict) else {}
        return NormalizedJobSubmission(
            internalJobId=job_id or plan.planId,
            providerJobId=job_id,
            queueJobId=job_id,
            generatorId=GENERATOR_ID,
            status="running" if created.get("status") == "running" else "queued",
            apiUsed=bool(prov.get("apiUsed", False)),
            providerMetadata={
                "planId": plan.planId,
                "modelId": prov.get("modelId") or "minimax-h3-route-a-local",
                "deployment": "private-local",
                "ltxUsed": bool(prov.get("ltxUsed", False)),
                "profile": prov.get("profile") or "Experimental Private Profile",
                "executionSnapshotId": request.executionSnapshotId,
                "batchBlockId": request.batchBlockId,
                "continuityStrategy": strategy,
                "continuityBridgeId": request.continuityBridgeId,
                "lastFrameAssetId": request.lastFrameAssetId,
                "temporalContinuityPacketId": request.temporalContinuityPacketId,
                "temporalContinuationApplied": bool(
                    (request.providerOptions or {}).get("temporalContinuation", {}).get("applied")
                ),
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        project_id = str(job.providerMetadata.get("projectId") or "")
        # projectId is required — recover from metadata or fail closed
        if not project_id:
            # Prefer queueJobId lookup path that embeds project in caller metadata
            project_id = str(job.providerMetadata.get("project_id") or "")
        job_id = job.queueJobId or job.providerJobId or job.internalJobId
        if not project_id:
            return NormalizedJobStatus(
                internalJobId=job.internalJobId,
                providerJobId=job.providerJobId,
                queueJobId=job.queueJobId,
                generatorId=GENERATOR_ID,
                status="failed",
                errorCode="H3_PROJECT_MISSING",
                errorMessage="MiniMax status requires projectId in providerMetadata.",
                apiUsed=job.apiUsed,
            )
        payload = get_job(project_id, job_id)
        raw = payload.get("job") if isinstance(payload.get("job"), dict) else {}
        status_raw = str(raw.get("status") or payload.get("status") or "queued")
        mapped = _map_status(status_raw)
        progress = 1.0 if mapped == "completed" else (0.5 if mapped == "running" else 0.0)
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            queueJobId=job.queueJobId,
            generatorId=GENERATOR_ID,
            status=mapped,
            progress=progress,
            errorCode=raw.get("error_code") or raw.get("errorCode"),
            errorMessage=raw.get("error_message") or raw.get("errorMessage"),
            apiUsed=bool((raw.get("provenance") or {}).get("apiUsed", job.apiUsed)),
            providerMetadata={
                **job.providerMetadata,
                "stage": raw.get("stage"),
                "outputPath": raw.get("output_path") or raw.get("outputPath"),
                "provenance": raw.get("provenance") or {},
                "media": raw.get("media") or {},
            },
        )

    def cancel(self, job: NormalizedJobSubmission) -> None:
        plan_id = str(job.providerMetadata.get("planId") or "")
        project_id = str(job.providerMetadata.get("projectId") or "")
        if project_id and plan_id:
            h3_cancel(project_id, plan_id, reason="timeline-batch-cancel")

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        import time
        from pathlib import Path

        from ....db import SessionLocal
        from ....minimax_h3.route_a_adapter import import_output_to_project_library

        status = self.get_status(job)
        if status.status != "completed":
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                providerJobId=job.providerJobId,
                queueJobId=job.queueJobId,
                generatorId=GENERATOR_ID,
                status=status.status,
                progress=status.progress,
                apiUsed=status.apiUsed,
                providerMetadata=status.providerMetadata,
                errorCode=status.errorCode or "H3_NOT_COMPLETE",
                errorMessage=status.errorMessage or "MiniMax job is not complete.",
            )

        asset_id = None
        # Library import may lag briefly after Comfy marks the job complete.
        for _ in range(30):
            status = self.get_status(job)
            prov = status.providerMetadata.get("provenance") or {}
            media = status.providerMetadata.get("media") or {}
            lib = media.get("libraryImport") if isinstance(media, dict) else None
            if isinstance(lib, dict):
                asset_id = lib.get("assetId")
            if not asset_id and isinstance(prov, dict):
                asset_id = prov.get("libraryAssetId")
            if asset_id:
                break
            output_path = status.providerMetadata.get("outputPath")
            project_id = str(job.providerMetadata.get("projectId") or "")
            if output_path and project_id and Path(str(output_path)).is_file():
                db = SessionLocal()
                try:
                    receipt = import_output_to_project_library(
                        project_id=project_id,
                        source_mp4=Path(str(output_path)),
                        tag="minimax-h3",
                        db=db,
                    )
                    asset_id = receipt.get("assetId")
                    if asset_id:
                        break
                except Exception:
                    pass
                finally:
                    db.close()
            time.sleep(2)

        if not asset_id:
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                providerJobId=job.providerJobId,
                queueJobId=job.queueJobId,
                generatorId=GENERATOR_ID,
                status="failed",
                apiUsed=status.apiUsed,
                providerMetadata=status.providerMetadata,
                errorCode="H3_LIBRARY_IMPORT_MISSING",
                errorMessage="MiniMax completed but Library asset id is missing.",
            )
        prov = status.providerMetadata.get("provenance") or {}
        if prov.get("ltxUsed") or status.providerMetadata.get("ltxUsed"):
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                generatorId=GENERATOR_ID,
                status="failed",
                errorCode="H3_SILENT_FALLBACK",
                errorMessage="LTX was used — forbidden for MiniMax Timeline batch without explicit approval.",
                providerMetadata=status.providerMetadata,
            )
        return TimelineGenerationResult(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            queueJobId=job.queueJobId,
            generatorId=GENERATOR_ID,
            status="completed",
            progress=1.0,
            outputAssetIds=[str(asset_id)],
            duration=5.0,
            resolution="480x256",
            apiUsed=bool(prov.get("apiUsed", False)),
            providerMetadata={
                **status.providerMetadata,
                "modelId": prov.get("modelId") or "minimax-h3-route-a-local",
                "ltxUsed": False,
            },
        )


def bind_project(job: NormalizedJobSubmission, project_id: str) -> NormalizedJobSubmission:
    meta = dict(job.providerMetadata or {})
    meta["projectId"] = project_id
    job.providerMetadata = meta
    return job


def _map_status(raw: str) -> Any:
    s = (raw or "").lower()
    if s in ("completed", "success", "done"):
        return "completed"
    if s in ("failed", "error"):
        return "failed"
    if s in ("cancelled", "canceled"):
        return "cancelled"
    if s in ("running", "processing"):
        return "running"
    if s in ("queued", "pending"):
        return "queued"
    return "running"
