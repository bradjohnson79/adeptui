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

Phase 2.1 source is a **separate** commit and **separate** Vercel SHA from Phase 2. Do not mix this work into the Phase 2 production deploy.

## Schema (`spatial-metric-v1`)

Keep `schemaVersion: 1`. Additive fields:

- Document: `metricSchema`, `metersPerCell` (default `1.0`), `originMeters`, `widthMeters` / `depthMeters` (default 10×10), `environmentalAnchors[]`
- Entities: `positionMeters`, `gridCell` (E8-style), `footprintMeters`
- Camera: `targetMeters`
- Prop: `dimensionsMeters`, `occupiedCells`

`positionMeters` is machine truth. Sync `x/y/z`, `normalized*`, and derived grid on every write. Legacy GET assumes 1 m/cell, fills meters from `x/y/z`, persists on the next save. Martial-arts cert map is 20×20 m so two fighters can stand 12 m apart.

## Product UI

Quiet label: **1 square = 1 meter**. APPROVED / PROPOSED / OBSERVED stay distinct. Camera-only commands must not move characters, props, or anchors.

## Certification

- Unit: `studio-api/tests/test_spatial_metric.py`
- Playwright: `tests/e2e/codirector/phase-2.1-spatial-metric.spec.ts` (Schnick only)
- Regress Revision B / C1 / C2 if those files are run in the same Beta
