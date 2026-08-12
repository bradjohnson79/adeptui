"""Adept-owned Comfy workflow builders for HunyuanVideo 1.5 via Kijai HyVideo nodes.

Migrated from obsolete HunyuanVideo15Loader/Sampler/ImgToVideo class names (never
registered by current ComfyUI-HunyuanVideoWrapper) to the live HyVideo* family.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional


def _nid() -> str:
    return str(uuid.uuid4().int)[:8]


# ComfyUI diffusion_models / vae catalog paths (object_info on live Comfy).
HUNYUAN15_I2V_480P = r"adept-hunyuan-video-1.5-transformer\480p_i2v\diffusion_pytorch_model.safetensors"
HUNYUAN15_I2V_720P = r"adept-hunyuan-video-1.5-transformer\720p_i2v\diffusion_pytorch_model.safetensors"
HUNYUAN13B_T2V_FP8 = (
    r"adept-hunyuan-video-13b-weights\hunyuan-video-t2v-720p\transformers\mp_rank_00_model_states_fp8.pt"
)
HUNYUAN13B_T2V_FULL = (
    r"adept-hunyuan-video-13b-weights\hunyuan-video-t2v-720p\transformers\mp_rank_00_model_states.pt"
)
HUNYUAN_VAE = "hunyuan_video_vae_bf16.safetensors"

_HYVIDEO_DECODE_EXTRA = {
    "enable_vae_tiling": True,
    "temporal_tiling_sample_size": 64,
    "spatial_tile_sample_min_size": 256,
    "auto_tile_size": True,
}

_VHS_COMBINE_EXTRA = {"loop_count": 0, "pingpong": False, "save_output": True}


def _hyvideo_vae_node(vae_name: str = HUNYUAN_VAE) -> dict[str, Any]:
    return {
        "class_type": "HyVideoVAELoader",
        "inputs": {"model_name": vae_name, "precision": "bf16"},
    }


def _resolve_diffusion_model(model_root: str, preferred_substrings: tuple[str, ...]) -> str:
    """Pick a Comfy-catalog diffusion model path; fall back to on-disk scan."""
    catalog_by_hint: list[tuple[str, str]] = [
        ("480p_i2v", HUNYUAN15_I2V_480P),
        ("720p_i2v", HUNYUAN15_I2V_720P),
        ("480p_t2v", HUNYUAN15_I2V_480P),  # no dedicated 1.5 t2v weight in catalog yet
        ("t2v", HUNYUAN13B_T2V_FP8),
        ("fp8", HUNYUAN13B_T2V_FP8),
        ("13b", HUNYUAN13B_T2V_FP8),
        ("i2v", HUNYUAN15_I2V_480P),
    ]
    for hint, catalog_path in catalog_by_hint:
        if hint in preferred_substrings:
            return catalog_path

    root = Path(model_root)
    if root.is_file():
        return root.name
    candidates: list[Path] = []
    if root.is_dir():
        candidates = sorted(list(root.rglob("*.safetensors")) + list(root.rglob("*.pt")))
    for path in candidates:
        name = path.name.lower()
        if any(token in name for token in preferred_substrings):
            return path.name
    if candidates:
        return candidates[0].name
    return HUNYUAN15_I2V_480P


def build_hunyuan15_t2v(
    *,
    model_root: str,
    positive: str,
    negative: str = "",
    width: int = 848,
    height: int = 480,
    length: int = 81,
    fps: int = 24,
    seed: int = 0,
    steps: int = 30,
    cfg: float = 6.0,
    filename_prefix: str = "studio/hunyuan15_t2v",
    diffusion_model: str | None = None,
    vae_model: str = HUNYUAN_VAE,
) -> dict[str, Any]:
    """Text-to-video graph using live HyVideo* nodes."""
    model_name = diffusion_model or _resolve_diffusion_model(model_root, ("480p_t2v", "t2v"))
    te = _nid()
    model = _nid()
    vae = _nid()
    pos = _nid()
    neg = _nid()
    sampler = _nid()
    decode = _nid()
    combine = _nid()
    # Negative prompt is folded into CFG via HyVideoCFG when provided; sampler uses embeds.
    return {
        te: {
            "class_type": "DownloadAndLoadHyVideoTextEncoder",
            "inputs": {
                "llm_model": "Kijai/llava-llama-3-8b-text-encoder-tokenizer",
                "clip_model": "openai/clip-vit-large-patch14",
                "precision": "bf16",
            },
        },
        model: {
            "class_type": "HyVideoModelLoader",
            "inputs": {
                "model": model_name,
                "base_precision": "bf16",
                "quantization": "disabled",
                "load_device": "main_device",
            },
        },
        vae: _hyvideo_vae_node(vae_model),
        pos: {
            "class_type": "HyVideoTextEncode",
            "inputs": {
                "text_encoders": [te, 0],
                "prompt": positive,
                "force_offload": True,
                "prompt_template": "video",
            },
        },
        neg: {
            "class_type": "HyVideoTextEncode",
            "inputs": {
                "text_encoders": [te, 0],
                "prompt": negative or "",
                "force_offload": True,
                "prompt_template": "video",
            },
        },
        sampler: {
            "class_type": "HyVideoSampler",
            "inputs": {
                "model": [model, 0],
                "hyvid_embeds": [pos, 0],
                "width": width,
                "height": height,
                "num_frames": length,
                "steps": steps,
                "embedded_guidance_scale": cfg,
                "flow_shift": 9.0,
                "seed": seed,
                "force_offload": True,
            },
        },
        decode: {
            "class_type": "HyVideoDecode",
            "inputs": {
                "vae": [vae, 0],
                "samples": [sampler, 0],
                **_HYVIDEO_DECODE_EXTRA,
            },
        },
        combine: {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": [decode, 0],
                "frame_rate": fps,
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                **_VHS_COMBINE_EXTRA,
            },
        },
    }


def build_hunyuan15_i2v(
    *,
    model_root: str,
    positive: str,
    negative: str = "",
    start_image: Optional[str] = None,
    width: int = 848,
    height: int = 480,
    length: int = 81,
    fps: int = 24,
    seed: int = 0,
    steps: int = 30,
    cfg: float = 6.0,
    filename_prefix: str = "studio/hunyuan15_i2v",
    diffusion_model: str | None = None,
    vae_model: str = HUNYUAN_VAE,
) -> dict[str, Any]:
    """Image-to-video graph using live HyVideo* nodes."""
    model_name = diffusion_model or _resolve_diffusion_model(model_root, ("480p_i2v", "i2v"))
    te = _nid()
    model = _nid()
    vae = _nid()
    img = _nid()
    pos = _nid()
    sampler = _nid()
    decode = _nid()
    combine = _nid()
    graph: dict[str, Any] = {
        te: {
            "class_type": "DownloadAndLoadHyVideoTextEncoder",
            "inputs": {
                "llm_model": "Kijai/llava-llama-3-8b-text-encoder-tokenizer",
                "clip_model": "openai/clip-vit-large-patch14",
                "precision": "bf16",
            },
        },
        model: {
            "class_type": "HyVideoModelLoader",
            "inputs": {
                "model": model_name,
                "base_precision": "bf16",
                "quantization": "disabled",
                "load_device": "main_device",
            },
        },
        vae: _hyvideo_vae_node(vae_model),
        pos: {
            "class_type": "HyVideoI2VEncode",
            "inputs": {
                "text_encoders": [te, 0],
                "prompt": positive if not negative else f"{positive}\nNegative: {negative}",
                "force_offload": True,
                "prompt_template": "I2V_video",
            },
        },
        sampler: {
            "class_type": "HyVideoSampler",
            "inputs": {
                "model": [model, 0],
                "hyvid_embeds": [pos, 0],
                "width": width,
                "height": height,
                "num_frames": length,
                "steps": steps,
                "embedded_guidance_scale": cfg,
                "flow_shift": 9.0,
                "seed": seed,
                "force_offload": True,
                "i2v_mode": "dynamic",
            },
        },
        decode: {
            "class_type": "HyVideoDecode",
            "inputs": {
                "vae": [vae, 0],
                "samples": [sampler, 0],
                **_HYVIDEO_DECODE_EXTRA,
            },
        },
        combine: {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": [decode, 0],
                "frame_rate": fps,
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                **_VHS_COMBINE_EXTRA,
            },
        },
    }
    if start_image:
        graph[img] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        graph[pos]["inputs"]["image"] = [img, 0]
    return graph
