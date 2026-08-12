"""Seedance hosted API adapter — normalized async contract (provider boundary)."""

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

GENERATOR_ID = "seedance-api"
ALIASES = frozenset({"seedance-api", "seedance-kie", "seedance-fal"})

# In-memory hosted job ledger for contract/regression tests and dry submissions.
_HOSTED_JOBS: dict[str, dict[str, Any]] = {}


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="Seedance (Hosted API)",
        executionType="api",
        supportsTextToVideo=True,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=True,
        supportsMultipleImageReferences=True,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        maximumReferenceImages=4,
        maximumReferenceVideos=0,
        maximumReferenceAudio=0,
        supportedDurations=[5.0, 8.0, 12.0],
        supportedResolutions=["1280x720"],
        supportedAspectRatios=["16:9", "9:16"],
        supportsSeed=True,
        supportsNegativePrompt=False,
        supportsCameraControls=False,
        executable=True,
        notes="Hosted asynchronous Seedance adapter. Live provider credentials required for production runs.",
    )


class SeedanceApiAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        return validate_against_capabilities(self.capabilities, request)

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        provider_job_id = f"seedance_{uuid4().hex[:12]}"
        internal = f"tgen_{uuid4().hex[:12]}"
        record = {
            "status": "running",
            "progress": 0.1,
            "request": request.model_dump(),
            "providerJobId": provider_job_id,
        }
        # Optional inject for tests: immediate complete with asset ids
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
                errorCode="SEEDANCE_NOT_COMPLETE",
                errorMessage="Seedance job is not complete.",
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
