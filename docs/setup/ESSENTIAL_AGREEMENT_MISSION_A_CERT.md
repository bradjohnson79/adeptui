# Essential Agreement + MoGe-2 Setup Registration — Mission A

**Verdict:** `GO — ADEPT UI ESSENTIAL COMPONENTS AGREEMENT + MOGE-2 SETUP REGISTRATION CERTIFIED`

This GO also requires `vggt_1b_commercial` in the Essential catalog and notice (gated access allowed). Mission B (geometry bake-off) is a separate verdict.

## What shipped

- Versioned notice `2026.08.1`: `docs/setup/ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md`
- Registry policy: `docs/setup/ESSENTIAL_COMPONENT_REGISTRY.md`
- Split license fields: `code_license` / `weights_license` / `license_status` / `owner_policy`
- Essentials: `moge2_geometry` and `vggt_1b_commercial` in `ESSENTIAL_IDS` and Spatial Intelligence
- Server agreement APIs + `setup_state.json` persistence
- Hard gate on Essential install/activation until `accepted_version == current_version`
- Document-unavailable never auto-accepts
- Setup Wizard: View / Open Full / AGREE / Decline + independent readiness badges
- VGGT may be Essential and `MODEL_ACCESS_GATED` and not Ready. Gated VGGT does not block MoGe-2.

## Tests

- `studio-api/tests/test_essential_agreement.py`: 11 passed
- `studio-api/tests/test_atlas_deterministic_renderer.py`: 3 passed (shared renderer unit)
- `studio-web` vitest `EssentialAgreementPanel.test.ts`: 3 passed
- Playwright: `tests/e2e/setup/essential-agreement.spec.ts` — 1 passed (37.3s) on Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/`

## Peers

- GLM 5.2: documentation-canon BLOCK on historical VGGT omit docs — repaired (supersession banners + registry Supersedes section).
- Kimi K3: bypass tickets on `/api/downloads`, link-existing, and install-jobs 400-vs-409 — repaired and covered by `test_downloads_and_link_existing_are_gated`. Uncommitted-files ticket is not a product defect; commit was not requested.

## Live URLs

- Creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/`
