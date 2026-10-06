# Spatial Map Rectangular Native-Aspect Calibration Workspace

**Governing document for this addendum.**

The Spatial Map workspace is a rectangular production surface. The Atlas keeps its native aspect. The placement grid stays square. There is no circular clip, mask, or circular production boundary.

**Verdict:** `GO — SPATIAL MAP RECTANGULAR NATIVE-ASPECT CALIBRATION WORKSPACE E2E CERTIFIED`

Prior certs remain governing for their own gates:

- Hand + Resize: `SPATIAL_MAP_BACKGROUND_ALIGNMENT_CERTIFICATION.md`
- Native-aspect contain-fit (no 1:1 crop): `SPATIAL_MAP_NATIVE_ASPECT_CALIBRATION_CERTIFICATION.md`

Circular **viewport** / `spatial-map-circle-clip` / `border-radius: 50%` language in those documents is superseded by this addendum.

**Terminology freeze (2026-09-04 repair):** Circular viewport = RETIRED. Circle-in-square placement grid + Circles toggle = REQUIRED. This cert remains valid for rectangular Atlas / native aspect / no picture clip / calibration. It is superseded only where it removed the placement-grid circles. See `SPATIAL_MAP_RECTANGULAR_ATLAS_CANONICAL_PLACEMENT_GRID_CERTIFICATION.md`.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455` (working tree includes this mission; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Proof maps | Native Aspect 16:9 `94494dec-8041-497a-941c-8f2add22d865` · Native Aspect 4:3 `04017ede-ee4e-42af-9401-6c0b940ea4f2` |
| Production map (leave-alone) | Venture Corridor Walk `7c7aac85-6932-4945-a13f-4a11fd69b79f` / Atlas `681cc247-8023-46dd-8e16-4446e60cae4e` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

Success string: `GO — SPATIAL MAP RECTANGULAR NATIVE-ASPECT CALIBRATION WORKSPACE E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP RECTANGULAR NATIVE-ASPECT CALIBRATION WORKSPACE INCOMPLETE`

---

## Classification

**Circular viewport / clip:** REGRESSED product chrome. Not world-coordinate authority.

| Retired (viewport only) | Kept (world / calibration) |
| --- | --- |
| SVG `clipPath` circle (`spatial-map-circle-clip`) | Square `[-1, 1]` normalized coordinates |
| `.spatial-map__grid-wrap--circle` / `border-radius: 50%` | Square N×N placement grid |
| Outer `spatial-map__circle-stroke` | Placement Precision density |
| Circles **viewport** (picture clip) | Circles **grid** + Labels (independent) |
| Circle-clamped resize handles | Freehand Align (X/Y only) |
| ERS ellipse mask on the atlas panel | Resize (uniform scale) |
|  | Workspace zoom (view only) |
|  | Reset Alignment / Reset Map / Save |
|  | GPT Image 2 API-only ERS |

A cell is still valid iff its center lies inside the unit circle. That is the existing world rule. It is not a circular crop of the picture.

---

## Architecture

```text
rectangular viewport  = CSS box at the source aspect (wide production surface)
square viewBox        = unchanged world / grid authority
atlas                 = contain-fit in the square, native W×H
SVG framing           = xMidYMid slice so the rectangle shows the picture, not letterbox bars
pointer math          = clientToSlicedSquareViewBox (slice-aware; does not rewrite coords)
workspace zoom        = view-only wrap size via --spatial-map-zoom; never writes backgroundAlignment (see zoom-fill cert)
```

Canonical transform (unchanged fields):

```json
{
  "backgroundAlignment": {
    "offsetX": 0.0,
    "offsetY": 0.0,
    "scale": 1.0,
    "sourceWidth": 1280,
    "sourceHeight": 720,
    "sourceAspectRatio": 1.7777777777777777
  }
}
```

No rotation (none existed; do not invent one).

---

## Canonical workspace

```text
Rectangular native-aspect viewport
+ original circle-in-square placement grid
+ Freehand Align
+ Resize
+ Workspace Zoom
+ Reset Map
+ Save Spatial Map
+ GPT Image 2 API-only ERS
```

Controls: **Grid | Circles | Labels**. Circles is the placement-grid overlay, not a circular viewport. See the 2026-09-04 placement-grid repair.

---

## Live proof

Playwright `tests/e2e/codirector/spatial-map-rectangular-viewport.spec.ts` — **1 passed** (7.6s).

| Check | 16:9 | 4:3 | Venture |
| --- | --- | --- | --- |
| `data-viewport=rect` / `data-clip=none` | PASS | PASS | PASS |
| `clipPath` count | 0 | 0 | 0 |
| Circles button | restored as placement-grid overlay (not viewport clip) | same | same |
| Frame aspect | 1331×749 ≈ 16:9 | 998×749 ≈ 4:3 | 1123×749 ≈ 3:2 |
| Border radius | 9.6px (not 50%) | 9.6px | 9.6px |
| Source | 1280×720 | 800×600 | 1536×1024 |
| Persist | scale 1.25 after Save / Library / return | scale 1.3 kept | scale 0.75; placements kept |

Venture placements after rectangular open (Reset Map not used):

| Entity | normalizedX | normalizedY |
| --- | --- | --- |
| Korri | `0.40` | `0.62` |
| Anadriya | `0.58` | `0.64` |
| C1 Mid Shot | `0.50` | `0.82` |

Playwright flow: open 16:9 → rectangular frame → workspace zoom (grid path unchanged) → Resize Size 125 → Freehand pan (scale held) → Save → Library → return/reload → 4:3 rectangular → Venture markers + coordinates unchanged.

---

## Tests (this run)

| Suite | Result |
| --- | --- |
| Vitest `backgroundAlignment.test.ts` + `gridGeometry.test.ts` + `SpatialMapPanel.test.ts` | **48 passed** |
| Pytest `test_background_alignment.py` + `test_ers_component_pipeline.py` | **16 passed** |
| Playwright `spatial-map-rectangular-viewport.spec.ts` | **1 passed** (7.6s) |

---

## Runtime

- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → 200
- `GET http://127.0.0.1:8188/system_stats` → 200 (leave-alone)

Studio API recycled for ERS ellipse-mask removal only (`oldPid 20012 → newPid 49092`).

**COMFY BEFORE:** PID **69108**, health 200  
**COMFY AFTER:** PID **69108**, health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Viewport/CSS/ERS compose. No supervisor restart.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — open Spatial Map; 16:9 + 4:3; Resize; Freehand; workspace zoom; Save; leave; return |
| Frontend | PASS — rectangular frame; no circular clip; native aspect; grid fixed |
| API | PASS — existing `backgroundAlignment` + source W/H/aspect |
| Backend | PASS — ERS panel no longer ellipse-masks the atlas |
| Persistence | PASS — 16:9 scale 1.25 + 1280×720 after reload; 4:3 800×600 kept |
| Runtime | PASS — Comfy untouched; Venture placements untouched |
| Result | PASS — rectangular native-aspect production surface |
| Reload | PASS — transform + ratio survive |
| Downstream | PASS — Scene Review / ERS label GPT Image 2; coordinates unchanged |

---

## Limitations

- Unit-circle cell validity remains the world placement rule. Corner cells are still not placeable. That is not a circular picture crop.
- No independent map rotation.
- Resize handles now sit on the Atlas image corners (see `SPATIAL_MAP_DIRECT_TRANSFORM_HANDLES_CERTIFICATION.md`). Circle/slice-clamped handles are retired.
- Workspace zoom is viewport-wide, not Atlas-only.
- **Reset Map** still confirms and clears placements; use **Reset Alignment** for calibration-only reset.
- Venture leftover Size `75` / `gridScale +5` predates this addendum. Normalized placements were not rewritten.
- Working tree is not committed unless requested.

---

## Final verdict

**GO — SPATIAL MAP RECTANGULAR NATIVE-ASPECT CALIBRATION WORKSPACE E2E CERTIFIED**
