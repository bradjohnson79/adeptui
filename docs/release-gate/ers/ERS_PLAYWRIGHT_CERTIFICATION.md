# ERS Playwright Certification

## Current state

`tests/e2e/codirector/codirector-ers-autonomous-cert.spec.ts` is now a real disposable-project certification harness rather than a single-panel smoke, and it completed cleanly on Beta against live ERS directional generation.

## Live commands run

- Beta restart:
  `powershell -ExecutionPolicy Bypass -File C:\AdeptFilmWorks\AIVideoStudio\Restart-AdeptUI-Beta.ps1`
- Playwright on Beta:
  `ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_BASE=http://127.0.0.1:8758 STUDIO_API_PORT=8758 npx playwright test tests/e2e/codirector/codirector-ers-autonomous-cert.spec.ts --project=chromium`
- Unit:
  `python -m pytest tests/test_ers_foundation.py -q`

`npm run test:e2e:beta -- ...` was attempted first, but the wrapper failed on this Windows host with `spawn EINVAL`, so the direct Beta env command above was used for the actual certification attempt.

## What the expanded suite now exercises

- Disposable project creation from Home UI
- Co-Director `Plans` empty-state proof that ERS remains review-only until a canonical sheet exists
- Co-Director proposal approval flow for:
  - `spatial.create_map`
  - `spatial.create_camera`
  - `ers.create_sheet`
  - `ers.attach_spatial_map`
  - `ers.generate_directional_views`
  - `ers.approve_direction`
  - `ers.validate_continuity`
  - `ers.compose_sheet`
  - `ers.export_sheet`
- Spatial Map north lock evidence
- Honest capability check that `ers.generate_directional_views` is `locally_verified` on this Beta when ComfyUI is healthy
- Isolation/cleanup intent against disposable projects only, never the Manual Beta Handoff project

## Observed Beta evidence

- Beta UI stayed reachable at `http://127.0.0.1:8760/`
- Beta API stayed reachable at `http://127.0.0.1:8758/api/health`
- Directional generation routed through the existing Image Pipeline -> local `comfyui` capability path and produced real project-owned directional assets after ComfyUI was restored on `:8188`
- The clean disposable-project certification advanced through:
  - project creation
  - ERS empty-state verification
  - Spatial Map creation
  - camera repair to clear the initial `No camera has been placed yet.` warning
  - canonical ERS draft creation
  - Spatial Map attachment
  - real `north/east/south/west` directional generation
  - north-direction approval plus warning-state continuity validation
  - preserved-direction repair progression through all four directions
  - continuity reaching `ready`
  - compose succeeding
  - PNG/PDF/offline export creation succeeding with generated directional media
  - ERS review panel showing export state after the browser/API no-store refresh repair
  - isolation project proof with no ERS or Spatial Map leakage
  - disposable-project cleanup without mutating Manual Beta Handoff `77a4b96c-8e3f-4501-897c-51bab99bedb7`

## Current pass/fail

- Playwright baseline empty-state test: **PASS**
- Expanded autonomous Beta certification: **PASS**
  - Final direct-env run on fresh Beta: **2 passed, 0 failed**
  - The single uninterrupted pass covered creation, repair, live directional generation, continuity, compose, exports, isolation, and cleanup
- Unit tests: **3 passed**

## Repairs required for the clean pass

- Restored the established local ComfyUI runtime so `ers.generate_directional_views` moved from `proposal_ready` to `locally_verified`
- Repaired `schedule_job_queue_enqueue` so same-loop queue submission no longer blocks approvals behind repeated timeout windows
- Added a regression test for the same-loop enqueue case in `studio-api/tests/test_production_executive.py`
- Made ERS review fetches non-cacheable and refreshed the ERS panel so browser review state reflects newly created exports during the same session

## Binary gate

Mission string: `CODIRECTOR ERS CERTIFIED`

Adept binary: **GO**

Treat ERS certification as **GO** on this Beta for the current runtime. The certified path is the restored local ComfyUI-backed Image Pipeline route, proven by one uninterrupted disposable-project Playwright pass with real generated directional media and export persistence.

## PRIMARY ACCEPTED GO stamp

Date: `2026-08-03` local (`2026-08-04T00:34Z` evidence refresh)

- Primary disposition: **ACCEPT GO**
- Branch: `feature/ai-guided-setup`
- SHA: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta URL: `http://127.0.0.1:8760/`
- API health: `http://127.0.0.1:8758/api/health` returned `200 OK`
- ComfyUI health: `http://127.0.0.1:8188/` reachable and API health reported `comfy_status: ready`

Fresh primary evidence commands:

- `ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_BASE=http://127.0.0.1:8758 STUDIO_API_PORT=8758 npx playwright test tests/e2e/codirector/codirector-ers-autonomous-cert.spec.ts --project=chromium`
- `python -m pytest tests/test_ers_foundation.py -q`

Fresh primary evidence results:

- Playwright: **2 passed, 0 failed** in `5.0m`
- Pytest: **3 passed** in `4.43s`
- Manual Beta Handoff `77a4b96c-8e3f-4501-897c-51bab99bedb7` was not used or mutated by this primary verification pass

Honest limitations:

- This acceptance is still runtime-specific to the currently healthy local Beta stack at `:8760` / `:8758` with ComfyUI healthy on `:8188`
- If ComfyUI becomes unavailable again, ERS directional generation must degrade honestly rather than silently falling back
- The requested pytest pass remains green but still emits existing non-blocking Pydantic deprecation warnings
