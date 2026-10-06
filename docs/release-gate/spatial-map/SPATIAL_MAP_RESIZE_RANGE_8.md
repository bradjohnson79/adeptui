# Spatial Map Resize Range −8…+8

**Status:** GOVERNING DOCUMENT — placement size range extension.
**Date:** 2026-09-11 · Branch: `feat/posecraft-v4-human-replacement`
**Mission:** Extend the square/circle placement size control from −5…+5 to −8…+8 (17 positions), continuing the size progression cleanly. Existing −5…+5 meanings unchanged.

---

## Finding

The −8…+8 extension was **already fully implemented** in the working tree (an
earlier uncommitted local edit), consistently across frontend and backend. This
mission verified it end-to-end and **closed the explicit assertion gaps** with
tests.

**Density table (all 17, strictly increasing — no collapsed steps):**

```
-8:2  -7:3  -6:4  -5:5  -4:6  -3:7  -2:8  -1:9   0:10
+1:12 +2:14 +3:16 +4:18 +5:20 +6:22 +7:24 +8:26
```

Density = grid cells across the square; **more cells = smaller placement**.
So −8 is the largest placement, +8 the smallest. The negative side continues
−1/step, the positive side +2/step; existing −5…+5 densities `[5,6,7,8,9,10,12,14,16,18,20]` are **unchanged**.

**Low-density floor validation (circle-in-square unchanged):** density 2 yields
4 valid cells (centers (±0.5,±0.5), x²+y²=0.5 ≤ 1); density 3 → 9; density 4 → 12.
No floor adjustment needed.

## Surface (live source — verified)

- `studio-web/.../gridGeometry.ts` — `MIN_GRID_SCALE=-8`, `MAX_GRID_SCALE=8`,
  widened `GridScale` union, `GRID_DENSITY` (17 entries), `clampGridScale` ±8.
- `studio-api/app/spatial_map/grid.py` — **backend mirror**, identical table.
- `studio-api/app/spatial_map/schemas.py` — comment; `service.py` —
  `clamp_grid_scale` on save. No hardcoded −5/5 bounds remain in live source.
- UI control (`SpatialMapPanel.tsx`) reads the `MIN/MAX_GRID_SCALE` constants, so
  the 17 positions flow through automatically.

## Preservation proof

- Center anchoring: `normalizedToPixel(0,0)` = exact map center at every density;
  `nearestValidCell(0,0)` non-null.
- Placement coordinates: full −8…+8 sweep never mutates `normalizedX/normalizedY`
  (display-only remap; snap distance < cell size).
- Persistence: ±10 input clamps to ±8 and survives reload (backend test).

## Tests

- Frontend `gridGeometry.test.ts` (+6) + `SpatialGrid.test.ts` (+1): all 17
  selectable exactly; density strictly increases; outer steps exceed old range;
  existing meanings unchanged; density-2 floor; center anchoring; coordinate
  preservation. **44/44 PASS.**
- Backend `tests/test_spatial_map_v1_grid_camera.py`: **18/18 PASS.**
- Full frontend Spatial Map folder: 253 pass / 17 fail — all 17 in
  `useSceneCreatorMini.test.ts`, **proven pre-existing** via stash-baseline
  (identical 17 fail without these edits; unrelated SceneCreatorMini markup drift).

## Verdicts

- −8 visibly larger than −5: **PASS** (density 2 < 5)
- +8 visibly smaller than +5: **PASS** (density 26 > 20)
- All 17 positions selectable: **PASS**
- No step collapses to the same rendered size: **PASS** (strictly increasing)
- Switching sizes does not shift center point: **PASS**
- Persisted size survives reload: **PASS**
- Existing −5…+5 meaning unchanged: **PASS**

**Final: GO — SPATIAL MAP RESIZE RANGE -8 TO +8 VERIFIED**
