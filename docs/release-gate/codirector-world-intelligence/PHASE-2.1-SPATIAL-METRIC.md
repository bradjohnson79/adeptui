# Revision C Phase 2.1 — Spatial Metric Map

**Status:** GOVERNING for Phase 2.1  
**Law 30:** This is the single governing document for Spatial Map meters. Phase 2 PoseCraft + JEPA is historical: [PHASE-2-POSECRAFT.md](./PHASE-2-POSECRAFT.md).

```text
Spatial Map = intended geography (canonical)
PoseCraft  = bodies at those world origins
JEPA       = observed/advisory only
Co-Director = intent vs observation
```

Do not add `zones[]` to `SpatialMapDocument`. Axes stay `adept-world-v1`: **+X East, +Y Up, +Z South, −Z North**. Existing Schnick `x/y/z` values are already meters and must not be rescaled.

## Environment

| Item | Value |
|---|---|
| Branch | `feat/codirector-temporal-continuity` |
| Phase 2 hosted frontend | `https://adeptui.vercel.app` (`5cbbb41` / `dpl_3MRKtGSvK1SfTqvJ2WmT884WV2J7`) |
| Cert project | Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` |
| Creator UI | http://127.0.0.1:8760/ |
| Studio API | http://127.0.0.1:8758/ |

Phase 2.1 source is a **separate** commit family from the Phase 2 production SHA. Do not mix this work into the Phase 2 Vercel deploy.

## Schema (`spatial-metric-v1`)

Keep `schemaVersion: 1`. Additive fields:

- Document: `metricSchema`, `metersPerCell` (default `1.0`), `originMeters`, `widthMeters` / `depthMeters` (default 10×10), `environmentalAnchors[]`
- Entities: `positionMeters`, `gridCell` (E8-style), `footprintMeters`
- Camera: `targetMeters`
- Prop: `dimensionsMeters`, `occupiedCells`
- Off-map anchors: `bearing`, `distanceMeters`, `elevationMeters` (example: mountain 40 m NW)

`positionMeters` is machine truth. Sync `x/y/z`, `normalized*`, and derived grid on every write. Legacy GET assumes 1 m/cell, fills meters from `x/y/z`, persists on the next save. Martial-arts cert map is 20×20 m so two fighters can stand 12 m apart.

## Product UI

Quiet label: **1 square = 1 meter**. APPROVED / PROPOSED / OBSERVED stay distinct. Camera-only commands must not move characters, props, or anchors.

## Local certification (measured)

| Gate | Result |
|---|---|
| Unit `studio-api/tests/test_spatial_metric.py` | **10 passed** |
| Playwright `tests/e2e/codirector/phase-2.1-spatial-metric.spec.ts` | **3 passed (5.2s)** — 20×20 / 12 m / camera lock / persist / isolation / `1 square = 1 meter` |
| Revision B + C regression | **14 passed (19.9s)** including Playwright H persist |
| Schnick coords rescale | **PASS** — `x=1.25, z=-0.5` unchanged after migrate |
| No `zones[]` | **PASS** |
| Beta | http://127.0.0.1:8760/ and http://127.0.0.1:8758/api/health **200** |

## Peer review

| Reviewer | SHA | Verdict |
|---|---|---|
| GLM 5.2 | `11cb0e1` | READY FOR PRIMARY REVIEW |
| Kimi K3 | `11cb0e1` | READY after primary adjudication |

Kimi flagged committed frontend `movementSegments` on `studio-web` `SpatialMapDocument`. That type is Phase 2 production legacy (`7964efd`), not a Phase 2.1 add. The backend Pydantic `SpatialMapDocument` at `11cb0e1` has no `movementSegments` / `zones`. Primary accepts this as out of Phase 2.1 scope.
