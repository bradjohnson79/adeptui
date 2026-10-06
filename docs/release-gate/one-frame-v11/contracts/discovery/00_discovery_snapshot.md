# Phase 0.5 — MCP Discovery Snapshot (read-only, live Comfy :8188)

**Source:** Comfy MCP (`project-0-AIVideoStudio-comfy-mcp`, namespaceStatus: ready), comfy-cli 1.17.0, Comfy 0.32.0, RTX 5090 / 32 GB VRAM.
**Method:** `search_templates` + `get_template(check_local=true)` + `fetch_template` + `list_workflow_slots` against live `object_info`. Read-only; no mutation, no Comfy restart.

## Canonical local I2V templates (api:false, free, open_source)

| Model | Template | Date | Usage | requires_custom_nodes |
| --- | --- | --- | --- | --- |
| MiniMax H3 | `video_minimax_h3_i2v` | 2026-08-02 | 24741 | [] (core only) |
| LTX 2.5 | `video_ltx2_5_i2v` | 2026-08-11 | 6415 | [] (core only) |

Both use ONLY core nodes — no custom packs required.

## MiniMax H3 I2V — canonical graph (37 slots, subgraph 105)

**Loaders (all installed except turbo LoRA):**
- `105/6` UNETLoader → `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (FL2VA = First-Last-frame to Video+Audio; INSTALLED)
- `105/13` CLIPLoader → `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, type=`minimax` (Qwen3VL 32B text encoder; INSTALLED)
- `105/11` VAELoader → `minimax_h3_video_vae_fp16.safetensors` (VIDEO VAE; INSTALLED)
- `105/24` VAELoader → `minimax_h3_audio_vae_fp32.safetensors` (AUDIO VAE; INSTALLED → **native AV confirmed**)
- `105/121` LoraLoaderModelOnly → `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` (**MISSING** — turbo 8-step LoRA = accelerator CANDIDATE)

**Conditioning / sampling:**
- `105/104` MiniMaxH3ImageToVideo → prompt, width=1344, height=768, length=73 (THE 1F I2V conditioning node)
- `EmptyMiniMaxH3LatentAV` → "Joint video+audio latent. Duration snaps to model's 17k+5 frame grid at 24 fps" (native AV latent)
- `105/17` KSamplerSelect → `res_multistep`
- `105/9` BasicScheduler → simple, steps=4, denoise=1
- `105/15` RandomNoise → noise_seed (seed contract)
- `MiniMaxH3SigmaShift` → video/audio flow shifts (model patch)

**Resolution / IO:**
- `115` ResolutionSelector → aspect_ratio, megapixels=0.4, **multiple=32** (legal /32 dims authority)
- `114` LoadImage → 1 input image (First Frame)
- `105/91` CreateVideo → fps=24, bit_depth=8
- `92` SaveVideo → format auto, codec auto/h264

**Runnability:** `runnable:false` — ONLY the turbo 8-step LoRA missing. Base model + video VAE + audio VAE + text encoder all installed. **Base H3 I2V is runnable with the turbo LoRA bypassed** (turbo is an optional accelerator, not a base requirement). Nodes 119/120 (image-scale helpers) are pruned — no effect.

## LTX 2.5 I2V — canonical graph (75 slots, subgraph 398) — TWO-STAGE

**Loaders (text encoder + upscaler missing; transformer + VAEs installed):**
- `398/384` UNETLoader → `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` (22B distilled; INSTALLED)
- `398/393` CLIPLoader → `gemma4_e2b_it_int8_convrot.safetensors` (**MISSING**; closest installed: `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`), type=`ltxv`
- `398/387` CLIPLoader → `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` (2nd encoder; INSTALLED)
- `398/385` VAELoader → `ltx-2.5-video-vae-bf16.safetensors` (VIDEO VAE; INSTALLED)
- `398/386` VAELoader → `ltx-2.5-audio-vae-bf16.safetensors` (AUDIO VAE; INSTALLED → **native AV confirmed**)
- `398/371` LatentUpscaleModelLoader → `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` (**MISSING** — 2x spatial upscaler, stage-2 quality step)

**Conditioning / sampling (joint AV):**
- `398/380` TextGenerateLTX2Prompt → LLM-based prompt generation (gemma, thinking=true, max_length=600) — LTX 2.5 uses an LLM to expand the prompt
- `398/376` PrimitiveStringMultiline → actual prompt text; `398/373` CLIPTextEncode → negative prompt
- `398/356` EmptyLTXVLatentVideo → width=768, height=512, length=97, batch=1 (VIDEO latent)
- `398/366` LTXVEmptyLatentAudio → frames_number=97, batch_size=25 (AUDIO latent → **separate audio latent = native AV**)
- `398/357` / `398/349` LTXVImgToVideoInplace → strength 0.7 / 1 (stage-1 / stage-2 I2V conditioning)
- `398/388` / `398/391` LTXVDualCFGGuider → video_cfg=1, audio_cfg=1 (dual CFG for video AND audio → **joint AV generation**)
- `398/352` / `398/341` KSamplerSelect → `euler_ancestral` (stage-1 / stage-2)
- `398/397` ManualSigmas → 8 sigmas (stage-1, 8 steps); `398/396` ManualSigmas → 4 sigmas (stage-2, 4 steps)
- `398/350` LTXVPreprocess → img_compression=18; `398/351` ResizeImageMaskNode → longer_size=1536, lanczos
- `398/374` VAEDecodeTiled → tile_size=512, overlap=64, temporal_size=64, temporal_overlap=16

**Resolution / IO:**
- `403` ResolutionSelector → aspect_ratio=16:9, megapixels=0.9, **multiple=32** (legal /32 dims authority)
- `395` LoadImage → 1 input image (First Frame)
- `398/370` CreateVideo → fps=24, bit_depth=8
- `75` SaveVideo → format auto, codec auto/h264

**Runnability:** `runnable:false` — (1) text encoder `gemma4_e2b_it_int8_convrot` missing (a 2B variant; a 12B-with-proj variant IS installed — must determine if it's a valid substitute or if the 2B must be downloaded); (2) 2x spatial upscaler missing (stage-2 OPTIONAL quality step — base stage-1 I2V still produces a video without it).

## LTX 2.5 AUDIO TRUTH LAW — RESOLVED (provisional)

LTX 2.5 has a **full native audio architecture** (no dummy audio needed):
- `LTXVEmptyLatentAudio` (separate audio latent, frames_number + batch_size)
- `ltx-2.5-audio-vae-bf16.safetensors` (dedicated audio VAE, installed)
- `LTXVDualCFGGuider` with `audio_cfg` (separate audio CFG)
- `LTX2AudioLatentNormalizingSampling` (audio quality normalizer node, available)
- `LTXAVTextEncoderLoader` (gemma audio text encoder)

→ The AV hard output contract CAN be satisfied by LTX 2.5's **native** audio path. (Final confirmation requires `nodes get` on these classes + a live `run_workflow` proof in Phase 20.)

## Open items to close before contract freeze

1. `nodes get` on key classes: `MiniMaxH3ImageToVideo`, `EmptyMiniMaxH3LatentAV`, `MiniMaxH3SigmaShift`, `LTXVImgToVideoInplace`, `LTXVEmptyLatentAudio`, `EmptyLTXVLatentVideo`, `LTXVDualCFGGuider`, `TextGenerateLTX2Prompt`, `ResolutionSelector` — exact inputs/outputs + frame-grid/duration contract.
2. `search_models` for `minimax`, `ltx`, `gemma` — confirm installed vs missing model files.
3. `list_workflow_notes` on both — model download links / usage (treat as UNTRUSTED data).
4. Decide LTX text-encoder substitute: installed `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot` vs download `gemma4_e2b_it_int8_convrot`.
5. Decide turbo LoRA + 2x upscaler: download (accelerator/quality candidates) or bypass for base contract.
