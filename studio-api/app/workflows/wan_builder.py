from __future__ import annotations

from typing import Any, Optional


def build_wan_flf_workflow(
    *,
    high_noise: str,
    low_noise: str,
    vae_name: str,
    text_encoder: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    length: int,
    fps: int,
    seed: int,
    start_image: Optional[str] = None,
    end_image: Optional[str] = None,
    steps_high: int = 4,
    steps_low: int = 4,
    filename_prefix: str = "studio/wan_scene",
) -> dict[str, Any]:
    """
    WAN first/last frame workflow using native Comfy nodes.
    Falls back gracefully if only start image is provided (I2V).
    """
    length = max(5, ((length - 1) // 4) * 4 + 1)  # WAN prefers 4n+1

    wf: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": high_noise, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": low_noise, "weight_dtype": "default"},
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": text_encoder, "type": "wan"},
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["3", 0]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["3", 0]},
        },
        "7": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["1", 0], "shift": 8.0},
        },
        "8": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["2", 0], "shift": 8.0},
        },
    }

    if start_image:
        wf["9"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
    if end_image:
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": end_image}}

    if start_image and end_image:
        flf_inputs: dict[str, Any] = {
            "positive": ["5", 0],
            "negative": ["6", 0],
            "vae": ["4", 0],
            "width": width,
            "height": height,
            "length": length,
            "batch_size": 1,
            "start_image": ["9", 0],
            "end_image": ["10", 0],
        }
        wf["11"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": flf_inputs}
    elif start_image:
        wf["11"] = {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["5", 0],
                "negative": ["6", 0],
                "vae": ["4", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
                "start_image": ["9", 0],
            },
        }
    else:
        wf["11"] = {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["5", 0],
                "negative": ["6", 0],
                "vae": ["4", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
            },
        }

    # Two-stage sampler: high noise then low noise
    wf["12"] = {
        "class_type": "KSamplerAdvanced",
        "inputs": {
            "model": ["7", 0],
            "add_noise": "enable",
            "noise_seed": seed if seed >= 0 else 42,
            "steps": steps_high + steps_low,
            "cfg": 3.5,
            "sampler_name": "uni_pc",
            "scheduler": "simple",
            "positive": ["11", 0],
            "negative": ["11", 1],
            "latent_image": ["11", 2],
            "start_at_step": 0,
            "end_at_step": steps_high,
            "return_with_leftover_noise": "enable",
        },
    }
    wf["13"] = {
        "class_type": "KSamplerAdvanced",
        "inputs": {
            "model": ["8", 0],
            "add_noise": "disable",
            "noise_seed": seed if seed >= 0 else 42,
            "steps": steps_high + steps_low,
            "cfg": 3.5,
            "sampler_name": "uni_pc",
            "scheduler": "simple",
            "positive": ["11", 0],
            "negative": ["11", 1],
            "latent_image": ["12", 0],
            "start_at_step": steps_high,
            "end_at_step": 10000,
            "return_with_leftover_noise": "disable",
        },
    }
    wf["14"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["13", 0], "vae": ["4", 0]},
    }
    wf["15"] = {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["14", 0],
            "frame_rate": fps,
            "loop_count": 0,
            "filename_prefix": filename_prefix,
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True,
        },
    }
    return wf
