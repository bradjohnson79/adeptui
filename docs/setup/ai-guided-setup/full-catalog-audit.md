# Full Catalog Audit

## Audit basis

- Source of truth checked live: `GET /api/setup/status`
- Branch: `feature/ai-guided-setup`
- Observed HEAD: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta runtime after restart: `http://127.0.0.1:8760/`
- Observed live counts after this repair: `33 ready`, `4 not_installed`, `0 needs_attention`

This file is the honest Phase 2 closure audit for the current Beta-visible setup catalog after the M5.0 wiring repair pass.

## Live first-class groups observed in Setup

| Group | Representative evidence | Current posture |
| --- | --- | --- |
| Image | `qwen_image_2512_models`, `flux1_dev_local`, `flux1_schnell_local`, `flux1_kontext_dev_local`, `sana_15_local` | Present as first-class local image inventory. |
| Video | `hunyuan_video_15`, `hunyuan_video_13b`, `ltx_checkpoint`, `wan_models` | Present as first-class video inventory. |
| Voice | `index_tts2`, `qwen_voice_design_17b`, `qwen_voice_clone_17b` | Present as first-class voice inventory. |
| Music | `ace_step_local`, `mmaudio_local` | Present as first-class music inventory. |
| Motion | `longcat-video-avatar-1-5-local`, `infinitetalk-local`, `musetalk-1-5-local`, `echomimic-v2-local` via `surfaceGroups` | Present as a creator-visible surface group for avatar and motion flows. |
| Avatar | `longcat-video-avatar-1-5-local`, `infinitetalk-local`, `musetalk-1-5-local`, `echomimic-v2-local` | Present as first-class avatar inventory. |
| ComfyUI Extensions | `comfyui_hunyuan_nodes` | Present and live-ready after corrected restart/verify flow. |
| Utilities | `python`, `ffmpeg`, `comfyui`, `ollama`, `ltx23_ic_lora_ingredients` | Present as general studio prerequisites. |
| API Providers | `fal_key` | Present as a first-class credentials group. |
| Creative Packs | `pack_essential_photoreal`, `pack_essential_anime`, `pack_essential_cinematic` | Present as a first-class creative-pack group. |

## Representative live payload evidence

| Component | Group | Subgroup | Status | Notes |
| --- | --- | --- | --- | --- |
| `fal_key` | `API Providers` | `Credentials` | `ready` | Live `/api/setup/status` now exposes provider credentials as a dedicated group instead of folding them into Utilities. |
| `ace_step_local` | `Music` | `Local Runtimes` | `ready` | Live payload exposes first-class music runtime posture. |
| `pack_essential_photoreal` | `Creative Packs` | `Essential Packs` | `ready` | Creative pack now presents as dedicated setup inventory. |
| `longcat-video-avatar-1-5-local` | `Avatar` | `Local Models` | `not_installed` | Live payload keeps honest `not_installed` status while also exposing `surfaceGroups = ["Avatar", "Motion"]`. |

## Validation run used for closure

- Backend regression: `python -m pytest tests/test_setup_refactor.py -q`
  - Result: `25 passed`
- Playwright AI-Guided lifecycle subset: `npm run test:e2e -- tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts`
  - Result: `4 passed`
- Live Beta sample after restart:
  - `GET /api/setup/status` returned first-class `Music`, `Avatar`, `API Providers`, and `Creative Packs` metadata for the representative rows above

## Audit verdict

Phase 2 is now honestly closed for the requested first-class group model.

Remaining certification work lives elsewhere:

- broader Setup install-progress regressions still fail in `tests/e2e/setup/setup-install-progress.spec.ts`
- final AI-Guided certification therefore remains controlled by Phase 7, not by the catalog group model
