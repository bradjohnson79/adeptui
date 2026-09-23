"""ComfyUI workflow builders for LTX 2.5 (Text-to-Video, Image-to-Video).

Architecture follows the official Lightricks LTX 2.5 single-stage distilled
workflow topology, verified against live ComfyUI /object_info at runtime:

  UNETLoader + VAELoader(video) + CLIPLoader(type=ltxv)
    → CLIPTextEncode → LTXVConditioning
    → ModelSamplingLTXV → LTXVScheduler → RandomNoise → KSamplerSelect
    → STGGuiderNode → LTXVBaseSampler (video-only)
    AV: EmptyLTXVLatentVideo (+ ImgToVideoInplace I2V) + EmptyAudio + ConcatAV
        → SamplerCustomAdvanced → SeparateAV → TiledVAEDecode + AudioVAEDecode
    → CreateVideo → SaveVideo

No LTXV2* nodes exist in the official extension. The LTXV2TextToVideo,
LTXV2ImgToVideo, and LTXV2FirstLastFrameToVideo class names used by the
previous builder were invented and are NOT registered in the live ecosystem.

Default variant: Distilled INT8 ConvRot.
Fast mode: 8 steps. Quality mode: 40 steps.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from ..video_runtime.seed_resolve import comfy_noise_seed

LTX_25_TURBO_LORA_NAME = "ltx-2.5-22b-distilled-lora-450-bf16.safetensors"
LTX_25_FULL_UNET_NAME = "ltx-2.5-22b-dev-transformer-bf16.safetensors"
LTX_25_TURBO_LORA_STRENGTH = 1.0
LTX_25_FAST_STEPS = 8
LTX_25_QUALITY_STEPS = 40
TURBO_LORA_UNAVAILABLE = "Turbo LoRA is enabled, but its required model resource is unavailable."


def _nid() -> str:
    return str(uuid.uuid4().int)[:8]


def ltx_25_runtime_steps(*, fast_mode: bool | None, plan_steps: int | None = None) -> int:
    """Honor the Timeline Fast/Quality flag. Never silently keep the VRAM-plan step count."""
    if fast_mode is True:
        return LTX_25_FAST_STEPS
    if fast_mode is False:
        return LTX_25_QUALITY_STEPS
    if plan_steps is not None:
        return LTX_25_FAST_STEPS if int(plan_steps) <= 16 else LTX_25_QUALITY_STEPS
    return LTX_25_FAST_STEPS



def _ltx25_sampler_supports_av_latent() -> bool:
    """True when EmptyAudio+ConcatAV init is wired into the AV sampler path.

    Live LTXVBaseSampler object_info has no optional_initialization_latents
    (only optional_cond_images/indices/strength/crop/crf/blur). Official
    LTX-2.5 distilled AV topology builds NestedTensor AV latents via
    EmptyLTXVLatentVideo (+ LTXVImgToVideoInplace for I2V) +
    LTXVEmptyLatentAudio + LTXVConcatAVLatent, then samples with
    SamplerCustomAdvanced(latent_image=AV), then LTXVSeparateAVLatent.
    """
    return True


def _wire_av_init_latents(
    wf: dict[str, Any],
    *,
    width: int,
    height: int,
    total_frames: int,
    fps: int,
    n_vae: str,
    n_avae: str,
    start_image_ref: list[Any] | None = None,
    img_strength: float = 0.95,
) -> str:
    """Build EmptyVideo (+ optional ImgToVideoInplace) + EmptyAudio + ConcatAV.

    Returns the ConcatAV node id (NestedTensor AV latent) for SamplerCustomAdvanced.
    """
    n_empty_vid = _nid()
    wf[n_empty_vid] = {
        "class_type": "EmptyLTXVLatentVideo",
        "inputs": {
            "width": int(width),
            "height": int(height),
            "length": int(total_frames),
            "batch_size": 1,
        },
    }
    video_latent_ref: list[Any] = [n_empty_vid, 0]
    if start_image_ref is not None:
        n_inplace = _nid()
        wf[n_inplace] = {
            "class_type": "LTXVImgToVideoInplace",
            "inputs": {
                "vae": [n_vae, 0],
                "image": start_image_ref,
                "latent": [n_empty_vid, 0],
                "strength": float(img_strength),
                "bypass": False,
            },
        }
        video_latent_ref = [n_inplace, 0]

    n_empty_aud = _nid()
    wf[n_empty_aud] = {
        "class_type": "LTXVEmptyLatentAudio",
        "inputs": {
            "frames_number": int(total_frames),
            "frame_rate": float(fps),
            "batch_size": 1,
            "audio_vae": [n_avae, 0],
        },
    }
    n_concat = _nid()
    wf[n_concat] = {
        "class_type": "LTXVConcatAVLatent",
        "inputs": {
            "video_latent": video_latent_ref,
            "audio_latent": [n_empty_aud, 0],
        },
    }
    return n_concat





def _resolve_steps(fast_mode: bool) -> int:
    return ltx_25_runtime_steps(fast_mode=bool(fast_mode))


def _compute_frame_count(length_seconds: float, fps: int) -> int:
    from ..video_runtime.legal_canvas import assert_legal_duration

    return assert_legal_duration("ltx-2.5", float(length_seconds), int(fps), surface="t2v")


def _assert_ltx_25_spatial(width: int, height: int) -> tuple[int, int]:
    from ..video_runtime.legal_canvas import assert_legal_canvas

    return assert_legal_canvas("ltx-2.5", int(width), int(height))


def _named_model_exists(models_dir: Path, filename: str, *folders: str) -> bool:
    if models_dir.joinpath(filename).is_file():
        return True
    for folder in folders:
        candidate = models_dir / folder / filename
        if candidate.is_file() and candidate.stat().st_size > 0:
            return True
        nested = models_dir / folder
        if nested.is_dir():
            for found in nested.rglob(filename):
                if found.is_file() and found.stat().st_size > 0:
                    return True
    return False


def ltx_25_turbo_resource_gaps(settings: Any | None = None) -> list[str]:
    """Missing official Full UNET and/or distilled LoRA files. Empty = available."""
    if settings is None:
        from ..config import settings as app_settings

        settings = app_settings
    models = Path(getattr(settings, "comfy_models_dir", "") or "")
    gaps: list[str] = []
    unet = str(getattr(settings, "ltx_2_5_full_checkpoint", "") or LTX_25_FULL_UNET_NAME)
    if not models or not _named_model_exists(models, unet, "diffusion_models", "checkpoints"):
        gaps.append(unet)
    if not models or not _named_model_exists(models, LTX_25_TURBO_LORA_NAME, "loras"):
        gaps.append(LTX_25_TURBO_LORA_NAME)
    return gaps


def _model_after_fast_cache(
    wf: dict[str, Any],
    *,
    model_in: str,
    n_easy_cache: str,
    fast_mode: bool,
) -> str:
    """EasyCache is a Fast-path accelerator only. Quality must not insert it."""
    if not fast_mode:
        return model_in
    wf[n_easy_cache] = {
        "class_type": "EasyCache",
        "inputs": {
            "model": [model_in, 0],
            "reuse_threshold": 0.2,
            "start_percent": 0.15,
            "end_percent": 0.95,
            "verbose": False,
        },
    }
    return n_easy_cache


def _apply_turbo_lora(
    wf: dict[str, Any],
    n_unet: str,
    n_model_patch: str,
    *,
    turbo_lora: bool,
    settings: Any,
) -> None:
    if not turbo_lora:
        return
    unet_name = str(getattr(settings, "ltx_2_5_full_checkpoint", "") or LTX_25_FULL_UNET_NAME)
    current = str(wf[n_unet]["inputs"].get("unet_name") or "")
    # Never silently keep a distilled INT8 UNET when Turbo is ON.
    if "distilled" in current.lower() or "int8" in current.lower() or "convrot" in current.lower():
        wf[n_unet]["inputs"]["unet_name"] = unet_name
    elif not current:
        wf[n_unet]["inputs"]["unet_name"] = unet_name
    n_lora = _nid()
    wf[n_lora] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {
            "model": [n_unet, 0],
            "lora_name": LTX_25_TURBO_LORA_NAME,
            "strength_model": float(LTX_25_TURBO_LORA_STRENGTH),
        },
        "_meta": {"title": f"Turbo LoRA — {LTX_25_TURBO_LORA_NAME}", "adeptTurboLora": True},
    }
    wf[n_model_patch]["inputs"]["model"] = [n_lora, 0]


def build_ltx_25_t2v(
    settings: Any,
    execution_id: str,
    prompt: str,
    negative_prompt: str = "",
    width: int = 1280,
    height: int = 704,
    length_seconds: float = 121 / 24,
    fps: int = 24,
    seed: int = 0,
    generate_audio: bool = False,
    fast_mode: bool = True,
    turbo_lora: bool = False,
) -> dict[str, Any]:
    """Build a ComfyUI workflow for LTX 2.5 Text-to-Video.

    Uses the verified official topology:
      video-only: LTXVBaseSampler → LTXVTiledVAEDecode → CreateVideo → SaveVideo
      generate_audio: EmptyVideo+EmptyAudio+ConcatAV → SamplerCustomAdvanced
        → SeparateAV → TiledVAEDecode + AudioVAEDecode → CreateVideo(audio)
    """
    if generate_audio and not _ltx25_sampler_supports_av_latent():
        generate_audio = False
    steps = _resolve_steps(fast_mode)
    total_frames = _compute_frame_count(length_seconds, fps)
    width, height = _assert_ltx_25_spatial(width, height)

    n_unet = _nid()
    n_vae = _nid()
    n_clip = _nid()
    n_pos = _nid()
    n_neg = _nid()
    n_cond = _nid()
    n_model_patch = _nid()
    n_stg_apply = _nid()
    n_easy_cache = _nid()
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
    _apply_turbo_lora(wf, n_unet, n_model_patch, turbo_lora=turbo_lora, settings=settings)

    wf[n_stg_apply] = {
        "class_type": "LTXVApplySTG",
        "inputs": {
            "model": [n_model_patch, 0],
            "block_indices": "14, 19",
        },
    }

    model_for_sampler = _model_after_fast_cache(
        wf, model_in=n_stg_apply, n_easy_cache=n_easy_cache, fast_mode=fast_mode
    )

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
            "noise_seed": comfy_noise_seed(seed)
        },
    }

    wf[n_sampler] = {
        "class_type": "KSamplerSelect",
        "inputs": {"sampler_name": "euler"},
    }

    wf[n_guider] = {
        "class_type": "STGGuiderNode",
        "inputs": {
            "model": [model_for_sampler, 0],
            "positive": [n_cond, 0],
            "negative": [n_cond, 1],
            "cfg": 3.0,
            "stg": 1.0,
            "rescale": 0.7,
        },
    }

    if generate_audio:
        # Official AV topology: EmptyVideo + EmptyAudio + ConcatAV → SamplerCustomAdvanced.
        # Do NOT use LTXVBaseSampler here — live schema has no init-latents input and
        # BaseSampler always creates video-only EmptyLTXVLatentVideo internally.
        wf[n_avae] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": settings.ltx_2_5_audio_vae},
        }
        n_av_init = _wire_av_init_latents(
            wf,
            width=width,
            height=height,
            total_frames=total_frames,
            fps=fps,
            n_vae=n_vae,
            n_avae=n_avae,
            start_image_ref=None,
        )
        n_adv = n_base_sampler  # reuse id slot as the AV sampler node
        wf[n_adv] = {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [n_noise, 0],
                "guider": [n_guider, 0],
                "sampler": [n_sampler, 0],
                "sigmas": [n_sched, 0],
                "latent_image": [n_av_init, 0],
            },
        }
        wf[n_sep] = {
            "class_type": "LTXVSeparateAVLatent",
            "inputs": {"av_latent": [n_adv, 0]},
        }
        wf[n_dec_audio] = {
            "class_type": "LTXVAudioVAEDecode",
            "inputs": {
                "samples": [n_sep, 1],
                "audio_vae": [n_avae, 0],
            },
        }
        video_latent_src = [n_sep, 0]
    else:
        wf[n_base_sampler] = {
            "class_type": "LTXVBaseSampler",
            "inputs": {
                "model": [model_for_sampler, 0],
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
        video_latent_src = [n_base_sampler, 0]

    wf[n_dec_video] = {
        "class_type": "LTXVTiledVAEDecode",
        "inputs": {
            "vae": [n_vae, 0],
            "latents": video_latent_src,
            "horizontal_tiles": 2,
            "vertical_tiles": 2,
            "overlap": 2,
            "last_frame_fix": False,
        },
    }

    create_inputs: dict[str, Any] = {
        "images": [n_dec_video, 0],
        "fps": float(fps),
        "bit_depth": 8,
    }
    if generate_audio:
        create_inputs["audio"] = [n_dec_audio, 0]
    wf[n_create_video] = {
        "class_type": "CreateVideo",
        "inputs": create_inputs,
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
    middle_image_path: str = "",
    end_image_path: str = "",
    width: int = 1280,
    height: int = 704,
    length_seconds: float = 121 / 24,
    fps: int = 24,
    seed: int = 0,
    generate_audio: bool = False,
    fast_mode: bool = True,
    turbo_lora: bool = False,
) -> dict[str, Any]:
    """Build a ComfyUI workflow for LTX 2.5 Image-to-Video.

    Uses LTXVImgToVideo for image conditioning, then routes into the
    standard LTX 2.5 sampler/decode/output pipeline.
    """
    if generate_audio and not _ltx25_sampler_supports_av_latent():
        # Honesty: do not wire LTXVSeparateAVLatent on video-only BaseSampler output.
        generate_audio = False
    steps = _resolve_steps(fast_mode)
    total_frames = _compute_frame_count(length_seconds, fps)
    width, height = _assert_ltx_25_spatial(width, height)

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
    n_easy_cache = _nid()
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

    cond_images = [n_img, 0]
    cond_indices = ["0"]
    last_idx = max(0, int(total_frames) - 1)
    mid_idx = max(0, int(total_frames) // 2)
    if middle_image_path:
        n_mid = _nid()
        wf[n_mid] = {"class_type": "LoadImage", "inputs": {"image": middle_image_path}}
        n_batch_mid = _nid()
        wf[n_batch_mid] = {
            "class_type": "ImageBatch",
            "inputs": {"image1": cond_images, "image2": [n_mid, 0]},
        }
        cond_images = [n_batch_mid, 0]
        cond_indices.append(str(mid_idx))
    if end_image_path:
        n_end = _nid()
        wf[n_end] = {"class_type": "LoadImage", "inputs": {"image": end_image_path}}
        n_batch_end = _nid()
        wf[n_batch_end] = {
            "class_type": "ImageBatch",
            "inputs": {"image1": cond_images, "image2": [n_end, 0]},
        }
        cond_images = [n_batch_end, 0]
        cond_indices.append(str(last_idx))

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
    _apply_turbo_lora(wf, n_unet, n_model_patch, turbo_lora=turbo_lora, settings=settings)

    wf[n_stg_apply] = {
        "class_type": "LTXVApplySTG",
        "inputs": {
            "model": [n_model_patch, 0],
            "block_indices": "14, 19",
        },
    }

    model_for_sampler = _model_after_fast_cache(
        wf, model_in=n_stg_apply, n_easy_cache=n_easy_cache, fast_mode=fast_mode
    )

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
            "noise_seed": comfy_noise_seed(seed)
        },
    }

    wf[n_sampler] = {
        "class_type": "KSamplerSelect",
        "inputs": {"sampler_name": "euler"},
    }

    wf[n_guider] = {
        "class_type": "STGGuiderNode",
        "inputs": {
            "model": [model_for_sampler, 0],
            "positive": [n_i2v, 0],
            "negative": [n_i2v, 1],
            "cfg": 3.0,
            "stg": 1.0,
            "rescale": 0.7,
        },
    }

    n_sep = _nid() if generate_audio else None
    n_dec_audio = _nid() if generate_audio else None
    if generate_audio:
        # Official I2V AV: ImgToVideoInplace on EmptyVideo BEFORE ConcatAV so the
        # first-frame write stays on a plain video tensor (NestedTensor-safe).
        wf[n_avae] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": settings.ltx_2_5_audio_vae},
        }
        n_av_init = _wire_av_init_latents(
            wf,
            width=width,
            height=height,
            total_frames=total_frames,
            fps=fps,
            n_vae=n_vae,
            n_avae=n_avae,
            start_image_ref=[n_img, 0],
            img_strength=0.95,
        )
        n_adv = n_base_sampler
        wf[n_adv] = {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [n_noise, 0],
                "guider": [n_guider, 0],
                "sampler": [n_sampler, 0],
                "sigmas": [n_sched, 0],
                "latent_image": [n_av_init, 0],
            },
        }
        wf[n_sep] = {
            "class_type": "LTXVSeparateAVLatent",
            "inputs": {"av_latent": [n_adv, 0]},
        }
        wf[n_dec_audio] = {
            "class_type": "LTXVAudioVAEDecode",
            "inputs": {
                "samples": [n_sep, 1],
                "audio_vae": [n_avae, 0],
            },
        }
        video_latent_src = [n_sep, 0]
    else:
        wf[n_base_sampler] = {
            "class_type": "LTXVBaseSampler",
            "inputs": {
                "model": [model_for_sampler, 0],
                "vae": [n_vae, 0],
                "width": width,
                "height": height,
                "num_frames": total_frames,
                "guider": [n_guider, 0],
                "sampler": [n_sampler, 0],
                "sigmas": [n_sched, 0],
                "noise": [n_noise, 0],
                "optional_cond_images": cond_images,
                "optional_cond_indices": ", ".join(cond_indices),
                "strength": 0.95,
                "crop": "center",
            },
        }
        video_latent_src = [n_base_sampler, 0]

    wf[n_dec_video] = {
        "class_type": "LTXVTiledVAEDecode",
        "inputs": {
            "vae": [n_vae, 0],
            "latents": video_latent_src,
            "horizontal_tiles": 2,
            "vertical_tiles": 2,
            "overlap": 2,
            "last_frame_fix": False,
        },
    }

    create_inputs: dict[str, Any] = {
        "images": [n_dec_video, 0],
        "fps": float(fps),
        "bit_depth": 8,
    }
    if generate_audio:
        create_inputs["audio"] = [n_dec_audio, 0]
    wf[n_create_video] = {
        "class_type": "CreateVideo",
        "inputs": create_inputs,
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
