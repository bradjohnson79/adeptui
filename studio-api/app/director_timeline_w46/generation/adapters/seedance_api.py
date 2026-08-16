"""Seedance hosted API adapter — normalized async contract (provider boundary)."""

from __future__ import annotations

import threading
from pathlib import Path
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

# In-memory hosted job ledger for contract/regression tests and live submissions.
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
        supportsVideoReferences=True,
        supportsAudioReferences=False,
        maximumReferenceImages=4,
        maximumReferenceVideos=1,
        maximumReferenceAudio=0,
        supportedDurations=[4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
        supportedResolutions=["480p", "720p"],
        supportedAspectRatios=["16:9", "9:16", "1:1", "4:3", "21:9"],
        supportsSeed=True,
        supportsNegativePrompt=False,
        supportsCameraControls=False,
        executable=True,
        notes=(
            "Hosted Seedance 2.0 via fal.ai. Draft uses 480p on the same model; "
            "Promote starts a new 720p generation. Video Reference uses reference-to-video."
        ),
        draftPathway="cheap_preview",
        supportsQueuedCancel=False,
        supportsRunningCancel=False,
        finalRequiresNewGeneration=True,
        draftResolution="480p",
        finalResolution="720p",
        supportsImageAndVideoTogether=True,
    )


def _asset_path(asset_id: str | None) -> Path | None:
    if not (asset_id or "").strip():
        return None
    from ....db import Asset, SessionLocal

    db = SessionLocal()
    try:
        row = db.get(Asset, str(asset_id))
        if row and row.path and Path(str(row.path)).is_file():
            return Path(str(row.path))
    finally:
        db.close()
    return None


def _run_live(internal: str, request: TimelineGenerationRequest) -> None:
    rec = _HOSTED_JOBS.get(internal) or {}
    try:
        import asyncio

        from ....fal_catalog import build_fal_arguments, build_seedance_r2v_arguments
        from ....fal_client import download_url, extract_video_url, run_fal_model, upload_file_to_fal
        from ....minimax_h3.route_a_adapter import import_output_to_project_library
        from ....secrets_store import get_secret
        from ....config import settings

        api_key = get_secret("fal_api_key")
        if not api_key:
            rec["status"] = "failed"
            rec["error"] = "Hosted AI Provider credential not configured for fal.ai."
            _HOSTED_JOBS[internal] = rec
            return

        draft = bool(request.providerOptions.get("draftMode"))
        resolution = request.resolution if request.resolution in ("480p", "720p") else (
            "480p" if draft else "720p"
        )
        aspect = request.aspectRatio or "16:9"
        seed = int(request.seed) if request.seed is not None else -1

        async def _go() -> None:
            image_url = None
            end_url = None
            video_url_in = None
            start_path = _asset_path(request.startImageAssetId)
            if start_path:
                image_url = await upload_file_to_fal(start_path, api_key)
            end_path = _asset_path(request.endImageAssetId)
            if end_path:
                end_url = await upload_file_to_fal(end_path, api_key)
            video_path = _asset_path(request.videoReferenceAssetId)
            if video_path:
                video_url_in = await upload_file_to_fal(video_path, api_key)

            if video_url_in:
                image_urls = [u for u in [image_url] if u]
                for extra in request.referenceAssetIds or []:
                    extra_path = _asset_path(extra)
                    if extra_path:
                        image_urls.append(await upload_file_to_fal(extra_path, api_key))
                model_id, args = build_seedance_r2v_arguments(
                    prompt=request.prompt,
                    image_urls=image_urls,
                    video_urls=[video_url_in],
                    duration_sec=request.duration,
                    aspect_ratio=aspect,
                    resolution=resolution,
                    seed=seed,
                )
            else:
                model_id, args = build_fal_arguments(
                    engine="fal_seedance",
                    prompt=request.prompt,
                    negative=request.negativePrompt or "",
                    image_url=image_url,
                    end_image_url=end_url,
                    duration_sec=request.duration,
                    width=0,
                    height=0,
                    seed=seed,
                    aspect_ratio=aspect,
                    resolution=resolution,
                )
            rec["falModelId"] = model_id
            rec["falArgs"] = {k: v for k, v in args.items() if k not in ("image_url", "image_urls", "video_urls", "end_image_url")}
            rec["progress"] = 0.3
            _HOSTED_JOBS[internal] = rec

            async def on_request_id(request_id: str) -> None:
                rec["falRequestId"] = request_id
                rec["providerJobId"] = request_id
                _HOSTED_JOBS[internal] = rec

            result = await run_fal_model(model_id, args, api_key, on_request_id=on_request_id)
            out_url = extract_video_url(result)
            dest_dir = settings.data_dir / "projects" / request.projectId / "renders"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"seedance_{uuid4().hex[:8]}.mp4"
            await download_url(out_url, dest)

            from ....db import SessionLocal

            db = SessionLocal()
            try:
                tag = "seedance-draft" if draft else "seedance"
                receipt = import_output_to_project_library(
                    project_id=request.projectId,
                    source_mp4=dest,
                    tag=tag,
                    db=db,
                )
                asset_id = receipt.get("assetId")
            finally:
                db.close()
            rec["status"] = "completed"
            rec["progress"] = 1.0
            rec["outputAssetIds"] = [str(asset_id)] if asset_id else []
            rec["outputPath"] = str(dest)
            rec["draftMode"] = draft
            rec["aspectRatio"] = aspect
            rec["resolution"] = resolution
            rec["videoReferenceAssetId"] = request.videoReferenceAssetId
            _HOSTED_JOBS[internal] = rec

        asyncio.run(_go())
    except Exception as exc:
        rec["status"] = "failed"
        rec["error"] = str(exc)[:800]
        _HOSTED_JOBS[internal] = rec


class SeedanceApiAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        return validate_against_capabilities(self.capabilities, request)

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        provider_job_id = f"seedance_{uuid4().hex[:12]}"
        internal = f"tgen_{uuid4().hex[:12]}"
        record: dict[str, Any] = {
            "status": "running",
            "progress": 0.1,
            "request": request.model_dump(),
            "providerJobId": provider_job_id,
            "draftMode": bool(request.providerOptions.get("draftMode")),
            "aspectRatio": request.aspectRatio,
            "resolution": request.resolution,
            "videoReferenceAssetId": request.videoReferenceAssetId,
        }
        inject = request.providerOptions.get("testInjectResult")
        if isinstance(inject, dict):
            record["testInject"] = True
            record["status"] = inject.get("status", "completed")
            record["progress"] = float(inject.get("progress", 1.0))
            record["outputAssetIds"] = list(inject.get("outputAssetIds") or [])
        _HOSTED_JOBS[internal] = record
        if not isinstance(inject, dict):
            thread = threading.Thread(
                target=_run_live,
                args=(internal, request),
                name=f"seedance-{internal[-8:]}",
                daemon=True,
            )
            thread.start()
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
                "draftMode": bool(request.providerOptions.get("draftMode")),
                "aspectRatio": request.aspectRatio,
                "resolution": request.resolution,
                "videoReferenceAssetId": request.videoReferenceAssetId,
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        rec = _HOSTED_JOBS.get(job.internalJobId) or {}
        status = str(rec.get("status") or "running")
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=rec.get("falRequestId") or rec.get("providerJobId") or job.providerJobId,
            queueJobId=job.queueJobId,
            generatorId=GENERATOR_ID,
            status=status,  # type: ignore[arg-type]
            progress=float(rec.get("progress") or 0.0),
            errorMessage=rec.get("error") if status == "failed" else None,
            apiUsed=True,
            providerMetadata={**job.providerMetadata, **rec},
        )

    def cancel(self, job: NormalizedJobSubmission) -> None:
        rec = _HOSTED_JOBS.get(job.internalJobId)
        if rec and rec.get("testInject"):
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
                errorCode="SEEDANCE_NOT_COMPLETE" if st.status != "failed" else "SEEDANCE_FAILED",
                errorMessage=st.errorMessage or "Seedance job is not complete.",
            )
        return TimelineGenerationResult(
            internalJobId=job.internalJobId,
            providerJobId=st.providerJobId,
            generatorId=GENERATOR_ID,
            status="completed",
            progress=1.0,
            outputAssetIds=[str(a) for a in (rec.get("outputAssetIds") or [])],
            apiUsed=True,
            providerMetadata=st.providerMetadata,
        )
