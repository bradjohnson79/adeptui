# MiniMax H3 1F I2V — Node Contracts (live object_info)

From `nodes get` on live Comfy :8188 (pack: core for all).

## MiniMaxH3ImageToVideo (model/conditioning/minimax, core)

The 1F I2V conditioning node. Outputs `positive` (CONDITIONING) + `LATENT`.

| input | type | required | min | max | step | default | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| clip | CLIP | yes | - | - | - | - | Qwen3VL 32B (`qwen3vl_32b_minimax_h3_nvfp4_awq`), CLIPLoader type=`minimax` |
| vae | VAE | yes | - | - | - | - | `minimax_h3_video_vae_fp16` (video VAE) |
| prompt | STRING | yes | - | - | - | - | text prompt |
| width | INT | yes | 32 | 16384 | **32** | 1344 | **must be /32** |
| height | INT | yes | 32 | 16384 | **32** | 768 | **must be /32** |
| length | INT | yes | 5 | 3600 | **17** | 124 | **17k+5 frame grid** (k=4→73, k=7→124) |
| first_frame | IMAGE | no | - | - | - | - | **THE 1 FRAME INPUT** (First Frame image) |
| last_frame | IMAGE | no | - | - | - | - | for FLF2V only; omit for 1F |

**Duration contract:** length = 17k+5 frames at 24 fps → duration = (17k+5)/24 s.
- k=4 → 73 frames → 3.04 s
- k=7 → 124 frames → 5.17 s (default)
- k=14 → 243 frames → 10.1 s
- k=21 → 362 frames → 15.1 s (max practical ≈ 3600 cap → k≤211)

**1F wiring:** `first_frame` = creator's First Frame image; `last_frame` = none.

## EmptyMiniMaxH3LatentAV (model/latent/minimax, core)

Joint video+audio latent. "Duration snaps to the model's 17k+5 frame grid at 24 fps."

| input | type | required | min | max | step | default |
| --- | --- | --- | --- | --- | --- | --- |
| width | INT | yes | 32 | 16384 | **32** | 1344 |
| height | INT | yes | 32 | 16384 | **32** | 768 |
| length | INT | yes | 5 | 3600 | **17** | 124 |

Output: `LATENT` (joint AV — video + audio in one latent). **Native audio confirmed.**

## ResolutionSelector (utilities, core)

Legal-size authority. Computes width+height from aspect ratio + megapixels, snapped to `multiple`.

| input | type | required | choices/options | default |
| --- | --- | --- | --- | --- |
| aspect_ratio | COMBO | yes | 1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9 | 1:1 |
| megapixels | FLOAT | yes | 0.1–16.0 (step 0.1) | 1.0 |
| multiple | INT | yes | 8–128 (step 4) | 8 |

Outputs: `width` (INT), `height` (INT). **For MiniMax H3: `multiple=32`** (matches width/height step 32). Template uses megapixels=0.4 (1:1) for base.

## MiniMax H3 1F I2V — frozen contract (provisional)

- **Inputs (creator):** First Frame image, prompt, generator=MiniMax H3, aspect_ratio (8 options), resolution (megapixels), fps=24 (fixed by model), duration (→ length=17k+5), seed, camera note (in prompt).
- **Resolution:** ResolutionSelector(aspect_ratio, megapixels, multiple=32) → /32 width/height. No silent snapping beyond /32; creator megapixels honored.
- **Duration:** creator seconds → length = 17k+5 (step 17). No clamp. If requested duration doesn't map to a valid 17k+5 grid point → STOP, explain, offer nearest valid durations.
- **Seed:** RandomNoise(noise_seed). -1 = random, resolved before submit; persist requested + resolved.
- **AV (hard contract):** EmptyMiniMaxH3LatentAV (joint video+audio) → minimax_h3_video_vae (video) + minimax_h3_audio_vae (audio) → SaveVideo with audio. ffprobe must show video + audio streams.
- **Accelerator (CANDIDATE only):** turbo 8-step LoRA (`minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16`) — NOT installed; bypass for base contract; benchmark before adopting.
- **Models installed:** transformer `minimax_h3_fl2va_pruned_int8_convrot`, video VAE, audio VAE, Qwen3VL text encoder. **Base 1F I2V runnable now** (turbo LoRA bypassed).
