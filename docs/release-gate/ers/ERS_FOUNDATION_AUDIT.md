# ERS Foundation Audit

## Verified foundations

- ERS storage is project-scoped JSON under the existing data root.
- Co-Director registry exposes a closed `ers.*` tool family rather than a parallel ad hoc path.
- Spatial Map is reused for directional prompts and north lock.
- Co-Director `spatial.create_map` plus `spatial.create_camera` can clear the initial map-warning state before ERS continuity review.
- Image Pipeline is reused for directional plan/candidate generation.
- The live directional route is Image Pipeline -> local `comfyui`, with `ers.generate_directional_views` reporting `locally_verified` once ComfyUI is healthy.
- Export outputs are registered as project assets rather than left as loose files.
- Production Bible integration uses the existing `location` entity type.
- Live Beta-backed certification reached `ers.create_sheet`, `ers.attach_spatial_map`, real directional generation, per-direction keeper approval, continuity validation, compose, and PNG/PDF/offline export creation.
- ERS review fetches are now served/read as live state, so the browser panel reflects newly created exports during the same certification session.

## Known limits

- Continuity validation is metadata-based and does not inspect image pixels.
- ERS review UI is read-only; canonical creation/export still depends on Co-Director proposals.
- The currently certified generation path depends on local ComfyUI availability; if ComfyUI goes down again, capability should honestly degrade rather than silently falling back.
- Certification evidence is runtime-specific to the current Beta stack and should be revalidated after major Image Pipeline, Comfy, or ERS review-surface changes.

## Risk call

The ERS foundation is now certification-backed rather than only integration-ready. The missing proof from the earlier blocked state has been closed by a clean disposable-project Playwright completion on Beta plus real directional generation and export evidence on the restored local Comfy-backed runtime. Current release status: **GO**.

## PRIMARY ACCEPTED GO stamp

Date: `2026-08-03` local (`2026-08-04T00:34Z` evidence refresh)

- Primary disposition: **ACCEPT GO**
- Branch: `feature/ai-guided-setup`
- SHA: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta URL: `http://127.0.0.1:8760/`
- API health confirmed at `http://127.0.0.1:8758/api/health`
- ComfyUI confirmed reachable on `http://127.0.0.1:8188/` with health reporting `ready`

Fresh primary evidence commands:

- `ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_BASE=http://127.0.0.1:8758 STUDIO_API_PORT=8758 npx playwright test tests/e2e/codirector/codirector-ers-autonomous-cert.spec.ts --project=chromium`
- `python -m pytest tests/test_ers_foundation.py -q`

Fresh primary evidence results:

- Playwright: **2 passed, 0 failed** in `5.0m`
- Pytest: **3 passed** in `4.43s`

Honest limitations retained:

- Acceptance is valid for the currently verified local Beta + local ComfyUI runtime and should be revalidated after major ERS, Image Pipeline, or Comfy changes
- ERS review remains read-only while creation/export actions continue through Co-Director proposals
- Continuity validation is still metadata-based rather than pixel-inspection based
- Pytest continues to emit existing non-blocking Pydantic deprecation warnings
