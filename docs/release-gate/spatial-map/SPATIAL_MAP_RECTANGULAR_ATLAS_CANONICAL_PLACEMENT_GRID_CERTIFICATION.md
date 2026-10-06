# Spatial Map Rectangular Atlas + Canonical Placement Grid + Entity Placement

**Governing document for this repair.**

The rectangular native-aspect Spatial Map picture and the original circle-in-square placement grid are separate layers. This mission restores the proven placement grid without returning the Atlas to a circular viewport.

**Verdict:** `GO — SPATIAL MAP RECTANGULAR ATLAS + CANONICAL PLACEMENT GRID + ENTITY PLACEMENT E2E CERTIFIED`

Prior cert remains valid for rectangular Atlas / native aspect / no picture clip / calibration:

- `SPATIAL_MAP_RECTANGULAR_NATIVE_ASPECT_WORKSPACE_CERTIFICATION.md`

That cert is superseded only where it removed the circle-in-square placement-grid presentation and the Circles control.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455` (working tree includes this repair; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Production map | Venture Corridor Walk `7c7aac85-6932-4945-a13f-4a11fd69b79f` / Atlas `681cc247-8023-46dd-8e16-4446e60cae4e` |
| Placement sandbox | Native Aspect 16:9 `94494dec-8041-497a-941c-8f2add22d865` / Atlas `7a70d734-69d7-4b83-ac1e-61850aa36bb8` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

Success string: `GO — SPATIAL MAP RECTANGULAR ATLAS + CANONICAL PLACEMENT GRID + ENTITY PLACEMENT E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP PLACEMENT GRID REGRESSION REMAINS`

---

## Terminology freeze

| Term | Status |
| --- | --- |
| Circular viewport / picture clip / `spatial-map-circle-clip` / `grid-wrap--circle` | RETIRED |
| Circle-in-square placement grid / cell circles / Circles toggle | REQUIRED |
| Unit-circle cell validity (`isValidCell`) | REQUIRED world rule |

Do not conflate these again.

---

## Layer model

```text
RECTANGULAR WORKSPACE / VIEWPORT
       |
       +-- Spatial Map image layer
       |     native aspect
       |     Freehand X/Y
       |     uniform Resize
       |     direct transform handles
       |
       +-- Canonical placement-grid layer
             square coordinate authority
             circle-in-square cell display
             characters / props / cameras / labels
```

---

## Root cause — why rectangular conversion disabled entity placement

The rectangular / direct-handle work changed `SpatialGrid.handleClick` so any pointer on the Atlas returned before placement:

```ts
if (onTransform) return;          // image hit, overlay, or data-atlas-hit
if (placementActive) { onCellClick(...) }
```

Creators place by clicking the picture. After the rectangular conversion the Atlas fills the production rectangle, so almost every click was classified as a transform hit. Placement never ran. Pointer math (`clientToSlicedSquareViewBox`) was not the defect; the swallow-before-place order was.

**Repair:** if `placementActive`, always `handlePointer` → `onCellClick`. Image-hit may select the Atlas only when placement is not armed. Slice-aware pointer mapping is kept so a rectangular CSS box still hits the square world correctly.

---

## Restored / preserved

Restored from last known-good `HEAD` `SpatialGrid` (not recreated):

- square Cartesian grid
- `validCells` + `spatial-map__cell-circle` (`r = cellPx * 0.4`)
- circle ghost cursor
- unit-circle validity
- original markers
- Grid / Circles / Labels
- Placement Precision

Preserved:

- rectangular native-aspect Atlas (no picture `clipPath`)
- Freehand Align and Photoshop-style resize handles on the map layer
- placements do not rewrite when the Atlas is aligned or resized
- Reset Alignment resets Atlas `{0,0,1}` + source dims only
- GPT Image 2 API-only ERS

---

## Live proof

Playwright `tests/e2e/codirector/spatial-map-rectangular-atlas-placement-grid.spec.ts` — **1 passed** (10.3s, then 9.9s on the suite rerun).

Live Venture Corridor Walk (browser + API), placements recorded first and left intact:

| Entity | normalizedX | normalizedY |
| --- | --- | --- |
| Korri | `0.40` | `0.62` |
| Anadriya | `0.58` | `0.64` |
| C1 Mid Shot | `0.50` | `0.82` |

Character / Prop / Camera select → enable → place → move → save → reload were proven on Native Aspect 16:9 so Venture production markers were not rewritten. After cleanup that sandbox has 0 leftover entities.

Live Venture UI: rectangular Deck 5 Atlas, circle-in-square overlay, Grid / Circles / Labels pressed, Korri / Anadriya / C1 assigned with Move, Size 100 after Reset Alignment, workspace zoom 75% and 50% with calibration Size still 100.

---

## Tests (this run)

| Suite | Result |
| --- | --- |
| Vitest Spatial Map (`backgroundAlignment` + `gridGeometry` + `SpatialMapPanel`) | **51 passed** |
| Playwright `spatial-map-rectangular-atlas-placement-grid.spec.ts` | **1 passed** |
| Playwright `spatial-map-rectangular-viewport.spec.ts` | **1 passed** |
| Playwright `spatial-map-direct-transform-handles.spec.ts` | **2 passed** |
| Playwright `spatial-map-background-alignment.spec.ts` | **2 passed** |
| Playwright `spatial-map-native-aspect.spec.ts` | **2 passed** |

---

## Runtime

- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → 200
- `GET http://127.0.0.1:8188/system_stats` → 200 (leave-alone)

**COMFY BEFORE:** health 200 (protected `:8188`)  
**COMFY AFTER:** health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** UI / pointer / CSS / Playwright only.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Grid/Circles/Labels; place Character, Prop, Camera; Freehand; handle resize; zoom |
| Frontend | PASS — placement-first click; cell circles; rectangular Atlas |
| API | PASS — existing character / prop / camera update endpoints |
| Backend | PASS — unit-circle validity unchanged |
| Persistence | PASS — sandbox placements survived Library leave/return; Venture coords unchanged |
| Runtime | PASS — Comfy untouched |
| Result | PASS — rectangular Atlas + circle-in-square grid + entities |
| Reload | PASS |
| Downstream | PASS — C1 still feeds Scene Creator contract (`0.50 / 0.82`) |

---

## Limitations

- Unit-circle cell validity remains the world rule. Corner cells are still not placeable. That is not a circular picture crop.
- Venture Placement Precision leftover `+5 (20×20)` predates this repair and was not rewritten.
- Venture calibration is now Reset Alignment `{0,0,1}` (1536×1024). The prior leftover Size `75` was not restored; placements were not moved.
- Working tree is not committed unless requested.

---

## Final verdict

**GO — SPATIAL MAP RECTANGULAR ATLAS + CANONICAL PLACEMENT GRID + ENTITY PLACEMENT E2E CERTIFIED**
