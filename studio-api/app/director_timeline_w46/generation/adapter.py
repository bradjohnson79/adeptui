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

    if request.startImageAssetId and mode == "image_to_video" and not caps.supportsImageToVideo:
        errors.append("Start image cannot be used for image-to-video on this generator.")
    if request.startImageAssetId and mode == "image_to_video" and not caps.supportsStartFrame:
        errors.append("Start frame is not supported by this generator.")
    if request.endImageAssetId and not caps.supportsEndFrame:
        errors.append("End frame is not supported by this generator.")

    # Generation references — never silently drop.
    image_refs = list(request.referenceAssetIds or [])
    if request.startImageAssetId and mode in ("image_to_video", "start_end_frame"):
        # start frame is a dedicated slot, not counted as a free reference
        pass
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

    if caps.supportedDurations and request.duration not in caps.supportedDurations:
        # Allow near-match within 0.05s for float noise; otherwise warn or block if strict.
        if not any(abs(request.duration - d) < 0.05 for d in caps.supportedDurations):
            # Soft: experimental profiles often fix length; warn only when far outside.
            max_d = max(caps.supportedDurations)
            if request.duration > max_d + 1e-6:
                errors.append(
                    f"Duration {request.duration}s exceeds {caps.label} max {max_d}s — no silent truncate."
                )

    if request.negativePrompt and not caps.supportsNegativePrompt:
        errors.append("Negative prompt is not supported by this generator (refusing silent drop).")
    if request.cameraMotion and not caps.supportsCameraControls:
        errors.append("Camera controls are not supported by this generator (refusing silent drop).")
    if request.temperature is not None and not caps.supportsTemperature:
        errors.append("Temperature is not supported by this generator (refusing silent drop).")
    if request.seed is not None and not caps.supportsSeed:
        errors.append("Seed is not supported by this generator (refusing silent drop).")

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
