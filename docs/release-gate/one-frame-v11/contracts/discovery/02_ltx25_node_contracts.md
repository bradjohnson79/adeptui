# LTX 2.5 1F I2V — Node Contracts (live object_info)

From `nodes get` on live Comfy :8188 (pack: core for all).

## LTXVImgToVideoInplace (model/conditioning/ltxv, core)

The I2V conditioning — injects the First Frame image into the video latent.

| input | type | required | min | max | step | default | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vae | VAE | yes | - | - | - | - | `ltx-2.5-video-vae-bf16` (video VAE) |
| image | IMAGE | yes | - | - | - | - | **THE 1 FRAME INPUT** (First Frame) |
| latent | LATENT | yes | - | - | - | - | from EmptyLTXVLatentVideo |
| strength | FLOAT | yes | 0.0 | 1.0 | - | 1.0 | stage-1=0.7, stage-2=1.0 in template |
| bypass | BOOLEAN | yes | - | - | - | false | |

Output: `LATENT`.

## EmptyLTXVLatentVideo (model/latent/ltxv, core)

Video latent. **/32 dims, length step 8.**

| input | type | required | min | max | step | default |
| --- | --- | --- | --- | --- | --- | --- |
| width | INT | yes | 64 | 16384 | **32** | 768 |
| height | INT | yes | 64 | 16384 | **32** | 512 |
| length | INT | yes | 1 | 16384 | **8** | 97 |
| batch_size | INT | yes | 1 | 4096 | - | 1 |

**Duration contract:** length = 8k frames at 24 fps → duration = 8k/24 s. k=12 → 97 frames → 4.04 s. (step 8, not 17 like MiniMax.)

## LTXVEmptyLatentAudio (model/latent/ltxv, core)

**Separate audio latent → native audio.**

| input | type | required | min | max | step | default |
| --- | --- | --- | --- | --- | --- | --- |
| frames_number | INT | yes | 1 | 1000 | 1 | 97 |
| frame_rate | FLOAT,INT | yes | 1.0 | 1000.0 | 0.01 | 25.0 |
| batch_size | INT | yes | 1 | 4096 | - | 1 |
| audio_vae | VAE | yes | - | - | - | - | `ltx-2.5-audio-vae-bf16` |

Output: `LATENT` (audio). Template: frames_number=97, batch_size=25.

## LTXVDualCFGGuider (model/sampling/guiders, core)

"Separate CFG scales for the video and audio modalities of a packed LTXV-AV latent." → **joint AV generation confirmed.**

| input | type | required | min | max | step | default |
| --- | --- | --- | --- | --- | --- | --- |
| model | MODEL | yes | - | - | - | - |
| positive | CONDITIONING | yes | - | - | - | - |
| negative | CONDITIONING | yes | - | - | - | - |
| video_cfg | FLOAT | yes | 0.0 | 100.0 | 0.1 | 3.0 |
| audio_cfg | FLOAT | yes | 0.0 | 100.0 | 0.1 | 7.0 |

Output: `GUIDER`. Template uses video_cfg=1, audio_cfg=1.

## LTX 2.5 1F I2V — frozen contract (provisional)

- **Inputs (creator):** First Frame image, prompt, generator=LTX 2.5, aspect_ratio (8 options), resolution (megapixels), fps=24, duration (→ length=8k), seed, camera note (in prompt).
- **Resolution:** ResolutionSelector(aspect_ratio, megapixels, multiple=32) → /32 width/height (EmptyLTXVLatentVideo width/height step 32). No silent snapping beyond /32.
- **Duration:** creator seconds → length = 8k (step 8) at 24 fps. No clamp. If requested duration doesn't map to valid 8k grid → STOP, explain, offer nearest valid.
- **AV (hard contract):** LTXVEmptyLatentAudio (audio latent) + ltx-2.5-audio-vae + LTXVDualCFGGuider(audio_cfg) → **native audio**. SaveVideo with audio. ffprobe video+audio. **No dummy audio.**
- **Two-stage:** stage-1 base (8 steps, ManualSigmas) → stage-2 2x spatial upscaler (4 steps, OPTIONAL — upscaler model `ltx-2.5-latent-spatial-upscaler-x2-bf16` MISSING). Base stage-1 produces a complete AV video without stage-2.
- **Text encoder:** gemma4. Template wants `gemma4_e2b_it_int8_convrot` (2B, MISSING); `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot` (12B, INSTALLED) is the closest. **Open item:** confirm substitute validity or download 2B.
- **Prompt expansion:** TextGenerateLTX2Prompt (LLM, optional) — can be bypassed with a direct CLIPTextEncode prompt.
- **Accelerator (CANDIDATE only):** LTX2MemoryEfficientSageAttentionPatch (SageAttention) — available; benchmark before adopting.
- **Models installed:** transformer `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot`, video VAE, audio VAE, one gemma4 encoder. **Base stage-1 1F I2V runnable** once text-encoder substitute confirmed; stage-2 upscaler optional.

## LTX 2.5 AUDIO TRUTH LAW — RESOLVED

LTX 2.5 has full native audio: `LTXVEmptyLatentAudio` + `ltx-2.5-audio-vae-bf16` (installed) + `LTXVDualCFGGuider.audio_cfg` + `LTX2AudioLatentNormalizingSampling` (available). **The AV hard output contract is satisfied by native audio — no dummy audio, no silence, no TTS.**
