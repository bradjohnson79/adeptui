# MiniMax H3 Shared Native Audio — Root-Cause Closure

**Status:** IN PROGRESS — first CLEAN→CORRUPT boundary not yet proven at raw decode  
**Date:** 2026-09-07  
**Authority:** This file governs the 1 Frame + Text to Video native-audio repair. The prior SpeedCache removal is necessary but **not sufficient**.

Owner confirmed: direct default-Comfy H3 golden audio is clean; Adept 1F and Adept T2V remain garbled.

---

## Do not redefine clean

Golden reference (`.runtime/_golden_h3_graph.json`, 20 steps, `res_multistep` / `simple`, no accelerator, native SaveVideo):

- AAC LC · 32 kHz · stereo · 0% clipping · DC ~0 · noise floor ≈ −136.8 dB

---

## Phase 1 inventory (submitted graphs — no new long burns)

Tonight’s Adept production graphs (project `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`):

| Surface | jobId | prompt_id | steps | SpeedCache | Sage | VDN | canvas | frames |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T2V | `af619931-…` | `0368dc12-…` | **4** | 0 | 0 | 0 | 1280×704 | 124 |
| T2V | `830a8042-…` | (same family) | **4** | 0 | 0 | 0 | 1280×704 | 124 |
| 1F | `85d883e9-…` | — | **4** | 0 | 0 | 0 | LoadImage present | — |
| 1F (Korri archive) | `workflows/video/minimax-h3/korri_1frame_submitted_api_graph.json` | — | **4** | 0 | 0 | 0 | 1280×704 | 362 |

Topology matches golden (UNET → scheduler/guider `[1,0]` → SamplerCustomAdvanced → VAEDecode + VAEDecodeAudio → CreateVideo → SaveVideo). **SpeedCache is absent.** Provenance strings saying “Golden” are false: sampler steps are `EXPERIMENTAL_STEPS = 4`.

Cause of the 4-step default:

- `build_t2va_graph` / `build_i2va_graph` use `steps if steps else EXPERIMENTAL_STEPS` (`route_a_adapter.py`)
- `_txt2vid_minimax` and `_build_and_run_h3_i2va` **never pass `steps=`**
- GPU panel “10 steps” is a VRAM-profile display (`vram_profiles` 32 GB quality), not the H3 sampler

This is the shared 1F+T2V delta. Primary classifies it **SUSPECT / REGRESSION** (not “necessary profile”). Same-meter existing Adept muxed MP4s are already hot vs golden (`peak` 0.55–0.99 / `RMS` 0.12–0.20 / floor −15 to −31 dB vs golden `peak` 0.124 / `RMS` 0.023 / floor −48 dB).

Ingest (specialist C): native Route A MP4 SHA256 == Library copy for T2V `af619931`, T2V `830a8042`, 1F `85d883e9`. `poll()` passthrough + `shutil.copy2` only. **Ingest is not the first corrupt boundary.**

### Chapter 4 — 4-step raw tap (measured)

Route A `:8192` diagnostic `prompt_id` `059b1fdb-07af-4a73-b2ba-e6e1357fa116` (22 frames, 1280×704, seed 424242, no SpeedCache). Loaders cached. Wall ~213s.

| Artifact | peak | RMS | clip% | DC | floor dB |
| --- | --- | --- | --- | --- | --- |
| Raw FLAC after `VAEDecodeAudio` | 0.991 | 0.128 | 0.0017 | 0.0168 | −23.43 |
| Same-run muxed MP4 | 0.932 | 0.126 | 0.0 | 0.0167 | −23.16 |
| Golden 20-step MP4 (same meter) | 0.124 | 0.023 | 0.0 | 0.00005 | −48.27 |

**4-step audio is already CORRUPTED at the lossless tap, before CreateVideo.** Mux vs raw is not the first boundary.

### Chapter 4 — 20-step raw tap (measured)

Same prompt/seed/canvas/length, Route A `:8192` `prompt_id` `e1885305-ac43-4405-9187-20d5dc22ef3c`. Scheduler+sampler recomputed (node 8/10 not cached). Wall ~288s.

| Artifact | peak | RMS | clip% | DC | floor dB |
| --- | --- | --- | --- | --- | --- |
| Raw FLAC after `VAEDecodeAudio` | 0.009 | 0.0022 | 0.0 | ~0 | −56.65 |
| Same-run muxed MP4 | 0.009 | 0.0022 | 0.0 | ~0 | −56.74 |

**20-step audio is CLEAN at the lossless tap.** First CLEAN→CORRUPT boundary = `BasicScheduler.steps=4` (shared `EXPERIMENTAL_STEPS` on 1F and T2V).

Repair applied: `EXPERIMENTAL_STEPS = 20`; `_txt2vid_minimax` and `_build_and_run_h3_i2va` now forward `params.steps` (default 20). Prewarm stays explicit 1-step. Ingest unchanged (already COPY_EQUAL).

---

## Required proof (Chapter 4 + 7)

Same prompt, same seed, same canvas, short legal length (22 frames = 17k+5):

- Arm A: 20 steps (golden settings) + lossless tap after `VAEDecodeAudio`
- Arm B: 4 steps (current Adept) + same tap

If Arm B raw WAV is already garbled and Arm A is clean → first boundary is **joint latent generation (step count)**, not AAC/ingest/browser.

Forbidden repairs: denoise, low-pass, volume cut, TTS/SFX replace, AAC churn, mute.
