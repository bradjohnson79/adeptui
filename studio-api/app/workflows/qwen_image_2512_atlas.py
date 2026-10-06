"""Atlas-only dual-condition Qwen 2512 graph.

Copies the Character Creator Plus encoder pattern (image1 / image2) without
editing qwen_image_edit_2509 defaults. Slot order must be proven, not assumed.
"""

from __future__ import annotations

from typing import Any, Literal

from .qwen_image_2512 import (
    QWEN_2512_DEFAULT_CFG,
    QWEN_2512_DEFAULT_SAMPLER,
    QWEN_2512_DEFAULT_SCHEDULER,
    QWEN_2512_DEFAULT_SHIFT,
)

QWEN_2512_ATLAS_KEY = "qwen2512.atlas"
QWEN_2512_ATLAS_DIRECT_KEY = "qwen2512.atlas_direct"
QWEN_2512_ATLAS_LAYOUT_KEY = "qwen2512.atlas_layout"
AtlasSlotOrder = Literal["guide_source", "source_guide"]
AtlasNegativeEncode = Literal["text_only", "dual_image"]
DEFAULT_SLOT_ORDER: AtlasSlotOrder = "guide_source"
# Atlas is a planning plate, not a cinematic still. Do not inherit 50-step / 1328 T2I.
ATLAS_PLANNING_SIZE = 1024
ATLAS_PLANNING_STEPS = 28
ATLAS_PLANNING_STEPS_LOW = 16
ATLAS_PLANNING_STEPS_HIGH = 36
DEFAULT_NEGATIVE_ENCODE: AtlasNegativeEncode = "text_only"

ATLAS_STANDARD_NEGATIVE = (
    "eye-level camera, cinematic perspective, horizon line, sky, dutch tilt, "
    "characters, people, overlay grid, edges-only, unchanged source photograph, "
    "blurry, low quality, deformed architecture"
)


def _normalize_dimension(value: int, *, fallback: int) -> int:
    if value <= 0:
        value = fallback
    return max(16, int(round(value / 8.0) * 8))


def _normalize_seed(seed: int) -> int:
    return seed if seed >= 0 else 42


def atlas_steps_for_detail(detail: str = "balanced") -> int:
    key = (detail or "balanced").strip().lower()
    if key == "low":
        return ATLAS_PLANNING_STEPS_LOW
    if key == "high":
        return ATLAS_PLANNING_STEPS_HIGH
    return ATLAS_PLANNING_STEPS


def resolve_slot_images(
    *,
    guide_image: str,
    source_image: str,
    slot_order: AtlasSlotOrder = DEFAULT_SLOT_ORDER,
) -> tuple[str, str, AtlasSlotOrder]:
    order: AtlasSlotOrder = slot_order if slot_order in {"guide_source", "source_guide"} else DEFAULT_SLOT_ORDER
    if order == "source_guide":
        return source_image, guide_image, order
    return guide_image, source_image, order


def build_qwen_2512_atlas_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str = ATLAS_STANDARD_NEGATIVE,
    source_image: str,
    guide_image: str,
    slot_order: AtlasSlotOrder = DEFAULT_SLOT_ORDER,
    width: int = ATLAS_PLANNING_SIZE,
    height: int = ATLAS_PLANNING_SIZE,
    seed: int = 42,
    steps: int = ATLAS_PLANNING_STEPS,
    negative_encode: AtlasNegativeEncode = DEFAULT_NEGATIVE_ENCODE,
    cfg: float = QWEN_2512_DEFAULT_CFG,
    sampler_name: str = QWEN_2512_DEFAULT_SAMPLER,
    scheduler: str = QWEN_2512_DEFAULT_SCHEDULER,
    model_shift: float = QWEN_2512_DEFAULT_SHIFT,
    filename_prefix: str = "studio/qwen2512_atlas",
) -> dict[str, Any]:
    """Two LoadImage nodes + TextEncodeQwenImageEditPlus (image1 + image2)."""
    image1, image2, order = resolve_slot_images(
        guide_image=guide_image,
        source_image=source_image,
        slot_order=slot_order,
    )
    if not source_image or not guide_image:
        raise RuntimeError("qwen2512.atlas requires both a source image and a structural guide.")
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "fp8_e4m3fn"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "qwen_image"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": float(model_shift)},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": image1},
        },
        "6": {
            "class_type": "LoadImage",
            "inputs": {"image": image2},
        },
        "7": {
            "class_type": "TextEncodeQwenImageEditPlus",
            "inputs": {
                "clip": ["2", 0],
                "prompt": positive,
                "vae": ["3", 0],
                "image1": ["5", 0],
                "image2": ["6", 0],
            },
        },
        "8": (
            {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative or ATLAS_STANDARD_NEGATIVE,
                    "clip": ["2", 0],
                },
            }
            if (negative_encode or DEFAULT_NEGATIVE_ENCODE) != "dual_image"
            else {
                "class_type": "TextEncodeQwenImageEditPlus",
                "inputs": {
                    "clip": ["2", 0],
                    "prompt": negative or ATLAS_STANDARD_NEGATIVE,
                    "vae": ["3", 0],
                    "image1": ["5", 0],
                    "image2": ["6", 0],
                },
            }
        ),
        "9": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": _normalize_dimension(width, fallback=ATLAS_PLANNING_SIZE),
                "height": _normalize_dimension(height, fallback=ATLAS_PLANNING_SIZE),
                "batch_size": 1,
            },
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "seed": _normalize_seed(seed),
                "steps": max(4, int(steps)),
                "cfg": float(cfg),
                "sampler_name": sampler_name or QWEN_2512_DEFAULT_SAMPLER,
                "scheduler": scheduler or QWEN_2512_DEFAULT_SCHEDULER,
                "positive": ["7", 0],
                "negative": ["8", 0],
                "latent_image": ["9", 0],
                "denoise": 1.0,
            },
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["3", 0]},
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {"images": ["11", 0], "filename_prefix": filename_prefix},
        },
    }


def build_qwen_2512_atlas_direct_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str = ATLAS_STANDARD_NEGATIVE,
    source_image: str,
    width: int = ATLAS_PLANNING_SIZE,
    height: int = ATLAS_PLANNING_SIZE,
    seed: int = 42,
    steps: int = ATLAS_PLANNING_STEPS,
    cfg: float = QWEN_2512_DEFAULT_CFG,
    sampler_name: str = QWEN_2512_DEFAULT_SAMPLER,
    scheduler: str = QWEN_2512_DEFAULT_SCHEDULER,
    model_shift: float = QWEN_2512_DEFAULT_SHIFT,
    filename_prefix: str = "studio/qwen2512_atlas_direct",
) -> dict[str, Any]:
    """Minimal one-image Qwen Edit Atlas graph. No guide, mask, ControlNet, or VAEEncode latent.

    Copies the official single-image TextEncodeQwenImageEdit shape. Atlas planning
    size/steps only — does not change ERS/cinematic qwen2512.ref defaults.
    """
    if not source_image:
        raise RuntimeError("qwen2512.atlas_direct requires a source location image.")
    mild_negative = negative or "blurry, low quality, deformed architecture, extra rooms"
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "fp8_e4m3fn"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "qwen_image"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": float(model_shift)},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": source_image},
        },
        "6": {
            "class_type": "TextEncodeQwenImageEdit",
            "inputs": {
                "clip": ["2", 0],
                "prompt": positive,
                "vae": ["3", 0],
                "image": ["5", 0],
            },
        },
        "7": {
            "class_type": "TextEncodeQwenImageEdit",
            "inputs": {
                "clip": ["2", 0],
                "prompt": mild_negative,
                "vae": ["3", 0],
                "image": ["5", 0],
            },
        },
        "8": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": _normalize_dimension(width, fallback=ATLAS_PLANNING_SIZE),
                "height": _normalize_dimension(height, fallback=ATLAS_PLANNING_SIZE),
                "batch_size": 1,
            },
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "seed": _normalize_seed(seed),
                "steps": max(4, int(steps)),
                "cfg": float(cfg),
                "sampler_name": sampler_name or QWEN_2512_DEFAULT_SAMPLER,
                "scheduler": scheduler or QWEN_2512_DEFAULT_SCHEDULER,
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["8", 0],
                "denoise": 1.0,
            },
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["9", 0], "vae": ["3", 0]},
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": filename_prefix},
        },
    }


def atlas_direct_graph_roles(graph: dict[str, Any]) -> dict[str, Any]:
    types = [str((node or {}).get("class_type") or "") for node in graph.values() if isinstance(node, dict)]
    loads = [nid for nid, node in graph.items() if isinstance(node, dict) and node.get("class_type") == "LoadImage"]
    return {
        "loadImageCount": len(loads),
        "usesTextEncodeQwenImageEdit": "TextEncodeQwenImageEdit" in types,
        "usesTextEncodeQwenImageEditPlus": "TextEncodeQwenImageEditPlus" in types,
        "hasGuideLoad": any(
            "guide" in str(((node or {}).get("inputs") or {}).get("image") or "").lower()
            for node in graph.values()
            if isinstance(node, dict) and node.get("class_type") == "LoadImage"
        ),
        "hasVAEEncode": "VAEEncode" in types,
        "hasControlNet": any("ControlNet" in t for t in types),
    }


def build_qwen_2512_atlas_layout_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str = ATLAS_STANDARD_NEGATIVE,
    guide_image: str,
    appearance_image: str = "",
    slot_order: AtlasSlotOrder = DEFAULT_SLOT_ORDER,
    width: int = ATLAS_PLANNING_SIZE,
    height: int = ATLAS_PLANNING_SIZE,
    seed: int = 42,
    steps: int = ATLAS_PLANNING_STEPS,
    cfg: float = QWEN_2512_DEFAULT_CFG,
    sampler_name: str = QWEN_2512_DEFAULT_SAMPLER,
    scheduler: str = QWEN_2512_DEFAULT_SCHEDULER,
    model_shift: float = QWEN_2512_DEFAULT_SHIFT,
    filename_prefix: str = "studio/qwen2512_atlas_layout",
) -> dict[str, Any]:
    """Paint a deterministic structural guide. Appearance is optional.

    Mode 1: guide only — single-image Qwen Edit of the layout.
    Mode 2: guide + appearance — dual-image Plus encoder. Slot order is proven
    empirically; default is guide as image1.
    """
    if not guide_image:
        raise RuntimeError("qwen2512.atlas_layout requires a structural guide image.")
    if appearance_image:
        return build_qwen_2512_atlas_workflow(
            unet_name=unet_name,
            clip_name=clip_name,
            vae_name=vae_name,
            positive=positive,
            negative=negative,
            source_image=appearance_image,
            guide_image=guide_image,
            slot_order=slot_order,
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
    return build_qwen_2512_atlas_direct_workflow(
        unet_name=unet_name,
        clip_name=clip_name,
        vae_name=vae_name,
        positive=positive,
        negative=negative,
        source_image=guide_image,
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


def atlas_graph_roles(graph: dict[str, Any]) -> dict[str, Any]:
    types = [str((node or {}).get("class_type") or "") for node in graph.values() if isinstance(node, dict)]
    loads = [nid for nid, node in graph.items() if isinstance(node, dict) and node.get("class_type") == "LoadImage"]
    plus = [
        node
        for node in graph.values()
        if isinstance(node, dict) and node.get("class_type") == "TextEncodeQwenImageEditPlus"
    ]
    negative = graph.get("8") if isinstance(graph.get("8"), dict) else {}
    return {
        "loadImageCount": len(loads),
        "usesTextEncodeQwenImageEditPlus": "TextEncodeQwenImageEditPlus" in types,
        "usesTextEncodeQwenImageEdit": "TextEncodeQwenImageEdit" in types,
        "hasImage1": any("image1" in (node.get("inputs") or {}) for node in plus),
        "hasImage2": any("image2" in (node.get("inputs") or {}) for node in plus),
        "negativeEncodeMode": (
            "text_only"
            if (negative or {}).get("class_type") == "CLIPTextEncode"
            else "dual_image"
        ),
    }
