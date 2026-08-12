# PoseCraft v1.1 — Primary Merge Review (Promotion, not parallel retention)

**Date:** 2026-08-04
**Source worktree:** `C:\AdeptFilmWorks\AIVideoStudio-posecraft` (~HEAD `2e4246f`, branch `feature/posecraft-v1-1-foundation`)
**Target:** primary tree `C:\AdeptFilmWorks\AIVideoStudio` (branch `feature/ai-guided-setup`)
**Decision:** PROMOTE PoseCraft v1.1 Babylon as the single production PoseCraft implementation. The Experimental landing page is retired as a product identity; landing/help is demoted to an overlay inside the 3D workspace.

## Hard acceptance (locked)

```
PoseCraft shall no longer exist as a hidden experimental workspace.
Every creator-facing entry point resolves to the same production PoseCraft implementation.
There shall be exactly one PoseCraft experience.
The Babylon workspace is the product.
Landing/help/introduction pages are secondary overlays only.
```

Failure string if violated: `NO-GO — POSECRAFT ROUTE DOES NOT OPEN THE 3D WORKSPACE`

## Promotion approach (not parallel retention)

The wrong path would be to merge the worktree *beside* the Experimental landing, leaving two competing PoseCraft UIs. Instead, the v1.1 Babylon viewport is promoted *into* the existing creator-facing `PoseCraftWorkspace`, replacing the landing page as the product surface.

| Wrong framing | Locked framing |
| --- | --- |
| Merge worktree next to Experimental landing | Promote v1.1 Babylon as **the** production PoseCraft |
| Keep `/posecraft-lab` + `?workspace=posecraft` as two UIs | **Exactly one** creator PoseCraft experience |
| Landing page as primary surface | Landing/help = secondary overlay / empty-state only |
| Fixture staging as equal path | PoseCraft is the **canonical** creator-driven blocking tool |

## Files promoted (net-new into primary)

From `AIVideoStudio-posecraft/studio-web/src/posecraft/` into `studio-web/src/posecraft/`:

- `types.ts` — PoseCraft scene/figure/camera/primitive/version contracts (`PoseCraftScene`, `PoseCraftDocument`, `FigureInstance`, `CameraState`, etc.).
- `constants.ts` — archetypes, figure colors, joint labels/limits, pose library, camera presets/aspects/guides.
- `state.ts` — pure scene reducers (add/remove/duplicate figure, pose preset apply, camera update, version save/restore).
- `history.ts` — undo/redo history state.
- `storage.ts` — document parse/migrate + localStorage facade.
- `exports.ts` — scene/reference export builders.
- `engine.ts` — `PoseCraftViewportController` (Babylon `@babylonjs/core` viewport: camera, lights, grid, figure rigs, primitives, snapshot).
- `posecraft.css` — panel/layout/canvas styles.
- `sceneState.test.ts` — vitest unit tests for state/history/storage.

## Files NOT taken wholesale

- **Worktree `App.tsx`** — NOT taken. The worktree routed `/posecraft-lab` to a standalone `PoseCraftLabPage` with its own topbar. The primary tree mounts PoseCraft inside the project editor (`?workspace=posecraft` → `PoseCraftWorkspace`), so the worktree's standalone chrome was intentionally discarded.
- **`PoseCraftLabPage.tsx`** — copied for reference then **deleted** from the primary tree. It is not routed anywhere in primary; keeping it would create a second, competing PoseCraft surface. The production component reuses the same `state`/`engine`/`constants` modules but mounts project-aware inside the editor.

## Files changed in primary

- `studio-web/src/components/GenerationTools/PoseCraftWorkspace.tsx` — rewritten from Experimental landing page into a **thin production shell** hosting the Babylon viewport (`data-testid="posecraft-babylon-canvas"`) plus the creator panels (cast browser, inspector, camera, versions/exports). Experimental badge replaced by a `Production` pill (`data-testid="posecraft-production-pill"`). Empty/help state is an overlay inside the 3D workspace only.
- `studio-web/src/components/GenerationTools/posecraft-workspace.css` — replaced landing-page styles with production shell header + intro-overlay styles; panel/layout/canvas styles come from the promoted `posecraft.css`.
- `studio-web/package.json` — added `@babylonjs/core@^9.19.0` (viewport runtime) and `vitest@^4.1.10` (unit tests for the state modules).
- `tests/e2e/integration/adept-ui-full-creator-pipeline.spec.ts` — Phase 0 + Phase 6 PoseCraft classification now detects production-ready (Babylon canvas + production pill present) vs Experimental-only, and records the appropriate classification/blocker. Report template Limitations + matrix rows now derive from `ctx` instead of hardcoded stale RED-run text.

## Routing / entry-point convergence

- `/posecraft-lab` — never existed in the primary tree nav, so no redirect was needed. The worktree's standalone lab route was not imported.
- `?workspace=posecraft` (Home / Production menu / Explore / Co-Director "Open PoseCraft") → `PoseCraftWorkspace` → Babylon canvas immediately. **One** creator PoseCraft experience.

## Dependency

`@babylonjs/core@^9.19.0` — matches the worktree version. Required for the Babylon viewport (`Engine`/`WebGPUEngine`, `Scene`, `ArcRotateCamera`, `HemisphericLight`, `MeshBuilder`, `StandardMaterial`, `TransformNode`, `Vector3`/`Color3`/`Color4`). `npm install` is required before the production build; the dependency is declared in `studio-web/package.json`.

## Build impact

- Voice Studio / unrelated TS were not modified; no TS-only fixes were needed for this merge. The promoted modules are self-contained under `studio-web/src/posecraft/` and the rewritten `PoseCraftWorkspace.tsx` imports only those modules plus existing `HelpTip`/`Button`/`Project` types.
- `sceneState.test.ts` runs under `vitest` (now declared). It exercises the pure state reducers used by the production component.

## What this merge does NOT yet include (honest)

This merge promotes the **UI + viewport + local state**. The following phases are tracked separately and are required before a GREEN verdict:

- **Phase 3 — Persistence:** project-scoped `studio-api/app/posecraft/` API (save/load/revision/export preview to Library). Today the production shell uses a per-project localStorage draft key as a fallback; no production state lives *only* in localStorage once the API lands.
- **Phase 4 — Co-Director:** `posecraft.*` tool registration (get_status, create_scene, open_scene, add_figure, map_character, set_figure_color, apply_pose, update_figure_transform, set_eyeline, set_camera, save_scene, export_reference, send_to_image_pipeline) with approval-gated mutations and no silent overwrite after `creatorModified`.
- **Phase 5 — Image Pipeline:** live `PoseCraftControlPackage` from the scene + Send → Image Gen → Library → Storyboard → Timeline; retire fixture as default for creator-driven multi-subject blocking.
- **Phases 6–8 — Coffee-shop full production cert** Playwright spec.
- **Phases 10–12 — Full pipeline rerun** with `POSECRAFT_PRODUCTION_READY` and real staging.

## Verdict for this phase

**READY for primary review (Phase 1 — merge promotion).** The single production PoseCraft experience is in place; the Experimental landing identity is removed; the Babylon canvas is the product. Subsequent phases (persistence, Co-Director, image pipeline, cert rerun) are required before the overall pipeline verdict can move from CONDITIONAL to GREEN.

---

## Master Program delta (2026-08-04 — deliberate reconcile with `AIVideoStudio-posecraft`)

The Master Program is a **quality + capability elevation** of the already-promoted GREEN baseline. It is **not** a second landing-page merge and **not** parallel retention. This section records the deliberate reconcile with the source worktree for **remaining unused assets only**.

### Method

A byte-for-byte comparison of the shared PoseCraft modules was performed between the worktree (`C:\AdeptFilmWorks\AIVideoStudio-posecraft\studio-web\src\posecraft\`) and the primary tree (`studio-web\src\posecraft\`):

| File | Result |
| --- | --- |
| `constants.ts` | IDENTICAL (already promoted) |
| `engine.ts` | IDENTICAL (already promoted) |
| `state.ts` | IDENTICAL (already promoted) |
| `types.ts` | IDENTICAL (already promoted) |
| `storage.ts` | IDENTICAL (already promoted) |
| `exports.ts` | IDENTICAL (already promoted) |
| `history.ts` | IDENTICAL (already promoted) |
| `posecraft.css` | IDENTICAL (already promoted) |
| `sceneState.test.ts` | IDENTICAL (already promoted) |

All nine shared modules are already promoted identically. There are **no remaining unused pose-data or mesh assets** in the worktree beyond what is already in `constants.ts` (the 8 text presets). The Master Program's ≥50-pose catalog is **new work** in primary, not a copy from the worktree.

### Accepted from worktree

(none — all shared modules were already promoted in the v1.1 promotion. The Master Program adds new primary-tree work: low-poly human rigs, the ≥50 integrity catalog, gizmos, API-backed persistence, expanded Co-Director tools, Storyboard handoff, build-time thumbnails, Master coffee cert.)

### Rejected from worktree (with reason)

| Worktree asset | Reason rejected |
| --- | --- |
| `studio-web/src/posecraft/PoseCraftLabPage.tsx` | Standalone lab UI with its own topbar routed at `/posecraft-lab`. Promoting it would create a **second, competing** PoseCraft surface. The primary tree mounts PoseCraft project-aware inside the editor (`?workspace=posecraft` → `PoseCraftWorkspace`). One PoseCraft experience. |
| `docs/posecraft/contracts/posecraft-scene-contract-draft.md` | Track B foundation draft. Its "Explicit non-goals" (No project DB persistence / No shared library contract / No Co-Director action registry) are now **false** in primary — Phases 3–5 (persistence, Co-Director tools, image pipeline) are live in the GREEN baseline. Stale. |
| `docs/posecraft/contracts/posecraft-export-contract-draft.md` | Track B export draft, superseded by the production `PoseCraftExportPreview` schema + honesty label in `studio-api/app/posecraft/schemas.py`. |
| `docs/posecraft/POSECRAFT_REVIEWER_PASS.md` | Track B reviewer pass (`READY WITH LIMITATIONS`). Superseded by the GREEN production certification. |
| `docs/posecraft/POSECRAFT_V1_1_PARALLEL_FOUNDATION_HANDOFF.md` | Parallel-foundation handoff note; the foundation is already promoted. |
| `docs/posecraft/SCENECRAFT_COMPATIBILITY.md` | SceneCraft compatibility note — SceneCraft is **out of scope** for the Master Program. |
| `docs/posecraft/FILE_MANIFEST.md` | Worktree file manifest; not a primary-tree asset. |
| `tests/e2e/posecraft/posecraft-foundation.spec.ts` | Old foundation spec; superseded by the production `posecraft-production-two-character.spec.ts` (16-step cert) and the Master upgrade to scenarios A–K. |

### No bulk copy, no second lab UI

- No bulk copy of worktree assets into primary.
- No reintroduction of a second lab UI. `PoseCraftLabPage.tsx` stays deleted from primary; `/posecraft-lab` is not routed.
- The Master Program's new work (rigs, catalog, gizmos, persistence wiring, tools, thumbnails, cert) is authored in the primary tree against the canonical contracts in `studio-api/app/posecraft/` and `studio-web/src/posecraft/`.

### Verdict for this phase

**READY for primary review (Phase 1 — Master Program merge review).** No new worktree assets are accepted; the deliberate delta is recorded above; no second lab UI is introduced.
