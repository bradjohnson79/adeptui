"""MiniMax H3 Timeline I2V row — same canonical R2V path as the H3 adapter."""

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

GENERATOR_ID = "minimax-h3-i2v-local"
ALIASES = frozenset({"minimax-h3-i2v-local", "minimax-h3-i2v"})
ENGINE = "minimax-h3"


def _h3_canonical_resolution_labels() -> list[str]:
    """Derive H3 WxH labels from the single D1 legal-pixel set."""
    from app.video_runtime.legal_canvas import H3_LEGAL_RESOLUTION_LABELS

    return list(H3_LEGAL_RESOLUTION_LABELS)



def _h3_capability_aspect_ratios() -> list[str]:
    """ONE owner: legal_canvas.H3_CAPABILITY_ASPECT_RATIOS (no cloned AR table)."""
    from app.video_runtime.legal_canvas import H3_CAPABILITY_ASPECT_RATIOS

    return list(H3_CAPABILITY_ASPECT_RATIOS)

def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="MiniMax H3 Director — Local",
        executionType="local",
        supportsTextToVideo=False,
        supportsImageToVideo=False,
        supportsStartFrame=False,
        supportsEndFrame=False,
        supportsMultipleImageReferences=True,
        supportsReferenceToVideo=True,
        supportsVideoReferences=True,
        supportsAudioReferences=True,
        maximumReferenceImages=9,
        maximumReferenceVideos=3,
        maximumReferenceAudio=3,
        supportedDurations=[float(s) for s in range(3, 16)],
        maxDurationSec=15.0,
        supportedResolutions=_h3_canonical_resolution_labels(),
        supportedAspectRatios=_h3_capability_aspect_ratios(),
        supportsSeed=True,
        supportsNegativePrompt=False,
        supportsCameraControls=False,
        audio_generation=True,
        qualityControl="h3_megapixels",
        audio={
            "generation": True,
            "synchronized": True,
            "native": True,
        },
        executable=True,
        notes=(
            "MiniMax H3 Director — Local. Character, place, and prior-frame pictures "
            "enter MiniMaxH3ReferenceToVideo as ref_images. Approved character voices "
            "enter as ref_audios with <Audio j> tags. Ordinary first-frame I2V "
            "is refused. Duration comes from the Inspector (max 15s) and snaps "
            "to the 17k+5 frame grid. Fast reuses similar steps. Quality runs every step."
        ),
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        finalRequiresNewGeneration=True,
        draftResolution=None,
        finalResolution="1152x640",
        supportsImageAndVideoTogether=True,
    )


class MiniMaxH3I2VLocalAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        result = validate_against_capabilities(self.capabilities, request)
        errors = list(result.errors or [])
        if request.fallbackAllowed:
            errors.append("fallbackAllowed must be false for MiniMax H3 Timeline R2V.")
        if request.generationMode != "reference":
            errors.append("MiniMax H3 Timeline is Reference-to-Video only.")
        if request.generatorId in {"minimax-h3-t2v-local", "minimax-h3-local", "minimax-h3"}:
            # Same mechanism; the T2V row is also R2V now.
            pass
        # Output size must be an H3 megapixel-table entry — never Scene canvas.
        res = str(request.resolution or "").strip().lower()
        if res and "x" in res:
            try:
                w_s, h_s = res.split("x", 1)
                from app.video_runtime.legal_canvas import check_h3_resolution

                checked = check_h3_resolution(int(w_s), int(h_s))
                if not checked.ok:
                    errors.append(checked.message or "H3_RESOLUTION_UNSUPPORTED")
            except ValueError:
                errors.append(f"MiniMax H3 resolution {request.resolution!r} is not a WxH pair.")
        return ValidationResult(ok=not errors, errors=errors, warnings=list(result.warnings or []))

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        validation = self.validate(request)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors) or "MiniMax H3 R2V validation failed.")
        from .minimax_h3_local import apply_h3_speech_authority_honesty

        apply_h3_speech_authority_honesty(request)
        return submit_render_scene(
            request,
            engine=ENGINE,
            generator_id=GENERATOR_ID,
            queue_message="Timeline batch MiniMax H3 Director — Local queued",
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        return get_render_status(job, engine=ENGINE)

    def cancel(self, job: NormalizedJobSubmission) -> None:
        cancel_render_job(job)

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        return collect_render_result(job, engine=ENGINE)


def bind_project(job: NormalizedJobSubmission, project_id: str) -> NormalizedJobSubmission:
    meta = dict(job.providerMetadata or {})
    meta["projectId"] = project_id
    job.providerMetadata = meta
    return job
