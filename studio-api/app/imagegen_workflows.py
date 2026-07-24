from __future__ import annotations

"""Model-agnostic ImageGen Comfy workflow builders (FLUX-class default)."""

from typing import Any


def build_txt2img_workflow(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    steps: int = 20,
    cfg: float = 3.5,
    filename_prefix: str = "studio/imagegen",
) -> dict[str, Any]:
    """
    Minimal checkpoint txt2img graph compatible with standard Comfy CheckpointLoaderSimple.
    Swap checkpoint for FLUX/SD3.5/HiDream weights as configured.
    """
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative or "blurry, low quality, watermark", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed if seed >= 0 else 0,
                "steps": max(4, steps),
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": filename_prefix},
        },
    }


def build_img2img_edit_stub(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    image_name: str,
    denoise: float = 0.45,
    seed: int = 0,
    steps: int = 16,
    filename_prefix: str = "studio/imagegen_edit",
) -> dict[str, Any]:
    """Simple img2img path used for edit operations until specialized graphs land."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative or "blurry, low quality", "clip": ["1", 1]},
        },
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed if seed >= 0 else 0,
                "steps": max(4, steps),
                "cfg": 3.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["7", 0], "filename_prefix": filename_prefix},
        },
    }


IMAGEGEN_MODELS = [
    {"id": "auto", "label": "Auto Select", "group": "auto"},
    {"id": "flux", "label": "FLUX.1 family", "group": "local"},
    {"id": "hidream", "label": "HiDream-I1", "group": "local"},
    {"id": "sd35", "label": "Stable Diffusion 3.5", "group": "local"},
    {"id": "custom", "label": "ComfyUI Custom checkpoint", "group": "local"},
]
