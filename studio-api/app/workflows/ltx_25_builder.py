"""ComfyUI workflow builders for LTX 2.5 (Text-to-Video, Image-to-Video, First/Last-Frame I2V).

LTX 2.5 uses:
  - Separate checkpoint, video VAE, audio VAE, and Gemma 4 text encoder
  - LTXV2* generation node family (T2V, I2V, FLF2V)
  - VAELoader for the video VAE (not extracted from CheckpointLoaderSimple)
  - Optional audio VAE for audio generation

Default variant: Distilled BF16
Fast mode: 8-step schedule
Quality mode: 40-step schedule
"""

from __future__ import annotations

import uuid
from typing import Any


def _nid() -> str:
    return str(uuid.uuid4().int)[:8]


def _resolve_steps(fast_mode: bool) -> int:
    return 8 if fast_mode else 40


def _resolve_cfg() -> float:
    return 3.0


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
    """Build a ComfyUI workflow for LTX 2.5 Text-to-Video."""
    steps = _resolve_steps(fast_mode)
    cfg = _resolve_cfg()
    total_frames = max(1, int(length_seconds * fps))

    n_ckpt = _nid(); n_vae = _nid(); n_te = _nid()
    n_pos = _nid(); n_neg = _nid(); n_t2v = _nid()
    n_noise = _nid(); n_sampler = _nid(); n_sched = _nid()
    n_guider = _nid(); n_custom = _nid(); n_dec = _nid(); n_combine = _nid()

    wf: dict[str, Any] = {
        n_ckpt: {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": settings.ltx_2_5_checkpoint}},
        n_vae: {"class_type": "VAELoader", "inputs": {"vae_name": settings.ltx_2_5_video_vae}},
        n_te: {"class_type": "LTXAVTextEncoderLoader", "inputs": {"text_encoder": settings.ltx_2_5_text_encoder, "ckpt_name": settings.ltx_2_5_checkpoint, "device": "default"}},
        n_pos: {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": [n_te, 0]}},
        n_neg: {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt or "", "clip": [n_te, 0]}},
        n_t2v: {"class_type": "LTXV2TextToVideo", "inputs": {"model": [n_ckpt, 0], "positive": [n_pos, 0], "negative": [n_neg, 0], "vae": [n_vae, 0], "width": width, "height": height, "length": total_frames, "batch_size": 1}},
        n_noise: {"class_type": "RandomNoise", "inputs": {"noise_seed": seed if seed >= 0 else abs(hash(prompt)) % (2**31)}},
        n_sampler: {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        n_sched: {"class_type": "BasicScheduler", "inputs": {"model": [n_t2v, 0], "scheduler": "normal", "steps": steps, "denoise": 1.0}},
        n_guider: {"class_type": "CFGGuider", "inputs": {"model": [n_t2v, 0], "positive": [n_t2v, 1], "negative": [n_t2v, 2], "cfg": cfg}},
        n_custom: {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [n_noise, 0], "guider": [n_guider, 0], "sampler": [n_sampler, 0], "sigmas": [n_sched, 0], "latent_image": [n_t2v, 3]}},
        n_dec: {"class_type": "VAEDecode", "inputs": {"samples": [n_custom, 0], "vae": [n_vae, 0]}},
        n_combine: {"class_type": "VHS_VideoCombine", "inputs": {"images": [n_dec, 0], "frame_rate": fps, "loop_count": 0, "filename_prefix": f"studio/ltx_25_t2v/{execution_id}", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }

    if generate_audio:
        n_avae = _nid(); n_sep = _nid(); n_auddec = _nid()
        wf[n_avae] = {"class_type": "VAELoader", "inputs": {"vae_name": settings.ltx_2_5_audio_vae}}
        wf[n_sep] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": [n_custom, 0]}}
        wf[n_auddec] = {"class_type": "VAEDecode", "inputs": {"samples": [n_sep, 1], "vae": [n_avae, 0]}}

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
    """Build a ComfyUI workflow for LTX 2.5 Image-to-Video."""
    steps = _resolve_steps(fast_mode)
    cfg = _resolve_cfg()
    total_frames = max(1, int(length_seconds * fps))

    n_ckpt = _nid(); n_vae = _nid(); n_te = _nid()
    n_pos = _nid(); n_neg = _nid(); n_img = _nid()
    n_i2v = _nid(); n_noise = _nid(); n_sampler = _nid()
    n_sched = _nid(); n_guider = _nid(); n_custom = _nid()
    n_dec = _nid(); n_combine = _nid()

    wf: dict[str, Any] = {
        n_ckpt: {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": settings.ltx_2_5_checkpoint}},
        n_vae: {"class_type": "VAELoader", "inputs": {"vae_name": settings.ltx_2_5_video_vae}},
        n_te: {"class_type": "LTXAVTextEncoderLoader", "inputs": {"text_encoder": settings.ltx_2_5_text_encoder, "ckpt_name": settings.ltx_2_5_checkpoint, "device": "default"}},
        n_pos: {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": [n_te, 0]}},
        n_neg: {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt or "", "clip": [n_te, 0]}},
        n_img: {"class_type": "LoadImage", "inputs": {"image": start_image_path}},
        n_i2v: {"class_type": "LTXV2ImgToVideo", "inputs": {"model": [n_ckpt, 0], "positive": [n_pos, 0], "negative": [n_neg, 0], "vae": [n_vae, 0], "image": [n_img, 0], "width": width, "height": height, "length": total_frames, "batch_size": 1, "strength": 0.95}},
        n_noise: {"class_type": "RandomNoise", "inputs": {"noise_seed": seed if seed >= 0 else abs(hash(prompt)) % (2**31)}},
        n_sampler: {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        n_sched: {"class_type": "BasicScheduler", "inputs": {"model": [n_i2v, 0], "scheduler": "normal", "steps": steps, "denoise": 1.0}},
        n_guider: {"class_type": "CFGGuider", "inputs": {"model": [n_i2v, 0], "positive": [n_i2v, 1], "negative": [n_i2v, 2], "cfg": cfg}},
        n_custom: {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [n_noise, 0], "guider": [n_guider, 0], "sampler": [n_sampler, 0], "sigmas": [n_sched, 0], "latent_image": [n_i2v, 3]}},
        n_dec: {"class_type": "VAEDecode", "inputs": {"samples": [n_custom, 0], "vae": [n_vae, 0]}},
        n_combine: {"class_type": "VHS_VideoCombine", "inputs": {"images": [n_dec, 0], "frame_rate": fps, "loop_count": 0, "filename_prefix": f"studio/ltx_25_i2v/{execution_id}", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }

    if generate_audio:
        n_avae = _nid(); n_sep = _nid(); n_auddec = _nid()
        wf[n_avae] = {"class_type": "VAELoader", "inputs": {"vae_name": settings.ltx_2_5_audio_vae}}
        wf[n_sep] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": [n_custom, 0]}}
        wf[n_auddec] = {"class_type": "VAEDecode", "inputs": {"samples": [n_sep, 1], "vae": [n_avae, 0]}}

    return wf


def build_ltx_25_flf2v(
    settings: Any,
    execution_id: str,
    prompt: str,
    negative_prompt: str = "",
    start_image_path: str = "",
    end_image_path: str = "",
    width: int = 1280,
    height: int = 720,
    length_seconds: float = 5.0,
    fps: int = 24,
    seed: int = 0,
    generate_audio: bool = True,
    fast_mode: bool = True,
) -> dict[str, Any]:
    """Build a ComfyUI workflow for LTX 2.5 First/Last-Frame Image-to-Video."""
    steps = _resolve_steps(fast_mode)
    cfg = _resolve_cfg()
    total_frames = max(1, int(length_seconds * fps))

    n_ckpt = _nid(); n_vae = _nid(); n_te = _nid()
    n_pos = _nid(); n_neg = _nid(); n_start_img = _nid()
    n_end_img = _nid(); n_flf = _nid(); n_noise = _nid()
    n_sampler = _nid(); n_sched = _nid(); n_guider = _nid()
    n_custom = _nid(); n_dec = _nid(); n_combine = _nid()

    wf: dict[str, Any] = {
        n_ckpt: {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": settings.ltx_2_5_checkpoint}},
        n_vae: {"class_type": "VAELoader", "inputs": {"vae_name": settings.ltx_2_5_video_vae}},
        n_te: {"class_type": "LTXAVTextEncoderLoader", "inputs": {"text_encoder": settings.ltx_2_5_text_encoder, "ckpt_name": settings.ltx_2_5_checkpoint, "device": "default"}},
        n_pos: {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": [n_te, 0]}},
        n_neg: {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt or "", "clip": [n_te, 0]}},
        n_start_img: {"class_type": "LoadImage", "inputs": {"image": start_image_path}},
        n_end_img: {"class_type": "LoadImage", "inputs": {"image": end_image_path}},
        n_flf: {"class_type": "LTXV2FirstLastFrameToVideo", "inputs": {"model": [n_ckpt, 0], "positive": [n_pos, 0], "negative": [n_neg, 0], "vae": [n_vae, 0], "start_image": [n_start_img, 0], "end_image": [n_end_img, 0], "width": width, "height": height, "length": total_frames, "batch_size": 1, "strength": 0.95}},
        n_noise: {"class_type": "RandomNoise", "inputs": {"noise_seed": seed if seed >= 0 else abs(hash(prompt)) % (2**31)}},
        n_sampler: {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        n_sched: {"class_type": "BasicScheduler", "inputs": {"model": [n_flf, 0], "scheduler": "normal", "steps": steps, "denoise": 1.0}},
        n_guider: {"class_type": "CFGGuider", "inputs": {"model": [n_flf, 0], "positive": [n_flf, 1], "negative": [n_flf, 2], "cfg": cfg}},
        n_custom: {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [n_noise, 0], "guider": [n_guider, 0], "sampler": [n_sampler, 0], "sigmas": [n_sched, 0], "latent_image": [n_flf, 3]}},
        n_dec: {"class_type": "VAEDecode", "inputs": {"samples": [n_custom, 0], "vae": [n_vae, 0]}},
        n_combine: {"class_type": "VHS_VideoCombine", "inputs": {"images": [n_dec, 0], "frame_rate": fps, "loop_count": 0, "filename_prefix": f"studio/ltx_25_flf2v/{execution_id}", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }

    if generate_audio:
        n_avae = _nid(); n_sep = _nid(); n_auddec = _nid()
        wf[n_avae] = {"class_type": "VAELoader", "inputs": {"vae_name": settings.ltx_2_5_audio_vae}}
        wf[n_sep] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": [n_custom, 0]}}
        wf[n_auddec] = {"class_type": "VAEDecode", "inputs": {"samples": [n_sep, 1], "vae": [n_avae, 0]}}

    return wf
