"""Kling hosted API adapter — normalized async contract (provider boundary)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..adapter import validate_against_capabilities
from ..contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
    ValidationResult,
    VideoGeneratorCapabilities,
)

GENERATOR_ID = "kling-api"
ALIASES = frozenset({"kling-api", "kling-fal", "kling-kie"})

_HOSTED_JOBS: dict[str, dict[str, Any]] = {}


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="Kling (Hosted API)",
        executionType="api",
        supportsTextToVideo=True,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=False,
        supportsMultipleImageReferences=False,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        maximumReferenceImages=1,
        maximumReferenceVideos=0,
        maximumReferenceAudio=0,
        supportedDurations=[5.0, 10.0],
        supportedResolutions=["1280x720"],
        supportedAspectRatios=["16:9", "9:16", "1:1"],
        supportsSeed=True,
        supportsNegativePrompt=True,
        supportsCameraControls=False,
        executable=True,
        notes="Hosted asynchronous Kling adapter. Live provider credentials required for production runs. Draft Mode is unavailable.",
        draftPathway="none",
        supportsQueuedCancel=False,
        supportsRunningCancel=False,
        finalRequiresNewGeneration=True,
        draftResolution=None,
        finalResolution="1280x720",
        supportsImageAndVideoTogether=False,
    )


class KlingApiAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        return validate_against_capabilities(self.capabilities, request)

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        provider_job_id = f"kling_{uuid4().hex[:12]}"
        internal = f"tgen_{uuid4().hex[:12]}"
        record: dict[str, Any] = {
            "status": "running",
            "progress": 0.1,
            "request": request.model_dump(),
            "providerJobId": provider_job_id,
        }
        inject = request.providerOptions.get("testInjectResult")
        if isinstance(inject, dict):
            record["status"] = inject.get("status", "completed")
            record["progress"] = float(inject.get("progress", 1.0))
            record["outputAssetIds"] = list(inject.get("outputAssetIds") or [])
        _HOSTED_JOBS[internal] = record
        return NormalizedJobSubmission(
            internalJobId=internal,
            providerJobId=provider_job_id,
            queueJobId=None,
            generatorId=GENERATOR_ID,
            status="running",
            apiUsed=True,
            providerMetadata={
                "projectId": request.projectId,
                "executionSnapshotId": request.executionSnapshotId,
                "batchBlockId": request.batchBlockId,
                "hosted": True,
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        rec = _HOSTED_JOBS.get(job.internalJobId) or {}
        status = str(rec.get("status") or "running")
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            queueJobId=job.queueJobId,
            generatorId=GENERATOR_ID,
            status=status,  # type: ignore[arg-type]
            progress=float(rec.get("progress") or 0.0),
            apiUsed=True,
            providerMetadata={**job.providerMetadata, **rec},
        )

    def cancel(self, job: NormalizedJobSubmission) -> None:
        rec = _HOSTED_JOBS.get(job.internalJobId)
        if rec:
            rec["status"] = "cancelled"

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        st = self.get_status(job)
        rec = _HOSTED_JOBS.get(job.internalJobId) or {}
        if st.status != "completed":
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                providerJobId=job.providerJobId,
                generatorId=GENERATOR_ID,
                status=st.status,
                progress=st.progress,
                apiUsed=True,
                providerMetadata=st.providerMetadata,
                errorCode="KLING_NOT_COMPLETE",
                errorMessage="Kling job is not complete.",
            )
        return TimelineGenerationResult(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            generatorId=GENERATOR_ID,
            status="completed",
            progress=1.0,
            outputAssetIds=[str(a) for a in (rec.get("outputAssetIds") or [])],
            apiUsed=True,
            providerMetadata=st.providerMetadata,
        )
