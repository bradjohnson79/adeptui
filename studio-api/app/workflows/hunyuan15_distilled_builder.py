"""HunyuanVideo 1.5 Distilled graphs for the staged 480p checkpoints.

The official templates in the download staging folder are 720p references.
They name 720p fp16 weights and a super-resolution stage. This builder keeps
the official node classes and points them at the staged 480p distilled files.
It does not load a 720p checkpoint and it does not run super-resolution.
"""

from __future__ import annotations

from typing import Any

T2V_UNET = "hunyuanvideo1.5_480p_t2v_cfg_distilled_fp8_scaled.safetensors"
I2V_UNET = "hunyuanvideo1.5_480p_i2v_step_distilled_fp8_scaled.safetensors"
CLIP_QWEN = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
CLIP_BYT5 = "byt5_small_glyphxl_fp16.safetensors"
VAE_NAME = "hunyuanvideo15_vae_fp16.safetensors"
CLIP_VISION = "sigclip_vision_patch14_384.safetensors"

T2V_STEPS = 50
T2V_SHIFT = 5.0
I2V_STEPS = 8
I2V_SHIFT = 7.0
CFG = 1.0
FPS = 24


def hunyuan_frames(duration_sec: float, fps: int = FPS) -> int:
    """Nearest 4n+1 frame count. Five seconds at 24 fps lands on 121."""

    target = max(1.0, float(duration_sec)) * int(fps)
    steps = max(1, int(round((target - 1.0) / 4.0)))
    return 4 * steps + 1


def hunyuan_size(aspect: str | None) -> tuple[int, int]:
    """480p-class canvas. 16:9 is 848×480, which is divisible by 16."""

    token = str(aspect or "16:9").strip().replace(" ", "")
    if token in {"9:16", "9/16"}:
        return 480, 848
    if token in {"1:1", "1/1"}:
        return 480, 480
    return 848, 480


def build_hunyuan_distilled_workflow(
    *,
    mode: str,
    prompt: str,
    filename_prefix: str,
    seed: int,
    width: int,
    height: int,
    duration_sec: float,
    start_image: str = "",
) -> dict[str, Any]:
    """Text to Video, or Start Frame via native HunyuanVideo15ImageToVideo."""

    token = str(mode or "t2v").strip().lower().replace("-", "_")
    i2v = token in {"i2v", "image_to_video", "one_frame", "start_frame"}
    if i2v and not str(start_image or "").strip():
        raise ValueError("HunyuanVideo 1.5 Distilled Start Frame needs a still image.")
    steps = I2V_STEPS if i2v else T2V_STEPS
    shift = I2V_SHIFT if i2v else T2V_SHIFT
    frames = hunyuan_frames(duration_sec)
    unet_name = I2V_UNET if i2v else T2V_UNET

    clip, unet, vae = "1", "2", "3"
    positive, negative = "4", "5"
    sampling, latent = "6", "7"
    guider, scheduler, sampler_select, noise = "8", "9", "10", "11"
    sampler, decode, create, save = "12", "13", "14", "15"

    graph: dict[str, Any] = {
        clip: {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": CLIP_QWEN,
                "clip_name2": CLIP_BYT5,
                "type": "hunyuan_video_15",
                "device": "default",
            },
        },
        unet: {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        vae: {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
        positive: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": str(prompt or ""), "clip": [clip, 0]},
        },
        negative: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": [clip, 0]},
        },
        sampling: {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": [unet, 0], "shift": float(shift)},
        },
        scheduler: {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": [unet, 0],
                "scheduler": "simple",
                "steps": int(steps),
                "denoise": 1.0,
            },
        },
        sampler_select: {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        noise: {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(seed)},
        },
        decode: {
            "class_type": "VAEDecode",
            "inputs": {"samples": [sampler, 0], "vae": [vae, 0]},
        },
        create: {
            "class_type": "CreateVideo",
            "inputs": {"images": [decode, 0], "fps": FPS},
        },
        save: {
            "class_type": "SaveVideo",
            "inputs": {
                "video": [create, 0],
                "filename_prefix": filename_prefix,
                "format": "mp4",
                "format.codec": "auto",
                "codec": "auto",
            },
        },
    }

    if i2v:
        vision, encode, picture, i2v_node = "16", "17", "18", "19"
        graph[vision] = {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": CLIP_VISION},
        }
        graph[picture] = {
            "class_type": "LoadImage",
            "inputs": {"image": str(start_image)},
        }
        graph[encode] = {
            "class_type": "CLIPVisionEncode",
            "inputs": {
                "clip_vision": [vision, 0],
                "image": [picture, 0],
                "crop": "center",
            },
        }
        graph[i2v_node] = {
            "class_type": "HunyuanVideo15ImageToVideo",
            "inputs": {
                "positive": [positive, 0],
                "negative": [negative, 0],
                "vae": [vae, 0],
                "width": int(width),
                "height": int(height),
                "length": int(frames),
                "batch_size": 1,
                "start_image": [picture, 0],
                "clip_vision_output": [encode, 0],
            },
        }
        positive_ref = [i2v_node, 0]
        negative_ref = [i2v_node, 1]
        latent_ref = [i2v_node, 2]
    else:
        graph[latent] = {
            "class_type": "EmptyHunyuanVideo15Latent",
            "inputs": {
                "width": int(width),
                "height": int(height),
                "length": int(frames),
                "batch_size": 1,
            },
        }
        positive_ref = [positive, 0]
        negative_ref = [negative, 0]
        latent_ref = [latent, 0]

    graph[guider] = {
        "class_type": "CFGGuider",
        "inputs": {
            "model": [sampling, 0],
            "positive": positive_ref,
            "negative": negative_ref,
            "cfg": CFG,
        },
    }
    graph[sampler] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": [noise, 0],
            "guider": [guider, 0],
            "sampler": [sampler_select, 0],
            "sigmas": [scheduler, 0],
            "latent_image": latent_ref,
        },
    }
    return graph
