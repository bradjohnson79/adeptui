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

GENERATOR_ID = "seedance-2.0"
ALIASES = frozenset({"seedance-2.0", "seedance-api", "seedance-fal", "fal_seedance"})
SEEDANCE_25_ID = "seedance-2.5"
SEEDANCE_25_ALIASES = frozenset({"seedance-2.5", "fal_seedance_25"})
SEEDANCE_MINI_ID = "seedance-2.0-mini"
SEEDANCE_MINI_ALIASES = frozenset({"seedance-2.0-mini", "seedance-mini", "fal_seedance_mini"})
SEEDANCE_FAST_ID = "seedance-2.0-fast"
SEEDANCE_FAST_ALIASES = frozenset({"seedance-2.0-fast", "seedance-fast", "fal_seedance_fast"})

# In-memory hosted job ledger for contract/regression tests and live submissions.
_HOSTED_JOBS: dict[str, dict[str, Any]] = {}


def _resolutions_for(product_id: str) -> list[str]:
    from ....fal_catalog import SEEDANCE_RESOLUTIONS

    return list(SEEDANCE_RESOLUTIONS.get(product_id, ("480p", "720p")))


def _capabilities(
    product_id: str,
    version: str,
    *,
    durations: list[float] | None = None,
    force_r2v: bool = False,
) -> VideoGeneratorCapabilities:
    # CERTIFIED_CURRENT (Brad + fal OpenAPI): Seedance 2.0/fast default 4–15;
    # Seedance 2.5 overrides to 4–30; mini overrides to 4–15.
    dur = durations or [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    # Mini Scene-12 path is reference-to-video only (no silent T2V).
    supports_t2v = not force_r2v
    return VideoGeneratorCapabilities(
        id=product_id,
        label=f"Seedance {version}",
        executionType="api",
        supportsTextToVideo=supports_t2v,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=True,
        supportsMultipleImageReferences=True,
        supportsVideoReferences=True,
        supportsAudioReferences=False,
        audio_generation=True,
        qualityControl="seedance_resolution",
        maximumReferenceImages=4,
        maximumReferenceVideos=1,
        maximumReferenceAudio=0,
        supportedDurations=dur,
        supportedResolutions=_resolutions_for(product_id),
        supportedAspectRatios=["16:9", "9:16", "1:1", "4:3", "21:9", "3:4", "auto"],
        supportsSeed=True,
        supportsNegativePrompt=False,
        supportsCameraControls=False,
        executable=True,
        continuationMode="soft" if product_id == SEEDANCE_MINI_ID else "hard",
        notes=(
            (
                "Hosted Seedance 2.0 Mini via fal.ai reference-to-video only "
                "(bytedance/seedance-2.0/mini/reference-to-video). Duration 4–15s. "
                "No silent T2V/full remap. Continuity via image_urls + @ImageN."
            )
            if force_r2v
            else (
                f"Hosted Seedance {version} via fal.ai. Draft uses 480p on the same model; "
                "Promote starts a new 720p generation. Video Reference uses reference-to-video. "
                "Adept does not invent extra duration or reference slots beyond this adapter."
            )
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


def _run_live(internal: str, request: TimelineGenerationRequest, *, product_id: str) -> None:
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

        from ....film_timeline.render_status import hold_api_preparation

        if not hold_api_preparation(rec):
            _HOSTED_JOBS[internal] = rec
            return
        _HOSTED_JOBS[internal] = rec

        draft = bool(request.providerOptions.get("draftMode"))
        from ....fal_catalog import normalize_seedance_resolution

        opts = request.providerOptions or {}
        if "generate_audio" in opts:
            generate_audio = bool(opts.get("generate_audio"))
        elif "audio_generation" in opts:
            generate_audio = bool(opts.get("audio_generation"))
        else:
            generate_audio = True
        asked = request.resolution or ("480p" if draft else "720p")
        resolution = normalize_seedance_resolution(product_id, asked)
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
            # A continuation start image is the generation state. The previous
            # clip is not uploaded with it: that clip repeats the earlier line
            # and gives the model a different opening.
            continuation = (
                str(request.continuityStrategy or "") == "last_frame_chain"
                and bool(str(request.startImageAssetId or "").strip())
            )
            video_path = None if continuation else _asset_path(request.videoReferenceAssetId)
            if video_path:
                video_url_in = await upload_file_to_fal(video_path, api_key)

            # Collect image URLs (start + extras) for R2V image_urls order.
            # Skip duplicate asset ids so @ImageN order stays 1:1 with refs.
            image_urls = [u for u in [image_url] if u]
            seen_ids = set()
            start_id = str(request.startImageAssetId or "").strip()
            if start_id:
                seen_ids.add(start_id)
            for extra in request.referenceAssetIds or []:
                eid = str(extra or "").strip()
                if not eid or eid in seen_ids:
                    continue
                seen_ids.add(eid)
                extra_path = _asset_path(eid)
                if extra_path:
                    image_urls.append(await upload_file_to_fal(extra_path, api_key))
            video_urls = [video_url_in] if video_url_in else []
            from ....fal_catalog import seedance_continuation_route

            route = seedance_continuation_route(
                product_id,
                has_start_image=bool(image_url),
                has_video=bool(video_url_in),
            )
            rec["continuationRoute"] = route
            use_mini_r2v = route == "reference_image" or (
                str(product_id) == "seedance-2.0-mini" and route != "image_to_video"
            )
            # Mini: always fal mini/reference-to-video when any image or video ref exists.
            # Full 2.0/2.5: keep prior gate (R2V only when video ref attached).
            if use_mini_r2v:
                if not image_urls and not video_urls:
                    raise RuntimeError(
                        "Seedance Mini reference-to-video requires at least one image or video reference."
                    )
                model_id, args = build_seedance_r2v_arguments(
                    prompt=request.prompt,
                    image_urls=image_urls,
                    video_urls=video_urls,
                    duration_sec=request.duration,
                    aspect_ratio=aspect,
                    resolution=resolution,
                    seed=seed,
                    generate_audio=generate_audio,
                    engine=product_id,
                )
            elif video_url_in:
                model_id, args = build_seedance_r2v_arguments(
                    prompt=request.prompt,
                    image_urls=image_urls,
                    video_urls=video_urls,
                    duration_sec=request.duration,
                    aspect_ratio=aspect,
                    resolution=resolution,
                    seed=seed,
                    generate_audio=generate_audio,
                    engine=product_id,
                )
            else:
                model_id, args = build_fal_arguments(
                    engine=product_id,
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
                    generate_audio=generate_audio,
                )
            rec["falModelId"] = model_id
            rec["falArgs"] = {k: v for k, v in args.items() if k not in ("image_url", "image_urls", "video_urls", "end_image_url")}
            import time as _time

            from ....film_timeline.render_status import begin_api_generation, note_api_render_progress

            started = _time.monotonic()

            def _note(message: str) -> None:
                note_api_render_progress(rec, message=message, elapsed_sec=_time.monotonic() - started)
                _HOSTED_JOBS[internal] = rec

            async def on_submit_meta(meta: dict[str, Any]) -> None:
                rec["falCancelUrl"] = meta.get("cancel_url")

            async def on_request_id(request_id: str) -> None:
                rec["falRequestId"] = request_id
                rec["providerJobId"] = request_id
                _HOSTED_JOBS[internal] = rec
                try:
                    from pathlib import Path as _P
                    import json as _json, time as _time
                    _ledger = _P(__file__).resolve().parents[4] / ".runtime" / "seedance_fal_ledger.jsonl"
                    # parents: adapters->generation->director_timeline_w46->app->studio-api; want AIVideoStudio
                    _ledger = _P(r"C:\AdeptFilmWorks\AIVideoStudio\.runtime\seedance_fal_ledger.jsonl")
                    _ledger.parent.mkdir(parents=True, exist_ok=True)
                    with _ledger.open("a", encoding="utf-8") as _fh:
                        _fh.write(_json.dumps({
                            "ts": _time.time(),
                            "internalJobId": internal,
                            "falRequestId": request_id,
                            "falModelId": rec.get("falModelId"),
                            "providerJobId": request_id,
                            "productId": product_id,
                        }) + "\n")
                except Exception:
                    pass

            async def on_progress(_progress: float, message: str) -> None:
                _note(message or "fal in progress")

            if str(rec.get("status") or "") == "cancelled":
                _HOSTED_JOBS[internal] = rec
                return
            begin_api_generation(rec)
            _HOSTED_JOBS[internal] = rec

            result = await run_fal_model(
                model_id, args, api_key,
                on_submit_meta=on_submit_meta,
                on_request_id=on_request_id,
                on_progress=on_progress,
            )
            _note("fal completed — downloading")
            out_url = extract_video_url(result)
            dest_dir = settings.data_dir / "projects" / request.projectId / "renders"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"seedance_{uuid4().hex[:8]}.mp4"
            await download_url(out_url, dest)

            from ....db import SessionLocal

            db = SessionLocal()
            try:
                version = "2.5" if product_id == SEEDANCE_25_ID else "2.0"
                tag = f"seedance-{version}-draft" if draft else f"seedance-{version}"
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
            rec["requestedEngineId"] = request.generatorId
            rec["resolvedEngineId"] = product_id
            rec["provider"] = "fal"
            rec["modelVersion"] = "2.5" if product_id == SEEDANCE_25_ID else "2.0"
            rec["falModelId"] = model_id
            _HOSTED_JOBS[internal] = rec

        asyncio.run(_go())
    except Exception as exc:
        rec["status"] = "failed"
        rec["error"] = str(exc)[:800]
        _HOSTED_JOBS[internal] = rec


class _SeedanceVersionAdapter:
    id: str
    version: str
    capabilities: VideoGeneratorCapabilities

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        # Mini (and any force-R2V Seedance): batch image/video refs must not
        # remain classified as text_to_video or CAPABILITY_VALIDATION fails.
        caps = self.capabilities
        refs = [str(x).strip() for x in (request.referenceAssetIds or []) if str(x or "").strip()]
        has_media = bool(
            str(request.startImageAssetId or "").strip()
            or refs
            or str(request.videoReferenceAssetId or "").strip()
        )
        if (
            request.generationMode == "text_to_video"
            and not caps.supportsTextToVideo
            and has_media
        ):
            if not str(request.startImageAssetId or "").strip() and refs:
                request.startImageAssetId = refs[0]
                request.referenceAssetIds = refs[1:]
            # Mini is reference-to-video; keep mode honest for capability checks.
            request.generationMode = "reference"
        return validate_against_capabilities(caps, request)

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
            "requestedEngineId": request.generatorId,
            "resolvedEngineId": self.id,
            "provider": "fal",
            "modelVersion": self.version,
        }
        inject = request.providerOptions.get("testInjectResult")
        if isinstance(inject, dict):
            record["testInject"] = True
            record["status"] = inject.get("status", "completed")
            record["progress"] = float(inject.get("progress", 1.0))
            record["outputAssetIds"] = list(inject.get("outputAssetIds") or [])
        _HOSTED_JOBS[internal] = record
        if not isinstance(inject, dict):
            from ....film_timeline.render_status import note_api_render_progress

            note_api_render_progress(record, message="preparing", elapsed_sec=0)
            thread = threading.Thread(
                target=_run_live,
                args=(internal, request),
                kwargs={"product_id": self.id},
                name=f"seedance-{self.version}-{internal[-8:]}",
                daemon=True,
            )
            thread.start()
        return NormalizedJobSubmission(
            internalJobId=internal,
            providerJobId=provider_job_id,
            queueJobId=None,
            generatorId=self.id,
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
                "temporalContinuityPacketId": request.temporalContinuityPacketId,
                "temporalContinuationApplied": bool(
                    (request.providerOptions or {}).get("temporalContinuation", {}).get("applied")
                ),
                "requestedEngineId": request.generatorId,
                "resolvedEngineId": self.id,
                "provider": "fal",
                "modelVersion": self.version,
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        rec = _HOSTED_JOBS.get(job.internalJobId) or {}
        status = str(rec.get("status") or "running")
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=rec.get("falRequestId") or rec.get("providerJobId") or job.providerJobId,
            queueJobId=job.queueJobId,
            generatorId=self.id,
            status=status,  # type: ignore[arg-type]
            progress=float(rec.get("progress") or 0.0),
            errorMessage=rec.get("error") if status == "failed" else None,
            apiUsed=True,
            providerMetadata={**job.providerMetadata, **rec},
        )

    def cancel(self, job: NormalizedJobSubmission) -> None:
        rec = _HOSTED_JOBS.get(job.internalJobId)
        if not rec:
            return

        # Regression / test fixture path (no remote call).
        if rec.get("testInject"):
            rec["status"] = "cancelled"
            return

        # Preparation has not called the provider yet. Cancel locally.
        if str(rec.get("apiPhase") or "") != "generating":
            rec["status"] = "cancelled"
            rec.pop("cancelRejected", None)
            return

        # Live hosted path: call fal's documented queue cancel endpoint.
        # Capability flags remain False by frozen product contract; the helper
        # is wired so a future cancel authority can invoke it without inventing
        # Comfy prompts or fake local state.
        try:
            from ....secrets_store import get_secret

            api_key = get_secret("fal_api_key")
            if not api_key:
                rec["cancelRejected"] = True
                rec["cancelReason"] = "PROVIDER_CANCEL_UNSUPPORTED"
                return

            model_id = rec.get("falModelId")
            request_id = rec.get("falRequestId")
            if not model_id or not request_id:
                rec["cancelRejected"] = True
                rec["cancelReason"] = "PROVIDER_CANCEL_UNSUPPORTED"
                return

            from ....fal_client import cancel_fal_request

            result = cancel_fal_request(
                model_id=str(model_id),
                request_id=str(request_id),
                api_key=api_key,
                cancel_url=rec.get("falCancelUrl"),
            )
            rec["falCancelResult"] = result
            rec["status"] = "cancelled"
        except Exception as exc:
            # Provider rejected or the request is already finished; leave the
            # in-memory job running so ongoing polling can report the true final
            # status instead of a fake local cancellation.
            rec["cancelRejected"] = True
            rec["cancelReason"] = "PROVIDER_CANCEL_UNSUPPORTED"
            rec["falCancelError"] = str(exc)[:500]

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        st = self.get_status(job)
        rec = _HOSTED_JOBS.get(job.internalJobId) or {}
        if st.status != "completed":
            return TimelineGenerationResult(
                internalJobId=job.internalJobId,
                providerJobId=job.providerJobId,
                generatorId=self.id,
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
            generatorId=self.id,
            status="completed",
            progress=1.0,
            outputAssetIds=[str(a) for a in (rec.get("outputAssetIds") or [])],
            apiUsed=True,
            providerMetadata=st.providerMetadata,
        )


class SeedanceApiAdapter(_SeedanceVersionAdapter):
    id = GENERATOR_ID
    version = "2.0"
    capabilities = _capabilities(GENERATOR_ID, "2.0")


class Seedance25ApiAdapter(_SeedanceVersionAdapter):
    id = SEEDANCE_25_ID
    version = "2.5"
    capabilities = _capabilities(
        SEEDANCE_25_ID,
        "2.5",
        durations=[float(s) for s in range(4, 31)],  # CERTIFIED_CURRENT 4–30
    )


class SeedanceMiniApiAdapter(_SeedanceVersionAdapter):
    id = SEEDANCE_MINI_ID
    version = "2.0-mini"
    capabilities = _capabilities(
        SEEDANCE_MINI_ID,
        "2.0 Mini",
        durations=[4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
        force_r2v=True,
    )


class SeedanceFastApiAdapter(_SeedanceVersionAdapter):
    id = SEEDANCE_FAST_ID
    version = "2.0-fast"
    capabilities = _capabilities(
        SEEDANCE_FAST_ID,
        "2.0 Fast",
        durations=[4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
    )

