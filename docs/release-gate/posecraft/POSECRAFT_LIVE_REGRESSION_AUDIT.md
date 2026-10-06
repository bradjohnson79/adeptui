# PoseCraft Deep Stability + Regression Audit (AUDIT ONLY)

**Status:** GOVERNING AUDIT DOCUMENT — no repair performed.
**Date:** 2026-09-12
**Branch:** `feat/character-creator-final-closure` · **HEAD:** `99665cf7`
**Backup:** `.runtime/backups/posecraft-audit-20260912-145153/` (34 files, pre-investigation)
**Live project:** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` — "Korri Anadriya"
**Live route:** `http://127.0.0.1:5173/project/beffd3d8-…?workspace=posecraft`

**Verdict: AUDIT COMPLETE — ROOT CAUSES PROVEN — READY FOR CLEAN REPAIR JOURNEY**

> No production code was modified. PoseCraft was inspected read-only. ComfyUI `:8188`
> and Studio API `:8758` lifecycle were not touched. Runtime-only mutation probes were
> proposed but correctly rejected by safety review and were NOT performed.

---

## 1. LIVE SYMPTOM (REPRODUCED)

The PoseCraft shell loads, "WebGPU active" is shown, the Cast list is populated,
Pose Intelligence renders data — **but the 3D viewport renders the initial default
scene, not the persisted production scene.**

Reproduced deterministically on a clean reload (`browser_navigate`) and sampled every
600 ms for 8.4 s. The engine never left the default state:

| t (s) | live rigs | live meshes | live radius | doc figures |
| --- | --- | --- | --- | --- |
| 0.6 … 8.4 (all samples) | **2** | **136** | **7.5** | **6** |

- `globalThis.__posecraftController` → `disposed: true`, `scene.meshes.length === 0`
  (a dead controller; the debug global was clobbered by the StrictMode mount race).
- The **only non-disposed controller on the React fiber path** had `figureRigs.size === 2`.
- `globalThis.__posecraftDocument.currentScene.figures.length === 6`.
- Center pick test in the stuck state hit a **default placeholder mesh**
  (`figure-29970722-…-pick-rightUpperLeg`), not a persisted figure.
- Other picks hit `axis-y`, `posecraft-floor`, `grid-x--1` — confirming the **grid and
  floor are real Babylon 3D geometry**, not a 2D overlay.

The persisted scene (read from the live DB `data/studio.db`, read-only) is healthy:
6 figures, all `visible=true`, positions spread `x∈[-1.4, 2.6]`, and a **plausible**
camera (`radius 16`, `target (0,1.2,0)`, `alpha -π/2`, `beta 1.12`) — i.e. the
previous audit's corrupt camera signature is **gone**.

## 2. PREVIOUS AUDIT vs CURRENT CODE vs CURRENT LIVE STATE

| Aspect | Previous audit (2026-09-11) | Current code | Current live state |
| --- | --- | --- | --- |
| Root symptom | Figure off-frame speck | — | **Default scene rendered, persisted scene absent** |
| Camera | Corrupt: `target (4.262,1.2,-3.627)`, `radius 13.948` | `sanitizePersistedCamera()` present in `sync()` | Plausible: `target (0,1.2,0)`, `radius 16` |
| Camera repair | Not implemented | Implemented **uncommitted** (`engine.ts` M, `cameraPlausibility.ts`/`.test.ts` untracked) | Present and effective (no bogus sanitize on new signature) |
| Actual defect | Camera plausibility boundary | **Engine/hydration mount race** | Persisted scene never reaches the engine |
| Figures | 1 figure (Adult Male 1) | v4 GLB pipeline + 6 figures staged | 6 doc figures; engine shows 2 defaults |

**Consequence:** today's failure is **NOT** the previous camera defect. The prior
camera repair was neither overwritten nor bypassed — it simply addresses a different
boundary. A **new/independent** defect is proven below.

## 3. FIGURE PIPELINE TRACE (where it diverges)

```
Cast record ....................... OK (Cast list shows 6 figures with positions)
canonical figure state ............ OK (__posecraftDocument = 6 figures)
archetype specification ........... OK (FIGURE_ARCHETYPES)
GLB asset ......................... OK (v4 GLBs served; not the failing link)
loader / mesh / rig instance ...... OK (when sync runs, 342 meshes / 6 rigs build)
scene attachment .................. OK
transform ......................... OK
visibility ........................ OK (isVisible/isEnabled/matAlpha=1)
camera/frustum .................... OK (pick hits body at dist 15.0)
rendered pixels ................... **DIVERGENCE** — engine never receives the
                                    hydrated scene in the stuck state
```

**First broken transition: `hydrated state → PoseCraftViewportController.sync()`.**

## 4. ROOT CAUSE — PROVEN

**A viewport create/sync race renders the mount-time default scene instead of the
hydrated persisted scene, and nothing re-syncs when the controller becomes ready.**

Evidence + code:

`studio-web/src/components/GenerationTools/PoseCraftWorkspace.tsx`

- The controller is created **asynchronously** in an effect with deps `[]` (~line 1027):
  ```tsx
  PoseCraftViewportController.create(canvasRef.current)
    .then((controller) => {
      controllerRef.current = controller;      // becomes ready HERE (async)
      controller.sync(scene, scene.selectedFigureId);  // `scene` is the MOUNT-TIME closure
    })
  ```
- The reactive sync effect (~line 1048):
  ```tsx
  useEffect(() => { controllerRef.current?.sync(scene, scene.selectedFigureId); }, [scene]);
  ```
  React runs effects **bottom-up, after commit**. When hydration commits a new `scene`,
  this effect fires — but if `controllerRef.current` is still `null` (the async
  `create()` promise has not resolved), the call is a **no-op**. There is **no re-sync**
  when the controller later becomes ready; the only later sync is inside `.then`, using
  the **stale mount-time `scene` closure**.
- Whichever side of the race wins decides the rendered scene:
  - **create resolves before hydration commit** → `.then` syncs default scene; the
    later `[scene]` effect syncs the hydrated scene → correct.
  - **hydration commits before create resolves** → `[scene]` effect no-ops, `.then`
    syncs the **default** scene → **stuck empty-ish viewport** (the reproduced failure).
- `globalThis.__posecraftController = controller` is set inside `create()` and is **not
  race-safe**: under React **StrictMode** (`studio-web/src/main.tsx` wraps `<App/>`),
  effects run setup → cleanup → setup, so one `create()` resolves after its cleanup has
  `dispose()`d it. In one live sample the debug global pointed at a **disposed**
  controller (`scene.meshes.length === 0`). **Precision note (Independent Review):** the
  disposed-vs-live-stale distinction is **not discriminated by the 2-rig stuck state**,
  because `dispose()` never clears the `figureRigs` map, so a disposed controller also
  reports 2 rigs. The disposed global is a **real observation about the debug mirror**, but
  it does **not** by itself prove the stuck viewport was rendered by a disposed controller;
  the live probe is to read `controller.disposed` / `getFigureIds().length` and whether the
  intro overlay is showing.
  - **Independent second hazard (StrictMode):** double `create()` on **one canvas** is
    unsafe — WebGPU double `configure()` + `device.destroy()` from the first dispose can
    break the second `initAsync()` (→ intro overlay, empty viewport), and the WebGL path
    never calls `camera.detachControl()`. This is a separate way to reach an empty viewport
    and must be fixed (single-flight create / detach control on dispose).

**Non-determinism (decisive):** the same build produced BOTH outcomes in one session,
proving a race rather than a deterministic defect:

| Run | Trigger | Live rigs | Meshes | Radius | Doc figures | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | clean `browser_navigate` reload | **2** | 136 | 7.5 | 6 | **STUCK (default scene)** |
| 2 | route away (`home`) → back to PoseCraft | **6** | 343 | 16 | 6 | **CORRECT (persisted scene)** |

The route-reentry load applied the persisted camera (`radius 16`) and all 6 figures at
t ≈ 0.7 s and held them for 7 s. Same code, same document — only the create/hydration
interleaving differed. This is the signature of the ordering race above.

Additional contributing facts:
- Hydration calls `setDocumentState(...)` then `setHistory(...)` (~lines 902–921), but
  `scene = history.present` (line 212). `currentDocument` is a `useMemo` over
  `[documentState, scene]` (line 213) and **recreates on every document/scene change**.
- `withRevision()` bumps `scene.revision` on every mutation (`state.ts` ~line 48), so
  every camera commit / edit produces a brand-new `scene` identity.

## 5. CONTRIBUTING DEFECTS (reconciled with specialist subagents)

1. **No readiness re-sync — INDEPENDENTLY CONFIRMED (HIGH confidence).** The async
   `create().then` (`PoseCraftWorkspace.tsx` ~1030–1037) executes with deps `[]`, so it
   **permanently captures the render-1 `scene`** (= `initialDocument.currentScene`, the
   2-figure `createDefaultScene`). The `[scene]` sync effect (~1048) *does* fire on
   hydration but **no-ops** because `controllerRef.current` is still `null` (assigned only
   after the awaited `create()`), and it **never runs again** because `scene` identity
   changes only once. Smoking gun: `__posecraftDocument` correctly shows **6** figures
   while the engine renders **2** — a strict **state → engine** desync, not persistence.
   *Falsifiable probe for the repair journey (not run — it mutates state):* with the bad
   state loaded, trigger one scene mutation (select a figure / press Delete); if the 6 rigs
   appear on that single click, the stale-closure diagnosis is confirmed outright.
2. **StrictMode / engine-lifecycle hazards.** Two distinct issues, one observed and one
   independent:
   - *Observed directly:* `globalThis.__posecraftController` pointed at a **disposed**
     instance with 0 meshes while the live controller (via React fiber) was healthy.
   - *Correction (Independent Review):* the **2-rig stuck state does NOT discriminate**
     disposed-vs-live-stale, because `dispose()` (`engine.ts` ~1744) never clears the
     `figureRigs` map — a disposed controller still reports 2 rigs. Both variants produce
     the same numbers; do not attribute the stuck viewport to disposal alone.
   - *Independent second defect:* StrictMode double-`create()` on **one canvas** is
     unsafe — WebGPU double `configure()` + `device.destroy()` from the first dispose can
     break the second `initAsync()` (→ intro overlay, empty viewport), and the WebGL path
     never calls `camera.detachControl()`. This is a separate way to get an empty viewport
     and must be fixed (single-flight create / detach control on dispose).
   - **`lastSyncedCamera` is EXONERATED:** it guards only the **camera write**; the figure
     reconciliation loop (~1530) runs **outside** the guard on every `sync()`. It cannot
     withhold rigs and is not a contributing cause.
3. **API-down overwrite vector — INDEPENDENT DATA-LOSS DEFECT (code-proven).** In the
   hydration catch (`PoseCraftWorkspace.tsx` ~941–946) `setHydrated(true)` runs while React
   state still holds the **default document**. The debounced-save effect (~974–983) is
   gated **only on `hydrated`**, so 600 ms later it PUTs the **default** document. If the
   API is still down the PUT fails (saved by the outage); but once the watchdog revives the
   API, the **next** state change (accordion toggle, selection, camera commit, inspector
   blur) re-arms the debounced save and **overwrites the creator's persisted scene with
   defaults** — yielding a **default 2-figure (Lead/Partner) scene**, the same outward
   shape as the mount race. The gate cannot distinguish "hydrated from server" from
   "hydrated from failure".
4. **Server empty-document fallback.** `posecraft/service.py` `load_scene()` returns
   `_empty_document()` when `posecraft_document_json` is empty, corrupt, or fails
   validation — a **0-figure** scene (floor/grid/axes only). Its camera is the plausible
   default, so the plausibility repair cannot address it.
5. **Repair not committed (repository-truth blocker).** The camera repair (`engine.ts`
   modified; `cameraPlausibility.ts`/`.test.ts` untracked) lives **only in the working
   tree**. A clean checkout, hosted build, or stale bundle does **not** contain it — so the
   empty viewport can legitimately reappear on those surfaces.
6. **Uncaught `scene.render()` kills the render loop permanently.** The loop
   (`engine.ts` ~824–828) has a `disposed` guard but **no try/catch**. In Babylon an
   exception thrown in the render callback breaks the rAF chain — **one bad frame leaves a
   frozen/blank canvas forever while the "WebGPU active" pill (set once at mount) stays
   green**. This is a genuine *empty-viewport-with-healthy-engine* signature.
7. **No `ResizeObserver` on the canvas.** `engine.resize()` fires only on **window**
   resize (`engine.ts` ~829). Accordion toggles / fullscreen / pane-layout changes resize
   the canvas via CSS without notifying Babylon; a stale/0×0 backing store renders nothing
   while the engine stays healthy.
8. **`containerCache` remount hazard (figures vanish, floor intact).** The module-level
   `containerCache` (`v4FigureLoader.ts` ~29) is **never cleared on `dispose()`**, so the
   cached `AssetContainer`s stay bound to the dead scene/engine. After tab-away → tab-back,
   `attachV4Figure` gets a **cache hit against the disposed scene** → figures
   broken/invisible **while floor/grid still render**. `resetV4ContainerCacheForTests`
   exists but no production code calls it. This precisely matches "figures not visible but
   stage present".
9. **Grid diagonal artifacts (literal "grid not rendering correctly").** Each of the 17
   grid meshes is a `CreateLines` **polyline built from four points** (`engine.ts`
   ~786–793): two points form the intended X-parallel line, then two more form the
   Z-parallel line — but `CreateLines` connects them, so **every grid line draws a long
   diagonal segment** from `(index, 8)` to `(-8, index)`. 17 diagonal streaks across the
   floor, present since `2f2a338d` (not from the camera repair) and live right now. The
   grid is still **real 3D geometry** (pick-proven) — it is simply defective.
10. **Custom figure import is BROKEN END-TO-END — mesh never renders (reproduced).** The
    asset URL ends in `/file` with no dot, so Babylon cannot resolve a loader plugin;
    its HEAD `Content-Type` fallback then gets **405** because the asset route is GET-only
    and FastAPI does not add HEAD for GET. (OBJ cannot be rescued by MIME either.) The
    upload/persistence half works — persistence ≠ rendering. Compounded by
    `visualState:"READY"` set **before** the import resolves (`engine.ts` ~452) and a
    console-only `onError`, so the failure is invisible to the creator. **This is the
    reusable loader layer future object import depends on, so repair it first.** Details:
    `POSECRAFT_OBJECT_IMPORT_ARCHITECTURE.md` §2a.
11. **`figure.scale` unvalidated end-to-end.** No range check client or server; a persisted
    `scale: 0` renders an invisible figure that the camera sanitizer still "frames".
12. **WebGPU snapshot readback risk.** `captureSnapshot()` / `captureCleanSnapshot()` use
    `canvas.toDataURL("image/png")` (engine.ts ~1679, 1725), but the `WebGPUEngine` is
    created **without `preserveDrawingBuffer`** (~723). Snapshot PNGs may be blank on
    WebGPU.
13. **Right Inspector flicker** — separate rerender-cascade defect; see
    `POSECRAFT_INSPECTOR_FLICKER.md`.

> **Which cause was today's symptom?** Live evidence shows `__posecraftDocument` held
> **6** figures in the stuck state (the GET succeeded), so the reproduced stuck viewport is
> the **mount/hydration race (Defect 1)**. Defects 3–5 are independent, code-proven
> vectors that produce the same "my scene is gone / blank viewport" symptom, especially
> during the API-down window observed this session. **Defects 6–8 are the
> "empty-viewport-with-healthy-engine" signatures** (loop death, stale backing store,
> disposed-scene asset cache), Defect 9 is the literal cause of the reported **grid**
> symptom, and **Defect 10 is a separately reproduced breakage of Custom Figure import**
> (an archetype scene is unaffected, which is why the 6 standard figures still render).
> Repair the race **and** close these gaps.
>
> **Independent review:** Defect 1 was **independently confirmed (HIGH confidence)**. No
> specialist disputed the state→engine desync. Two sub-claims were **corrected/limited**:
> the "disposed controller" story is not discriminated by the 2-rig count, and
> `lastSyncedCamera` is **exonerated** (it guards only the camera write; the figure loop
> runs outside it). Independent review *added* the StrictMode double-`create()`-on-one-canvas
> hazard (Defect 2) and refined the flicker ranking (the per-frame **label RAF** is the
> dominant driver when Labels are on — the analysis-effect stutter is secondary). The
> asset/object audit **reproduced** the custom-import loader defect (Defect 10).

## 6. PERFORMANCE + LIFECYCLE (measured)

In the healthy (route-reentry) state:

| Metric | Value |
| --- | --- |
| Engine FPS | **60** (start and end of a 3 s sample) |
| Engine/scene count | **1 engine / 1 scene** (no duplicate engines) |
| Scene meshes | 343 |
| Active meshes / draw calls | 142 |
| Figure rigs / primitive rigs | 6 / 0 |
| Materials / transform nodes / textures | 158 / 117 / 1 |
| Skeletons | 0 (v4 rig is TransformNode-based) |
| DOM mutations (idle right pane, 6 s) | 0 |

`dispose()` (engine.ts ~1745) correctly clears the wheel-commit timer, removes pointer +
resize listeners, stops the render loop, and disposes scene + engine — so route-away
disposal is sound; the second entry rebuilt a fresh, correct engine.

## 7. WORKING SYSTEMS (DO NOT REBUILD)

- Babylon renderer selection + WebGPU/WebGL fallback, device init, render loop,
  resize (engine `create()` ~715–850).
- v4 GLB pipeline (`v4FigureLoader` → `attachV4Figure`), 17-joint rig, region bind,
  pick colliders, tint/highlight; archetype specs.
- Figure rig construction/mutation (`createFigureRig`, `sync()` figure loop ~1540–1595).
- Floor / grid / axes as **real 3D geometry** (engine ~773–816) — confirmed by pick.
  *(The grid's diagonal-streak defect (§5.9) is a fix, not a rebuild: split the 4-point
  polyline into two 2-point `CreateLines`, and drop the unused `gridMat` at ~777.)*
- Gizmos, pose ring, picking, gamepad-free camera orbit.
- Persistence + migration (`state.ts`, `posecraft_slice.py`, `posecraft/service.py`);
  the persisted 6-figure scene is intact in `data/studio.db`.
- Camera plausibility module (`cameraPlausibility.ts`) — pure, unit-testable, and the
  current persisted camera classifies **valid** (verified by arithmetic).
- Pose Intelligence backend (reads canonical joint/pose state, not meshes).

## 8. REPAIR SURFACE (describe only — NOT implemented)

- **Primary (mount race):** `PoseCraftWorkspace.tsx` ~1027–1046 — make the create
  effect re-sync the **latest** scene via `sceneRef.current` / a `ready` flag; keep the
  reactive `[scene]` sync (~1048) and add a controller-ready dependency so the first sync
  after readiness uses current state.
- **StrictMode canvas safety:** make `create()` single-flight (or reuse an existing
  controller) and call `camera.detachControl()` on dispose, so a double-invoked create on
  one canvas cannot destroy the surviving device / leave inputs attached.
- **API-down overwrite:** split the `hydrated` gate into `hydratedFromServer` (only this
  arms autosave / flush). Never PUT a document that came from a **failed** GET. Surface a
  clear "scene not loaded — changes will not be saved" state instead.
- **Server fallback:** distinguish "new project (no document)" from "corrupt document".
  Do not silently return an empty scene for corrupt bytes — preserve the original and
  fail loudly (or serve the last good revision).
- **Commit the repair** so clean checkout / hosted builds contain it.
- **`engine.ts` `create()`:** set `globalThis.__posecraftController` only for the live
  instance (guard on `disposed`), or set it from the React layer after StrictMode settles.
- **Flicker:** decouple Pose Intelligence from `scene.revision` (key it on pose-relevant
  state); isolate it so its status change does not rerender the whole workspace; memoize
  the right-pane accordions. See `POSECRAFT_INSPECTOR_FLICKER.md`.
- **Constants:** consolidate the duplicated camera framing/limits to one pure module
  (see `POSECRAFT_CAMERA_ZOOM_AUDIT.md` §6).
- **Grid defect:** split each 4-point `CreateLines` into two 2-point lines (engine ~786–793);
  remove the dead `gridMat` (~777); wire `stage.showAxes`.
- **Render-loop resilience:** wrap `scene.render()` in a try/catch (or a bounded
  error-count guard) so one bad frame cannot silently kill the loop (`engine.ts` ~824–828).
- **Canvas sizing:** add a `ResizeObserver` on the canvas (or a container observer) calling
  `engine.resize()`, so accordion/fullscreen/pane changes cannot leave a stale backing store.
- **Asset cache on remount:** clear `containerCache` (or use `scene`-keyed cache entries) in
  `dispose()` — figures vanish after tab-away/tab-back otherwise (`v4FigureLoader.ts` ~29).
- **Custom-figure honesty:** do not set `visualState:"READY"` before the import resolves;
  emit a visual ERROR event (reuse the v4 path's event) and guard against an empty
  `api.assetUrl()`.
- **Custom-figure import (broken):** fix loader resolution — pass an explicit
  `pluginExtension` from the stored filename (do not rely on the dot-less `/file` URL or
  MIME), and make the asset route answer HEAD (or bypass the HEAD probe). Offer only
  formats with a registered loader (remove `.fbx` or register the FBX loader). See
  `POSECRAFT_OBJECT_IMPORT_ARCHITECTURE.md` §2a.
- **Scale validation:** clamp/validate `figure.scale` client + server so `scale: 0`
  cannot render an invisible figure.
- Optional: `captureCleanSnapshot()` WebGPU readback (only if snapshots are in scope).

## 8. RISK

- A naïve fix (e.g. always sync on a timer, or reset camera on every load) risks
  regressing legitimate saved framings and the lastSyncedCamera orbit protection.
- The fix must distinguish **"controller became ready"** (sync latest state once) from
  **"user is orbiting"** (never stomp). The `lastSyncedCamera` guard must remain intact.

---

## 9. AUDIT PANEL — SPECIALIST FINDINGS RECONCILED

Four read-only specialist audits (+ the primary's live investigation) were reconciled into
these deliverables:

| Auditor | Key contribution |
| --- | --- |
| Primary (live) | Reproduced the non-deterministic race; proved grid/floor are real 3D; proved figures render when hydration wins; 60 FPS / 1 engine; performed the pixel + pick evidence. |
| Rendering | Confirmed floor/grid/axes are unconditional real geometry and that **no code path yields a fully empty viewport**; found the **grid diagonal-streak defect** (4-point `CreateLines`), the **unprotected `scene.render()`** loop-death gap, the **missing `ResizeObserver`**, the **`containerCache` remount hazard**, **custom figures marked READY before import**, and **unvalidated `figure.scale`**. |
| State / Regression | Proved the **API-down overwrite vector** (`setHydrated(true)` after a failed GET + `hydrated`-only save gate) and the **server `_empty_document()`** 0-figure fallback; flagged the **repair as uncommitted** (clean-clone/hosted blocker); re-verified the plausibility arithmetic (corrupt revision-13 camera → drift 6.727 > reach 5.52 → implausible; valid camera preserved); found `selectedPrimitiveId`/`worldOriginMeters` schema drift. |
| Camera | Quantified deep-zoom blockers (`lowerRadiusLimit 2.2` needs ~0.47 m; `minZ 1` clips below ~1.1 m); proved the orbit-echo/sanitize loop **converges in 2 passes, one PUT**; flagged the **duplicated camera constants** (stale-limits trap) and the `panningSensibility 70` over-sensitivity. |
| UI Stability | Proved the flicker is a **rerender cascade** (camera-commit echo → unmemoized 7-panel repaint; `scene.revision`-driven Pose Intelligence POST); no `setInterval`/observers; StrictMode lifecycle is clean; no unbounded loop. |
| Asset / Object Import | **Reproduced the custom-figure import failure end-to-end** (upload/persist work; mesh never renders — dot-less `/file` URL defeats plugin resolution, HEAD sniff 405 on a GET-only FastAPI route); traced all format support (FBX offered but unloadable); found the **asset delete-guard gap**; inventoried the procedural furniture + semantic-object layer; produced the parallel `PoseCraftObject` architecture (no SQL migration). |
| **Independent Review** | **Independently CONFIRMED the root cause (HIGH confidence)** via the `__posecraftDocument`=6 vs engine=2 divergence; supplied the exact React 19 effect ordering; **corrected** the disposed-controller sub-claim (not discriminated by rig count); **exonerated `lastSyncedCamera`** (figure loop runs outside the guard); **added** the StrictMode double-`create()`-on-one-canvas hazard; verified the eval'd `panningSensibility`/`minZ` behavior against Babylon source; ranked the flicker with the label RAF dominant when Labels are on. |

**No specialist disputed the state→engine root cause.** The Rendering and State/Regression
audits supplied additional *independent* vectors (grid defect; render-loop death; stale
backing store; disposed-scene asset cache; API-down overwrite; empty-document fallback) to
close alongside the race; Independent Review tightened the reasoning and added the
StrictMode canvas hazard.

## REQUIRED VERDICTS

| Area | Verdict |
| --- | --- |
| WEBGPU RENDERER HEALTH | **HEALTHY** — real WebGPUEngine, device up, frames advancing (~60fps) |
| WEBGL FALLBACK HEALTH | **NOT DIRECTLY EXERCISED** — fallback branch present; WebGPU took precedence |
| SCENE GRAPH | **PARTIAL/INCORRECT IN STUCK STATE** — default 2 rigs/136 meshes vs doc 6; correct (6/342) on a good mount |
| 3D GRID / FLOOR | **REAL 3D GEOMETRY, BUT GRID DEFECTIVE** — verified by pick (`grid-x--1`, `posecraft-floor`, `axis-y`); however every grid line is a 4-point polyline that draws 17 **diagonal streaks** (§5.9); unused `gridMat` dead; `stage.showAxes` never read |
| RENDER LOOP RESILIENCE | **GAP** — loop alive (60fps) but `scene.render()` has no try/catch; one exception can permanently freeze the canvas while the status pill stays green |
| CANVAS SIZING | **GAP** — no `ResizeObserver`; only window resize calls `engine.resize()` |
| ASSET CACHE / REMOUNT | **PATCH-GAP** — module-level `containerCache` never cleared on `dispose()`; figures can vanish after tab-away/tab-back while floor/grid render |
| FIGURE ASSET LOADING | **HEALTHY** — v4 GLBs load; rigs READY with real meshes |
| FIGURE SCENE ATTACHMENT | **HEALTHY WHEN SYNC RUNS** — 342 meshes / 6 rigs |
| FIGURE VISIBILITY | **HEALTHY** — `isVisible/isEnabled`, `matAlpha=1`, in-frustum, pick hits body; **custom figures** marked READY before import resolves (silent-failure divergence) |
| CAMERA HYDRATION | **DEFECTIVE (race)** — hydrated camera reaches engine only if create wins race |
| CAMERA AUTHORITY | **SINGLE CANONICAL WRITER (sync) + orbit/UI writers**; orbit-echo loop proven to converge in 2 passes (self-terminating, one PUT); `lastSyncedCamera` **exonerated** (guards camera only; figure loop runs outside it); two **duplicate constants** to consolidate; see `POSECRAFT_AUTHORITY_MAP.md` |
| PREVIOUS CAMERA REPAIR | **PRESENT, EFFECTIVE, NOT BYPASSED — BUT UNCOMMITTED** (clean-clone/hosted blocker); plausibility arithmetic re-verified (corrupt revision-13 camera → drift 6.727 > reach 5.52 → classified implausible; valid current camera preserved) |
| CAMERA CONSTANTS | **DUPLICATED AUTHORITY** — framing + radius limits copied in 3/2 places; must consolidate before deep-zoom work |
| RIGHT INSPECTOR FLICKER | **ROOT CAUSE IDENTIFIED (code-level)** — rerender cascade; see `POSECRAFT_INSPECTOR_FLICKER.md` |
| POSE INTELLIGENCE | **HEALTHY** — reads canonical pose state (intentional); contributes to flicker via `scene.revision` dep |
| API-DOWN OVERWRITE | **DEFECT PROVEN** — failed GET + `hydrated=true` can PUT defaults over the creator scene |
| SERVER EMPTY-DOC FALLBACK | **DEFECT PROVEN** — corrupt/unset document silently returns 0-figure scene |
| SAVE / RELOAD | **DEFECTIVE (non-deterministic)** — reload can show defaults/blank instead of saved scene |
| ROUTE REENTRY | **WORKED THIS RUN (6 rigs/radius 16); AT RISK** — same create/hydration race applies on re-mount |
| PERFORMANCE | **HEALTHY** — 60 FPS, 1 engine/scene, 142 draw calls, 0 idle right-pane mutations |
| DEEP ZOOM FEASIBILITY | **FEASIBLE WITH CHANGES** — see `POSECRAFT_CAMERA_ZOOM_AUDIT.md` |
| CUSTOM FIGURE IMPORT | **BROKEN (rendering) — reproduced** — upload/persistence work, but the mesh never renders (dot-less `/file` URL defeats plugin resolution; HEAD sniff gets 405 on a GET-only route); `.fbx` offered with no loader; failure is console-only. See `POSECRAFT_OBJECT_IMPORT_ARCHITECTURE.md` §2a |
| 3D OBJECT/FURNITURE IMPORT FEASIBILITY | **PARTIAL FOUNDATION** — see `POSECRAFT_OBJECT_IMPORT_ARCHITECTURE.md` |
| PATCH / WORKAROUND CENSUS | see `POSECRAFT_PATCH_CENSUS.md` |

**FINAL VERDICT: AUDIT COMPLETE — ROOT CAUSES PROVEN — READY FOR CLEAN REPAIR JOURNEY**
