# M3.2a — Open Source Capability Acquisition Notes

| Tool | Selected | License | Integration | Notes |
|---|---|---|---|---|
| Image Upscaler | RealESRGAN / SeedVR2 image (batch_size=1) | BSD/Apache | Comfy `ImageUpscaleWithModel` or SeedVR2 | Replaces img2img stub |
| Video Upscaler | [ComfyUI-SeedVR2_VideoUpscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler) | Apache-2.0 | Comfy custom node | Temporal; not ESRGAN-per-frame |
| Background Remover | BiRefNet (Comfy native / ZhengPeng7) | MIT | Comfy Remove Background | Prefer MIT over GPL RMBG packs |
| Chroma key | OpenCV / Pillow local | — | `generation_tools.ops.run_chroma_key` | Spill + edge feather |
| Portrait Skin | CodeFormer / GFPGAN | Apache/non-commercial check per weights | Comfy face restore nodes | Identity fidelity default |
| Music | ACE-Step (existing m210b) | project license | Audio Studio + Library | Sandbox flags |
| SFX | MMAudio (existing m210b) | project license | Audio Studio + Library | Sandbox flags |
| Video Extender | WAN/LTX I2V continuation | existing | `video.extend` job | Labeled generative continuation |
| De-Lighting | **BLOCKED** | — | — | No production-ready OSS certified; color grade ≠ de-lighting |
| Brand Studio | Adept module + ref-locked ImageGen | — | Brand Studio workspace | Locked logos/wording metadata |

## Install hints (operator)

1. Update ComfyUI; place BiRefNet weights under `models/background_removal/`.
2. Install SeedVR2 custom node + HF weights for video upscale.
3. Enable `STUDIO_FEATURE_AUDIO_PRODUCTION_V1` + `STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1` for music/SFX.
4. Never enable silent paid cloud paths for these tools.
