# Adept UI — Spatial Map Environment Image Picker Fix — Completion Report

**Date:** 2026-08-12
**Branch:** `beta`
**HEAD SHA:** `ceef886050fc693d7f7efae265ed7471b9cc2b94`
**Deployed SHA:** `ceef886050fc693d7f7efae265ed7471b9cc2b94` (Vercel production alias `https://adeptui.vercel.app`)
**Vercel URL:** https://adeptui.vercel.app
**Deployment inspect:** https://vercel.com/anoint/adeptui/6vfa4HPo88bG6LrE2xWuFLbTr9NG

---

## ROOT CAUSE

`LibraryAtlasPicker` in `SpatialMapPanel.tsx` reused `EntityPicker` with `kind="prop"`:

```tsx
<EntityPicker
  kind="prop"
  projectId={projectId}
  slot={{ index: 0, colorKey: "purple", label: "Atlas Shot", kind: "prop" }}
  onClose={onClose}
  onConfirm={(_tag, assetId, _label) => onPick(assetId)}
/>
```

`EntityPicker` had only two modes (`character` | `prop`). For non-character kinds it always rendered `PropPickerBody`, which:
- Title: hard-coded to `"Add a Prop"` (line 58)
- Body copy: `"Step 1 — choose a Library image (anchors the prop's visual identity)"` and `"Step 2 — name this prop"`
- Validation: `canConfirm = !!selectedAsset && !!labelInput.trim() && !!normalizedTag` (required a prop name/tag)
- Confirm stayed disabled because the environment-selection flow never fills the prop label field.

The `onConfirm` callback wrapped away the prop tag/label (`(_tag, assetId, _label) => onPick(assetId)`), but the underlying validation still required them — so the visible UI was wrong AND the Confirm button was permanently disabled.

---

## FILES CHANGED

| File | Change |
|---|---|
| `studio-web/src/components/CoDirector/SpatialMap/EntityPicker.tsx` | Added `kind: "environment"` to the `Props` union (with `title?` and `onConfirm: (assetId: string) => void`). Added `EnvironmentPickerBody` component: image-only grid, no prop tag/name field, `canConfirm = !!selectedAsset`, "Use as Spatial Map Image" confirm button, Atlas Shot badge when asset tag contains "atlas". Updated title rendering to use `title || "Select Spatial Map Image"` for environment mode. |
| `studio-web/src/components/CoDirector/SpatialMap/SpatialMapPanel.tsx` | `LibraryAtlasPicker` now uses `kind="environment"` with `title="Select Spatial Map Image"` and `onConfirm={(assetId) => onPick(assetId)}`. Affects both the empty-state "Choose from Library" flow and the Replace-Atlas flow (both render `LibraryAtlasPicker`). |
| `studio-web/src/components/CoDirector/SpatialMap/spatialMap.css` | Added `.spatial-map__atlas-badge` style for the "Atlas Shot" badge in the environment picker grid. |
| `tests/e2e/codirector/spatial-map-environment-picker.spec.ts` | NEW — 4 Playwright tests certifying environment picker title/no-prop/select-confirm-persist, normal Master Environment image, cancel preserves state, and Prop regression. |

---

## ENVIRONMENT PICKER

| Requirement | Status | Evidence |
|---|---|---|
| Correct title ("Select Spatial Map Image") | ✅ GO | `EntityPicker.tsx:70` renders `title || "Select Spatial Map Image"` for environment mode; Playwright test 1 asserts `getByText(/Select Spatial Map Image/i)` visible. |
| Correct helper copy | ✅ GO | `EnvironmentPickerBody` renders "Choose an Atlas Shot or Master Environment Image from your Library." + "Atlas Shots provide the clearest spatial reference, but a normal Master Environment Image can also be used." |
| No Prop controls | ✅ GO | Playwright tests 1 & 2 assert `Add a Prop`, `anchors the prop's visual identity`, `name this prop`, and `Prop label` input are NOT visible. |
| Image select state | ✅ GO | Clicking an asset card adds `is-selected` class; Playwright test 1 asserts `toHaveClass(/is-selected/)`. |
| Confirm state | ✅ GO | `canConfirm = !!selectedAsset` (no tag/label required); Playwright tests 1 & 2 assert Confirm enabled after selecting. |
| Persistence | ✅ GO | `onConfirm(assetId)` → `LibraryAtlasPicker.onPick` → `spatialMapApi.updateMap(projectId, document.id, { backgroundAssetId: assetId })` (or `createMap` for first selection). Playwright tests 1 & 2 reload the page and assert `active-atlas-panel` still visible. |
| Atlas badge | ✅ GO | When `asset.tag` includes "atlas", an `Atlas Shot` badge is rendered (`data-testid="atlas-badge-{id}"`). |
| Image-only filtering | ✅ GO | `EnvironmentPickerBody` filters with `isImageAsset` (checks `kind`/`mime_type` for "image"); no audio/video/docs. |
| Cancel preserves previous state | ✅ GO | Playwright test 3: select environment, open Replace picker, close via X → previous environment still active. |

---

## PROP REGRESSION

| Requirement | Status | Evidence |
|---|---|---|
| Title still says "Add a Prop" | ✅ GO | Playwright test 4 asserts `getByText(/Add a Prop/i)` visible when opened from prop slot. |
| Library image selectable | ✅ GO | Test 4 clicks `.spatial-map__picker-card` (generic prop picker card). |
| Prop name/tag field present | ✅ GO | Test 4 asserts `getByLabel(/Prop label/i)` visible. |
| Confirm disabled until valid | ✅ GO | Test 4: after selecting image, Confirm still disabled; only after filling "Coffee Cup" does Confirm enable. |
| Prop creation flow intact | ✅ GO | `PropPickerBody` is unchanged — `handlePickerConfirmProp` in `SpatialMapPanel.tsx` is unchanged. |

---

## PLAYWRIGHT

**Run command:**
```
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:5175"; $env:STUDIO_API_PORT="8758"
npx playwright test tests/e2e/codirector/spatial-map-environment-picker.spec.ts --reporter=line
```

**Result:** `4 passed (41.5s)`

| # | Test | Result |
|---|---|---|
| 1 | Environment picker: correct title, no Prop fields, select → Confirm → persist | ✅ passed |
| 2 | Normal Master Environment image (non-Atlas) is selectable and persists | ✅ passed |
| 3 | Cancel preserves previous state (no save, no Prop created) | ✅ passed |
| 4 | Prop regression: Add Prop still shows Prop fields and requires tag | ✅ passed |

**Regression — existing Spatial Map Atlas UX:**
```
npx playwright test tests/e2e/codirector/spatial-map-atlas-ux.spec.ts --reporter=line
```
**Result:** `3 passed (38.7s)` — no regression in Atlas result escape / Reset Map / Remove Atlas / refresh recovery.

**Frontend build:** `npm --prefix studio-web run build` → `✓ built in 1.50s` (no TypeScript errors).

---

## CONSOLE ERRORS

No new console errors introduced. The Playwright `AuditObserver` attached to each test recorded no unexpected console errors or page errors attributable to the environment picker. (The pre-existing "Production planning is unavailable because Co-Director intelligence is off" alert is unrelated to this fix and appears only when intelligence is disabled in the test project.)

---

## KNOWN LIMITATIONS

1. **Atlas badge heuristic**: The Atlas badge is shown when `asset.tag` (lowercased) includes "atlas". This matches the existing upload convention (`uploadAsset(..., "atlas_shot", "image")`) and Co-Director Atlas generation. If a non-Atlas asset is manually tagged with a string containing "atlas", it will also show the badge. This is acceptable for V1; a stricter `classification`-based check can be added later if needed.
2. **Vercel SSO**: Playwright certification was run against the local Vite dev server (`http://127.0.0.1:5175`) with the Studio API on `:8758`, per the established pattern. Hosted Beta visual smoke verified via HTTP 200 on `https://adeptui.vercel.app/`. Full hosted-browser Playwright against Vercel requires SSO auth and was not re-run (consistent with prior sessions).
3. **No separate `master_environment` field**: Per the current Spatial Map contract, environment selection stores the asset ID as `backgroundAssetId`. The contract does not currently distinguish `atlas_asset_id` vs `master_environment_asset_id`; both are stored as `backgroundAssetId`. This matches the existing authoritative schema (`SpatialMapUpdateBody.backgroundAssetId`).

---

## MAIN AGENT DOUBLE-CHECK

| Check | Result |
|---|---|
| Modal mode selection | ✅ `kind="environment"` now exists in the `Props` union and is selected for environment selection. |
| Prop/environment validation split | ✅ `EnvironmentPickerBody.canConfirm = !!selectedAsset`; `PropPickerBody.canConfirm = !!selectedAsset && !!labelInput.trim() && !!normalizedTag`. Separate functions, no shared `canConfirm`. |
| Confirm enable logic | ✅ Environment Confirm enables immediately on image selection; no disabled-button race. |
| Asset type filtering | ✅ `EnvironmentPickerBody` uses `isImageAsset` filter; Prop body unchanged. |
| Persistence field used | ✅ `backgroundAssetId` via `spatialMapApi.updateMap` / `createMap` (existing contract). |
| Prop regression | ✅ `PropPickerBody` and `handlePickerConfirmProp` unchanged. |
| Spatial Map reload behavior | ✅ Playwright tests 1 & 2 reload and verify `active-atlas-panel` restored. |
| Shared stale state | ✅ No shared state between environment and prop modes — each has its own component body and local state. |
| Prop tag requirement leaking into environment mode | ✅ Eliminated — environment mode has no tag/label input. |
| Selected image propagating | ✅ `selectedAsset` state in `EnvironmentPickerBody` drives both the highlight and the Confirm callback. |
| Wrong asset ID persistence | ✅ `onConfirm(selectedAsset.id)` passes the real asset ID. |
| Environment saved as Prop | ✅ Not possible — environment `onConfirm` signature is `(assetId: string) => void`, no prop tag/label. |
| UI-only selection | ✅ Confirm triggers `LibraryAtlasPicker.onPick` → `spatialMapApi.updateMap`/`createMap` → server-side persist. |

---

## DEPLOYMENT

- ✅ Committed: `ceef886050fc693d7f7efae265ed7471b9cc2b94`
- ✅ Pushed to `origin beta`
- ✅ Deployed to Vercel production: `https://adeptui-cmo40zci8-anoint.vercel.app` (alias `https://adeptui.vercel.app`)
- ✅ Deployed SHA verified: `ceef886050fc693d7f7efae265ed7471b9cc2b94`
- ✅ Hosted visual smoke: `Invoke-WebRequest https://adeptui.vercel.app/` → `200`

---

## FINAL VERDICT

**GO — SPATIAL MAP ENVIRONMENT PICKER CERTIFIED**

All mandatory criteria met:
- ✅ Environment picker no longer says "Add a Prop"
- ✅ No Prop tag/name field in environment mode
- ✅ Selected image enables Confirm immediately
- ✅ Atlas image works
- ✅ Normal Master Environment image works
- ✅ Selection persists (server-side via `backgroundAssetId`, survives reload)
- ✅ Cancel preserves previous state
- ✅ Prop flow still works (regression verified)
- ✅ Playwright passes (4 new + 3 regression)
- ✅ Deployed Beta verified (HTTP 200)
