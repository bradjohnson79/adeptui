# PoseCraft Inspector Flicker — Root-Cause Analysis

**Status:** AUDIT DELIVERABLE D · read-only · 2026-09-12
**Symptom:** Right Inspector pane visibly flickers / repaints.

---

## 1. MEASURED BASELINE

- Idle, steady state (6-figure scene, menu untouched): **0 DOM mutations in the right
  pane over 6 s** (`MutationObserver` on `.posecraft-pane--right`, attributes
  `class/style/data-testid/aria-expanded` + subtree). So the flicker is **not** a
  continuous loop; it is **event/condition triggered**.

## 2. ROOT CAUSE — RERENDER-CASCADE CHURN (ranked)

The flicker is a **rerender-cascade**, not a loop. `PoseCraftWorkspace` holds ~40
`useState` hooks and **no panel is memoized**, so any single state change rerenders all
7 right-pane accordions + left pane + header. Ranked drivers:

**1. Per-frame label RAF → whole-component re-render (HIGH — dominant when Labels are ON).**
Effect (~1053–1066) runs a `requestAnimationFrame` loop that calls
`getLabelScreenPositions(scene)` — which returns a **brand-new array of new objects every
frame** — and `setViewportLabels(...)` commits it **~60×/s**, reconciling the entire
workspace (both panes, inspector, every snapshot `<img loading="lazy">`) with fresh object
identities. This is the only true per-frame setState. It is **dormant by default**
(`stage.showLabels: false`), so it is not today's idle symptom — but it is the largest
flicker source when the creator toggles Labels on, and must be throttled/deduped.

**2. Camera-commit echo chain (HIGH — dominant during interaction).**
`engine.ts` orbit/wheel → `emitCameraCommit()` → `mutateScene(updateCamera(...))` →
`withRevision` (`revision + 1`) → new `scene` → **full-workspace rerender**, including the
Camera accordion number inputs repainting. ~2.5 repaints/s while orbiting (400 ms debounce).

**3. Pose Intelligence analyze effect (HIGH — stutter on every edit).**
Effect (~961–970) keyed on `scene.revision` + `scene.selectedFigureId` → 900 ms debounce →
POST → `poseIntelStatus` flips `idle→analyzing→ready / unavailable`, swapping panel content.
`withRevision` bumps `revision` on **every** mutation (including camera orbit/zoom), so each
edit resets the debounce and flips the panel. Not per-frame; **stutter on every edit**. On
API-down each attempt fails → status flips to unavailable → visible text swap.

**4. Status-message churn (MEDIUM).** `setStatusMessage` on every move/rotate/pose/select
and on save failure — one more full rerender each.

**5. Autosave timer churn (LOW — traffic).** The save effect (~974–983) depends on
`currentDocument`, which is a new object whenever `documentState` or `scene` changes, so
every mutation clears/restarts the 600 ms timer. Request churn, not direct flicker.

## 3. THE NEW `emitCameraCommit`-IN-`sync()` — BOUNDED (verified)

The repair's sanitize path adds **one guaranteed extra full rerender per load** when a
corrupt camera is sanitized (visible as a one-shot flicker), and **not** a loop:

- Pass 1: `sync()` sees a new `cameraKey` → `sanitizePersistedCamera` → implausible →
  apply safe camera → `lastSyncedCamera = JSON.stringify(applied)` → `emitCameraCommit()`
  (synchronous) → state updated with the safe camera.
- Pass 2: React re-renders; the `[scene]` effect re-syncs with the **mutated** scene
  (never the stale corrupt bytes). Keys match (or differ only by the intentional
  `toFixed(3)` target rounding, which re-sanitizes to **plausible**, `sanitized=false`) →
  **no emit** → `lastSyncedCamera` converges.
- **Result: 2 passes, one extra revision bump, one 600 ms-debounced PUT, no PUT spam, no
  infinite loop.** `buildSafeCamera`'s output is a guaranteed plausible fixed point.

*(Residual: the plausibility gate also runs on in-session camera-key changes, so a creator
who pans the target far from every figure can be silently re-framed and persisted — see
`POSECRAFT_AUTHORITY_MAP.md`.)*

## 4. RULED OUT (with evidence)

| Candidate | Verdict | Evidence |
| --- | --- | --- |
| Per-frame `onBeforeRenderObservable` → React | **NO** | Only mutates Babylon scalings (`updateAdaptiveVisuals`); never setState. |
| `setInterval` polling | **NONE** | No `setInterval` in PoseCraft; timers are debounces only. |
| `ResizeObserver` / `MutationObserver` layout loop | **NONE** | No such observers; **0 idle right-pane mutations over 6 s**. |
| Unstable React keys | **NONE** | All lists key by stable ids (figure/pose/snapshot/version/guide). |
| CSS animations | **NONE** | No `@keyframes`; one hover-only transition on the divider. |
| Lifecycle leaks (StrictMode) | **NONE** | Engine create/dispose is `cancelled`-guarded; all effects clean up except two harmless window globals. |

## 5. REPAIR SURFACE (describe only — NOT implemented)

- **Memoize / state-scope the right-pane accordions** so one state change does not repaint
  all seven panels (largest single win).
- **Decouple Pose Intelligence from `scene.revision`.** Key it on pose-relevant state
  (figure id + joint rotations hash) instead of the global revision counter, so camera
  commits do not trigger analysis; don't flip to `analyzing` when nothing pose-relevant
  changed.
- **Isolate Pose Intelligence** into its own component so its status swap does not rerender
  the whole workspace.
- **Stop bumping `revision` for pure camera commits**, or exclude camera-only changes from
  the analyze deps.
- Avoid unnecessary `setStatusMessage` calls (silent camera commits already are silent).
- Gate/limit the per-frame RAF label loop (only when Labels is on; project incrementally).
- Make the camera key compare only the fields `readCameraState()` writes.

## 6. VERDICT

**RIGHT INSPECTOR FLICKER: ROOT CAUSE IDENTIFIED (code-level) —**
a rerender-cascade: every camera interaction bumps `scene.revision` (via `withRevision`),
which fans out into (1) a full unmemoized rerender of all right-pane accordions including
Camera number inputs, and (2) a 900 ms-debounced Pose Intelligence POST whose state swap
repaints the panel; API-down amplifies it with failure-status swaps. The new
`emitCameraCommit`-in-`sync()` adds one bounded extra rerender per load — it converges in
2 passes and is **not** a loop.
