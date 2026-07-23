from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STUDIO_", env_file=".env", extra="ignore")

    app_name: str = "Adept UI Video Studio"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    comfy_url: str = "http://127.0.0.1:8188"
    comfy_input_dir: Path = Path(
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input"
    )
    comfy_output_dir: Path = Path(
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output"
    )
    default_width: int = 1280
    default_height: int = 720
    default_fps: int = 24
    ltx_checkpoint: str = "ltx-2.3-22b-distilled-fp8.safetensors"
    wan_high_noise: str = "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
    wan_low_noise: str = "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"
    wan_vae: str = "WanVideo/Wan2_1_VAE_bf16.safetensors"
    wan_text_encoder: str = "umt5-xxl-enc-bf16.safetensors"
    poll_interval_sec: float = 1.5
    job_timeout_sec: float = 3600.0
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:12b"
    ollama_timeout_sec: float = 180.0
    zimage_unet: str = "z_image_turbo_bf16.safetensors"
    zimage_clip: str = "qwen_3_4b.safetensors"
    zimage_vae: str = "ae.safetensors"
    zimage_clip_vision: str = "clip_vision_h.safetensors"
    zimage_steps: int = 8
    zimage_cfg: float = 1.0
    zimage_size: int = 1024


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "assets").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "exports").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "projects").mkdir(parents=True, exist_ok=True)
