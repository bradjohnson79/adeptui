# Approve Uploaded Image as Environment — Unified Completion Report

Date: 2026-09-17 · Branch: `feat/character-creator-final-closure` · HEAD at start: `99665cf7`
Mission: CURSOR JOURNEY — APPROVE UPLOADED IMAGE AS ENVIRONMENT (Path A direct approval in Environment Creator).

## Verdict

**CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED**

Path A (direct approval) and Path B (generated ERS) converge on one contract:
`ers_composite_asset_id` + `status=approved` + canonical pointer + scope sync.
No second schema. No duplicate environment. Library bytes never deleted.

## What shipped

### Backend (studio-api)

- `app/environment_reference_sheet/direct_approve.py` (new) — `approve_reference_as_environment`
  and `clear_reference_environment_approval`. Approval sets the sheet's official visual
  (`ers_composite_asset_id` + composition rendered ids), keeps the saved plan's
  `referenceImageAssetId` pointing at the same asset (reload shows the same attached image),
  stamps the Library asset as an environment reference (same stamp as Preview Monitor →
  Approve as Environment), then delegates to `versioning.approve_ers_version` — the sole
  writer that flips `status=approved`, stamps approval requirements, and moves the canonical
  pointer. `sync_environment_scope` updates the creator-scope identity asset so Co-Director
  `#Tag` resolution binds the approved image. Clear releases the visual, returns the sheet to
  `draft`, restamps approval requirements, clears the canonical pointer when held, and never
  deletes Library bytes.
- `app/environment_reference_sheet/api.py` — new routes:
  - `POST /api/environment-reference-sheets/projects/{project_id}/{sheet_id}/approve-reference`
  - `POST /api/environment-reference-sheets/projects/{project_id}/{sheet_id}/clear-approval`
  - 404 unknown sheet · 403 foreign-owned Global sheet (owner/mutation rules unchanged) ·
    400 non-image asset.
- `tests/test_environment_direct_approve.py` (new) — 10 tests, all passing.

### Frontend (studio-web)

- `src/api.ts` — `environmentReferenceSheet.approveReference` / `.clearApproval` clients.
- `src/components/CoDirector/EnvironmentCreator/EnvironmentCreatorSurface.tsx`
  - "Approve as Environment" button beside Change from Library / Upload Image / Remove.
    States: disabled with no image · enabled when attached · "Approved Environment ✓"
    (disabled) when the attached image is the approved visual.
  - Click with unsaved changes upserts first (approval is one committed action — no separate
    save), then approves, then refreshes the lower Project Environment Reference Sheets list
    immediately (no manual refresh, no reopening Co-Director).
  - Replace-after-approval: attaching a different image leaves the old approval untouched
    until explicitly re-approved (button returns to "Approve as Environment").
  - Remove on the approved image: confirms "This image is the approved Environment
    Reference. Remove approval as well?" → clears approval via the backend, then detaches.
    Cancel aborts the removal; clear failure keeps the image attached and surfaces the error.
  - **Ownership guard in `resolveTargetSheetId`** (bug found by live E2E): a visible Global
    sheet owned by another project is never a save/approve target. Previously, with a foreign
    Global sheet auto-hydrated, editing + saving/approving sent the foreign `sheetId` to
    `/save` and failed 403. Now a new environment identity is created in the current project.
- `src/components/CoDirector/EnvironmentCreator/environmentCreatorContracts.test.ts` —
  contract coverage for the new chrome (14/14 passing).
- `e2e/environment-direct-approve.spec.ts` (new) — live Playwright, no mocks.

## E2E TRACE (live Beta: Vite :5173 → Studio API :8758)

| Stage | Result |
| --- | --- |
| User action (name → attach Library image → Approve as Environment) | PASS |
| Frontend (button states, disabled→enabled→Approved ✓, upsert-then-approve) | PASS |
| API (`POST /save` 200 → `POST /approve-reference` 200) | PASS |
| Backend (official visual set, status=approved via sole writer, canonical pointer) | PASS |
| Persistence (sheet JSON + scope row; canonical tag unchanged) | PASS |
| Runtime/provider (no generation on this path — N/A by design) | N/A |
| Result (lower list shows approved item with thumbnail immediately) | PASS |
| Reload (approval persists; Select rehydrates attached image as approved) | PASS |
| Downstream (Co-Director resolver contract fields; Timeline binding identity+asset) | PASS |

Playwright: `1 passed (5.1s)` — `ADEPT_BETA_TARGET=1 npx playwright test --project=workspaces environment-direct-approve`.
Artifacts: `artifacts/functional-audit/test-output/`, `artifacts/functional-audit/playwright-results.json`.

## Test evidence (exact counts)

- Backend: `test_environment_direct_approve.py` + `test_environment_creator_save.py` — **14 passed, 0 failed**
  (covers: happy path, reload persistence, missing sheet 404, non-image 400, cross-project
  asset denied, replace-keeps-old-approval, clear releases visual+canonical but keeps Library
  bytes, Global owner-only mutation + cross-project readability, Co-Director resolver
  convergence (`found`, `bindable_asset_id`, `approved_sheet`, canonical tag), Timeline
  binding identity/asset/canonical tag).
- Backend regression: `test_preview_approve_as.py` + `test_ers_image_product.py` — 2 failures
  reproduced on the stashed baseline (pre-existing, unrelated to this mission).
- Frontend: `environmentCreatorContracts.test.ts` — **14 passed, 0 failed**.
- Frontend lint (oxlint on touched files): clean.
- TypeScript `tsc -b`: no errors in touched files; the repo carries pre-existing errors in
  unrelated files (e.g. `ErsEditModal.tsx` TS6133 — untracked baseline file, not touched here).

## Runtime verification

- Studio API recycled via `scripts/restart_studio_api_only.py` (PID 24216 → 33056); new routes
  confirmed in live OpenAPI.
- `GET :8758/api/healthz` → ok · `GET :5173/` → 200.
- COMFY BEFORE: up, VRAM free 30.1 GB · COMFY AFTER: up, VRAM free 30.1 GB ·
  COMFY RESTARTED?: **NO** (read-only observation only, per ComfyUI Protection Law).

## Live-data housekeeping

The first E2E run's attempt 1 leaked an orphaned Global sheet (`E2E Venture Corridor`, owner
project deleted by afterAll). Removed surgically (scope row + sheet JSON, identity-verified)
via `.runtime/_cleanup_orphan_e2e_sheet.py`. Post-cleanup probe: fresh projects see only the
two pre-existing Global sheets owned by real projects; zero leftover E2E projects. The spec
now deletes the sheet before the project and uses unique names per run.

## Observed pre-existing behavior (not changed by this mission)

- The surface auto-hydrates the most recent visible sheet with a composite — including Global
  sheets from other projects — and inherits its name/Global scope into the planning form
  (`EnvironmentCreatorSurface` effect on `ers.sheetId`). Creators should review the Global
  toggle before saving in a fresh project. The new ownership guard prevents the 403 this used
  to cause on save/approve.
- `GlobalScopeField` patches the hydrated sheet's identity on toggle even when foreign-owned
  (silently caught 403).
- Project deletion does not remove Global ERS sheets/scope rows (orphan risk, seen above).

## Limitations

- Direct approval requires an image asset in the same project (cross-project assets are
  denied, matching Library permission rules).
- The Playwright spec asserts the Co-Director resolution contract over HTTP (the exact fields
  `_resolve_environment` binds); service-level resolver + Timeline `resolve_binding_id`
  convergence is proven in pytest. No LLM chat turn is driven in E2E.

**GO**
