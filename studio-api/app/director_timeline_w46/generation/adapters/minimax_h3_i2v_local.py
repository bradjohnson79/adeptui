"""MiniMax H3 local image-to-video adapter — Route A I2VA (LoadImage → first_frame)."""

from __future__ import annotations

from typing import Any

from ....minimax_h3.contracts import AdeptMiniMaxH3Request, H3ReferenceAssignment, H3TimelineContext
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

GENERATOR_ID = "minimax-h3-i2v-local"
ALIASES = frozenset({"minimax-h3-i2v-local", "minimax-h3-i2v"})


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="MiniMax H3 Image-to-Video (Local)",
        executionType="local",
        supportsTextToVideo=False,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=False,
        supportsMultipleImageReferences=False,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        maximumReferenceImages=1,
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
            "Experimental Private Profile — image-to-video with native audio. "
            "Requires a start image; never silently falls back to text-to-video."
        ),
    )


class MiniMaxH3I2VLocalAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        result = validate_against_capabilities(self.capabilities, request)
        errors = list(result.errors or [])
        if request.fallbackAllowed:
            errors.append("fallbackAllowed must be false for MiniMax H3 I2V certification path.")
        if request.generationMode != "image_to_video":
            errors.append("MiniMax H3 I2V requires generationMode=image_to_video.")
        if not (request.startImageAssetId or "").strip():
            errors.append("MiniMax H3 I2V requires startImageAssetId.")
        # Refuse T2V-only generator ids / silent downgrade.
        if request.generatorId in {"minimax-h3-t2v-local", "minimax-h3-local", "minimax-h3"}:
            errors.append("T2V-only MiniMax profile cannot run image-to-video.")
        return ValidationResult(
            ok=not errors,
            errors=errors,
            warnings=list(result.warnings or []),
        )

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        validation = self.validate(request)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors) or "MiniMax H3 I2V validation failed.")

        start_id = str(request.startImageAssetId or "").strip()
        h3_req = AdeptMiniMaxH3Request(
            projectId=request.projectId,
            prompt=request.prompt,
            territory=str(request.providerOptions.get("territory") or "PRIVATE"),
            sourceSurface="timeline",
            mode="one-frame",
            deployment="local_weights",
            durationSec=float(request.duration or 5.0),
            referenceAssignments=[
                H3ReferenceAssignment(
                    role="start",
                    assetId=start_id,
                    displayName="Start frame",
                )
            ],
            timelineContext=H3TimelineContext(
                sceneId=request.sceneId,
                shotId=request.batchBlockId,
                notes=[
                    f"batchBlockId={request.batchBlockId}",
                    f"executionSnapshotId={request.executionSnapshotId}",
                    f"startImageAssetId={start_id}",
                    "generatorId=minimax-h3-i2v-local",
                ],
            ),
            creatorNotes=(
                f"timeline-batch generatorId={request.generatorId} "
                f"startImageAssetId={start_id}"
            ),
        )
        plan = prepare_plan(h3_req)
        created = create_job_or_block(request.projectId, plan.planId, approval_id=None)
        if not created.get("ok"):
            raise RuntimeError(
                str(created.get("message") or created.get("status") or "MiniMax H3 I2V submit failed")
            )

        job_id = str(created.get("jobId") or "")
        # Fail closed if runtime persisted a T2V-only graph (no LoadImage / first_frame).
        binding = _load_i2v_binding(request.projectId, job_id)
        if binding is None or not binding.get("comfyImageName") or not binding.get("hasFirstFrame"):
            raise RuntimeError(
                "MiniMax H3 I2V refused to continue: submitted Comfy graph omitted image binding."
            )

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
                "projectId": request.projectId,
                "modelId": prov.get("modelId") or "minimax-h3-route-a-local",
                "deployment": "private-local",
                "ltxUsed": bool(prov.get("ltxUsed", False)),
                "profile": prov.get("profile") or "Experimental Private Profile",
                "workflowId": "route-a-experimental-private-i2va",
                "executionSnapshotId": request.executionSnapshotId,
                "batchBlockId": request.batchBlockId,
                "startImageAssetId": start_id,
                "startImageSha256": binding.get("startImageSha256"),
                "comfyImageName": binding.get("comfyImageName"),
                "firstFrameNodeId": binding.get("firstFrameNodeId"),
                "submittedGraphPath": binding.get("submittedGraphPath"),
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        project_id = str(job.providerMetadata.get("projectId") or "")
        job_id = job.queueJobId or job.providerJobId or job.internalJobId
        if not project_id:
            return NormalizedJobStatus(
                internalJobId=job.internalJobId,
                providerJobId=job.providerJobId,
                queueJobId=job.queueJobId,
                generatorId=GENERATOR_ID,
                status="failed",
                errorCode="H3_PROJECT_MISSING",
                errorMessage="MiniMax I2V status requires projectId in providerMetadata.",
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
                "submittedGraph": raw.get("submittedGraph") or {},
                "comfyImageName": raw.get("comfyImageName") or job.providerMetadata.get("comfyImageName"),
                "startImageSha256": raw.get("startImageSha256")
                or job.providerMetadata.get("startImageSha256"),
            },
        )

    def cancel(self, job: NormalizedJobSubmission) -> None:
        plan_id = str(job.providerMetadata.get("planId") or "")
        project_id = str(job.providerMetadata.get("projectId") or "")
        if project_id and plan_id:
            h3_cancel(project_id, plan_id, reason="timeline-batch-i2v-cancel")

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
                errorMessage=status.errorMessage or "MiniMax I2V job is not complete.",
            )

        asset_id = None
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
                        tag="minimax-h3-i2v",
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
                errorMessage="MiniMax I2V completed but Library asset id is missing.",
            )
        prov = status.providerMetadata.get("provenance") or {}
        if prov.get("ltxUsed") or status.providerMetadata.get("ltxUsed"):
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                generatorId=GENERATOR_ID,
                status="failed",
                errorCode="H3_SILENT_FALLBACK",
                errorMessage="LTX was used — forbidden for MiniMax I2V Timeline batch.",
                providerMetadata=status.providerMetadata,
            )
        if prov.get("workflowId") == "route-a-experimental-private-t2va":
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                generatorId=GENERATOR_ID,
                status="failed",
                errorCode="H3_I2V_DOWNGRADED_TO_T2V",
                errorMessage="I2V path produced a T2V workflow id — refused.",
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
                "workflowId": prov.get("workflowId") or "route-a-experimental-private-i2va",
                "ltxUsed": False,
                "startImageAssetId": job.providerMetadata.get("startImageAssetId"),
                "startImageSha256": status.providerMetadata.get("startImageSha256")
                or job.providerMetadata.get("startImageSha256"),
                "comfyImageName": status.providerMetadata.get("comfyImageName")
                or job.providerMetadata.get("comfyImageName"),
            },
        )


def _load_i2v_binding(project_id: str, job_id: str) -> dict[str, Any] | None:
    if not project_id or not job_id:
        return None
    payload = get_job(project_id, job_id)
    raw = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    graph = raw.get("submittedGraph") if isinstance(raw.get("submittedGraph"), dict) else {}
    has_load = any(
        isinstance(node, dict) and node.get("class_type") == "LoadImage" for node in graph.values()
    )
    has_first = False
    for node in graph.values():
        if not isinstance(node, dict) or node.get("class_type") != "MiniMaxH3ImageToVideo":
            continue
        first = (node.get("inputs") or {}).get("first_frame")
        if isinstance(first, list) and first:
            has_first = True
            break
    from ....minimax_h3.store import project_dir

    graph_path = project_dir(project_id) / "jobs" / f"{job_id}.submitted-graph.json"
    return {
        "comfyImageName": raw.get("comfyImageName"),
        "startImageSha256": raw.get("startImageSha256"),
        "firstFrameNodeId": (raw.get("provenance") or {}).get("firstFrameNodeId"),
        "hasLoadImage": has_load,
        "hasFirstFrame": has_first,
        "submittedGraphPath": str(graph_path) if graph_path.is_file() else None,
    }


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
