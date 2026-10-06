# 1 Frame I2V — Frozen Product Contract (v1.1, MCP-verified)

**Authority:** Comfy MCP live `object_info` (Comfy 0.32.0, comfy-cli 1.17.0, RTX 5090 / 32 GB). No node/loader/VAE/sampler/resolution/duration/accelerator invented from Python/JSON/memory — all from live MCP.
**Status:** CONTRACT FROZEN. Open items are model-substitute decisions resolved by live `validate_workflow` + `run_workflow` in Phase 20 (not by guessing).

## 1F creator inputs (the ONLY inputs)

| input | type | notes |
| --- | --- | --- |
| First Frame | IMAGE | the single conditioning image (1 frame) |
| Prompt | STRING | text prompt (camera note folded into prompt) |
| Generator | enum | **MiniMax H3** \| LTX 2.5 (only these two) |
| Aspect ratio | enum | 1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9 (ResolutionSelector) |
| Resolution | megapixels | via ResolutionSelector; actual /32 dims shown |
| FPS | int | 24 (MiniMax model-fixed) / 24 (LTX) |
| Duration | seconds | → model frame grid (no clamp) |
| Seed | int | -1 = random, resolved before submit; persist requested + resolved |

**Disallowed in 1F UI:** References, Character Creator, Scene selection/management, MiniMax Plan, lip sync, global prompt, duplicate Render Queue, duplicate GPU controls, left sidebar. (Enforced in Phases 17-19.)

## MiniMax H3 1F I2V contract

**Graph (core nodes only):**
LoadImage → ResolutionSelector(aspect, megapixels, **multiple=32**) → MiniMaxH3ImageToVideo(clip=Qwen3VL, vae=video_vae, prompt, width, height, length, **first_frame=image**) → EmptyMiniMaxH3LatentAV(width, height, length) → MiniMaxH3SigmaShift(model) → KSamplerSelect(res_multistep) → BasicScheduler(simple, steps, denoise) → RandomNoise(seed) → [LoraLoaderModelOnly(turbo, **CANDIDATE/bypassed**)] → sampler → VAE decode (video_vae + audio_vae) → CreateVideo(24fps) → SaveVideo.

**Hard contracts:**
- **Resolution:** width/height step 32 (min 32, max 16384). ResolutionSelector(multiple=32) → /32 dims. No silent snapping beyond /32; creator megapixels honored; actual dims shown.
- **Duration:** length = 17k+5 frames (step 17, min 5, max 3600) at 24 fps → duration = (17k+5)/24 s. **No clamp.** If requested duration doesn't map to a valid 17k+5 grid point → STOP before GPU spend, explain, offer nearest valid durations (k=4→3.04s, k=7→5.17s, k=14→10.1s, k=21→15.1s).
- **Seed:** RandomNoise(noise_seed). -1=random, resolved before submit; persist requested + resolved.
- **AV (HARD OUTPUT CONTRACT):** EmptyMiniMaxH3LatentAV = joint video+audio latent → minimax_h3_video_vae (video) + minimax_h3_audio_vae (audio) → SaveVideo with audio. **ffprobe must show video + audio streams.** No silence, no dummy track, no TTS. Native audio via the model's own audio VAE.
- **Accelerator (CANDIDATE only):** turbo 8-step LoRA `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16` (MISSING). Bypassed in base contract. Adopt only after RTX 5090 benchmark preserves quality/audio/sync.

**Models (all base installed):** `minimax_h3_fl2va_pruned_int8_convrot` (transformer), `qwen3vl_32b_minimax_h3_nvfp4_awq` (text enc), `minimax_h3_video_vae_fp16`, `minimax_h3_audio_vae_fp32`. **Base 1F I2V runnable now.**

## LTX 2.5 1F I2V contract

**Graph (core nodes only, two-stage):**
LoadImage → ResizeImageMaskNode → LTXVPreprocess → EmptyLTXVLatentVideo(width, height, length) + LTXVEmptyLatentAudio(frames_number, frame_rate, batch_size, audio_vae) → LTXVImgToVideoInplace(image, latent, strength) → CLIPTextEncode(prompt) + CLIPTextEncode(negative) → LTXVDualCFGGuider(model, pos, neg, video_cfg, audio_cfg) → KSamplerSelect(euler_ancestral) + ManualSigmas(8 steps) → stage-1 AV latent → [stage-2 OPTIONAL: LatentUpscaleModelLoader(2x) → LTXVImgToVideoInplace(strength=1) → LTXVDualCFGGuider → KSampler + ManualSigmas(4 steps)] → VAEDecodeTiled(video_vae + audio_vae) → CreateVideo(24fps) → SaveVideo.

**Hard contracts:**
- **Resolution:** EmptyLTXVLatentVideo width/height step 32 (min 64, max 16384). ResolutionSelector(multiple=32) → /32 dims. No silent snapping; actual dims shown.
- **Duration:** length = 8k frames (step 8, min 1) at 24 fps → duration = 8k/24 s. **No clamp.** If requested duration doesn't map to valid 8k grid → STOP, explain, offer nearest valid (k=12→97 frames→4.04s).
- **Seed:** RandomNoise(noise_seed). -1=random, resolved before submit; persist requested + resolved.
- **AV (HARD OUTPUT CONTRACT):** LTXVEmptyLatentAudio (audio latent) + ltx-2.5-audio-vae + LTXVDualCFGGuider(audio_cfg) → **native audio**. SaveVideo with audio. **ffprobe video + audio.** No dummy audio. (LTX 2.5 AUDIO TRUTH LAW: native audio architecture exists — preserved, not invented.)
- **Stage-2 (OPTIONAL):** 2x spatial upscaler `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0` (MISSING). Base stage-1 produces a complete AV video without it. Adopt only after benchmark.
- **Accelerator (CANDIDATE only):** LTX2MemoryEfficientSageAttentionPatch (SageAttention, available). Adopt only after benchmark.

**Models:** transformer `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot` (installed), video VAE + audio VAE (installed). **Text encoder OPEN ITEM** (below).

## Open items (resolved by live test in Phase 20, not guessing)

1. **LTX text encoder:** template names `gemma4_e2b_it_int8_convrot` (2B int8, MISSING). Installed substitutes: `gemma4_e2b_it_bf16` (2B bf16) and `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot` (12B with proj). The template uses TWO CLIPLoaders (398/393 + 398/387) — one wants the 2B int8, the other the 12B-with-proj. **Resolve by `validate_workflow` with `gemma4_e2b_it_bf16` substituting the 2B int8, then `run_workflow`; if it fails, download the int8.** (Decision belongs to Phase 20 live test, not contract freeze.)
2. **MiniMax turbo LoRA** + **LTX 2x upscaler**: accelerator/quality candidates — download only if benchmark adopts them. Base contracts do not require them.

## What is FROZEN (authoritative for all downstream phases)

- 1F inputs (above table) — nothing else.
- MiniMax H3: /32 dims, 17k+5 frames @24fps, native AV (video_vae + audio_vae), first_frame only, turbo LoRA bypassed.
- LTX 2.5: /32 dims, 8k frames @24fps, native AV (video_vae + audio_vae), first_frame via LTXVImgToVideoInplace, stage-2 upscaler optional, SageAttention candidate.
- Both: seed -1 resolved + persisted, no duration clamp, no silent resolution snapping, no dummy audio, accelerators are candidates only.
- Generator restricted to MiniMax H3 + LTX 2.5 (WAN/Hunyuan/LTX 2.3 retired from 1F per v1.1 model law).

**Contract freeze complete. Downstream phases must not invent nodes/loads/VAEs/samplers/resolutions/durations/accelerators outside this frozen contract; changes require primary approval.**
