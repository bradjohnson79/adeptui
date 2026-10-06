"""MiniMax H3 Timeline adapter — Adept Comfy Reference-to-Video."""

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

GENERATOR_ID = "minimax-h3-t2v-local"
ALIASES = frozenset({"minimax-h3-t2v-local", "minimax-h3-local", "minimax-h3"})
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
        label="MiniMax H3 (Local)",
        executionType="local",
        supportsTextToVideo=False,
        supportsImageToVideo=False,
        supportsStartFrame=False,
        supportsEndFrame=False,
        supportsMultipleImageReferences=True,
        supportsReferenceToVideo=True,
        supportsVideoReferences=True,
        continuationMode="hard",
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
            "Timeline Reference-to-Video on Adept Comfy. Uses MiniMaxH3ReferenceToVideo "
            "and the ref2va UNET with <Picture n> and <Audio j> tags. Not text-to-video "
            "and not ordinary first-frame image-to-video. Exact script speech is not guaranteed at Comfy (no language widget; ref_audios are timbre-only; Omni QC enforces Manifest). Approved character voices "
            "enter as ref_audios. Duration comes from the Inspector (max 15s) and snaps "
            "to the 17k+5 frame grid at 24 fps. Fast reuses similar steps. Quality runs "
            "every step. Same pictures."
        ),
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        finalRequiresNewGeneration=True,
        draftResolution=None,
        finalResolution="1152x640",
        supportsImageAndVideoTogether=True,
    )




def apply_h3_speech_authority_honesty(request: TimelineGenerationRequest) -> dict:
    """H3-only speech authority honesty.

    MiniMaxH3ReferenceToVideo has no language widget. Voice refs are timbre-only.
    Timed Prompt bytes on request.prompt must remain == Comfy Input Text.
    Exact speech is NOT guaranteed by the generator — Omni post-gen QC enforces
    Manifest fidelity when lockedScript is set.
    """
    opts = dict(request.providerOptions or {})
    da = opts.get("dialogueAuthority") if isinstance(opts.get("dialogueAuthority"), dict) else {}
    pre = dict(opts.get("dialoguePreflight") or {})
    honesty = {
        "generatorId": GENERATOR_ID,
        "engine": ENGINE,
        "comfyLanguageWidget": "absent",
        "exactSpeechGuaranteedByGenerator": False,
        "exactScriptDialogue": bool(da.get("exactScriptDialogue")) if da else False,
        "voiceRefsControl": "voice_timbre_ref_only",
        "promptAuthority": opts.get("h3PromptAuthority") or "timed_prompt_direct_line",
        "timedPromptBytesPreserved": True,
        "spokenLanguage": (opts.get("spokenLanguage") or {}).get("language")
        if isinstance(opts.get("spokenLanguage"), dict)
        else opts.get("spokenLanguage"),
        "enforcedBy": "omni_post_gen_qc" if (da or pre) else None,
        "generatorOwnsDialogue": False,
    }
    opts["h3SpeechAuthority"] = honesty
    # Never rewrite request.prompt here — Direct Line freeze.
    request.providerOptions = opts
    return honesty

class MiniMaxH3LocalAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        result = validate_against_capabilities(self.capabilities, request)
        errors = list(result.errors or [])
        if request.fallbackAllowed:
            errors.append("fallbackAllowed must be false for MiniMax H3 Timeline R2V.")
        if request.generationMode in {"text_to_video", "image_to_video", "start_end_frame"}:
            errors.append("MiniMax H3 Timeline is Reference-to-Video only.")
        return ValidationResult(ok=not errors, errors=errors, warnings=list(result.warnings or []))

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        validation = self.validate(request)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors) or "MiniMax H3 R2V validation failed.")
        # Speech authority honesty only — does not mutate Timed Prompt bytes.
        apply_h3_speech_authority_honesty(request)
        return submit_render_scene(
            request,
            engine=ENGINE,
            generator_id=GENERATOR_ID,
            queue_message="Timeline batch MiniMax H3 Reference-to-Video queued",
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        return get_render_status(job, engine=ENGINE)

    def cancel(self, job: NormalizedJobSubmission) -> None:
        cancel_render_job(job)

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        return collect_render_result(job, engine=ENGINE)


def minimax_built_payload(request: TimelineGenerationRequest) -> dict:
    """Compatibility view of the Timeline H3 request. No Route A T2V fields."""
    return {
        "mode": request.generationMode,
        "prompt": request.prompt,
        "r2v": (request.providerOptions or {}).get("r2v") or {},
    }


def bind_project(job: NormalizedJobSubmission, project_id: str) -> NormalizedJobSubmission:
    meta = dict(job.providerMetadata or {})
    meta["projectId"] = project_id
    job.providerMetadata = meta
    return job


# --- Omni Wave 3A: CanonicalGenerationMedia → native H3 sockets ---------------
def map_canonical_generation_media_to_ref_sockets(items):
    """Adapter-owned socket decision: CGM reference images → ref_image_N.

    Does not invent Timeline image generation or CRS/Front remaps.
    """
    from ..canonical_generation_media import map_cgm_images_to_h3_ref_sockets

    return map_cgm_images_to_h3_ref_sockets(items)
