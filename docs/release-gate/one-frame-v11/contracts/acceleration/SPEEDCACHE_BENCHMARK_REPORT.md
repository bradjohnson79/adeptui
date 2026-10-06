# MiniMax H3 1 Frame Accelerator Benchmark — Speed Cache vs SageAttention

**Status:** COMPLETE — Comfy MCP-verified, live-generated, ffprobe-verified, visually verified
**Date:** 2026-09-05
**Baseline:** Korri 1F I2V (`korri_1frame_submitted_api_graph.json`), 4-step `res_multistep`, 1280×704, 362 frames (15.08s @ 24fps), seed 3294228055, first frame `studio/h3_i2v_e86917d7.png`
**Comfy MCP:** `project-0-AIVideoStudio-comfy-mcp` (39 tools, `:8188` local)
**Custom node:** `comfyui-speed-minimaxH3` (`linjian-ufo/comfyui-speed-minimaxH3`) — `MiniMaxH3SpeedCache` node, MCP-verified contract, installed in `custom_nodes/`
**Patch applied:** `minimax_patch.py:340` `time_shift_slope` → `time_shift_sigma` (ComfyUI v0.34.5 API compat; author already applied same fix at line 152)

---

## VERDICT

**MiniMax H3 1 Frame Certified Accelerator = SageAttention**
(delivered via `MiniMaxH3SpeedCache` node configured with `reuse_threshold=0.0` (cache DISABLED) + `sage_attention="auto"`)

- ✅ Measurable speed gain: **2.14x** (avg 161.9s vs 347.15s baseline)
- ✅ No visual quality regression: **CLEAN** (no echo/ripple/ghosting artifacts)
- ✅ Native AV intact: h264 1280×704 362f 15.08s + aac stereo 32kHz 15.075s (ffprobe-verified, identical to baseline)
- ✅ Repeated-run stability: 162.22s / 161.61s (0.4% variance)

**Speed Cache (the caching feature itself) = NO-GO at 4-step distilled sampling.**
The cache's residual-reuse mechanism causes severe visual regression (echoing/ghosting/ripple) on the 4-step Korri baseline, confirmed across default AND quality-first profiles. Root cause: 4-step distilled sampling makes large per-step changes, so reusing a prior step's residual is a poor approximation. The cache is designed for longer sampling trajectories (README: validated during continuous long-video generation with ~20 steps), not 4-step distilled runs.

---

## Benchmark table (identical Korri test across all arms)

| Arm | Config | Total time | Speedup | Cache skips | Visual (f181) | AV |
|-----|--------|-----------|---------|-------------|---------------|----|
| Baseline | no cache, no sage | 347.15s | 1.00x | 0/4 | CLEAN ✅ | intact ✅ |
| Arm A | cache (default 0.12), sage disabled | 272.67s | 1.27x | 1/4 | **SEVERE artifacts** ❌ | intact ✅ |
| Arm B | cache (default 0.12) + sage auto | 136.11s | 2.55x | 1/4 | **SEVERE artifacts** ❌ | intact ✅ |
| QFirst+Sage | cache (0.08 qfirst) + sage auto | 132.89s | 2.61x | 1/4 | **SEVERE artifacts** ❌ | intact ✅ |
| **SageOnly v1** | **cache disabled (0.0) + sage auto** | **162.22s** | **2.14x** | **0/4 (all RUN)** | **CLEAN** ✅ | **intact** ✅ |
| **SageOnly v2** | **cache disabled (0.0) + sage auto** | **161.61s** | **2.15x** | **0/4 (all RUN)** | **CLEAN** ✅ | **intact** ✅ |

Identical across all arms: first frame, prompt, seed (3294228055), resolution (1280×704), length (362f), FPS (24), sampler (`res_multistep`), steps (4), AV decode path (Video VAE + Audio VAE).

---

## Per-step timing (sage backend)

SageOnly steps: 28.93s / 29.01s / 29.22s / final — vs baseline ~70s/step. SageAttention gives ~2.4x per-step speedup as a non-cache attention backend optimization (no residual reuse → no echo artifacts).

## Root cause of cache regression

`MiniMaxH3SpeedCache` reuses transformer-block residuals across sampling steps when the accumulated `rel_l1` signature is below `reuse_threshold`. On the 4-step Korri baseline:
- Step 1: RUN (init)
- Step 2: SKIP (accumulated 0.04390 < threshold) — **reuses step 1's residual**
- Step 3: RUN
- Step 4: RUN

With only 4 distilled steps, each step makes large latent changes, so step 1's residual is a poor approximation for step 2 → severe "echo/ghost/ripple" artifacts. The quality-first threshold (0.08) does NOT prevent the skip because 0.04390 < 0.08 too — the same residual is applied, same artifacts. Only `reuse_threshold=0.0` (no skipping) avoids it, which disables the cache entirely.

## AV verification (ffprobe, all arms)

```
video: h264, 1280x704, 362 frames, 15.083333s
audio: aac, stereo, 32000 Hz, 2 channels, 15.075000s, 473 frames
format: 2 streams, 15.083333s
```
Identical across baseline and all arms — native MiniMax Video VAE + Audio VAE preserved, AV sync intact. Speed gain never altered the AV architecture.

## Visual evidence

Frame 181 (middle) extracted from each arm to `.runtime/_sc_cmp_*.png`:
- `_sc_cmp_baseline_f181.png` — CLEAN (reference)
- `_sc_cmp_armA_nosage_f181.png` — SEVERE ripple/echo/ghosting
- `_sc_cmp_armB_sage_f181.png` — SEVERE ripple/echo/ghosting (same as Arm A)
- `_sc_cmp_qfirst_sage_f181.png` — SEVERE ripple/echo/ghosting (same as Arm A/B)
- `_sc_cmp_sageonly_f181.png` — CLEAN (matches baseline)

## Comfy MCP verification

- `validate_workflow` PASS for all arm graphs (0 errors, 0 warnings)
- `run_workflow` executed live on `:8188` for all arms
- `job(action="status")` confirmed `completed` for all arms
- `MiniMaxH3SpeedCache` node contract MCP-verified (inputs/outputs/defaults)
- ComfyUI Protection Law: scoped Comfy-only restart after node install + after `minimax_patch.py` fix; Route A `:8192` confirmed down pre/post to avoid GPU admission conflict. `COMFY RESTARTED?: YES (2x, scoped — node install + API-compat patch only)`

## Required MCP verdicts

- ✅ COMFY MCP VERIFIED (39 tools, `:8188` local, validate+run+job all live)
- ✅ SPEED CACHE NODE VERIFIED (MCP contract: `MiniMaxH3SpeedCache`, inputs/outputs/defaults confirmed)
- ✅ LIVE GENERATION VERIFIED (all 5 arms executed live, outputs produced)
- ✅ VIDEO STREAM VERIFIED (ffprobe h264 1280×704 362f on certified arm)
- ✅ AUDIO STREAM VERIFIED (ffprobe aac stereo 32kHz on certified arm)
- ✅ AV SYNC VERIFIED (video 15.083s / audio 15.075s, identical to baseline)
- ✅ BENCHMARK VERIFIED (identical Korri test, 5 arms, timing + ffprobe + visual)
- ⚠️ LIVE PREVIEW VERIFIED — NOT in scope for this accelerator benchmark (deferred to Phase 6)

## Recommendation

Freeze the certified MiniMax H3 1 Frame accelerator config as:
**`MiniMaxH3SpeedCache` node with `reuse_threshold=0.0`, `sage_attention="auto"`** (SageAttention-only, cache disabled).

Do NOT enable the Speed Cache residual cache on 4-step distilled MiniMax H3 1F generation — it causes severe visual regression. The cache may be re-evaluated for higher step counts (20+) in future work, but is out of scope for v1.1 1F production.

VDN-H3 remains out of scope for v1.1 (experimental/future evaluation only).
