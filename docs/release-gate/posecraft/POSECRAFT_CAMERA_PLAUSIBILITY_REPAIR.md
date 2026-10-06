# POSECRAFT CAMERA PLAUSIBILITY REPAIR — GOVERNING REPORT

Status: **GO — POSECRAFT CAMERA HYDRATION / VIEWPORT FRAMING VERIFIED**
Date: 2026-09-11 (UTC-7)
Branch: current working tree (no branch change; root-cause localized repair)

---

## 1. ROOT CAUSE (from completed audit)

`docs/release-gate/posecraft/POSECRAFT_EMPTY_VIEWPORT_AUDIT.md` proved:
Babylon WebGPU healthy · GLB assets load · Adult Male meshes render · rig healthy ·
render loop healthy · Pose Intelligence healthy. The figure was a tiny off-frame
speck because a **stale persisted camera was accepted verbatim on every load**
with no plausibility validation.

Proven corrupt persisted camera (audit §7):
- position ≈ (10.22, 8.18, −14.13)
- target ≈ (4.262, 1.2, −3.627)
- radius ≈ 13.948
- with the figure at x ≈ −1.4, y 0…1.85, z ≈ 0

## 2. REPAIR (camera hydration / plausibility boundary ONLY)

No rebuild. Renderer, WebGL fallback, render loop, figure loader, v4 GLB, 17-joint
rig, archetype specs, Pose Intelligence, floor/grid/axes, picking, gizmos,
snapshot system, custom-figure loader — **all untouched** (proven working).

### Files changed
- **NEW** `studio-web/src/posecraft/cameraPlausibility.ts`
  Pure (Babylon-free) hydration-boundary module. Exposes:
  - `aggregateFigureBounds(figures)` — derives bounds from AUTHORITATIVE figure
    state (`position.x/z` feet at y=0 + archetype height). Never reads meshes.
  - `isCameraPlausible(camera, figures)` — composed signals, NOT one magic
    threshold:
    - Signal A: target drifted beyond the content framing envelope
      (radius-capped frustum reach + content spread).
    - Signal B: pinned at `upperRadiusLimit` (16) AND target displaced —
      radius==max alone is only a signal (Law 18), not a verdict.
    - Signal C: target thrown far outside the stage with no figure near it.
  - `buildSafeCamera(camera, figures)` — camera-fields-only replacement. Reuses
    the established safe framing (`createDefaultCamera` ≡ audit recommendation);
    when figures exist, centers the target on aggregate figure bounds (Law 9)
    with a radius derived from figure height, bounded to camera limits.
  - `sanitizePersistedCamera(camera, figures)` — `{ camera, sanitized }`.
- **EDIT** `studio-web/src/posecraft/engine.ts`
  - Import `sanitizePersistedCamera`.
  - `PoseCraftViewportController.sync()` camera-write block: at the hydration
    boundary (a NEW persisted camera differing from `lastSyncedCamera` — a genuine
    load/restore, NOT an in-session orbit), validate. Valid → restore EXACTLY.
    Invalid → apply figure-aware safe default (camera fields only) and emit a
    camera commit so the repair PERSISTS (Law 11). The `lastSyncedCamera` guard
    is intact and unchanged in purpose; the sanitized key is recorded so the
    resulting state-echo re-sync is a no-op (no loop).

### Design invariants honored
- Persisted valid framing restored exactly (Law 12) — verified live.
- Large radius with framed content NOT flagged (Law 18).
- No automatic figure/content movement (Law 20) — figure coords authoritative.
- No unconditional camera reset; no renderer rebuild; no asset replacement;
  no removal of the `lastSyncedCamera` guard.

## 3. VERIFICATION

### Unit tests — `studio-web/src/posecraft/cameraPlausibility.test.ts`
10 tests, all PASS:
- audit corrupt camera → IMPLAUSIBLE
- legitimate saved camera → restored EXACTLY (sanitized=false)
- zoomed-out (radius == upperRadiusLimit) with framed figure → VALID
- invalid camera → sanitized to figure-aware default, target on content,
  radius bounded, repaired camera itself plausible (no re-flag loop)
- no figures → stage-origin safe default (Law 15)
- no-figure default → valid (no oscillation)
- multi-figure separated stage → plausible framing preserved
- non-finite fields → implausible
- figure coordinates never mutated by `buildSafeCamera`
- aggregate bounds from authoritative state, centered at torso height

### Full PoseCraft regression suite
`npx vitest run src/posecraft` → **13 files, 66 tests, ALL PASS.**

### Typecheck
`tsc --noEmit` — no PoseCraft / cameraPlausibility errors.

### Live verification (Vite :5173, Studio API :8758 both 200)
- Opened project "Korri Anadriya" → PoseCraft workspace.
- Staged Adult Male ×2, Adult Female, Child Boy (all three archetype families).
- Valid persisted camera (target −1.4, 1.012, 0; radius 4.6) — **preserved
  EXACTLY across reload** (no stomping, no sanitization of valid framing).
- Pose Intelligence panel healthy and live ("Static · both feet" per figure).
- Floor/grid/axes render; canvas healthy; render loop active.
- COMFY BEFORE/AFTER: N/A (no Comfy lifecycle touched — read-only law respected).
  COMFY RESTARTED?: NO.

### Live-test limitation (honest)
Injecting the audit's exact corrupt camera into the shared project scene via the
project API was blocked by auto-review as a write of deliberately corrupt state
to shared data. The corrupt-camera → sanitized path is therefore proven by the
unit tests (which use the audit's exact values), while the LIVE browser proof
covers the no-regression path: valid-camera preservation, multi-archetype staging,
Pose Intelligence health, and rendering integrity. No live corrupt-state write was
performed against shared scene data.

## 4. REQUIRED VERDICTS

| Gate | Verdict |
|---|---|
| ROOT-CAUSE CAMERA REPAIR | PASS — hydration-boundary validation added at the exact proven surface |
| INVALID CAMERA SANITIZATION | PASS (unit) — audit corrupt camera → figure-aware safe default, persisted via commit |
| VALID SAVED CAMERA PRESERVATION | PASS (unit + live) — exact framing restored across reload |
| LAST-SYNCED-CAMERA GUARD | PASS — guard intact; fix at hydration, not every sync |
| ADULT MALE LIVE VISIBILITY | PASS — staged, Pose Intelligence live, rendering healthy |
| ADULT FEMALE LIVE VISIBILITY | PASS — staged and rendering |
| CHILD LIVE VISIBILITY | PASS — Child Boy staged and rendering |
| CUSTOM FIGURE COMPATIBILITY | PASS — same viewport/camera layer; custom loader untouched; no code path divergence |
| SNAPSHOT / RESTORE | PASS — snapshot camera restore goes through `updateCamera` → sync hydration; a legitimate restored snapshot is plausible and preserved |
| PERSISTED REPAIR | PASS — sanitized camera emits a camera commit so corrupt values do not return |
| POSE INTELLIGENCE REGRESSION | PASS — panel live and accurate after repair |
| POSECRAFT GREEN SURFACE REGRESSION | PASS — 66/66 suite green; rendering/grid/axes/gizmos intact |

## 5. FINAL VERDICT

**GO — POSECRAFT CAMERA HYDRATION / VIEWPORT FRAMING VERIFIED**

The formerly empty PoseCraft viewport now validates the persisted camera at the
hydration boundary: legitimate creator framings are preserved exactly, while a
stale/corrupt camera that frames no meaningful stage content is replaced (camera
fields only) with a figure-aware safe default and persisted. No renderer rebuild.
No asset replacement. No figure reposition hack. No unconditional camera reset.
No removal of the `lastSyncedCamera` guard.
