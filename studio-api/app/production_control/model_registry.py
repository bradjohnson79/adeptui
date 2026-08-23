"""Static model catalog for Production Control Dock — honest CapabilityLabel."""

from __future__ import annotations

from typing import Any

from .contracts import CapabilityLabel, LocalLifecycle, ModelDescriptor, Modality

# Catalog-only families with no certified workflow — hide from ordinary pickers.
CATALOG_ONLY_HIDDEN_FROM_PICKER = frozenset(
    {
        "cogview-4-local",
        "hidream-local",
        "lumina-image-2-local",
        "pixart-sigma-local",
        "kolors-local",
        "omnigen-local",
        "sana-15-local",
        "janus-local",
        "janus-pro-local",
        "hunyuan-image-local",
    }
)


def is_ordinary_picker_hidden(model_id: str) -> bool:
    return str(model_id or "") in CATALOG_ONLY_HIDDEN_FROM_PICKER


# Action tags map to TimelineActionCapability + common generator actions.
_ACTION_TAGS: dict[str, set[str]] = {
    "generate": {"audio_generation", "full_scene", "timeline_batch"},
    "text_to_image": {"full_scene", "timeline_batch"},
    "image_to_video": {"start_end_frame", "continuation", "reference_conditioning"},
    "text_to_video": {"full_scene", "timeline_batch"},
    "music": {"audio_generation"},
    "sfx": {"audio_generation"},
    "chat": {"timeline_batch"},
    "edit": {"native_inpaint", "range_replacement"},
    "inpaint": {"native_inpaint"},
    "continuation": {"continuation"},
}


def _desc(
    *,
    id: str,
    modality: Modality,
    label: str,
    locality: str,
    provider_id: str | None,
    capability: CapabilityLabel,
    lifecycle: LocalLifecycle | None = None,
    supports: list[str] | None = None,
    does_not_support: list[str] | None = None,
    vram: float | None = None,
    gpu: bool = False,
    executable: bool = False,
) -> ModelDescriptor:
    return ModelDescriptor(
        id=id,
        modality=modality,
        label=label,
        locality=locality,  # type: ignore[arg-type]
        providerId=provider_id,
        capabilityLabel=capability,
        lifecycle=lifecycle,
        supports=supports or [],
        doesNotSupport=does_not_support or [],
        estimatedVramGb=vram,
        gpuCompatible=gpu,
        executable=executable,
    )


_CATALOG: list[ModelDescriptor] = [
    # LLM
    _desc(
        id="ollama-gemma4-31b",
        modality="llm",
        label="Gemma 4 31B (Local)",
        locality="local",
        provider_id="ollama",
        capability="Available",
        lifecycle="Installed",
        supports=["chat", "timeline_batch"],
        gpu=True,
        executable=True,
    ),
    _desc(
        id="ollama-gemma4-12b",
        modality="llm",
        label="Gemma 4 12B (Local fallback)",
        locality="local",
        provider_id="ollama",
        capability="Available",
        lifecycle="Installed",
        supports=["chat"],
        gpu=True,
        executable=True,
    ),
    # Video — local
    _desc(
        id="ltx-local",
        modality="video",
        label="LTX 2.3 (Local)",
        locality="local",
        provider_id="comfy",
        capability="Certified",
        lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation"],
        vram=22.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="ltx-2.5-full",
        modality="video",
        label="LTX 2.5 Full",
        locality="local",
        provider_id="comfy",
        capability="Testing",
        lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation", "native_multishot", "audio_generation", "auto_duration", "fast_generation"],
        vram=24.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="ltx-2.5-distilled",
        modality="video",
        label="LTX 2.5 Distilled",
        locality="local",
        provider_id="comfy",
        capability="Testing",
        lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation", "native_multishot", "audio_generation", "auto_duration", "fast_generation"],
        vram=16.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="ltx-2.5-comfy",
        modality="video",
        label="LTX 2.5 Comfy INT8",
        locality="local",
        provider_id="comfy",
        capability="Testing",
        lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation", "audio_generation"],
        vram=12.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="wan-local",
        modality="video",
        label="WAN 2.2 I2V (Local)",
        locality="local",
        provider_id="comfy",
        capability="Certified",
        lifecycle="Installed",
        supports=["image_to_video", "continuation", "start_end_frame"],
        vram=14.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="hunyuan-video-1.5-local",
        modality="video",
        label="HunyuanVideo 1.5 (Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_video", "image_to_video", "timeline_batch"],
        does_not_support=["start_end_frame"],
        vram=24.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="hunyuan-video-13b-local",
        modality="video",
        label="HunyuanVideo 13B (Local Advanced)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_video", "image_to_video", "timeline_batch"],
        does_not_support=["start_end_frame"],
        vram=32.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="minimax-h3",
        modality="video",
        label="MiniMax H3",
        locality="local",
        provider_id=None,
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_video", "image_to_video", "start_end_frame", "native_audio"],
        does_not_support=["native_three_keyframe", "three_frame_uses_adept_segmented_assembly"],
        gpu=True,
        executable=False,
    ),
    # Video — hosted
    _desc(
        id="kling-kie",
        modality="video",
        label="Kling (Kie)",
        locality="hosted",
        provider_id="kie",
        capability="Testing",
        supports=["text_to_video", "image_to_video"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="kling-fal",
        modality="video",
        label="Kling (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Unavailable",
        supports=["text_to_video", "image_to_video"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="seedance-fal",
        modality="video",
        label="Seedance (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Unavailable",
        supports=["text_to_video", "image_to_video"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="veo-fal",
        modality="video",
        label="Veo (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Unavailable",
        supports=["text_to_video"],
        gpu=False,
        executable=False,
    ),
    # Image — local
    _desc(
        id="qwen-image-edit-2509-local",
        modality="image",
        label="Qwen Image Edit 2509 (Local)",
        locality="local",
        provider_id="comfy",
        capability="Draft",
        lifecycle="Installed",
        supports=["edit", "reference_conditioning", "identity_reference"],
        vram=24.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="qwen-image-2512-local",
        modality="image",
        label="Qwen Image 2512 (Local)",
        locality="local",
        provider_id="comfy",
        capability="Certified",
        lifecycle="Installed",
        supports=["text_to_image", "edit", "inpaint", "reference_conditioning"],
        vram=12.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="flux-local",
        modality="image",
        label="FLUX Dev (Local Comfy)",
        locality="local",
        provider_id="comfy",
        capability="Available",
        lifecycle="Installed",
        supports=["text_to_image", "inpaint"],
        vram=12.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="zimage-local",
        modality="image",
        label="Z-Image Turbo (Local)",
        locality="local",
        provider_id="comfy",
        capability="Testing",
        lifecycle="Installed",
        supports=["text_to_image"],
        vram=8.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="illustrious-local",
        modality="image",
        label="Illustrious XL (Local)",
        locality="local",
        provider_id="comfy",
        capability="Certified",
        lifecycle="Installed",
        supports=["text_to_image"],
        vram=12.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="krea2-turbo-local",
        modality="image",
        label="Krea 2 Turbo (Local)",
        locality="local",
        provider_id="comfy",
        capability="Available",
        lifecycle="Installed",
        supports=["text_to_image", "reference_conditioning", "lora"],
        does_not_support=["edit", "inpaint"],
        vram=24.0,
        gpu=True,
        executable=True,
    ),
    _desc(
        id="sensenova-u15-local",
        modality="image",
        label="SenseNova U1.5 (Local)",
        locality="local",
        provider_id="comfy",
        capability="Draft",
        lifecycle="Installed",
        supports=["text_to_image", "edit", "reference_conditioning", "native_reference_sheet"],
        does_not_support=["inpaint", "outpaint"],
        vram=24.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="krea2-raw-local",
        modality="image",
        label="Krea 2 RAW (Local training base)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image", "reference_conditioning", "lora"],
        does_not_support=["edit", "inpaint", "creator_default_route"],
        vram=24.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="flux-schnell-local",
        modality="image",
        label="FLUX.1 Schnell (Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="flux-kontext-dev-local",
        modality="image",
        label="FLUX.1 Kontext Dev (Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image", "edit", "inpaint", "reference_conditioning"],
        vram=24.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="sana-15-local",
        modality="image",
        label="Sana 1.5 (Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=12.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="sdxl-local",
        modality="image",
        label="Stable Diffusion XL (Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image", "edit", "inpaint", "outpaint"],
        vram=12.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="sd35-large-local",
        modality="image",
        label="Stable Diffusion 3.5 Large (Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="cogview-4-local",
        modality="image",
        label="CogView 4 (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="hidream-local",
        modality="image",
        label="HiDream (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="lumina-image-2-local",
        modality="image",
        label="Lumina Image 2 (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="pixart-sigma-local",
        modality="image",
        label="PixArt Sigma (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=12.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="kolors-local",
        modality="image",
        label="Kolors (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=12.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="omnigen-local",
        modality="image",
        label="OmniGen (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image", "edit"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="janus-pro-local",
        modality="image",
        label="Janus-Pro (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image", "edit"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    _desc(
        id="hunyuan-image-local",
        modality="image",
        label="Hunyuan Image (Experimental Local)",
        locality="local",
        provider_id="comfy",
        capability="Requires Setup",
        lifecycle=None,
        supports=["text_to_image"],
        vram=16.0,
        gpu=True,
        executable=False,
    ),
    # Image — hosted
    _desc(
        id="flux-kie",
        modality="image",
        label="FLUX (Kie)",
        locality="hosted",
        provider_id="kie",
        capability="Testing",
        supports=["text_to_image"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="flux-fal",
        modality="image",
        label="FLUX (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Available",
        supports=["text_to_image"],
        gpu=False,
        executable=True,
    ),
    _desc(
        id="nano-banana-kie",
        modality="image",
        label="Nano Banana (Kie)",
        locality="hosted",
        provider_id="kie",
        capability="Testing",
        supports=["text_to_image", "edit"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="gpt-image-2-kie",
        modality="image",
        label="GPT Image 2 (Kie)",
        locality="hosted",
        provider_id="kie",
        capability="Testing",
        supports=["text_to_image", "edit"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="seedream-kie",
        modality="image",
        label="Seedream (Kie)",
        locality="hosted",
        provider_id="kie",
        capability="Testing",
        supports=["text_to_image", "edit"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="krea2-turbo-fal",
        modality="image",
        label="Krea 2 Turbo (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Available",
        supports=["text_to_image"],
        gpu=False,
        executable=True,
    ),
    _desc(
        id="krea2-medium-fal",
        modality="image",
        label="Krea 2 Medium (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Available",
        supports=["text_to_image"],
        gpu=False,
        executable=True,
    ),
    _desc(
        id="krea2-large-fal",
        modality="image",
        label="Krea 2 Large (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Available",
        supports=["text_to_image"],
        gpu=False,
        executable=True,
    ),
    _desc(
        id="openai-images",
        modality="image",
        label="OpenAI Images",
        locality="hosted",
        provider_id="openai",
        capability="Requires Setup",
        supports=["text_to_image", "edit"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="google-imagen",
        modality="image",
        label="Google Imagen",
        locality="hosted",
        provider_id="google_imagen",
        capability="Requires Setup",
        supports=["text_to_image", "edit", "reference_conditioning"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="replicate-images",
        modality="image",
        label="Replicate Images",
        locality="hosted",
        provider_id="replicate",
        capability="Requires Setup",
        supports=["text_to_image", "edit"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="ideogram-images",
        modality="image",
        label="Ideogram",
        locality="hosted",
        provider_id="ideogram",
        capability="Requires Setup",
        supports=["text_to_image"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="recraft-images",
        modality="image",
        label="Recraft",
        locality="hosted",
        provider_id="recraft",
        capability="Requires Setup",
        supports=["text_to_image"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="leonardo-images",
        modality="image",
        label="Leonardo",
        locality="hosted",
        provider_id="leonardo",
        capability="Requires Setup",
        supports=["text_to_image"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="runware-images",
        modality="image",
        label="Runware",
        locality="hosted",
        provider_id="runware",
        capability="Requires Setup",
        supports=["text_to_image"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="together-images",
        modality="image",
        label="Together AI Images",
        locality="hosted",
        provider_id="together",
        capability="Requires Setup",
        supports=["text_to_image"],
        gpu=False,
        executable=False,
    ),
    # Audio — local
    _desc(
        id="ace-step-local",
        modality="audio",
        label="ACE-Step (Local)",
        locality="local",
        provider_id="ace-step",
        capability="Certified",
        lifecycle="Installed",
        supports=["music", "audio_generation"],
        vram=8.0,
        gpu=True,
        executable=False,  # resolved at runtime via provider_resolver
    ),
    _desc(
        id="mmaudio-local",
        modality="audio",
        label="MMAudio (Local)",
        locality="local",
        provider_id="mmaudio",
        capability="Certified",
        lifecycle="Installed",
        supports=["sfx", "audio_generation"],
        vram=6.0,
        gpu=True,
        executable=False,
    ),
    # Audio — hosted
    _desc(
        id="audio-kie",
        modality="audio",
        label="Hosted Audio (Kie)",
        locality="hosted",
        provider_id="kie",
        capability="Unavailable",
        supports=["music", "sfx"],
        does_not_support=["stems"],
        gpu=False,
        executable=False,
    ),
    _desc(
        id="audio-fal",
        modality="audio",
        label="Hosted Audio (fal.ai)",
        locality="hosted",
        provider_id="fal",
        capability="Unavailable",
        supports=["music", "sfx"],
        gpu=False,
        executable=False,
    ),
]

# Static catalog claims are metadata, never install truth (CDX-075). Local rows
# start with no lifecycle and no executability: runtime truth is derived at list
# time from Setup/Source Manager component verification (_apply_setup_status)
# and live probes (Ollama tags, Docker runtimes, registered model folders). A
# Certified label proves the workflow exists, not that the weights are on disk.
_CATALOG = [
    m.model_copy(update={"lifecycle": None, "executable": False})
    if m.locality == "local"
    else m
    for m in _CATALOG
]

_BY_ID: dict[str, ModelDescriptor] = {m.id: m for m in _CATALOG}

_SETUP_COMPONENT_BY_MODEL_ID = {
    "ltx-local": "ltx_checkpoint",
    "ltx-2.5-full": ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae", "ltx_2_5_audio_vae"),
    "ltx-2.5-distilled": ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae", "ltx_2_5_audio_vae"),
    "ltx-2.5-comfy": ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"),
    "wan-local": "wan_models",
    "hunyuan-video-1.5-local": "hunyuan_video_15",
    "hunyuan-video-13b-local": "hunyuan_video_13b",
    "qwen-image-edit-2509-local": "qwen_image_edit_2509_models",
    "qwen-image-2512-local": "qwen_image_2512_models",
    "flux-local": "flux1_dev_local",
    "flux-schnell-local": "flux1_schnell_local",
    "flux-kontext-dev-local": "flux1_kontext_dev_local",
    "zimage-local": "zimage_models",
    "illustrious-local": "illustrious_local",
    "krea2-turbo-local": "krea2_models",
    "krea2-raw-local": "krea2_models",
    "sensenova-u15-local": "sensenova_u15_models",
    "sana-15-local": "sana_15_local",
    "sdxl-local": "sdxl_local",
    "sd35-large-local": "sd35_large_local",
    "cogview-4-local": "cogview4_local",
    "hidream-local": "hidream_local",
    "lumina-image-2-local": "lumina_image_2_local",
    "pixart-sigma-local": "pixart_sigma_local",
    "kolors-local": "kolors_local",
    "omnigen-local": "omnigen_local",
    "janus-pro-local": "janus_pro_local",
    "hunyuan-image-local": "hunyuan_image_local",
}


def _capability_from_setup_status(status: str, *, certified: bool) -> CapabilityLabel:
    if status == "ready":
        return "Certified" if certified else "Available"
    if status == "checking":
        return "Loading"
    if status in {"error"}:
        return "Error"
    return "Requires Setup"


def _lifecycle_from_setup_status(status: str) -> LocalLifecycle | None:
    if status == "ready":
        return "Installed"
    if status == "checking":
        return "Loading"
    if status == "error":
        return "Dependency error"
    return None


_IMAGE_VERIFY_CACHE: dict[str, tuple[float, str, bool]] = {}
_IMAGE_VERIFY_CACHE_TTL_SEC = 5.0


def _apply_setup_status(models: list[ModelDescriptor]) -> list[ModelDescriptor]:
    # Derive capability/executable from runtime status WITHOUT calling
    # build_status(), which probes ALL components — including slow audio/avatar
    # subprocess probes (60s torch import) that block the image route AND hang
    # list_models() (which calls this on every modality). Image-modality
    # components verify with fast file checks, so they are live-verified here
    # (fresh, fixes stale persisted entries like krea2). Non-image modalities
    # read persisted setup state (instant file read); they are overridden by
    # modality-specific refresh paths (e.g. _refresh_audio_executable) where
    # relevant. On any exception we keep the static catalog (no override) so
    # an unreachable runtime never silently downgrades a Certified model.
    try:
        from ..setup.state import load_state
    except Exception:
        load_state = None  # type: ignore[assignment]

    import time as _time

    def _image_status(component_id: str) -> tuple[str, bool] | None:
        # Live-verify an image component (fast file check) with a short TTL
        # cache so repeated resolves don't re-stat the same files. Returns
        # (status, certified) or None to fall back to the static catalog.
        cached = _IMAGE_VERIFY_CACHE.get(component_id)
        now = _time.monotonic()
        if cached and (now - cached[0]) < _IMAGE_VERIFY_CACHE_TTL_SEC:
            return cached[1], cached[2]
        try:
            from ..setup.diagnostics import verify_component
            from ..setup.lifecycle.service import get_certification
            verification = verify_component(component_id)
            healthy = bool(getattr(verification, "healthy", False))
            absent = bool(getattr(verification, "absent", False))
            if healthy:
                status = "ready"
            elif absent:
                status = "not_installed"
            else:
                status = "error"
            record = get_certification(component_id)
            certified = bool(record and record.certified)
        except Exception:
            return None
        _IMAGE_VERIFY_CACHE[component_id] = (now, status, certified)
        return status, certified

    def _persisted_status(component_id: str) -> tuple[str, bool] | None:
        # Non-image modalities derive from persisted setup state (instant file
        # read), NOT build_status — list_models() calls _apply_setup_status on
        # ALL modalities, and build_status probes slow audio/avatar
        # subprocesses that would hang every list_models() call. Non-image
        # executable truth is overridden by modality-specific refresh paths
        # (e.g. _refresh_audio_executable) where relevant. Contract tests
        # monkeypatch load_state to control this.
        if load_state is None:
            return None
        try:
            entry = load_state().get("status", {}).get(component_id)
        except Exception:
            return None
        if not isinstance(entry, dict):
            return None
        status = str(entry.get("status") or "not_installed")
        try:
            from ..setup.lifecycle.service import get_certification
            record = get_certification(component_id)
            certified = bool(record and record.certified)
        except Exception:
            certified = False
        return status, certified

    updated: list[ModelDescriptor] = []
    for model in models:
        component_id = _SETUP_COMPONENT_BY_MODEL_ID.get(model.id)
        if not component_id:
            updated.append(model)
            continue
        if getattr(model, "modality", None) == "image":
            result = _image_status(component_id)
        else:
            result = _persisted_status(component_id)
        if result is None:
            # Keep static catalog (don't override) when verification/persisted
            # state is unavailable — never silently downgrade a Certified model.
            updated.append(model)
            continue
        status, certified = result
        updated.append(
            model.model_copy(
                update={
                    "capabilityLabel": _capability_from_setup_status(status, certified=certified),
                    "lifecycle": _lifecycle_from_setup_status(status),
                    "estimatedVramGb": model.estimatedVramGb,
                    "executable": status == "ready",
                }
            )
        )
    return updated


def _docker_dock_models() -> list[ModelDescriptor]:
    """W47: Docker / classified runtimes as Dock entries (never silent Certified)."""
    try:
        from ..docker_runtime.service import list_runtimes
    except Exception:
        return []
    out: list[ModelDescriptor] = []
    for r in list_runtimes():
        mod = r.get("modality") or "video"
        if mod == "multi":
            mod = "video"
        if mod not in ("llm", "video", "image", "audio"):
            continue
        exec_class = r.get("executionClass") or "native_local"
        if exec_class == "native_local" and r.get("classification") == "core_mandatory":
            # Core native already represented in static catalog (ltx/comfy) — skip duplicates
            continue
        rid = str(r["id"])
        mid = f"docker-runtime:{rid}" if exec_class == "docker_local" else rid
        ready = r.get("readiness") in ("ready", "tested_locally") and not r.get("disabled")
        if r.get("disabled"):
            cap: CapabilityLabel = "Unavailable"
        elif r.get("readiness") == "ready":
            cap = "Available"
        elif r.get("readiness") == "tested_locally":
            cap = "Testing"
        elif r.get("readiness") == "requires_repair":
            cap = "Requires Setup"
        else:
            cap = "Unavailable"
        out.append(
            ModelDescriptor(
                id=mid,
                modality=mod,  # type: ignore[arg-type]
                label=str(r.get("name") or rid),
                locality="local",
                executionClass=exec_class,  # type: ignore[arg-type]
                runtimeId=rid,
                providerId="docker-runtime" if exec_class == "docker_local" else "native-runtime",
                capabilityLabel=cap,
                supports=list(r.get("models") or ["timeline_batch"]),
                estimatedVramGb=r.get("minimumVramGb"),
                gpuCompatible=bool(r.get("gpuReady") or r.get("minimumVramGb")),
                executable=bool(ready and r.get("healthOk", ready)),
            )
        )
    return out


def _apply_private_owner_h3(models: list[ModelDescriptor]) -> list[ModelDescriptor]:
    """Stamp the MiniMax H3 dock entry as Private Local · Experimental when the
    private owner Route A path is ready; otherwise keep it disabled."""
    try:
        from ..minimax_h3.private_access import (
            private_local_enabled,
            public_creator_enabled,
        )
        from ..minimax_h3.route_a_adapter import RouteARuntimeAdapter
    except Exception:
        return models
    if not private_local_enabled() or public_creator_enabled():
        return models
    ready = False
    try:
        ready = bool(RouteARuntimeAdapter().readiness().get("ready"))
    except Exception:
        ready = False
    updated: list[ModelDescriptor] = []
    for model in models:
        if model.id != "minimax-h3":
            updated.append(model)
            continue
        if ready:
            updated.append(
                model.model_copy(
                    update={
                        "capabilityLabel": "Testing",
                        "lifecycle": "Installed",
                        "executable": True,
                        "supports": ["text_to_video", "native_audio"],
                        "doesNotSupport": [
                            "image_to_video",
                            "native_three_keyframe",
                            "three_frame_uses_adept_segmented_assembly",
                            "start_end_frame",
                        ],
                    }
                )
            )
        else:
            updated.append(
                model.model_copy(
                    update={
                        "capabilityLabel": "Requires Setup",
                        "lifecycle": None,
                        "executable": False,
                    }
                )
            )
    return updated


def _ollama_dock_models() -> list[ModelDescriptor]:
    """Live Ollama tags → dock LLM rows (merged with static catalog; no silent Certified)."""
    try:
        import httpx

        from ..codirector.config_store import load_config
        from ..config import settings

        cfg = load_config()
        endpoint = str(cfg.get("endpoint") or settings.ollama_url or "http://127.0.0.1:11434").rstrip("/")
        r = httpx.get(f"{endpoint}/api/tags", timeout=3.0)
        if r.status_code != 200:
            return []
        data = r.json()
        models_raw = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models_raw, list):
            return []
    except Exception:
        return []
    out: list[ModelDescriptor] = []
    seen: set[str] = set()
    for item in models_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name:
            continue
        from .runtime_map import dock_id_for_ollama_tag

        mid = dock_id_for_ollama_tag(name)
        if not mid or mid in seen:
            continue
        seen.add(mid)
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        label = name
        if details.get("parameter_size"):
            label = f"{name} ({details.get('parameter_size')})"
        out.append(
            ModelDescriptor(
                id=mid,
                modality="llm",
                label=label,
                locality="local",
                executionClass="native_local",
                providerId="ollama",
                capabilityLabel="Available",
                lifecycle="Installed",
                supports=["chat", "timeline_batch"],
                gpuCompatible=True,
                executable=True,
            )
        )
    return out


def _registered_local_llm_models() -> list[ModelDescriptor]:
    """Registered external folders from Model Storage → CUSTOM LOCAL dock rows."""
    try:
        from ..model_storage.store import get_registered_folders
    except Exception:
        return []
    out: list[ModelDescriptor] = []
    for folder in get_registered_folders():
        status = str(folder.get("validationStatus") or "")
        ready = status in ("Ready", "Ready With Limitations")
        if status == "Drive Unavailable":
            cap: CapabilityLabel = "Unavailable"
        elif status == "Runtime Missing":
            cap = "Requires Setup"
        elif ready:
            cap = "Available" if status == "Ready" else "Testing"
        else:
            cap = "Requires Setup"
        runtime = str(folder.get("runtimeType") or "unknown")
        models = (folder.get("classification") or {}).get("models") or []
        if not models:
            models = [{"name": folder.get("label") or folder.get("id")}]
        for m in models[:20]:
            name = str(m.get("name") or folder.get("label") or "local-model")
            mid = f"custom-local:{(folder.get('id') or '')[:8]}:{name.replace(':', '-').replace('/', '-')}"
            out.append(
                ModelDescriptor(
                    id=mid,
                    modality="llm",
                    label=f"{name} (Custom Local)",
                    locality="local",
                    executionClass="native_local",
                    providerId=f"custom-{runtime}",
                    capabilityLabel=cap,
                    lifecycle="Installed" if ready else None,
                    supports=["chat", "timeline_batch"],
                    gpuCompatible=runtime in ("ollama", "gguf", "huggingface"),
                    executable=ready and runtime in ("ollama", "gguf"),
                )
            )
    return out


_REGISTRY_WORKFLOW_BY_MODEL: dict[str, tuple[str, str]] = {
    "ltx-2.5-full": ("video", "ltx_25.t2v"),
    "ltx-2.5-distilled": ("video", "ltx_25.t2v"),
    "ltx-2.5-comfy": ("video", "ltx_25.i2v"),
    "kling-fal": ("video", "fal.kling"),
    "seedance-fal": ("video", "fal.seedance"),
    "veo-fal": ("video", "fal.veo"),
    "illustrious-local": ("image", "illustrious.txt2img"),
}

_NEVER_DEFAULT_ELIGIBLE = frozenset(
    {
        "sensenova-u15-local",
        "krea2-turbo-local",
        "krea2-raw-local",
        "krea2-turbo-fal",
        "krea2-medium-fal",
        "krea2-large-fal",
        "minimax-h3",
        "qwen-image-edit-2509-local",
    }
)

_LABEL_RANK = {
    "Certified": 6,
    "Testing": 5,
    "Available": 4,
    "Loading": 3,
    "Requires Setup": 2,
    "Draft": 2,
    "Error": 1,
    "Unavailable": 1,
    "Unsupported": 0,
}


def _registry_status_to_label(status: str) -> CapabilityLabel:
    s = str(status or "").strip()
    if s == "Certified":
        return "Certified"
    if s == "Blocked":
        return "Unavailable"
    if s == "Retired":
        return "Unsupported"
    if s in {"Draft", "Built", "SmokeTested"}:
        return "Testing"
    if s == "Deferred":
        return "Requires Setup"
    return "Available"


def _more_conservative_label(current: CapabilityLabel, registry: CapabilityLabel) -> CapabilityLabel:
    if _LABEL_RANK.get(registry, 0) < _LABEL_RANK.get(current, 0):
        return registry
    return current


def _workflow_status(modality: str, workflow_key: str) -> str | None:
    try:
        if modality == "video":
            from ..video_runtime.certified_registry import get_workflow
        else:
            from ..image_runtime.certified_registry import get_workflow
        wf = get_workflow(workflow_key)
    except Exception:
        return None
    if wf is None:
        return None
    return str(getattr(wf, "status", "") or "")


def _apply_certified_registry_honesty(models: list[ModelDescriptor]) -> list[ModelDescriptor]:
    """Dock labels cannot exceed certified-registry status (LTX 2.5 Built, fal Blocked)."""
    out: list[ModelDescriptor] = []
    for model in models:
        mapped = _REGISTRY_WORKFLOW_BY_MODEL.get(model.id)
        if not mapped:
            out.append(model)
            continue
        status = _workflow_status(*mapped)
        if not status:
            out.append(model)
            continue
        capped = _more_conservative_label(model.capabilityLabel, _registry_status_to_label(status))
        executable = False if capped in {"Unavailable", "Unsupported", "Requires Setup"} else model.executable
        out.append(model.model_copy(update={"capabilityLabel": capped, "executable": executable}))
    return out


def _stamp_default_eligible(models: list[ModelDescriptor]) -> list[ModelDescriptor]:
    out: list[ModelDescriptor] = []
    for model in models:
        eligible = (
            model.capabilityLabel == "Certified"
            and bool(model.executable)
            and model.id not in _NEVER_DEFAULT_ELIGIBLE
            and not is_ordinary_picker_hidden(model.id)
        )
        if model.id == "sensenova-u15-local":
            eligible = False
            if model.capabilityLabel == "Certified":
                model = model.model_copy(update={"capabilityLabel": "Testing", "executable": False})
        out.append(model.model_copy(update={"defaultEligible": eligible}))
    return out


def list_models(modality: Modality | None = None) -> list[ModelDescriptor]:
    merged = list(_CATALOG) + _docker_dock_models() + _ollama_dock_models() + _registered_local_llm_models()
    # Deduplicate by id — prefer earlier (static catalog) then live Ollama
    by_id: dict[str, ModelDescriptor] = {}
    for m in merged:
        if m.id not in by_id:
            by_id[m.id] = m
    merged = list(by_id.values())
    # Stamp executionClass on static local/hosted rows
    stamped: list[ModelDescriptor] = []
    for m in merged:
        if m.executionClass is None:
            m = m.model_copy(
                update={"executionClass": "hosted_api" if m.locality == "hosted" else "native_local"}
            )
        stamped.append(m)
    stamped = _apply_setup_status(stamped)
    stamped = _apply_private_owner_h3(stamped)
    stamped = _apply_certified_registry_honesty(stamped)
    stamped = _stamp_default_eligible(stamped)
    if modality is None:
        return stamped
    return [m for m in stamped if m.modality == modality]


def get_model(model_id: str | None) -> ModelDescriptor | None:
    if not model_id:
        return None
    for m in list_models():
        if m.id == model_id:
            return m
    found = _BY_ID.get(model_id)
    if found:
        if found.executionClass is None:
            return found.model_copy(
                update={"executionClass": "hosted_api" if found.locality == "hosted" else "native_local"}
            )
        return found
    # Discovered API models may not be in the static local catalog.
    try:
        from ..hosted_providers.model_store import load_catalog

        for row in load_catalog().get("models") or []:
            if row.get("id") != model_id:
                continue
            label_raw = str(row.get("capabilityLabel") or "Requires Setup")
            capability: CapabilityLabel
            if label_raw in (
                "Certified",
                "Testing",
                "Available",
                "Unavailable",
                "Unsupported",
                "Requires Setup",
                "Loading",
                "Error",
            ):
                capability = label_raw  # type: ignore[assignment]
            else:
                capability = "Requires Setup"
            return _desc(
                id=str(row["id"]),
                modality=row.get("modality") or "video",
                label=str(row.get("label") or row.get("displayName") or model_id),
                locality="hosted",
                provider_id=row.get("providerId"),
                capability=capability,
                supports=list(row.get("capabilities") or []),
                gpu=False,
                executable=bool(row.get("executable")),
            )
    except Exception:
        return None
    return None


def filter_for_action(modality: Modality, action: str) -> list[dict[str, Any]]:
    """Return models for modality annotated with action compatibility."""
    tags = _ACTION_TAGS.get(action, {action})
    out: list[dict[str, Any]] = []
    for model in list_models(modality):
        action_match = not model.supports or bool(tags & set(model.supports))
        item = model.model_dump()
        item["actionMatch"] = action_match
        item["action"] = action
        out.append(item)
    return out
