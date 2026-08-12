from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


QWEN_2512_DEFAULT_SIZE = 1328
QWEN_2512_DEFAULT_STEPS = 50
QWEN_2512_DEFAULT_CFG = 4.0
QWEN_2512_DEFAULT_SAMPLER = "euler"
QWEN_2512_DEFAULT_SCHEDULER = "simple"
QWEN_2512_DEFAULT_SHIFT = 1.73

QWEN_2512_STANDARD_NEGATIVE = (
    "blurry, low quality, low resolution, deformed anatomy, extra fingers, extra limbs, "
    "cropped, duplicate subject, watermark, logo, text"
)
QWEN_2512_CHARACTER_NEGATIVE = (
    "blurry, low quality, deformed anatomy, duplicate character, extra limbs, extra fingers, "
    "bad hands, asymmetrical eyes, inconsistent face, cropped body, watermark, logo, text"
)


@dataclass(frozen=True)
class Qwen2512SamplingPreset:
    width: int = QWEN_2512_DEFAULT_SIZE
    height: int = QWEN_2512_DEFAULT_SIZE
    steps: int = QWEN_2512_DEFAULT_STEPS
    cfg: float = QWEN_2512_DEFAULT_CFG
    sampler_name: str = QWEN_2512_DEFAULT_SAMPLER
    scheduler: str = QWEN_2512_DEFAULT_SCHEDULER
    model_shift: float = QWEN_2512_DEFAULT_SHIFT
    negative: str = QWEN_2512_STANDARD_NEGATIVE


def qwen_2512_recommended_settings(
    preset: Literal["txt2img", "character_concept", "character_profile"] = "txt2img",
) -> dict[str, Any]:
    if preset == "character_concept":
        value = Qwen2512SamplingPreset(
            negative=QWEN_2512_CHARACTER_NEGATIVE,
        )
    elif preset == "character_profile":
        value = Qwen2512SamplingPreset(
            negative=QWEN_2512_CHARACTER_NEGATIVE,
        )
    else:
        value = Qwen2512SamplingPreset()
    return asdict(value)


def _normalize_dimension(value: int, *, fallback: int) -> int:
    if value <= 0:
        value = fallback
    return max(16, int(round(value / 8.0) * 8))


def _normalize_seed(seed: int) -> int:
    return seed if seed >= 0 else 42


def _compose_character_prompt(prompt: str, *, variant: Literal["concept", "profile"]) -> str:
    base = prompt.strip()
    if variant == "profile":
        prefix = (
            "character profile reference, single character, consistent face, clean wardrobe read, "
            "front-facing presentation, neutral studio backdrop, production-ready identity sheet"
        )
    else:
        prefix = (
            "character concept art, single character, full-body design focus, clean silhouette, "
            "readable costume details, neutral studio backdrop, production-ready concept frame"
        )
    return f"{prefix}, {base}" if base else prefix


def _build_qwen_2512_graph(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    model_shift: float,
    filename_prefix: str,
) -> dict[str, Any]:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": unet_name,
                "weight_dtype": "fp8_e4m3fn",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": clip_name,
                "type": "qwen_image",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae_name,
            },
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {
                "model": ["1", 0],
                "shift": float(model_shift),
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive,
                "clip": ["2", 0],
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative or QWEN_2512_STANDARD_NEGATIVE,
                "clip": ["2", 0],
            },
        },
        "7": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": _normalize_dimension(width, fallback=QWEN_2512_DEFAULT_SIZE),
                "height": _normalize_dimension(height, fallback=QWEN_2512_DEFAULT_SIZE),
                "batch_size": 1,
            },
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "seed": _normalize_seed(seed),
                "steps": max(4, int(steps)),
                "cfg": float(cfg),
                "sampler_name": sampler_name or QWEN_2512_DEFAULT_SAMPLER,
                "scheduler": scheduler or QWEN_2512_DEFAULT_SCHEDULER,
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "denoise": 1.0,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],
                "vae": ["3", 0],
            },
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["9", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }


def build_qwen_2512_txt2img_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str = QWEN_2512_STANDARD_NEGATIVE,
    width: int = QWEN_2512_DEFAULT_SIZE,
    height: int = QWEN_2512_DEFAULT_SIZE,
    seed: int = 42,
    steps: int = QWEN_2512_DEFAULT_STEPS,
    cfg: float = QWEN_2512_DEFAULT_CFG,
    sampler_name: str = QWEN_2512_DEFAULT_SAMPLER,
    scheduler: str = QWEN_2512_DEFAULT_SCHEDULER,
    model_shift: float = QWEN_2512_DEFAULT_SHIFT,
    filename_prefix: str = "studio/qwen2512_txt2img",
) -> dict[str, Any]:
    return _build_qwen_2512_graph(
        unet_name=unet_name,
        clip_name=clip_name,
        vae_name=vae_name,
        positive=positive,
        negative=negative or QWEN_2512_STANDARD_NEGATIVE,
        width=width,
        height=height,
        seed=seed,
        steps=steps,
        cfg=cfg,
        sampler_name=sampler_name,
        scheduler=scheduler,
        model_shift=model_shift,
        filename_prefix=filename_prefix,
    )


def build_qwen_2512_character_concept_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    negative: str = QWEN_2512_CHARACTER_NEGATIVE,
    width: int = QWEN_2512_DEFAULT_SIZE,
    height: int = QWEN_2512_DEFAULT_SIZE,
    seed: int = 42,
    steps: int = QWEN_2512_DEFAULT_STEPS,
    cfg: float = QWEN_2512_DEFAULT_CFG,
    sampler_name: str = QWEN_2512_DEFAULT_SAMPLER,
    scheduler: str = QWEN_2512_DEFAULT_SCHEDULER,
    model_shift: float = QWEN_2512_DEFAULT_SHIFT,
    filename_prefix: str = "studio/qwen2512_character_concept",
    workflow_variant: Literal["concept", "profile"] = "concept",
) -> dict[str, Any]:
    return _build_qwen_2512_graph(
        unet_name=unet_name,
        clip_name=clip_name,
        vae_name=vae_name,
        positive=_compose_character_prompt(prompt, variant=workflow_variant),
        negative=negative or QWEN_2512_CHARACTER_NEGATIVE,
        width=width,
        height=height,
        seed=seed,
        steps=steps,
        cfg=cfg,
        sampler_name=sampler_name,
        scheduler=scheduler,
        model_shift=model_shift,
        filename_prefix=filename_prefix,
    )
