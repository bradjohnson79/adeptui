from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STUDIO_", env_file=".env", extra="ignore")

    app_name: str = "Adept UI Studio"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    comfy_url: str = "http://127.0.0.1:8188"
    comfy_input_dir: Path = Path(
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input"
    )
    comfy_output_dir: Path = Path(
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output"
    )
    comfy_models_dir: Path = Path(
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models"
    )
    default_width: int = 1280
    default_height: int = 720
    default_fps: int = 24
    ltx_checkpoint: str = "ltx-2.3-22b-distilled-fp8.safetensors"
    # LTX 2.3 CheckpointLoaderSimple returns CLIP=None; load Gemma/LTX text encoder separately.
    ltx_text_encoder: str = "gemma_3_12B_it_fp4_mixed.safetensors"
    # LTX 2.5
    ltx_2_5_checkpoint: str = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
    ltx_2_5_text_encoder: str = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
    ltx_2_5_video_vae: str = "ltx-2.5-video-vae-bf16.safetensors"
    ltx_2_5_audio_vae: str = "ltx-2.5-audio-vae-bf16.safetensors"
    ltx_2_5_spatial_upscaler: str = "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
    wan_high_noise: str = "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
    wan_low_noise: str = "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"
    # Comfy VAELoader lists subdirectory names with backslashes on Windows.
    wan_vae: str = r"WanVideo\Wan2_1_VAE_bf16.safetensors"
    # Comfy-Org WAN repackaged encoder (4096-dim). The older umt5-xxl-enc-bf16
    # variant can load under type=wan but emit 768-dim embeddings and break sampling.
    wan_text_encoder: str = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    poll_interval_sec: float = 1.5
    job_timeout_sec: float = 3600.0
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:31b-it-qat"
    ollama_timeout_sec: float = 180.0
    zimage_unet: str = "z_image_turbo_bf16.safetensors"
    zimage_clip: str = "qwen_3_4b.safetensors"
    zimage_vae: str = "ae.safetensors"
    zimage_clip_vision: str = "clip_vision_h.safetensors"
    zimage_steps: int = 8
    zimage_cfg: float = 1.0
    zimage_size: int = 1024
    qwen_image_2512_unet: str = "qwen_image_2512_fp8_e4m3fn.safetensors"
    qwen_image_2512_clip: str = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
    qwen_image_2512_vae: str = "qwen_image_vae.safetensors"
    qwen_image_2512_steps: int = 50
    qwen_image_2512_cfg: float = 4.0
    qwen_image_2512_size: int = 1328
    qwen_image_2512_sampler: str = "euler"
    qwen_image_2512_scheduler: str = "simple"
    qwen_image_2512_shift: float = 1.73
    # Krea 2 still-image family (HF krea/Krea-2-Turbo + krea/Krea-2-Raw — gated repos
    # under the Krea 2 Community License; weights are linked, never auto-downloaded).
    # Authoritative root is the shared Model Storage image root, NOT the ComfyUI shared
    # models dir. Official checkpoint filenames are turbo.safetensors / raw.safetensors;
    # Comfy-Org repack (e.g. FP8) filenames are discovered at install time, so the
    # encoder/VAE defaults stay empty and the krea2_files verifier pattern-matches them
    # under the Krea 2 root. Any value can be overridden (absolute path accepted) via
    # the STUDIO_KREA2_* env vars.
    krea2_model_root: str = r"D:\01_Models\krea2"
    krea2_turbo_checkpoint: str = "turbo.safetensors"
    krea2_raw_checkpoint: str = "raw.safetensors"
    krea2_text_encoder: str = ""
    krea2_vae: str = ""
    # Reference-conditioning support weights (Phase C): CLIP vision encoder +
    # IPAdapter model consumed by the Krea 2 reference graph wiring. Empty =
    # not configured; filenames are discovered at install time (same gated /
    # manual-link pattern as the checkpoints above). LoRA files resolve from
    # krea2_model_root/loras (see image_runtime/asset_refs.py).
    krea2_clip_vision: str = ""
    krea2_ipadapter: str = ""
    # Official recommended inference settings (verified 2026-08-08; consumed by Phase B
    # workflow builders — Turbo is distilled: 8 steps, CFG disabled, constant mu=1.15).
    krea2_turbo_steps: int = 8
    krea2_turbo_cfg: float = 0.0
    krea2_turbo_mu: float = 1.15
    krea2_raw_steps: int = 52
    krea2_raw_cfg: float = 3.5
    # ImageGen checkpoints (model-agnostic Comfy path; override via STUDIO_* env)
    imagegen_flux_checkpoint: str = "flux1-kontext-dev.safetensors"
    imagegen_flux_clip_l: str = "clip_l.safetensors"
    imagegen_flux_t5: str = "t5xxl_fp16.safetensors"
    imagegen_flux_vae: str = "ae.safetensors"
    imagegen_flux_steps: int = 20
    imagegen_flux_cfg: float = 1.0
    imagegen_hidream_checkpoint: str = "hidream_i1_dev_fp8.safetensors"
    imagegen_sd35_checkpoint: str = "sd3.5_large.safetensors"
    imagegen_custom_checkpoint: str = ""
    # Illustrious XL v1.0 — SDXL anime/animation/stylized/realistic-anime engine.
    imagegen_illustrious_checkpoint: str = "Illustrious-XL-v1.0.safetensors"
    imagegen_illustrious_steps: int = 28
    imagegen_illustrious_cfg: float = 5.0
    imagegen_default_steps: int = 20
    imagegen_default_cfg: float = 3.5

    # MiniMax H3 — Private owner-only Route A integration. Public creator / Best
    # Match / general routing stay disabled by default. The isolated Route A
    # ComfyUI lives on 127.0.0.1:8192 and must never be confused with the
    # production Comfy on :8188.
    minimax_h3_owner_only: bool = True
    minimax_h3_public_creator_enabled: bool = False
    minimax_h3_best_match_enabled: bool = False
    minimax_h3_general_routing_enabled: bool = False
    minimax_h3_runtime_url: str = "http://127.0.0.1:8192"
    minimax_h3_model_root: str = r"D:\01_Models"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "assets").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "exports").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "projects").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "marketplace").mkdir(parents=True, exist_ok=True)
