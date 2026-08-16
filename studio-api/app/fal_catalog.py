from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FalEngine = Literal["fal_seedance", "fal_kling", "fal_veo", "fal_runway"]
LocalEngine = Literal["ltx", "wan"]
EngineName = Literal["auto", "ltx", "wan", "fal_seedance", "fal_kling", "fal_veo", "fal_runway"]

FAL_ENGINES: tuple[FalEngine, ...] = ("fal_seedance", "fal_kling", "fal_veo", "fal_runway")
ALL_ENGINES: tuple[EngineName, ...] = ("auto", "ltx", "wan", *FAL_ENGINES)


MediaType = Literal["video", "image"]


@dataclass(frozen=True)
class FalModel:
    engine: FalEngine
    label: str
    provider: str
    model_id: str
    mode: Literal["image_to_video", "text_to_video"]
    durations: tuple[int, ...]
    default_duration: int
    supports_end_image: bool
    description: str
    media_type: MediaType = "video"


FAL_MODELS: dict[FalEngine, FalModel] = {
    "fal_seedance": FalModel(
        engine="fal_seedance",
        label="Seedance 2.0 (fal.ai)",
        provider="ByteDance via fal.ai",
        model_id="bytedance/seedance-2.0/image-to-video",
        mode="image_to_video",
        durations=(4, 5, 6, 7, 8, 9, 10, 11, 12),
        default_duration=5,
        supports_end_image=True,
        description="Cinematic I2V with native audio — strong motion & director control.",
    ),
    "fal_kling": FalModel(
        engine="fal_kling",
        label="Kling 2.5 Turbo Pro (fal.ai)",
        provider="Kuaishou via fal.ai",
        model_id="fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        mode="image_to_video",
        durations=(5, 10),
        default_duration=5,
        supports_end_image=False,
        description="Fluid image-to-video with strong prompt adherence.",
    ),
    "fal_veo": FalModel(
        engine="fal_veo",
        label="Veo 3.1 (fal.ai)",
        provider="Google via fal.ai",
        model_id="fal-ai/veo3.1/image-to-video",
        mode="image_to_video",
        durations=(4, 6, 8),
        default_duration=8,
        supports_end_image=False,
        description="Google Veo 3.1 image-to-video with optional audio.",
    ),
    "fal_runway": FalModel(
        engine="fal_runway",
        label="Runway Gen-3 Turbo (fal.ai)",
        provider="Runway via fal.ai",
        model_id="fal-ai/runway-gen3/turbo/image-to-video",
        mode="image_to_video",
        durations=(5, 10),
        default_duration=5,
        supports_end_image=False,
        description="Fast Runway-style image-to-video for iteration.",
    ),
}


# fal image families (Seedream, GPT Image, Nano Banana, …) are not wired yet: no endpoint
# id for any of them appears anywhere in this repository, and inventing one would produce a
# model the UI offers and the queue cannot run. Still-image generation currently goes
# through the local ComfyUI ImageGen path (`imagegen_workflows.py`). Adding a family here
# means adding its verified endpoint id plus the argument builder below — nothing else in
# the stack special-cases video.
FAL_IMAGE_MODELS: dict[str, FalModel] = {}



# Dock id -> fal still-image endpoint. Video engines stay in FAL_MODELS.
# These are the same providerModelIds as hosted_providers.discovery fal image rows.
FAL_IMAGE_ENDPOINT_BY_DOCK: dict[str, str] = {
    "krea2-turbo-fal": "fal-ai/krea-2/turbo",
    "krea2-medium-fal": "krea/v2/medium/text-to-image",
    "krea2-large-fal": "krea/v2/large/text-to-image",
    "flux-fal": "fal-ai/flux/dev",
    "flux-2-pro-fal": "fal-ai/flux-2-pro",
    "flux-schnell-fal": "fal-ai/flux/schnell",
    "nano-banana-2-fal": "fal-ai/nano-banana-2",
}


def fal_image_model_id_for_dock(dock_model_id: str | None) -> str | None:
    """Resolve a Production Dock / Character API model id to a fal still-image endpoint."""
    mid = (dock_model_id or "").strip()
    if not mid:
        return None
    if mid in FAL_IMAGE_ENDPOINT_BY_DOCK:
        return FAL_IMAGE_ENDPOINT_BY_DOCK[mid]
    try:
        from .hosted_providers.discovery import _PROVIDER_CATALOG

        for row in _PROVIDER_CATALOG.get("fal") or []:
            if str(row.get("dockModelId") or "") != mid:
                continue
            if str(row.get("modality") or "") != "image":
                continue
            pid = str(row.get("providerModelId") or "").strip()
            if pid:
                return pid
    except Exception:
        pass
    return None


def build_fal_image_arguments(
    *,
    model_id: str,
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int = -1,
) -> dict[str, Any]:
    """Minimal still-image payload for fal queue submit. Does not start a job."""
    args: dict[str, Any] = {"prompt": prompt, "num_images": 1}
    if seed is not None and int(seed) >= 0:
        args["seed"] = int(seed)
    mid = (model_id or "").strip()
    w, h = int(width or 1024), int(height or 1024)
    if mid.startswith("krea/v2"):
        args["aspect_ratio"] = "1:1" if w == h else ("16:9" if w > h else "9:16")
    else:
        args["image_size"] = {"width": w, "height": h}
    return args


def is_fal_engine(engine: str | None) -> bool:
    return (engine or "") in FAL_MODELS


def list_fal_models_by_media(media_type: str) -> list[dict[str, Any]]:
    """Catalogue entries for one media type ("video" today; "image" once wired)."""
    return [m for m in list_fal_models() if m.get("media_type") == media_type]


def get_fal_model(engine: str) -> FalModel:
    if engine not in FAL_MODELS:
        raise KeyError(f"Unknown fal engine: {engine}")
    return FAL_MODELS[engine]  # type: ignore[index]


def list_fal_models() -> list[dict[str, Any]]:
    out = []
    for m in FAL_MODELS.values():
        d = asdict(m)
        d["durations"] = list(m.durations)
        out.append(d)
    return out


def list_engines_for_ui() -> list[dict[str, str]]:
    return [
        {"id": "auto", "label": "Auto Select (recommend)", "group": "auto"},
        {"id": "minimax-h3", "label": "MiniMax H3 (Default · local)", "group": "local"},
        {"id": "ltx", "label": "LTX Video (local ComfyUI)", "group": "local"},
        {"id": "hunyuan15", "label": "HunyuanVideo 1.5 (local optional)", "group": "local"},
        {"id": "hunyuan13b", "label": "HunyuanVideo 13B (local advanced)", "group": "local"},
        {"id": "wan", "label": "WAN 2.2 (local optional)", "group": "local"},
        *[
            {"id": m.engine, "label": m.label, "group": "fal"}
            for m in FAL_MODELS.values()
        ],
    ]


def nearest_duration(seconds: float, allowed: tuple[int, ...], default: int) -> int:
    if not allowed:
        return default
    target = int(round(seconds))
    return min(allowed, key=lambda d: abs(d - target))


def aspect_from_size(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "16:9"
    r = width / height
    options = {
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "1:1": 1.0,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "21:9": 21 / 9,
    }
    return min(options.items(), key=lambda kv: abs(kv[1] - r))[0]


def resolution_label(height: int) -> str:
    if height >= 1000:
        return "1080p"
    if height >= 700:
        return "720p"
    return "480p"


def build_fal_arguments(
    *,
    engine: str,
    prompt: str,
    negative: str,
    image_url: str | None,
    end_image_url: str | None,
    duration_sec: float,
    width: int,
    height: int,
    seed: int,
    generate_audio: bool = True,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (model_id, arguments) for fal queue submit."""
    model = get_fal_model(engine)
    duration = nearest_duration(duration_sec, model.durations, model.default_duration)
    aspect = (aspect_ratio or "").strip() or aspect_from_size(width, height)
    if resolution in ("480p", "720p", "1080p"):
        res = resolution
    else:
        res = resolution_label(height)

    if model.mode == "image_to_video" and not image_url:
        # Fall back to text-to-video endpoints where available
        if engine == "fal_seedance":
            model_id = "bytedance/seedance-2.0/text-to-video"
            args: dict[str, Any] = {
                "prompt": prompt,
                "resolution": res if res in ("480p", "720p") else "720p",
                "duration": str(duration),
                "aspect_ratio": aspect,
                "generate_audio": generate_audio,
            }
            if seed >= 0:
                args["seed"] = seed
            return model_id, args
        if engine == "fal_veo":
            model_id = "fal-ai/veo3.1"
            args = {
                "prompt": prompt,
                "aspect_ratio": aspect if aspect in ("16:9", "9:16") else "16:9",
                "duration": f"{duration}s",
                "resolution": res if res in ("720p", "1080p") else "720p",
                "generate_audio": generate_audio,
            }
            if seed >= 0:
                args["seed"] = seed
            return model_id, args
        raise RuntimeError(f"{model.label} needs a start image for image-to-video")

    args = {"prompt": prompt}

    if engine == "fal_seedance":
        args.update(
            {
                "image_url": image_url,
                "resolution": res if res in ("480p", "720p") else "720p",
                "duration": str(duration),
                "aspect_ratio": aspect,
                "generate_audio": generate_audio,
            }
        )
        if end_image_url and model.supports_end_image:
            args["end_image_url"] = end_image_url
        if seed >= 0:
            args["seed"] = seed
    elif engine == "fal_kling":
        args.update(
            {
                "image_url": image_url,
                "duration": str(duration if duration in (5, 10) else 5),
                "negative_prompt": negative or "blur, distort, and low quality",
                "cfg_scale": 0.5,
            }
        )
    elif engine == "fal_veo":
        args.update(
            {
                "image_url": image_url,
                "aspect_ratio": aspect if aspect in ("16:9", "9:16") else "16:9",
                "duration": f"{duration}s" if duration in (4, 6, 8) else "8s",
                "resolution": res if res in ("720p", "1080p") else "720p",
                "generate_audio": generate_audio,
            }
        )
        if seed >= 0:
            args["seed"] = seed
    elif engine == "fal_runway":
        args.update(
            {
                "image_url": image_url,
                "duration": duration if duration in (5, 10) else 5,
            }
        )
        if seed >= 0:
            args["seed"] = seed
    else:
        raise RuntimeError(f"Unhandled fal engine {engine}")

    return model.model_id, args


SEEDANCE_R2V_MODEL_ID = "bytedance/seedance-2.0/reference-to-video"


def build_seedance_r2v_arguments(
    *,
    prompt: str,
    image_urls: list[str],
    video_urls: list[str],
    duration_sec: float,
    aspect_ratio: str | None,
    resolution: str | None,
    seed: int = -1,
    generate_audio: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Seedance 2.0 reference-to-video — used only when a Video Reference is attached."""
    duration = nearest_duration(float(duration_sec or 5), (4, 5, 6, 7, 8, 9, 10, 11, 12), 5)
    res = resolution if resolution in ("480p", "720p", "1080p", "4k") else "720p"
    aspect = (aspect_ratio or "auto").strip() or "auto"
    args: dict[str, Any] = {
        "prompt": prompt,
        "resolution": res,
        "duration": str(duration),
        "aspect_ratio": aspect,
        "generate_audio": generate_audio,
    }
    if image_urls:
        args["image_urls"] = list(image_urls)[:9]
    if video_urls:
        args["video_urls"] = list(video_urls)[:1]
    if seed >= 0:
        args["seed"] = seed
    return SEEDANCE_R2V_MODEL_ID, args
