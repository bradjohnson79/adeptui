"""VideoGeneratorAdapter protocol and shared capability validation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
    ValidationResult,
    VideoGeneratorCapabilities,
)


@runtime_checkable
class VideoGeneratorAdapter(Protocol):
    id: str
    capabilities: VideoGeneratorCapabilities

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult: ...

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission: ...

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus: ...

    def cancel(self, job: NormalizedJobSubmission) -> None: ...

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult: ...


def validate_against_capabilities(
    caps: VideoGeneratorCapabilities,
    request: TimelineGenerationRequest,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not request.generatorId:
        errors.append("generatorId is required.")

    if request.fallbackAllowed:
        warnings.append("fallbackAllowed=true requires explicit creator authorization at submit time.")

    mode = request.generationMode
    if mode == "text_to_video" and not caps.supportsTextToVideo:
        errors.append(f"{caps.label} does not support text-to-video.")
    if mode == "image_to_video" and not caps.supportsImageToVideo:
        errors.append(f"{caps.label} does not support image-to-video on this profile.")
    if mode == "start_end_frame" and not (caps.supportsStartFrame and caps.supportsEndFrame):
        errors.append(f"{caps.label} does not support start/end frame generation.")
    if mode == "reference":
        if caps.executionType == "local" and not caps.supportsReferenceToVideo:
            errors.append(f"{caps.label} does not support Timeline Reference-to-Video.")
        from .r2v import TIMELINE_R2V_REQUIRED, r2v_from_request, visual_slot_asset_ids

        payload = r2v_from_request(request)
        visual_ids = visual_slot_asset_ids(payload)
        if caps.executionType == "local" and not visual_ids:
            errors.append(TIMELINE_R2V_REQUIRED)
        audio_ids = [
            str(slot.assetId).strip()
            for slot in (payload.slots if payload is not None else [])
            if slot.role == "audio" and str(slot.assetId or "").strip()
        ]
        if audio_ids:
            if not caps.supportsAudioReferences or caps.maximumReferenceAudio <= 0:
                errors.append(
                    f"{caps.label} does not support voice references. Approved character "
                    "voices will not be dropped silently — use MiniMax H3 Reference-to-Video "
                    "or remove the voices."
                )
            elif len(audio_ids) > caps.maximumReferenceAudio:
                errors.append(
                    f"Too many voice/audio references ({len(audio_ids)}); max is {caps.maximumReferenceAudio}."
                )
        if audio_ids and not visual_ids:
            video_present = any(
                str(getattr(slot, "assetId", "") or "").strip()
                for slot in (payload.slots if payload is not None else [])
                if getattr(slot, "role", None) == "video"
            )
            if not video_present:
                errors.append(
                    f"{caps.label} audio references must accompany at least one image or video "
                    "reference — audio cannot be the sole Ref2VA input."
                )
        video_slot_ids = [
            str(slot.assetId).strip()
            for slot in (payload.slots if payload is not None else [])
            if slot.role == "video" and str(slot.assetId or "").strip()
        ]
        if video_slot_ids:
            if not caps.supportsVideoReferences or caps.maximumReferenceVideos <= 0:
                errors.append(
                    f"{caps.label} does not support video references. Remove the video "
                    "reference or choose a model that supports motion reference — the "
                    "reference will not be dropped silently."
                )
            elif len(video_slot_ids) > caps.maximumReferenceVideos:
                errors.append(
                    f"Too many video references ({len(video_slot_ids)}); max is {caps.maximumReferenceVideos}."
                )

    if request.startImageAssetId and mode == "image_to_video" and not caps.supportsImageToVideo:
        errors.append("Start image cannot be used for image-to-video on this generator.")
    if request.startImageAssetId and mode == "image_to_video" and not caps.supportsStartFrame:
        errors.append("Start frame is not supported by this generator.")
    if request.endImageAssetId and not caps.supportsEndFrame:
        errors.append("End frame is not supported by this generator.")

    # Generation references — never silently drop. Canonical R2V slots are
    # not counted against the leftover I2V extra-ref cap.
    image_refs = list(request.referenceAssetIds or [])
    if request.startImageAssetId and mode in ("image_to_video", "start_end_frame"):
        # start frame is a dedicated slot, not counted as a free reference
        pass
    if mode != "reference":
        if len(image_refs) > caps.maximumReferenceImages:
            errors.append(
                f"Too many image references ({len(image_refs)}); max is {caps.maximumReferenceImages}."
            )
        if image_refs and not (
            caps.supportsMultipleImageReferences or caps.maximumReferenceImages > 0
        ):
            errors.append(f"{caps.label} does not accept image references for this mode.")

    if not (request.prompt or "").strip() and mode == "text_to_video":
        errors.append("Prompt is required for text-to-video.")
    if mode == "image_to_video" and not request.startImageAssetId:
        errors.append("Start image is required for image-to-video.")
    if mode == "start_end_frame" and (not request.startImageAssetId or not request.endImageAssetId):
        errors.append("Start and end images are required for start/end frame mode.")
    if mode == "reference" and not (request.prompt or "").strip():
        errors.append("Prompt is required for Reference-to-Video.")

    max_d = getattr(caps, "maxDurationSec", None)
    if max_d is None and caps.supportedDurations:
        max_d = max(caps.supportedDurations)
    dur = int(request.duration)
    if max_d is not None and dur > int(max_d):
        errors.append(
            f"Duration {dur}s exceeds {caps.label} max {int(max_d)}s — no silent truncate."
        )
    elif caps.supportedDurations:
        listed_ints = [int(d) for d in caps.supportedDurations]
        if dur not in listed_ints:
            listed_max = max(listed_ints)
            if dur > listed_max:
                errors.append(
                    f"Duration {dur}s exceeds {caps.label} max {listed_max}s — no silent truncate."
                )
            else:
                listed = ", ".join(f"{d}s" for d in caps.supportedDurations)
                errors.append(
                    f"Duration {dur}s is not supported by {caps.label}. "
                    f"Supported durations: {listed}."
                )

    if request.negativePrompt and not caps.supportsNegativePrompt:
        errors.append("Negative prompt is not supported by this generator (refusing silent drop).")
    if request.cameraMotion and not caps.supportsCameraControls:
        errors.append("Camera controls are not supported by this generator (refusing silent drop).")
    if request.seed is not None and not caps.supportsSeed:
        errors.append("Seed is not supported by this generator (refusing silent drop).")

    # Scene aspect is framing authority. Soft-warn-and-still-gen is a defect (Law 64).
    aspect = str(request.aspectRatio or "").strip()
    listed_aspects = [str(a) for a in (caps.supportedAspectRatios or [])]
    if aspect and listed_aspects:
        ok = aspect in listed_aspects or any(aspect in a for a in listed_aspects)
        if not ok:
            errors.append(
                f"{caps.label} does not support aspect {aspect}. "
                f"Supported: {', '.join(listed_aspects)}. "
                f"Adept will not crop a different ratio and call it {aspect}."
            )

    video_ref = (request.videoReferenceAssetId or "").strip()
    stored_videos = []
    extra = request.providerOptions or {}
    for item in extra.get("videoReferenceAssetIds") or []:
        token = str(item or "").strip()
        if token and token not in stored_videos:
            stored_videos.append(token)
    if video_ref and video_ref not in stored_videos:
        stored_videos.insert(0, video_ref)
    if caps.maximumReferenceVideos > 0 and len(stored_videos) > caps.maximumReferenceVideos:
        errors.append(
            f"Too many video references ({len(stored_videos)}); max is {caps.maximumReferenceVideos}."
        )
    if video_ref:
        if not caps.supportsVideoReferences or caps.maximumReferenceVideos <= 0:
            errors.append(
                f"{caps.label} does not support video reference. Remove the Video Reference clip "
                "or choose a model that supports motion reference — the reference will not be dropped silently."
            )
        elif not caps.supportsImageAndVideoTogether and (
            request.startImageAssetId or request.referenceAssetIds
        ):
            errors.append(
                f"{caps.label} cannot use image and video references together."
            )

    if not caps.executable:
        errors.append(f"{caps.label} is not executable in this environment.")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)
