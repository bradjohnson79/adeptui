from __future__ import annotations

import json
import uuid
from typing import Any, Optional


def _nid() -> str:
    return str(uuid.uuid4().int)[:8]


def build_ltx_director_timeline(
    *,
    segments: list[dict[str, Any]],
    audio_segments: list[dict[str, Any]] | None = None,
    global_prompt: str = "",
    duration_frames: int,
    retake_mode: bool = False,
    retake_start: int = 0,
    retake_length: int = 48,
    retake_prompt: str = "",
) -> dict[str, Any]:
    return {
        "mainTrackEnabled": True,
        "audioTrackEnabled": True,
        "motionTrackEnabled": True,
        "propHeight": 90,
        "globalPropHeight": 60,
        "showFilenames": True,
        "overrideAudio": False,
        "inpaint_audio": True,
        "global_prompt": global_prompt,
        "retake_global_prompt": global_prompt,
        "retakeMode": retake_mode,
        "retakeStart": retake_start,
        "retakeLength": retake_length,
        "retakePrompt": retake_prompt,
        "retakeStrength": 1,
        "retakeVideo": None,
        "normalStartFrame": 0,
        "normalDurationFrames": duration_frames,
        "segments": segments,
        "motionSegments": [],
        "audioSegments": audio_segments or [],
    }


def build_ltx_scene_workflow(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    length: int,
    fps: int,
    seed: int,
    start_image: Optional[str] = None,
    middle_image: Optional[str] = None,
    end_image: Optional[str] = None,
    audio_file: Optional[str] = None,
    guide_strength: float = 0.9,
    steps: int = 8,
    cfg: float = 1.0,
    filename_prefix: str = "studio/ltx_scene",
    text_encoder: str = "gemma_3_12B_it_fp4_mixed.safetensors",
) -> dict[str, Any]:
    """
    Practical LTX I2V workflow using LTXDirector + LTXDirectorGuide.
    Keyframes are encoded as image segments on the Director timeline.

    LTX 2.3 distilled/dev checkpoints expose MODEL+VAE via CheckpointLoaderSimple but
    CLIP is None — CLIP must come from LTXAVTextEncoderLoader.
    """
    # Frame placement: start at 0, middle at mid, end marked isEndFrame
    segs: list[dict[str, Any]] = []
    strengths: list[str] = []
    if start_image:
        segs.append(
            {
                "id": _nid(),
                "start": 0,
                "length": max(1, length // 3),
                "prompt": positive,
                "type": "image",
                "imageFile": start_image,
                "isEndFrame": False,
                "guideStrength": guide_strength,
            }
        )
        strengths.append(str(guide_strength))
    if middle_image:
        mid = max(1, length // 2)
        segs.append(
            {
                "id": _nid(),
                "start": mid,
                "length": max(1, length // 4),
                "prompt": positive,
                "type": "image",
                "imageFile": middle_image,
                "isEndFrame": False,
                "guideStrength": guide_strength,
            }
        )
        strengths.append(str(guide_strength))
    if end_image:
        segs.append(
            {
                "id": _nid(),
                "start": max(0, length - max(1, length // 4)),
                "length": max(1, length // 4),
                "prompt": positive,
                "type": "image",
                "imageFile": end_image,
                "isEndFrame": True,
                "guideStrength": guide_strength,
            }
        )
        strengths.append(str(guide_strength))

    if not segs:
        # Text-only segment spanning full duration
        segs.append(
            {
                "id": _nid(),
                "start": 0,
                "length": length,
                "prompt": positive,
                "type": "text",
            }
        )

    audio_segs: list[dict[str, Any]] = []
    if audio_file:
        audio_segs.append(
            {
                "id": _nid(),
                "start": 0,
                "length": length,
                "audioFile": audio_file,
                "trimStart": 0,
            }
        )

    local_prompts = " | ".join(s.get("prompt", positive) or positive for s in segs if s.get("type") != "image" or True)
    # Prefer explicit text segments; for image-only, use scene prompt once
    textish = [s for s in segs if s.get("type") == "text"]
    if textish:
        local_prompts = " | ".join(s.get("prompt", "") for s in textish)
    else:
        local_prompts = positive

    segment_lengths = ",".join(str(int(s.get("length", 1))) for s in segs)
    timeline = build_ltx_director_timeline(
        segments=segs,
        audio_segments=audio_segs,
        global_prompt=positive,
        duration_frames=length,
    )

    # Node IDs
    n_ckpt, n_clip, n_vae, n_avae = "1", "2", "3", "4"
    n_dir, n_guide, n_noise, n_samp, n_sched = "10", "11", "12", "13", "14"
    n_guider, n_custom, n_dec, n_vid, n_save = "15", "16", "17", "18", "19"
    n_sep, n_auddec = "20", "21"

    wf: dict[str, Any] = {
        n_ckpt: {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        n_clip: {
            "class_type": "LTXAVTextEncoderLoader",
            "inputs": {
                "text_encoder": text_encoder,
                "ckpt_name": checkpoint,
                "device": "default",
            },
        },
        n_dir: {
            "class_type": "LTXDirector",
            "inputs": {
                "model": [n_ckpt, 0],
                "clip": [n_clip, 0],
                "start_second": 0.0,
                "end_second": length / float(fps),
                "duration_seconds": length / float(fps),
                "start_frame": 0,
                "end_frame": length,
                "duration_frames": length,
                "timeline_data": json.dumps(timeline),
                "local_prompts": local_prompts,
                "segment_lengths": segment_lengths,
                "epsilon": 0.001,
                "guide_strength": ",".join(strengths) if strengths else "1.0",
                "global_prompt": positive,
                "use_custom_audio": bool(audio_file),
                "use_custom_motion": False,
                "inpaint_audio": True,
                "frame_rate": fps,
                "display_mode": "seconds",
                "custom_width": width,
                "custom_height": height,
                "resize_method": "maintain aspect ratio",
                "divisible_by": 32,
                "img_compression": 18,
                "override_audio": False,
            },
        },
        n_guide: {
            "class_type": "LTXDirectorGuide",
            "inputs": {
                "positive": [n_dir, 1],
                "negative": [n_dir, 1],  # will zero-out below
                "vae": [n_ckpt, 2],
                "latent": [n_dir, 2],
                "guide_data": [n_dir, 4],
                "motion_guide_data": [n_dir, 5],
                "model": [n_dir, 0],
                "ic_lora_name": "None",
                "ic_lora_strength": 1.0,
            },
        },
        "11b": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": [n_dir, 1]},
        },
        n_noise: {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed if seed >= 0 else abs(hash(positive)) % (2**31)},
        },
        n_samp: {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        n_sched: {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": [n_guide, 3],
                "scheduler": "normal",
                "steps": steps,
                "denoise": 1.0,
            },
        },
        n_guider: {
            "class_type": "CFGGuider",
            "inputs": {
                "model": [n_guide, 3],
                "positive": [n_guide, 0],
                "negative": ["11b", 0],
                "cfg": cfg,
            },
        },
        n_custom: {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [n_noise, 0],
                "guider": [n_guider, 0],
                "sampler": [n_samp, 0],
                "sigmas": [n_sched, 0],
                "latent_image": [n_guide, 2],
            },
        },
        n_dec: {
            "class_type": "VAEDecode",
            "inputs": {"samples": [n_custom, 0], "vae": [n_ckpt, 2]},
        },
        n_vid: {
            "class_type": "CreateVideo",
            "inputs": {
                "images": [n_dec, 0],
                "fps": float(fps),
            },
        },
        n_save: {
            "class_type": "SaveVideo",
            "inputs": {
                "video": [n_vid, 0],
                "filename_prefix": filename_prefix,
                "format": "mp4",
                "codec": "h264",
            },
        },
    }

    # Wire negative from zero-out into guide
    wf[n_guide]["inputs"]["negative"] = ["11b", 0]

    # Optional audio decode path if director produced audio latent
    if audio_file:
        wf[n_sep] = {
            "class_type": "LTXVSeparateAVLatent",
            "inputs": {"av_latent": [n_custom, 0]},
        }
        # Prefer video frames from separate if available; keep simple CreateVideo path

    return wf


def build_ltx_simple_i2v(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    length: int,
    fps: int,
    seed: int,
    start_image: str,
    steps: int = 8,
    filename_prefix: str = "studio/ltx_simple",
    text_encoder: str = "gemma_3_12B_it_fp4_mixed.safetensors",
) -> dict[str, Any]:
    """Fallback simpler LTXVImgToVideo path if Director graph fails validation/execution."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "1b": {
            "class_type": "LTXAVTextEncoderLoader",
            "inputs": {
                "text_encoder": text_encoder,
                "ckpt_name": checkpoint,
                "device": "default",
            },
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["1b", 0]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["1b", 0]},
        },
        "3b": {
            "class_type": "LTXVConditioning",
            "inputs": {
                "positive": ["2", 0],
                "negative": ["3", 0],
                "frame_rate": float(fps),
            },
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": start_image},
        },
        "5": {
            "class_type": "LTXVImgToVideo",
            "inputs": {
                "positive": ["3b", 0],
                "negative": ["3b", 1],
                "vae": ["1", 2],
                "image": ["4", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
                "strength": 0.95,
            },
        },
        "6": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed if seed >= 0 else 42},
        },
        "7": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "8": {
            "class_type": "BasicScheduler",
            "inputs": {"model": ["1", 0], "scheduler": "normal", "steps": steps, "denoise": 1.0},
        },
        "9": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["5", 1], "cfg": 1.0},
        },
        "10": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["6", 0],
                "guider": ["9", 0],
                "sampler": ["7", 0],
                "sigmas": ["8", 0],
                "latent_image": ["5", 2],
            },
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["1", 2]},
        },
        "12": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["11", 0],
                "frame_rate": fps,
                "loop_count": 0,
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }
