# PoseCraft Camera / Deep-Zoom Audit

**Status:** AUDIT DELIVERABLE E · read-only · 2026-09-12
**Goal (owner):** creator must zoom from a broad multi-character staging view all the
way into an individual character's face, regardless of figure position on the stage,
without clipping through the mesh. NO implementation in this mission.

---

## 1. CURRENT CAMERA ARCHITECTURE

`studio-web/src/posecraft/engine.ts`

| Parameter | Value | Line |
| --- | --- | --- |
| Camera type | `ArcRotateCamera` | ~751 |
| Initial alpha / beta / radius / target | `-π/2` / `1.12` / `7.5` / `(0,1.2,0)` | ~751–757 |
| `lowerRadiusLimit` | `2.2` | ~760 |
| `upperRadiusLimit` | `16` | ~761 |
| `wheelDeltaPercentage` | `0.01` | ~762 |
| `panningSensibility` | `70` | ~763 |
| `minZ` | `1` (engine default) | — |
| `maxZ` | `10000` (engine default) | — |
| FOV | `lensToFov(lensMm)` (~0.75 rad at 35 mm) | ~1528 |

`ArcRotateCamera.attachControl(canvas, true)` enables the standard orbit/pan/wheel.

## 2. LIVE CAMERA STATE (this audit)

Persisted (DB, read-only): `radius 16.0` (== `upperRadiusLimit`), `target (0,1.2,0)`,
`alpha -π/2`, `beta 1.12`. Verified **plausible** by `cameraPlausibility.ts` arithmetic
(target drift @ content spread 2.0 → allowance 3.55 + 2.0 = 5.55; drift 1.2 < 5.55).
Engine, when hydrated, applied `radius 16` correctly.

## 3. BLOCKERS TO FACE-LEVEL ZOOM (quantified)

For a 1.84 m adult male (head ≈ 0.24 m), vertical frame extent at the target plane is
`2·r·tan(fov_v/2)` (`fovMode = FOVMODE_VERTICAL_FIXED`; `lensToFov(35) = 0.952 rad`).

| Blocker | Severity | Math |
| --- | --- | --- |
| **`lowerRadiusLimit = 2.2`** | **PRIMARY** | A face close-up at 35 mm needs `r ≈ 0.47 m` — **4.7× closer than allowed**. Even at 135 mm it needs `r ≈ 0.9 m` — still 2.4× under the floor. |
| **`minZ = 1` (near plane)** | **HARD BLOCKER below ~1.1 m radius** | At `r = 0.9` around a head target, the head surface is ~0.75 m from the camera — inside the 1 m near plane → **clipped/invisible**. Must become ~**0.05**. |
| **Fixed stage target** | **BLOCKER for head framing** | Orbit pivot stays at `(0,1.2,0)`; zooming shrinks the radius around that pivot rather than moving it to a face. No focus feature exists. |
| **`panningSensibility = 70`** | **BLOCKER at close range** | Babylon 8.x: `panScale = 1 / panningSensibility` (default `1000`) → `70` moves **~14× more target per pixel than default** — far too coarse for fine head framing. (Verified in `arcRotateCameraPointersInput.js`.) |
| `wheelDeltaPercentage = 0.01` | **NOT a blocker** | Radius-proportional: ~4 mm/notch at r=0.4, ~7.5 cm at r=7.5 — already precise at close range. |
| `upperRadiusLimit = 16` | Adequate | Covers the stage except corner-to-corner (22.6 m) on a 35 mm lens; the 18 mm preset covers it. |
| Beta limits (`0.01…π−0.01`, Babylon default) | Not a blocker | Eye-level head shot needs `β ≈ π/2` with the target at head height. |
| Collision | Absent | No `checkCollisions`/collision meshes; camera passes through figures freely. |

## 4. CAN ArcRotateCamera SUPPORT IT CLEANLY?

**Yes — without a collision system.** ArcRotateCamera orbits its **target**; radius is
distance *from the target*. `_checkLimits` enforces radius limits **every frame**
(including clamping direct property writes) — so a **target-aware `lowerRadiusLimit`** is
itself the "collision" clamp (no mesh collision, no perf cost, no fighting orbit inertia).

Progression: **Stage** (r 8–16, target = centroid) → **Body** (r ≈ 2.5·height, target =
torso) → **Head** (r ≈ 0.5, target = head) — pure target+radius+minZ changes; `alpha/beta`
limits don't constrain it.

Required changes:
1. `camera.minZ = 0.05` at create (near-plane; mandatory for any r < ~1.1 m).
2. **Dynamic `lowerRadiusLimit` per target preset** (stage 2.2 / body 1.2 / face 0.35).
   Do NOT simply drop the floor: target inside a head + r < head half-extent (~0.12 m)
   would put the camera inside the skull.
3. Wheel: **leave as-is** (`wheelDeltaPercentage = 0.01` is already right).
4. Pan: make radius-aware (e.g. `clamp(r·32, 20, 320)`) or rely on focus presets instead.

## 5. FOCUS / TARGET RECOMMENDATION (no build)

- **Focus Selected Figure** — target at figure x/z @ 0.55·height, radius ≈ 2·height.
- **Focus Head** — target at figure x/z @ ~0.92·height·scale, radius ≈ 0.45–0.6.
- **Reset to Stage** — restore the stage framing.
- Reuse the existing `pickBodyJoint` path (head is a body region) so "Frame Face /
  Frame Body" is a creator-language chip.
- All focus moves flow through the canonical `updateCamera` → `sync()` authority so they
  persist and survive reload (no schema change — `CameraState` already has target+radius).

## 6. DUPLICATED CONSTANTS — CRITICAL PREREQUISITE

The framing and limits are **duplicated across authorities**, held together only by
comments — no shared constant, no drift-detection test:

| Constant | Copies |
| --- | --- |
| Framing `alpha/beta/radius/target` | `engine.ts` create() (~750–758) · `SAFE_CAMERA` (`cameraPlausibility.ts` ~17–22) · `createDefaultCamera()` (`state.ts` ~262–271) |
| Radius limits `{lower, upper}` | `engine.ts` ~760–761 · `CAMERA_RADIUS_LIMITS` (`cameraPlausibility.ts` ~23) |

**This is the trap deep zoom will spring:** lowering `lowerRadiusLimit` to ~0.4 for face
close-ups would leave `CAMERA_RADIUS_LIMITS.lower = 2.2` behind, and `buildSafeCamera`'s
clamps (`lower + 0.5`) would then emit cameras violating the new engine floor.
**Consolidate into one pure module first**, derive `SAFE_CAMERA` from
`createDefaultCamera()`, and add a test asserting the shared limits equal what `create()`
applies.

## 7. CLIPPING PREVENTION

- **`minZ` must be smaller than the closest intended subject distance (→ 0.05).** Confirmed
  `minZ` is **never overridden anywhere in `studio-web/src`** — Babylon's default `1` stands.
- Never place the target *inside* a mesh; a head target sits at head centre with a
  positive radius.
- Plausibility must not classify a legitimate deep-zoom camera as corrupt: a face-zoom
  camera has its target ON a figure and a small radius → **plausible** (target drift ≈ 0).
- **`buildSafeCamera` currently clamps radius to `[2.7, 15]`** (`cameraPlausibility.ts`
  ~151–165) — a **sanitized** camera can therefore never be a close-up. Any zoom-limit change
  must update `CAMERA_RADIUS_LIMITS`, `buildSafeCamera`'s clamp, **and** `engine.ts` — or
  sanitization will fight the new range.
- **Near-plane clipping is a real risk at deep zoom:** at `r = 2.2` (current floor) with a
  torso target, the head sits ~0.35–0.5 m from the camera — **inside** the default 1 m near
  plane, so it is already clipped today.
- **`Distance` inspector input cannot defeat the limit:** `sync()` writes `radius`, but
  Babylon re-clamps at `_checkInputs` next frame → snaps back to 2.2 (state/viewport diverge).
- **Re-confirm after** the shared-limit consolidation.

## 8. KNOWN SIDE-DEFECT (found while auditing limits)

The inspector Distance field writes any number into `scene.camera.radius`; `sync()` applies
it; Babylon clamps the engine camera back to `lowerRadiusLimit` next frame → **state says
1.0 while the viewport shows 2.2** until the next orbit commit heals state. Fix with the
shared-limits constant.

## 9. VERDICT

**DEEP ZOOM FEASIBILITY: FEASIBLE WITH CHANGES** — `minZ`, a target-aware
`lowerRadiusLimit`, and figure focus presets must change together; no camera replacement
required. **Blocker prerequisite:** consolidate the duplicated camera constants first.
