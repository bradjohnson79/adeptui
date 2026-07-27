# M3.0d Audio Capability Report

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register items | B5 (audio boundary), B13 (syncEvent) |
| Module | `studio-api/app/codirector/m29/audio/service.py` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Executive summary

| Capability | Status |
|------------|--------|
| Import audio to project library | **VERIFIED** |
| Place cue on Director timeline | **VERIFIED** |
| Gain/volume persistence | **VERIFIED** |
| Normalize imported audio (ffmpeg) | **VERIFIED** |
| syncEvent bar timing (Option A) | **VERIFIED (B13 Closed)** |
| Generative dialogue | **UNAVAILABLE — import-only honest** |
| Generative SFX | **UNAVAILABLE** |
| Generative music | **UNAVAILABLE** |

Production situations S01–S12 used **imported PCM WAV** stems. S07 places SFX on the SFX track. Generative audio endpoints may exist in sandbox but are not production-certified.

## B13 — syncEvent wired through place_cue (Closed)

### Problem

`syncEvent` was schema-only — bar-relative timing promises were not applied when placing cues.

### Fix (Option A)

`_resolve_sync_start(start_sec, sync_event)` maps bar labels to seconds (e.g. `bar-3` → 4.0s at 2s/bar). `place_cue` persists `syncEvent` in cue metadata and returns resolved `startSec`.

### Test evidence

| Test | Assertion |
|------|-----------|
| `test_b13_sync_event_resolves_bar_timing` | `bar-3` → start 4.0 |
| `test_b13_place_cue_persists_sync_event` | meta JSON contains `"syncEvent": "bar-2"`, startSec 2.0 |

## B5 — Provider honesty (Closed — bounded)

### Stills

Local ComfyUI Z-Image — fresh PNG per situation (`imagegen_generate_*.png` in export packs).

### Motion

Reused fal Seedance MP4 from M3.0c proof — no new fal audio/video spend in M3.0d.

### Audio

Service header documents the honest contract:

> Generate (dialogue/sfx/music): no native TTS/SFX generator on platform — fixture CI only.
> Import (real stems): honest path for WAV bytes the user already has.

Situation matrix disclosure: `docs/m3.0c/PRODUCTION_SITUATION_CERTIFICATION_MATRIX.md`.

## Test surfaces

- `studio-api/tests/test_m30_audio_timeline.py` — import, cue promotion, gain
- `studio-api/tests/test_m30d_closures.py` — B13 syncEvent
- `artifacts/m30-situations/phase18-final-validation.json` — WAV bytes in every pack

## Status

| ID | Status |
|----|--------|
| B13 | **Closed** |
| B5 (audio portion) | **Closed (import-only disclosure)** |

Prior doc: `docs/m3.0c/SOUND_PIPELINE_CERTIFICATION.md` — unchanged generative boundary, B13 now closed.
