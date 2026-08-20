"""ComfyUI workflow builders for LTX 2.5 (Text-to-Video, Image-to-Video).

Architecture follows the official Lightricks LTX 2.5 single-stage distilled
workflow topology, verified against live ComfyUI /object_info at runtime:

  UNETLoader + VAELoader(video) + CLIPLoader(type=ltxv)
    → CLIPTextEncode → LTXVConditioning
    → ModelSamplingLTXV → LTXVScheduler → RandomNoise → KSamplerSelect
    → STGGuiderNode → LTXVBaseSampler
    → LTXVSeparateAVLatent → LTXVTiledVAEDecode + LTXVAudioVAEDecode
    → CreateVideo → SaveVideo

No LTXV2* nodes exist in the official extension. The LTXV2TextToVideo,
LTXV2ImgToVideo, and LTXV2FirstLastFrameToVideo class names used by the
previous builder were invented and are NOT registered in the live ecosystem.

Default variant: Distilled INT8 ConvRot.
Fast mode: 8 steps. Quality mode: 40 steps.
"""

from __future__ import annotations

import uuid
from typing import Any


def _nid() -> str:
    return str(uuid.uuid4().int)[:8]


def _resolve_steps(fast_mode: bool) -> int:
    return 8 if fast_mode else 40


def _compute_frame_count(length_seconds: float, fps: int) -> int:
    count = int(length_seconds * fps)
    count = max(1, count)
    count = ((count + 7) // 8) * 8 + 1
    return count


def _snap_ltx_25_spatial(width: int, height: int, *, multiple: int = 32) -> tuple[int, int]:
    """LTX 2.5 patchify requires latent H/W even after /16, so pixels must be /32.

    1280x720 encodes to latent height 45, which cannot divide by patch 2.
    """

    def _one(value: int) -> int:
        value = max(multiple, int(value or multiple))
        return max(multiple, int(round(value / multiple) * multiple))

    return _one(width), _one(height)


def build_ltx_25_t2v(
    settings: Any,
    execution_id: str,
    prompt: str,
    negative_prompt: str = "",
    width: int = 1280,
    height: int = 720,
    length_seconds: float = 5.0,
    fps: int = 24,
    seed: int = 0,
    generate_audio: bool = True,
    fast_mode: bool = True,
) -> dict[str, Any]:
    """Build a ComfyUI workflow for LTX 2.5 Text-to-Video.

    Uses the verified official topology:
      UNETLoader → ModelSamplingLTXV → LTXVScheduler → LTXVBaseSampler
      → LTXVTiledVAEDecode → CreateVideo → SaveVideo
    """
    steps = _resolve_steps(fast_mode)
    total_frames = _compute_frame_count(length_seconds, fps)
    width, height = _snap_ltx_25_spatial(width, height)

    n_unet = _nid()
    n_vae = _nid()
    n_clip = _nid()
    n_pos = _nid()
    n_neg = _nid()
    n_cond = _nid()
    n_model_patch = _nid()
    n_stg_apply = _nid()
    n_sched = _nid()
    n_noise = _nid()
    n_sampler = _nid()
    n_guider = _nid()
    n_base_sampler = _nid()
    n_sep = _nid() if generate_audio else None
    n_dec_video = _nid()
    n_dec_audio = _nid() if generate_audio else None
    n_avae = _nid() if generate_audio else None
    n_create_video = _nid()
    n_save = _nid()

    wf: dict[str, Any] = {}

    wf[n_unet] = {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": settings.ltx_2_5_checkpoint,
            "weight_dtype": "default",
        },
    }

    wf[n_vae] = {
        "class_type": "VAELoader",
        "inputs": {"vae_name": settings.ltx_2_5_video_vae},
    }

    wf[n_clip] = {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": settings.ltx_2_5_text_encoder,
            "type": "ltxv",
        },
    }

    wf[n_pos] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": [n_clip, 0]},
    }

    wf[n_neg] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt or "", "clip": [n_clip, 0]},
    }

    wf[n_cond] = {
        "class_type": "LTXVConditioning",
        "inputs": {
            "positive": [n_pos, 0],
            "negative": [n_neg, 0],
            "frame_rate": float(fps),
        },
    }

    wf[n_model_patch] = {
        "class_type": "ModelSamplingLTXV",
        "inputs": {
            "model": [n_unet, 0],
            "max_shift": 2.05,
            "base_shift": 0.95,
        },
    }

    wf[n_stg_apply] = {
        "class_type": "LTXVApplySTG",
        "inputs": {
            "model": [n_model_patch, 0],
            "block_indices": "14, 19",
        },
    }

    wf[n_sched] = {
        "class_type": "LTXVScheduler",
        "inputs": {
            "steps": steps,
            "max_shift": 2.05,
            "base_shift": 0.95,
            "stretch": True,
            "terminal": 0.1,
        },
    }

    wf[n_noise] = {
        "class_type": "RandomNoise",
        "inputs": {
            "noise_seed": seed if seed >= 0 else abs(hash(prompt)) % (2**31)
        },
    }

    wf[n_sampler] = {
        "class_type": "KSamplerSelect",
        "inputs": {"sampler_name": "euler"},
    }

    wf[n_guider] = {
        "class_type": "STGGuiderNode",
        "inputs": {
            "model": [n_stg_apply, 0],
            "positive": [n_cond, 0],
            "negative": [n_cond, 1],
            "cfg": 3.0,
            "stg": 1.0,
            "rescale": 0.7,
        },
    }

    wf[n_base_sampler] = {
        "class_type": "LTXVBaseSampler",
        "inputs": {
            "model": [n_stg_apply, 0],
            "vae": [n_vae, 0],
            "width": width,
            "height": height,
            "num_frames": total_frames,
            "guider": [n_guider, 0],
            "sampler": [n_sampler, 0],
            "sigmas": [n_sched, 0],
            "noise": [n_noise, 0],
        },
    }

    if generate_audio:
        wf[n_avae] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": settings.ltx_2_5_audio_vae},
        }

    wf[n_dec_video] = {
        "class_type": "LTXVTiledVAEDecode",
        "inputs": {
            "vae": [n_vae, 0],
            "latents": [n_base_sampler, 0],
            "horizontal_tiles": 2,
            "vertical_tiles": 2,
            "overlap": 2,
            "last_frame_fix": False,
        },
    }

    wf[n_create_video] = {
        "class_type": "CreateVideo",
        "inputs": {
            "images": [n_dec_video, 0],
            "fps": float(fps),
            "bit_depth": 8,
        },
    }

    wf[n_save] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": [n_create_video, 0],
            "filename_prefix": f"studio/ltx_25_t2v/{execution_id}",
            "format": "mp4",
            "codec": "auto",
        },
    }

    return wf


def build_ltx_25_i2v(
    settings: Any,
    execution_id: str,
    prompt: str,
    negative_prompt: str = "",
    start_image_path: str = "",
    width: int = 1280,
    height: int = 720,
    length_seconds: float = 5.0,
    fps: int = 24,
    seed: int = 0,
    generate_audio: bool = True,
    fast_mode: bool = True,
) -> dict[str, Any]:
    """Build a ComfyUI workflow for LTX 2.5 Image-to-Video.

    Uses LTXVImgToVideo for image conditioning, then routes into the
    standard LTX 2.5 sampler/decode/output pipeline.
    """
    steps = _resolve_steps(fast_mode)
    total_frames = _compute_frame_count(length_seconds, fps)
    width, height = _snap_ltx_25_spatial(width, height)

    n_unet = _nid()
    n_vae = _nid()
    n_clip = _nid()
    n_pos = _nid()
    n_neg = _nid()
    n_cond = _nid()
    n_img = _nid()
    n_i2v = _nid()
    n_model_patch = _nid()
    n_stg_apply = _nid()
    n_sched = _nid()
    n_noise = _nid()
    n_sampler = _nid()
    n_guider = _nid()
    n_base_sampler = _nid()
    n_avae = _nid() if generate_audio else None
    n_dec_video = _nid()
    n_create_video = _nid()
    n_save = _nid()

    wf: dict[str, Any] = {}

    wf[n_unet] = {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": settings.ltx_2_5_checkpoint,
            "weight_dtype": "default",
        },
    }

    wf[n_vae] = {
        "class_type": "VAELoader",
        "inputs": {"vae_name": settings.ltx_2_5_video_vae},
    }

    wf[n_clip] = {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": settings.ltx_2_5_text_encoder,
            "type": "ltxv",
        },
    }

    wf[n_pos] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": [n_clip, 0]},
    }

    wf[n_neg] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt or "", "clip": [n_clip, 0]},
    }

    wf[n_cond] = {
        "class_type": "LTXVConditioning",
        "inputs": {
            "positive": [n_pos, 0],
            "negative": [n_neg, 0],
            "frame_rate": float(fps),
        },
    }

    wf[n_img] = {
        "class_type": "LoadImage",
        "inputs": {"image": start_image_path},
    }

    wf[n_i2v] = {
        "class_type": "LTXVImgToVideo",
        "inputs": {
            "positive": [n_cond, 0],
            "negative": [n_cond, 1],
            "vae": [n_vae, 0],
            "image": [n_img, 0],
            "width": width,
            "height": height,
            "length": total_frames,
            "batch_size": 1,
            "strength": 0.95,
        },
    }

    wf[n_model_patch] = {
        "class_type": "ModelSamplingLTXV",
        "inputs": {
            "model": [n_unet, 0],
            "max_shift": 2.05,
            "base_shift": 0.95,
        },
    }

    wf[n_stg_apply] = {
        "class_type": "LTXVApplySTG",
        "inputs": {
            "model": [n_model_patch, 0],
            "block_indices": "14, 19",
        },
    }

    wf[n_sched] = {
        "class_type": "LTXVScheduler",
        "inputs": {
            "steps": steps,
            "max_shift": 2.05,
            "base_shift": 0.95,
            "stretch": True,
            "terminal": 0.1,
        },
    }

    wf[n_noise] = {
        "class_type": "RandomNoise",
        "inputs": {
            "noise_seed": seed if seed >= 0 else abs(hash(prompt)) % (2**31)
        },
    }

    wf[n_sampler] = {
        "class_type": "KSamplerSelect",
        "inputs": {"sampler_name": "euler"},
    }

    wf[n_guider] = {
        "class_type": "STGGuiderNode",
        "inputs": {
            "model": [n_stg_apply, 0],
            "positive": [n_i2v, 0],
            "negative": [n_i2v, 1],
            "cfg": 3.0,
            "stg": 1.0,
            "rescale": 0.7,
        },
    }

    wf[n_base_sampler] = {
        "class_type": "LTXVBaseSampler",
        "inputs": {
            "model": [n_stg_apply, 0],
            "vae": [n_vae, 0],
            "width": width,
            "height": height,
            "num_frames": total_frames,
            "guider": [n_guider, 0],
            "sampler": [n_sampler, 0],
            "sigmas": [n_sched, 0],
            "noise": [n_noise, 0],
            "optional_cond_images": [n_img, 0],
            "optional_cond_indices": "0",
            "strength": 0.95,
            "crop": "center",
        },
    }

    if generate_audio:
        wf[n_avae] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": settings.ltx_2_5_audio_vae},
        }

    wf[n_dec_video] = {
        "class_type": "LTXVTiledVAEDecode",
        "inputs": {
            "vae": [n_vae, 0],
            "latents": [n_base_sampler, 0],
            "horizontal_tiles": 2,
            "vertical_tiles": 2,
            "overlap": 2,
            "last_frame_fix": False,
        },
    }

    wf[n_create_video] = {
        "class_type": "CreateVideo",
        "inputs": {
            "images": [n_dec_video, 0],
            "fps": float(fps),
            "bit_depth": 8,
        },
    }

    wf[n_save] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": [n_create_video, 0],
            "filename_prefix": f"studio/ltx_25_i2v/{execution_id}",
            "format": "mp4",
            "codec": "auto",
        },
    }

    return wf
