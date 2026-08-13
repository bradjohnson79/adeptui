"""FLUX.1 (Kontext Dev) ComfyUI workflow builders for Adept UI image generation.

These builders produce the node graph required by the modern ComfyUI API for
FLUX-class rectified-flow models. They use the standard core nodes:
  - UNETLoader (diffusion model)
  - VAELoader (ae VAE)
  - DualCLIPLoader (clip_l + t5xxl)
  - EmptySD3LatentImage / LoadImage + VAEEncode
  - CLIPTextEncode
  - ConditioningZeroOut
  - KSampler
  - VAEDecode
  - SaveImage
"""

from __future__ import annotations

from typing import Any


def _flux_model_nodes(
    *,
    unet_name: str,
    clip_l_name: str,
    t5_name: str,
    vae_name: str,
    weight_dtype: str = "default",
) -> tuple[dict[str, Any], str, str, str]:
    """Return the three model-loader nodes and their output id map.

    Returns (loaders_dict, model_node_id, vae_node_id, clip_node_id).
    """
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": unet_name,
                "weight_dtype": weight_dtype,
            },
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae_name,
            },
        },
        "3": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": clip_l_name,
                "clip_name2": t5_name,
                "type": "flux",
                "device": "default",
            },
        },
    }, "1", "2", "3"


def _flux_positive_negative_nodes(
    *,
    positive: str,
    negative: str,
    clip_node_id: str,
) -> dict[str, Any]:
    """Encode positive prompt and zero-out negative conditioning for FLUX.

    FLUX was trained without negative conditioning, so the standard recipe is to
    encode the positive prompt and feed a zeroed conditioning tensor as the
    negative input. The user-supplied negative prompt is appended to the positive
    prompt so the guidance still has some effect.
    """
    effective_positive = positive.strip()
    if negative and negative.strip():
        effective_positive += f"\n{negative.strip()}"
    return {
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": effective_positive,
                "clip": [clip_node_id, 0],
            },
        },
        "5": {
            "class_type": "ConditioningZeroOut",
            "inputs": {
                "conditioning": ["4", 0],
            },
        },
    }


def _flux_sampler(
    *,
    model_node_id: str,
    positive_node_id: str,
    negative_node_id: str,
    latent_node_id: str,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
) -> dict[str, Any]:
    return {
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": [model_node_id, 0],
                "positive": [positive_node_id, 0],
                "negative": [negative_node_id, 0],
                "latent_image": [latent_node_id, 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        },
    }


def _flux_decode_and_save(
    *,
    vae_node_id: str,
    sampler_node_id: str,
    filename_prefix: str,
) -> dict[str, Any]:
    return {
        "7": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [sampler_node_id, 0],
                "vae": [vae_node_id, 0],
            },
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["7", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }


def build_flux_txt2img_workflow(
    *,
    positive: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    unet_name: str,
    clip_l_name: str,
    t5_name: str,
    vae_name: str,
    steps: int = 20,
    cfg: float = 1.0,
    sampler_name: str = "euler",
    scheduler: str = "simple",
    filename_prefix: str = "studio/flux",
) -> dict[str, Any]:
    """Build a FLUX.1 txt2img ComfyUI workflow graph."""
    loaders, model_id, vae_id, clip_id = _flux_model_nodes(
        unet_name=unet_name,
        clip_l_name=clip_l_name,
        t5_name=t5_name,
        vae_name=vae_name,
    )
    conditioning = _flux_positive_negative_nodes(
        positive=positive,
        negative=negative,
        clip_node_id=clip_id,
    )
    latent = {
        "9": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
    }
    sampler = _flux_sampler(
        model_node_id=model_id,
        positive_node_id="4",
        negative_node_id="5",
        latent_node_id="9",
        seed=seed,
        steps=steps,
        cfg=cfg,
        sampler_name=sampler_name,
        scheduler=scheduler,
        denoise=1.0,
    )
    decode_save = _flux_decode_and_save(
        vae_node_id=vae_id,
        sampler_node_id="6",
        filename_prefix=filename_prefix,
    )
    return {**loaders, **conditioning, **latent, **sampler, **decode_save}


def build_flux_img2img_workflow(
    *,
    positive: str,
    negative: str,
    image_name: str,
    seed: int,
    unet_name: str,
    clip_l_name: str,
    t5_name: str,
    vae_name: str,
    denoise: float = 0.35,
    steps: int = 20,
    cfg: float = 1.0,
    sampler_name: str = "euler",
    scheduler: str = "simple",
    filename_prefix: str = "studio/flux_edit",
) -> dict[str, Any]:
    """Build a FLUX.1 img2img/edit ComfyUI workflow graph.

    The source image is loaded, encoded into the latent space, and used as the
    latent_image for the KSampler with denoise < 1.0.
    """
    loaders, model_id, vae_id, clip_id = _flux_model_nodes(
        unet_name=unet_name,
        clip_l_name=clip_l_name,
        t5_name=t5_name,
        vae_name=vae_name,
    )
    conditioning = _flux_positive_negative_nodes(
        positive=positive,
        negative=negative,
        clip_node_id=clip_id,
    )
    latent = {
        "9": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_name,
            },
        },
        "10": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["9", 0],
                "vae": [vae_id, 0],
            },
        },
    }
    sampler = _flux_sampler(
        model_node_id=model_id,
        positive_node_id="4",
        negative_node_id="5",
        latent_node_id="10",
        seed=seed,
        steps=steps,
        cfg=cfg,
        sampler_name=sampler_name,
        scheduler=scheduler,
        denoise=denoise,
    )
    decode_save = _flux_decode_and_save(
        vae_node_id=vae_id,
        sampler_node_id="6",
        filename_prefix=filename_prefix,
    )
    return {**loaders, **conditioning, **latent, **sampler, **decode_save}
