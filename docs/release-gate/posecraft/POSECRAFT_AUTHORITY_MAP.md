# PoseCraft Authority Map (state / camera / render)

**Status:** AUDIT DELIVERABLE B · read-only · 2026-09-12
**Scope:** who owns PoseCraft state, camera, and rendering — and which writers compete.

---

## 1. STATE AUTHORITY

| Layer | File | Authority |
| --- | --- | --- |
| Canonical scene | Project API `GET/PUT /api/posecraft/projects/{id}/scene` | **SoT** (server) |
| Server doc | `data/studio.db` → `projects.posecraft_document_json` | **SoT** (persisted bytes) |
| Client working copy | `history.present` in `PoseCraftWorkspace.tsx` (~line 137) | Session authority |
| Document wrapper | `documentState` + `useMemo currentDocument` (~210–213) | Derived (recreated often) |
| Migration | `state.ts migrateSceneToCurrent`, service `migrate_scene_to_current` | Idempotent normalizer |
| localStorage | favorites only (`adept.posecraft.favorites`) | **Not** SoT (correct) |

`withRevision()` (`state.ts` ~48) bumps `revision` and `updatedAt` on **every** mutation
— so every edit/camera-commit yields a new `scene` object identity. This is what makes
the `[scene]` effect fire frequently (and, combined with the create race, is central to
the viewport defect).

## 2. CAMERA AUTHORITY

| # | Writer | When it fires | Canonical? | Can overwrite user camera? |
| --- | --- | --- | --- | --- |
| 1 | `createDefaultCamera()` (`state.ts` ~262–271) | mount seed | Yes (seed) | Initial only |
| 2 | Hard-coded `engine.ts` ctor defaults (~751–758) | controller create | **No — duplicate engine default** | Yes, on create |
| 3 | Limits + `wheelDeltaPercentage`/`panningSensibility` (~760–763) | create | mirror of state limits | Limits only |
| 4 | `sync()` camera block (~1515–1527) | when `JSON.stringify(sceneDoc.camera) !== lastSyncedCamera` | **Canonical restore** | Yes — on a NEW camera value |
| 5 | `sanitizePersistedCamera` → `emitCameraCommit` (~1516–1526) | new + implausible camera | Yes (repair) | Yes, by design |
| 6 | `sync()` `this.camera.fov = lensToFov(...)` (~1528) | **every** `sync()`, **unguarded** | Yes | Rewrites fov unconditionally |
| 7 | Live orbit / pan (`attachControl`, ~758) | pointer drag | Live authority | n/a (the user) |
| 8 | Wheel zoom | wheel | Live | Live wins until commit |
| 9 | `scheduleCameraCommit()` / `emitCameraCommit()` (~1104–1113) | after 400 ms wheel/pointer-up debounce | **Writes back to state** | Commits live → state |
| 10 | `Use View` (~1115–1120) | creator click | Yes | **Yes** — replaces saved camera |
| 11 | `Restore Camera View` (~684–693) | creator click | Yes | **Yes** — overwrites saved camera |
| 12 | Snapshot capture (~1678; `state.ts` ~599–630) | capture | copy only | No |
| 13 | Lens presets / Aspect (~1927–1938) | creator click/change | Yes | lens / aspect only |
| 14 | Distance / Orbit / Lift inputs (~1942–1953) | creator input | Yes | Yes; radius clamped by Babylon `_checkInputs` |
| 15 | Guides checkboxes (~1958–1962) | creator change | Yes | guides only |
| 16 | `updateCamera` (`state.ts` ~478–488) | all of the above | Yes | Yes |
| 17 | Resize (~828–829, ~1484–1488) | window resize | No | No (render size only) |
| 18 | `updateAdaptiveVisuals` (~988–1016) | every frame | No | Reads radius; writes gizmos only |

**Findings**

- **Single canonical camera restorer is `sync()`** — good architecture (preferred over
  per-mode duplicate camera state). No separate inpaint/theater camera exists.
- **Two duplicate authorities (must consolidate):**
  1. Hard-coded `engine.ts` ctor defaults (~751–758) duplicate `state.ts` ~262–271 — two
     copies of the same numbers. They are currently identical, which is exactly why the
     first `sync()` camera write is a **no-op** and the engine default always survives.
  2. `CAMERA_RADIUS_LIMITS` (`cameraPlausibility.ts` ~26) manually mirrors `engine.ts`
     ~760–761; `buildSafeCamera` clamps to `[2.7, 15]`, so any sanitized camera can never
     be a close-up. Changing zoom limits in one file silently desynchronizes the others.
- **`engine.ts` ~1528 (fov) is an unguarded state→engine write**, alongside unguarded
  `selectedFigureId` / `currentFigures` writes (~1491–1492).
- **`lastSyncedCamera` compares `JSON.stringify(camera)`** (~689, 1516, 1518). Because
  writers #4 and #9 both round-trip through state, a plausible orbit echo is a no-op — by
  design. **Independent review confirmed the figure reconciliation loop (~1530) runs
  *outside* this guard**, so the guard cannot withhold rigs — it is not the cause of the
  empty viewport.
- **Ordering hazard:** `lastSyncedCamera` is set to the **sanitized** JSON while
  `sceneDoc.camera` keeps the original bytes. If the sanitize-write-back is not applied to
  state, the next `sync()` re-sanitizes and re-emits a camera commit. Independent review
  and the UI-stability audit both find the write-back **is** applied in normal operation,
  so it converges in 2 passes (one redundant PUT) — a latent risk, not the current defect.
- **Feedback-loop check:** `emitCameraCommit` → `mutateScene(updateCamera)` → new `scene` →
  `[scene]` effect → `sync()` → key now equals the live camera → written once,
  `lastSyncedCamera` updated → **stop. No runaway state→engine→state loop.** During a live
  orbit the state camera is unchanged, so the key is unchanged and `sync()` cannot snap the
  view away — the guard working as designed.

## 3. RENDER AUTHORITY

| Concern | Owner | Notes |
| --- | --- | --- |
| Renderer selection | `create()` (~717–741) | WebGPU if `navigator.gpu`, else WebGL |
| Engine instance | `PoseCraftViewportController.engine` | 1 per controller |
| Scene | `PoseCraftViewportController.scene` | 1 per controller |
| Render loop | `engine.runRenderLoop(() => scene.render())` (~824) | Healthy (~60fps) |
| Per-frame adaptive visuals | `scene.onBeforeRenderObservable` → `updateAdaptiveVisuals()` (~833) | Sized by camera distance |
| Floor/grid/axes | `create()` (~773–816) | **Real 3D geometry** |
| Figure rigs | `figureRigs` Map | Driven by `sync()` |
| Primitive (furniture) rigs | `primitiveRigs` Map | Driven by `sync()` |
| Labels | `getLabelScreenPositions()` + React rAF | DOM overlay |
| Gizmos / pose ring | `moveGizmo` / `rotateGizmo` / `poseRing` | Enabled/disabled per mode |
| Snapshot PNG | `captureCleanSnapshot()` → `canvas.toDataURL` | **WebGPU `preserveDrawingBuffer` risk** |

**Findings**

- Only **one live engine/scene** is expected; the live audit found exactly one
  non-disposed controller on the fiber path (`engineScenes: 1`).
- `globalThis.__posecraftController` is **not** an authority — it is a debug mirror and
  currently points at a **disposed** controller under StrictMode. It must never be used
  as a source of truth.
- The create→sync race (regression audit §4) means render authority can be driven by a
  **stale scene snapshot**; the render pipeline itself is healthy.

## 4. FEEDBACK-LOOP RISK MAP

| Loop | Path | Risk |
| --- | --- | --- |
| Camera echo | orbit → emitCameraCommit → updateCamera → sync (no-op echo) | LOW (guard) |
| Sanitize write-back | sync → sanitize → emit → state → sync | LOW (emit writes sanitized values to state; recurs only if write-back is dropped) |
| Pose analyze | `scene.revision` / `selectedFigureId` → debounce 900 ms → POST analyze | MED (Inspector) |
| Label rAF | rAF → `setViewportLabels` → render | MED (flicker) |
| Autosave | `currentDocument` change → debounce 600 ms → PUT | LOW |

See `POSECRAFT_INSPECTOR_FLICKER.md` and `POSECRAFT_PATCH_CENSUS.md`.
