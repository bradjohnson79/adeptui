"""HunyuanVideo 1.5 Distilled — Text to Video and Start Frame only.

This is a new product id. Retired ids hunyuan-video-1.5-local and
hunyuan-video-13b-local stay retired.
"""

from __future__ import annotations

from ..adapter import validate_against_capabilities
from ..contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
    ValidationResult,
    VideoGeneratorCapabilities,
)
from .comfy_render_scene import cancel_render_job, collect_render_result, get_render_status, submit_render_scene

GENERATOR_ID = "hunyuan-video-1.5-distilled"
ALIASES = frozenset({GENERATOR_ID})
ENGINE = GENERATOR_ID


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="HunyuanVideo 1.5 Distilled",
        executionType="local",
        supportsTextToVideo=True,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=False,
        supportsThreeFrame=False,
        supportsMultipleImageReferences=False,
        supportsReferenceToVideo=False,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        continuationMode="hard",
        maximumReferenceImages=0,
        maximumReferenceVideos=0,
        maximumReferenceAudio=0,
        supportedDurations=[5.0],
        maxDurationSec=5.0,
        supportedResolutions=["848x480", "480x848", "480x480"],
        supportedAspectRatios=["16:9", "9:16", "1:1"],
        supportsSeed=True,
        supportsNegativePrompt=False,
        supportsCameraControls=False,
        audio_generation=False,
        qualityControl=None,
        executable=True,
        notes="480p-class output. The finished video keeps its real size.",
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        finalRequiresNewGeneration=True,
        draftResolution="848x480",
        finalResolution="848x480",
        supportsImageAndVideoTogether=False,
    )


class Hunyuan15DistilledAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        result = validate_against_capabilities(self.capabilities, request)
        errors = list(result.errors or [])
        if request.fallbackAllowed:
            errors.append("fallbackAllowed must be false for HunyuanVideo 1.5 Distilled.")
        if request.generationMode == "reference":
            errors.append("HunyuanVideo 1.5 Distilled does not take character, place, or prop references.")
        if request.endImageAssetId and request.generationMode != "text_to_video":
            errors.append("HunyuanVideo 1.5 Distilled does not take an end frame.")
        if request.generationMode == "image_to_video" and not str(request.startImageAssetId or "").strip():
            errors.append("Choose a start picture for this Hunyuan shot.")
        return ValidationResult(ok=not errors, errors=errors, warnings=list(result.warnings or []))

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        validation = self.validate(request)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors) or "HunyuanVideo 1.5 Distilled validation failed.")
        return submit_render_scene(
            request,
            engine=ENGINE,
            generator_id=GENERATOR_ID,
            queue_message="Timeline batch HunyuanVideo 1.5 Distilled queued",
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        return get_render_status(job, engine=ENGINE)

    def cancel(self, job: NormalizedJobSubmission) -> None:
        cancel_render_job(job)

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        return collect_render_result(job, engine=ENGINE)
