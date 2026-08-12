from __future__ import annotations

from typing import Any, Optional


def build_zimage_inpaint_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    clip_vision_name: str,
    source_image: str,
    mask_image: str,
    prompt: str,
    negative: str = "blurry, deformed, watermark, text, logo, extra limbs",
    width: int = 1024,
    height: int = 1024,
    seed: int = 42,
    steps: int = 8,
    cfg: float = 1.0,
    denoise: float = 0.85,
    filename_prefix: str = "studio/zimg_inpaint",
    use_clip_vision: bool = True,
    inpaint_mode: str = "vae_encode_for_inpaint",
) -> dict[str, Any]:
    """
    Z-Image inpaint graph. Prefers VAEEncodeForInpaint + optional SetLatentNoiseMask;
    falls back to whole-image VAEEncode + SetLatentNoiseMask when inpaint_mode='latent_mask'.
    """
    if not source_image:
        raise RuntimeError("zimage.inpaint requires source_image")
    if not mask_image:
        raise RuntimeError("zimage.inpaint requires mask_image")

    wf: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "lumina2"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": source_image},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": mask_image},
        },
        # LoadImage yields IMAGE; VAEEncodeForInpaint / SetLatentNoiseMask need MASK
        "5b": {
            "class_type": "ImageToMask",
            "inputs": {"image": ["5", 0], "channel": "red"},
        },
        "6": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.0},
        },
        # Text-only conditioning avoids Omni+image latent shape mismatches on inpaint latents
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["2", 0]},
        },
        "9": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["2", 0]},
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

    if inpaint_mode == "latent_mask":
        wf["13"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["4", 0], "vae": ["3", 0]},
        }
        wf["14"] = {
            "class_type": "SetLatentNoiseMask",
            "inputs": {"samples": ["13", 0], "mask": ["5b", 0]},
        }
        latent_ref: list[Any] = ["14", 0]
    else:
        wf["13"] = {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {
                "pixels": ["4", 0],
                "vae": ["3", 0],
                "mask": ["5b", 0],
                "grow_mask_by": 6,
            },
        }
        latent_ref = ["13", 0]

    wf["10"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["6", 0],
            "seed": seed if seed >= 0 else 42,
            "steps": max(4, steps),
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "simple",
            "positive": ["8", 0],
            "negative": ["9", 0],
            "latent_image": latent_ref,
            "denoise": denoise,
        },
    }

    _ = width, height, use_clip_vision, clip_vision_name
    return wf


def build_zimage_outpaint_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    clip_vision_name: str,
    source_image: str,
    prompt: str,
    negative: str = "blurry, deformed, watermark, text, logo, extra limbs",
    left: int = 0,
    top: int = 0,
    right: int = 256,
    bottom: int = 256,
    seed: int = 42,
    steps: int = 8,
    cfg: float = 1.0,
    denoise: float = 0.85,
    filename_prefix: str = "studio/zimg_outpaint",
    use_clip_vision: bool = True,
    feathering: int = 40,
) -> dict[str, Any]:
    """
    Z-Image outpaint via ImagePadForOutpaint → VAEEncodeForInpaint → KSampler.
    Requires Comfy ImagePadForOutpaint; raises if padding would be zero on all sides.
    """
    if not source_image:
        raise RuntimeError("zimage.outpaint requires source_image")
    if left + top + right + bottom <= 0:
        raise RuntimeError("zimage.outpaint requires non-zero padding on at least one side")

    wf: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "lumina2"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": source_image},
        },
        "5": {
            "class_type": "ImagePadForOutpaint",
            "inputs": {
                "image": ["4", 0],
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "feathering": feathering,
            },
        },
        "6": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.0},
        },
        "7": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {
                "pixels": ["5", 0],
                "vae": ["3", 0],
                "mask": ["5", 1],
                "grow_mask_by": 6,
            },
        },
        "9": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["2", 0]},
        },
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["2", 0]},
        },
        "11": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["6", 0],
                "seed": seed if seed >= 0 else 42,
                "steps": max(4, steps),
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["9", 0],
                "negative": ["10", 0],
                "latent_image": ["7", 0],
                "denoise": denoise,
            },
        },
        "12": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["11", 0], "vae": ["3", 0]},
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {"images": ["12", 0], "filename_prefix": filename_prefix},
        },
    }
    _ = use_clip_vision, clip_vision_name
    return wf


def build_image_upscale_workflow(
    *,
    source_image: str,
    upscale_model: str = "",
    filename_prefix: str = "studio/upscale",
    scale: float = 2.0,
) -> dict[str, Any]:
    """Upscale via UpscaleModelLoader when model present; else ImageScale ×N (resolution-increase)."""
    if not source_image:
        raise RuntimeError("image.upscale requires source_image")

    # Prefer model upscale when a model name is provided; cert environments may have empty combo.
    if upscale_model and upscale_model not in {"", "none", "ImageScale"}:
        return {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": source_image},
            },
            "2": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": upscale_model},
            },
            "3": {
                "class_type": "ImageUpscaleWithModel",
                "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]},
            },
            "4": {
                "class_type": "SaveImage",
                "inputs": {"images": ["3", 0], "filename_prefix": filename_prefix},
            },
        }

    # Deterministic local upscale without ESRGAN weights (still increases resolution)
    factor = max(1.5, float(scale or 2.0))
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": source_image},
        },
        "2": {
            "class_type": "ImageScaleBy",
            "inputs": {
                "image": ["1", 0],
                "upscale_method": "lanczos",
                "scale_by": factor,
            },
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": filename_prefix},
        },
    }


def build_zimage_inpaint_ref_fallback(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    clip_vision_name: str,
    reference_image: str,
    prompt: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Last-resort img2img-style path when inpaint nodes unavailable.
    Uses reference workflow without mask semantics — caller should treat as degraded.
    """
    from .image_tools import build_zimage_ref_workflow

    return build_zimage_ref_workflow(
        unet_name=unet_name,
        clip_name=clip_name,
        vae_name=vae_name,
        clip_vision_name=clip_vision_name,
        reference_image=reference_image,
        prompt=prompt,
        **kwargs,
    )
