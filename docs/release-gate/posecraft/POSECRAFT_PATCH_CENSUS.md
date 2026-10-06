# PoseCraft Patch / Workaround Census

**Status:** AUDIT DELIVERABLE C · read-only · 2026-09-12
**Purpose:** classify PoseCraft code touched by recent missions so the repair journey
does **not** layer a new fix on top of bad patch code. No code changed.

Legend: **CANONICAL** · **LEGITIMATE** · **COMPATIBILITY** · **STALE** ·
**DUPLICATED** · **PATCH/WORKAROUND** · **DEAD**

---

## 1. UNCOMMITTED CAMERA REPAIR (branch `feat/character-creator-final-closure`, HEAD `99665cf7`)

`git diff` on `studio-web/src/posecraft/engine.ts` = **+24 / −9**, plus two untracked files.

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| `sanitizePersistedCamera()` call in `sync()` | `engine.ts` ~1516 | **CANONICAL** | Correct boundary: validates a NEW persisted camera, preserves valid framing exactly, replaces only camera fields. |
| `cameraPlausibility.ts` | untracked | **CANONICAL** | Pure, unit-testable, composable signals; explicitly avoids a single magic threshold. |
| `cameraPlausibility.test.ts` | untracked | **CANONICAL** | Covers plausible/implausible/heavy camera cases. |
| `lastSyncedCamera = JSON.stringify(applied)` | `engine.ts` ~1518 | **PATCH (minor)** | Stores the **sanitized** JSON while `sceneDoc.camera` keeps the original bytes. Terminates normally via the write-back, but if the `emitCameraCommit()` write-back is dropped, the next `sync()` re-sanitizes and re-emits — a redundant-commit risk. Should compare the raw `sceneDoc.camera` key, not the applied value. |
| `emitCameraCommit()` on sanitize | `engine.ts` ~1525 | **LEGITIMATE** | Persists the repaired camera so corrupt bytes do not return. |
| `apiUrl` → `api.assetUrl()` for custom figures | `engine.ts` ~418 | **LEGITIMATE (scope creep)** | Unrelated to the camera repair; affects custom-figure asset URL resolution. Bundled into the camera change-set — should be split/verified separately. |
| `(globalThis as any).__posecraftController = controller` | `engine.ts` ~840 | **PATCH/DEBUG** | Not race-safe under StrictMode: the assigned controller can be the one a cleanup disposes. Confirmed live: the global was **disposed** with 0 meshes. Test-only mirror; never use as authority. |

**Bundling concern:** the camera repair carries an unrelated custom-figure asset-URL
change. The repair journey should separate these so a regression in one is not masked by
the other.

## 2. MOUNT / HYDRATION RACE (the current defect — NOT previously patched)

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| Async `create()` `.then` syncs stale mount closure | `PoseCraftWorkspace.tsx` ~1027–1038 | **PATCH (defective — root cause, independently confirmed)** | No re-sync when the controller becomes ready; whichever wins the race decides the rendered scene. Falsifiable probe: one scene mutation should snap in the 6 rigs. |
| `[scene]` sync effect no-ops while controller null | `PoseCraftWorkspace.tsx` ~1048 | **PATCH (defective)** | No readiness dependency; never re-runs because `scene` identity changes only once. |
| `setHistory(...)` then `setDocumentState(...)` in hydration | `PoseCraftWorkspace.tsx` ~902–921 | **LEGITIMATE** | Merge-not-overwrite intent is sound; the engine simply is not listening yet. |
| `globalThis.__posecraftController` mirror | `engine.ts` ~840 | **PATCH/DEBUG** | See §1. The disposed-vs-live claim is **not discriminated** by the 2-rig count (`dispose()` leaves `figureRigs` readable). |
| `lastSyncedCamera` camera guard | `engine.ts` ~1516 | **CANONICAL — EXONERATED** | Guards only the camera write; the figure loop (~1530) runs outside it. Not the cause of missing figures. |
| StrictMode double `create()` on one canvas | `PoseCraftWorkspace.tsx` ~1027–1044 | **PATCH-GAP (independent hazard)** | WebGPU double `configure()` + `device.destroy()` can break the second `initAsync()`; WebGL path never `detachControl()`. |

## 3. STATE / PERSISTENCE — GENERAL

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| `withRevision()` bumps on every mutation | `state.ts` ~45–51 | **LEGITIMATE (with side effect)** | Drives the Pose Intelligence re-analyze loop (Inspector flicker). Consider decoupling. |
| `currentDocument` useMemo on `[documentState, scene]` | `PoseCraftWorkspace.tsx` ~213 | **LEGITIMATE** | Recreates often; couples renders. |
| `migrateSceneToCurrent` (client + server) | `state.ts` ~108; `posecraft/service.py` | **COMPATIBILITY** | Idempotent schema normalizer; correct. |
| `legacyBlockModel: false` metadata | `engine.ts` ~406/485 | **COMPATIBILITY** | Honest capability label for the v4 rig; harmless. |
| `legacyJointData` retention | `types.ts` ~120; `state.ts` ~116–137 | **COMPATIBILITY** | Provenance for legacy joints; correct. |

## 4. FURNITURE / PRIMITIVES

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| `BlockingPrimitive` + `FurnitureKind` | `types.ts` ~146–185 | **CANONICAL** | Procedural staging furniture foundation. |
| `createPrimitiveRig` (box/table/wall builders) | `engine.ts` ~501–628 | **CANONICAL** | Real 3D primitive geometry. |
| `createFurniture` / `addFurnitureToScene` | `state.ts` ~218–240 | **CANONICAL** | Procedural, not imported assets. |
| Imported (GLB) furniture/objects | — | **MISSING** | See `POSECRAFT_OBJECT_IMPORT_ARCHITECTURE.md`. |

## 4b. RENDERING / ENGINE *[Rendering Bot]*

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| Grid lines built as 4-point `CreateLines` polylines | `engine.ts` ~786–793 | **CANONICAL-BUT-DEFECTIVE (pre-existing)** | `CreateLines` connects all four points → **17 diagonal streaks** across the floor. Since `2f2a338d`. Split into two 2-point lines. |
| Unused `gridMat` | `engine.ts` ~777–778 | **DEAD** | Created, colored, never assigned; grid lines set `line.color` directly. |
| `stage.showAxes` never read | `types.ts` ~211 / `state.ts` ~491 vs engine | **DISCONNECTED** | Axes always render; the flag is inert. |
| Unprotected `scene.render()` in render loop | `engine.ts` ~824–828 | **PATCH-GAP (pre-existing)** | No try/catch; one bad frame silently kills the rAF loop while the status pill stays green. |
| No `ResizeObserver` (window-resize only) | `engine.ts` ~829 / ~1487 | **PATCH-GAP** | Accordion/fullscreen/pane resizes can leave a stale backing store. |
| WebGPU→WebGL fallback `catch` | `engine.ts` ~720–733 | **CANONICAL** | Installs WebGL engine + records fallback detail; not a dead-canvas path. Edge: if WebGL *also* throws, the created WebGPUEngine is orphaned. |
| `containerCache` never cleared on dispose | `v4FigureLoader.ts` ~29 | **PATCH-GAP (remount hazard)** | Cache hits bound to the dead scene → figures vanish after tab-away/tab-back. `resetV4ContainerCacheForTests` has no production caller. |
| Custom figure marked `READY` before import | `engine.ts` ~452/455–457, ~435–437 | **PATCH-WORKAROUND (incomplete error path)** | Silent `console.error`; no visual ERROR event; `api.assetUrl` may be `""`. |
| **Custom-figure loader resolution BROKEN** | `engine.ts` ~418–437 + asset route `asset_file.py` ~142–144 | **DEFECT (reproduced)** | Dot-less `/file` URL → no plugin extension; HEAD sniff → **405** (FastAPI GET route has no HEAD). Mesh never renders; persistence works. See `POSECRAFT_OBJECT_IMPORT_ARCHITECTURE.md` §2a. |
| `.fbx` offered, loader never registered | `PoseCraftWorkspace.tsx` ~1440 vs `engine.ts` ~21–22 | **DEFECT (accepted-but-broken)** | Only OBJ + glTF loaders imported; FBX package present but unused. |
| `figure.scale` unvalidated | state/schema/engine ~1569 | **PATCH-GAP** | `scale: 0` → invisible figure the sanitizer still "frames". |
| `__posecraftController` never cleared on dispose | `engine.ts` ~840 | **DEBUG residue** | Stale global handle; see §6. |

## 5. STATE / PERSISTENCE / HYDRATION *[State/Regression Bot]*

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| `setHydrated(true)` in hydration **catch** | `PoseCraftWorkspace.tsx` ~945 | **PATCH / DEFECT** | Arms the debounced save while state still holds the **default** document → post-recovery PUT overwrites the creator's scene. Must split into `hydratedFromServer`. |
| Debounced-save gate on `hydrated` only | `:974–983` | **STALE guard design** | Cannot distinguish hydrated-from-server vs hydrated-from-failure. |
| Server `_empty_document()` on corrupt/unset JSON | `posecraft/service.py` ~130, 150–169 | **PATCH / DEFECT** | Silently returns a 0-figure scene; the next client PUT persists the emptiness. Distinguish "new project" from "corrupt". |
| localStorage scene SoT (`adept.posecraft.v1`) | `posecraft/storage.ts` | **DEAD** (tests only) | No production importer; keep only if tests need it, else retire. |
| `documentState.currentScene` duplicate | `PoseCraftWorkspace.tsx` ~217–218 | **DUPLICATED** (benign) | Always overridden by `history.present`; vestigial. |
| `selectedPrimitiveId` absent from server schema | `schemas.py` ~108–127 vs `types.ts` ~226 | **STALE contract drift** | Silently dropped on PUT → furniture selection lost on reload. |
| `worldOriginMeters` absent from server schema | same | **STALE contract drift** | Re-derived from Spatial Map at each load; never persists. |
| Spatial-Map origin import at hydration | `PoseCraftWorkspace.tsx` ~878–899 | **LEGITIMATE COMPATIBILITY (surprise)** | Figures standing at exactly `(0,0)` get repositioned on every load. |
| Co-Director `apply_tool_mutation` 409 gate | `service.py` ~472–490 | **CANONICAL** | Refuses to overwrite `creatorModified` scenes without approval. |

## 6. DEBUG INSTRUMENTATION

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| `globalThis.__posecraftController` | `engine.ts` ~840 | **PATCH/DEBUG** | Not race-safe under StrictMode; observed pointing at a disposed instance. Test-only. |
| `globalThis.__pcManipulate` counter | `PoseCraftWorkspace.tsx` ~792 | **PATCH/DEBUG** | Per-event global write; leftover diagnostics. |
| `globalThis.__posecraftDocument` | `PoseCraftWorkspace.tsx` ~1070–1072 | **PATCH/DEBUG** | No cleanup on unmount; minor. |

## 7. SNAPSHOT READBACK

| Item | Location | Class | Notes |
| --- | --- | --- | --- |
| `captureSnapshot()` / `captureCleanSnapshot()` → `canvas.toDataURL` | `engine.ts` ~1679, ~1725 | **PATCH RISK (unproven)** | WebGPU path is created **without `preserveDrawingBuffer`** (~723), so PNG readback may be blank on WebGPU. WebGL path sets it (~733/740). Flag for the repair journey. |

## 8. VERDICT

**PATCH / WORKAROUND CENSUS: complete.**
- The prior camera repair is **canonical and should survive** — with corrections: compare
  the raw `sceneDoc.camera` key (not the applied value); split the unrelated asset-URL
  change; consolidate the duplicated camera constants.
- The **current defect is unpatched** (mount/hydration race) — it is **not** a regression of
  the camera repair.
- Two further **proven defects** produce the same symptom: the API-down overwrite gate and
  the server `_empty_document()` fallback.
- No duplicated camera authority or blanket camera reset found.
- **Rendering census adds:** the grid diagonal defect (§4b), the unprotected render loop,
  the missing `ResizeObserver`, the disposed-scene `containerCache` hazard, the silent
  custom-figure error path, the dead `gridMat`, and the inert `stage.showAxes`. None of
  these is a masking workaround — they are honest pre-existing gaps.
- Debug globals (`__posecraftController`, `__pcManipulate`, `__posecraftDocument`) are
  PATCH/DEBUG artifacts and must **not** be treated as truth.
- **Repository-truth blocker:** the repair is uncommitted/untracked; clean checkout and
  hosted builds do not contain it.
