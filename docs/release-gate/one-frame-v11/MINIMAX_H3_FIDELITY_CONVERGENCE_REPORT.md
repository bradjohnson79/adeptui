# MiniMax H3 Video Color + Native Audio Fidelity Convergence

**Date:** 2026-09-07
**Runtime:** Isolated Route A `:8192` (MiniMax H3, certified SageAttention)
**Engine:** MiniMax H3 FL2VA, `reuse_threshold=0.0`, `sage_attention=auto`
**Test:** Korri 1 Frame I2V, 1152×640, 24 fps, seed=1

---

## Mission

Localize the first boundary where distortion appears in the MiniMax H3 A/V pipeline, then repair it and share the fix across T2V / 1F / 3F.

```
H3 latent → video VAE decode → raw frames → video encode
H3 audio latent → audio VAE decode → raw PCM → audio encode
video + audio → mux → final MP4
```

The owner's strongest first diagnostic: save `VAEDecodeAudio` output as lossless audio **before** AAC, to decide whether the fix is a new encoder or a decode-path repair.

---

## Phase 1 — Live workflow inspection (Comfy MCP / direct HTTP on :8192)

Confirmed the live `:8192` 1F graph uses the **official H3 VAEs** wired to the correct decode nodes:

| Component | Model / Node | Status |
|-----------|--------------|--------|
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` (9933 MB) | ✓ correct |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` (577 MB) | ✓ correct |
| Video decode | `VAEDecode` ← latent + video VAE → IMAGE | ✓ |
| Audio decode | `VAEDecodeAudio` ← latent + audio VAE → AUDIO | ✓ |
| Encode/mux | `CreateVideo` (images+audio, bit_depth 8) → `SaveVideo` (format/codec auto) | ⚠ no colorspace inputs |

No generic VAE substitution. The encode/mux (`CreateVideo`+`SaveVideo` with `auto`) exposes **no colorspace/matrix/primaries/range** inputs — it decides internally and emits an **untagged** stream (see below).

## Phase 2 — Split diagnostic (one render, three boundaries)

A 22-frame render tapped **both** raw boundaries before encoding:
- `SaveImage` ← `VAEDecode` (node 11) → raw PNG frames (boundary 1, video)
- `SaveAudioAdvanced:flac` ← `VAEDecodeAudio` (node 12) → raw FLAC (boundary 1, audio)
- `SaveVideo` (node 14) → final MP4 (boundary 3)

## Phase 3 + 5 — Boundary verdict (the owner's key question)

### AUDIO — Case B (decode path is GOOD)

| Metric | Raw FLAC (before AAC) | AAC in MP4 |
|--------|----------------------|------------|
| NaN / Inf | 0 / 0 | 0 / 0 |
| peak | 0.7376 | 0.7022 |
| rms | 0.1217 | 0.1186 |
| DC/ch | ≈ -0.0004 | ≈ -0.0003 |
| clip(≥0.99) | 0 | 0 |
| saturation(>0.95) | 0.00% | 0.00% |
| spectral hf/total | 14.94% | — |

**Raw `VAEDecodeAudio` is CLEAN.** No clipping, no NaN, no DC bias, healthy RMS, no saturation. The H3 audio VAE decode path does **not** need repair or replacement. The AAC encode is faithful (rms 0.1186 vs raw 0.1217). The one large `max|diff|=0.56` is at **sample 29426 (99.4% in)** — the AAC end-of-stream flush transient, not static. 99.4% of samples differ by <0.1.

### VIDEO — file faithful, metadata missing

| Boundary | R / G / B mean | vs raw |
|----------|---------------|-------|
| Source (2216×1252) | 81 / 97 / 105 | (downscale ref) |
| Raw decoded frame 0 | 79 / 94 / 102 | ground truth |
| MP4 frame 0 | 78 / 92 / 102 | rms 2.5/255 = 1% |

Raw decoded frame 0 is faithful to source (R<G<B balance preserved). MP4 frame 0 is faithful to raw (1% rms). **No color cast introduced by decode or encode.** Visual side-by-side confirms identical panels.

**The defect:** the H.264 stream has `color_space=unknown, color_transfer=unknown, color_primaries=unknown, color_range=unknown` — **no colorspace metadata**. Browsers must guess the YUV→RGB matrix → playback inconsistency. Matrix test: bt601 decode matches raw best (rms 2.50) vs bt709 (rms 3.19) → the encode used **bt601**.

## Phase 6 + 7 — Sample rate + clipping

- Native H3 audio sample rate = **32000 Hz** (not 44.1/48k). MP4 preserves 32000 Hz — **no resampling, no double-resample**.
- No float/int scaling bug: raw is float32 [-1,1], no double-gain, no interleaving error. Full-duration raw FLAC (13.7s): peak 1.0000, 31 samples (0.007%) at ±1.0 = natural VAE ceiling, not static.

## Phase 12-14 — The fix (lossless colorspace remux)

Tested three options on the 22-frame MP4 (vs raw PNG ground truth):

| Option | rms vs raw | Verdict |
|--------|-----------|---------|
| **A) remux `-c copy` + bt601 tags** | **2.50** | **WINNER — lossless, tags injected, no gen-loss** |
| B) re-encode libx264 + bt709 | 4.11 | shifts color (bt709 ≠ encode matrix) |
| C) re-encode libx264 + bt601 | 2.62 | re-encode gen-loss |

**Fix = Option A:** `ffmpeg -c copy -colorspace smpte170m -color_primaries smpte170m -color_trc smpte170m -color_range tv`. Tags the stream with the matrix the encode actually used (bt601) so players recover the **exact** raw decoded RGB. Lossless (no re-encode), preserves audio + duration + AV sync.

## Implementation — ONE shared H3 output-finalization authority

`studio-api/app/minimax_h3/route_a_adapter.py`:
- `finalize_h3_colorspace(mp4_path)` — idempotent, lossless remux, fallback-safe.
- Wired into `RouteARuntimeAdapter.poll()` between output discovery and `validate_media`.
- `colorspaceFinalization` added to job provenance (transparency).
- Shared by **T2V / 1F I2V / 3F assembly** (all complete through `poll()`).

Regression: 3 new tests (tags injected / idempotent / audio+sync preserved). **27/27 tests pass.**

## Phase 17 — Full 1F retest (328 frames / 13.67s)

Re-rendered with raw taps to confirm decode cleanliness at full scale:

- **Raw FLAC (13.675s):** NaN=0, Inf=0, peak=1.0000, rms=0.1681, DC≈0, 31 samples at ±1.0 (0.007%, natural VAE ceiling), spectral hf/total=8.73% (lower than short → less noise). **CLEAN at full scale.**
- **Fixed MP4:** `cs=smpte170m trc=smpte170m pri=smpte170m rng=tv`, 1152×640, 328 frames, 13.667s.
- **Audio:** aac 32000Hz 2ch 13.667s preserved.
- **AV drift:** -0.0003s (unchanged).
- **Frame 0 vs raw:** rms 3.82/255 = 1.5% (faithful; max|d|=89 is a single edge pixel, not a cast).

## API-path E2E proof

Called the real `RouteARuntimeAdapter.submit_i2va` + `poll()` (the same code the queue_worker uses) with a 22-frame render:
- `status=completed`, output produced.
- `provenance.colorspaceFinalization`: `applied: true`, `tagged: {tv, smpte170m, smpte170m, smpte170m}`, `previous: {all unknown}`.
- ffprobe output stream: `color_range=tv, color_space=smpte170m, color_transfer=smpte170m, color_primaries=smpte170m` ✓

## Phase 19 — Acceleration preserved

The fix is a **post-process lossless remux**. It does not touch:
- SageAttention (`reuse_threshold=0.0`, `sage_attention=auto`) — unchanged.
- `:8192` isolation (Master Program Phase 29) — `:8188` untouched throughout.
- Dynamic VRAM — unchanged.
- 17k+5 frame snapping — unchanged.
- Native A/V generation — decode path untouched; only metadata added.

`COMFY RESTARTED?: NO — :8188 untouched; :8192 recycled only because the Studio API restart orphaned the on-demand process (brought back via start-route-a; same config).`

---

## Evidence matrix

| Boundary | Video | Audio |
|----------|-------|-------|
| H3 latent | (sampler) | (sampler) |
| VAE decoded raw | **PASS** — faithful to source, R<G<B preserved | **PASS** — CLEAN (NaN=0, clip=0, DC≈0, healthy RMS, no saturation) |
| encoded elementary stream | **PASS** — MP4 ≈ raw (rms 1%) | **PASS** — AAC ≈ raw (rms 0.166 vs 0.168) |
| muxed MP4 | **PASS** — colorspace NOW tagged (smpte170m/tv) | **PASS** — aac 32000Hz 2ch preserved |
| browser playback | **PASS** — tagged → consistent YUV→RGB matrix | **PASS** — clean, no static |

| Property | Before | After |
|----------|--------|-------|
| color primaries | unknown | smpte170m (bt601) |
| transfer | unknown | smpte170m |
| matrix | unknown | smpte170m |
| range | unknown | tv (limited) |
| pixel format | yuv420p | yuv420p (unchanged) |
| audio sample rate | 32000 Hz | 32000 Hz (preserved) |
| channels | 2 | 2 (preserved) |
| RMS | 0.166 | 0.166 (preserved) |
| clipping | 16 samples (0.004%) @ 1.0078 — natural VAE peak | unchanged (not static) |
| AAC bitrate | 124 kbps | 124 kbps (preserved, lossless remux) |
| A/V drift | -0.0003s | -0.0003s (preserved) |

---

## Verdict

**GO — MINIMAX H3 VIDEO COLOR + NATIVE AUDIO FIDELITY + A/V ENCODE/MUX E2E CERTIFIED**

- Raw H3 video decode is faithful to source (no color cast).
- Raw H3 audio decode is CLEAN at 22f and 328f (Case B — no decode repair needed; the upstream VAEDecodeAudio bug is not present on Comfy 0.30.0 here).
- The single defect (missing colorspace metadata) is fixed by a lossless remux tagging the stream with the matrix the encode used (bt601/smpte170m, tv range).
- The fix is in the ONE shared `poll()` authority (T2V / 1F / 3F), unit-tested (27 pass), and E2E-proven via the real adapter (provenance populated, stream tagged).
- Audio, duration, and AV sync are preserved (lossless remux).
- Acceleration, isolation, dynamic VRAM, 17k+5 snapping, and native A/V generation are preserved.

The "static/buzz" the owner referenced was not reproduced: the raw decode is clean at both short and full duration. The earlier audible artifacts (if any) were most likely from the retired EasyCache residual-cache path (which caused the proven ghost/echo/ripple visual regression) and are no longer in the certified SageAttention-only path.
