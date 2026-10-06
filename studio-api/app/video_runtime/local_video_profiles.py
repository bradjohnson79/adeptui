"""Identities for the two local video profiles added beside Standard H3 and LTX 2.5.

Standard MiniMax H3 and LTX 2.5 keep their existing ids. Retired Hunyuan ids
stay retired. These constants are the one place the new product ids live.
"""

from __future__ import annotations

H3_STANDARD_TIMELINE_ID = "minimax-h3-i2v-local"
H3_BO_ID = "minimax-h3-base-optimized"
HUNYUAN_DISTILLED_ID = "hunyuan-video-1.5-distilled"

# Turbo LoRA is already staged. 4-step is the LoRA's training length, not the
# Timeline default: 4-step is held back until a visual pass shows audio and
# motion hold up. 6 is the fastest step count on that LoRA short of 4.
BO_LORA_NAME = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
BO_DEFAULT_STEPS = 6

# One product model. Adept picks the execution profile before Comfy is called.
# A fresh shot has no previous-ending clip, so it keeps the fast attention that
# already finishes. A continuation packs that ending clip, and the fast kernel
# locks up on this GPU before a step completes. The safe profile leaves that
# kernel off. It is still Base Optimized: same checkpoint, same LoRA, same steps.
H3_BO_FRESH_FAST = "H3_BO_FRESH_FAST"
H3_BO_CONTINUATION_SAFE = "H3_BO_CONTINUATION_SAFE"
BO_SAGE_FAST = "auto"
BO_SAGE_SAFE = "disabled"

H3_BO_FILES: tuple[tuple[str, str], ...] = (
    ("diffusion_models", "minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
    ("text_encoders", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
    ("vae", "minimax_h3_video_vae_fp16.safetensors"),
    ("vae", "minimax_h3_audio_vae_fp32.safetensors"),
    ("loras", BO_LORA_NAME),
)

HUNYUAN_FILES: tuple[tuple[str, str], ...] = (
    ("diffusion_models", "hunyuanvideo1.5_480p_t2v_cfg_distilled_fp8_scaled.safetensors"),
    ("diffusion_models", "hunyuanvideo1.5_480p_i2v_step_distilled_fp8_scaled.safetensors"),
    ("text_encoders", "qwen_2.5_vl_7b_fp8_scaled.safetensors"),
    ("text_encoders", "byt5_small_glyphxl_fp16.safetensors"),
    ("vae", "hunyuanvideo15_vae_fp16.safetensors"),
    ("clip_vision", "sigclip_vision_patch14_384.safetensors"),
)


def is_h3_base_optimized(generator_id: str | None) -> bool:
    return str(generator_id or "").strip().lower() == H3_BO_ID


def bo_execution_profile(*, has_ending_clip: bool) -> dict[str, str]:
    """Profile for one Base Optimized submit. The ending clip is the hang.

    A fresh shot does not carry that clip and stays on the fast kernel.
    Standard H3 does not use this function.
    """

    if has_ending_clip:
        return {"profile": H3_BO_CONTINUATION_SAFE, "sageAttention": BO_SAGE_SAFE}
    return {"profile": H3_BO_FRESH_FAST, "sageAttention": BO_SAGE_FAST}


def is_hunyuan_15_distilled(generator_id: str | None) -> bool:
    return str(generator_id or "").strip().lower() == HUNYUAN_DISTILLED_ID
