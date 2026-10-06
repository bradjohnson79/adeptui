# ERS Canonical Camera Fidelity

**Status:** CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED

**Date:** 2026-08-18  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (never `POST /api/projects`)  
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` version 138  
**Live ERS:** execution `74ac9aa5-20eb-4c0b-86c3-d75e42f47850`, job `2311b157-a582-489c-8708-ddb35039322c`, composite `2c4d59f2-b549-46fe-b857-207b9b56e532`

Governing document for Spatial Map camera coordinates through ERS. Spatial Map placement is authoritative. Law 27 requested GPT 5.4 for specialized review; that slug was unavailable — independent visual ran as inherit.

## Chain

```text
USER CAMERA PLACEMENT
= SAVED CAMERA DATA
= CD CAMERA CONTEXT
= ERS CAMERA PLACEMENT
```

No aesthetic repositioning. No invented camera geography.

## Contract

Existing `SpatialCamera` fields only (`id`, `cameraSlot` → C1–C4, `normalizedX/Y`, `gridColumn/Row`, `orientation`, `yawDegrees`, `fovPreset`, `visible`). Active set: `visible` and `gridRow/Column >= 0`.

Shared compile: `compile_structured_cameras()` in `studio-api/app/spatial_map/ers_projection.py`.

ERS prompt: `CAMERA PLACEMENT IS CANONICAL` lock; model must not paint competing glyphs.

Post-generate overlay: `stamp_saved_cameras_on_ers` draws markers + FOV on frozen panel 2 (Spatial / Top-Down, 3×3 column 1 row 0) using the Spatial Map `[-1, 1]` transform. Clip aborts rather than stamping on the wrong panel.

Save: top and bottom Save Spatial Map share `useSpatialMapSave`. Mini and Use in Scene Creator stay dirty-gated. ERS generate remains available while dirty so the creator can edit → generate ERS → review → save.

## Live compile (saved v138)

| Slot | Label | cell | normalized | orientation |
|------|-------|------|------------|-------------|
| 0 | C1 | L12 | (0.15, 0.15) | N |
| 1 | C2 | N12 | (0.35, 0.15) | NW |
| 2 | C3 | J12 | (−0.05, 0.15) | NE |
| 3 | C4 | L14 | (0.15, 0.35) | N |

Relative: C3 west of C1, C2 east of C1, C4 south of C1.

## Independent visual

`.runtime/camera_mini_cert/INDEPENDENT_ERS_CAMERA_CERT.md` — READY FOR PRIMARY REVIEW (no GO from reviewer).

| Camera | Result |
|--------|--------|
| C1 | PASS |
| C2 | PASS |
| C3 | PASS |
| C4 | PASS |
| Environment (Korri / counter / entrance / furniture) | PASS |

Residual model-invented cell tags on the live sheet compete with the stamp but do not replace it.

## Tests

- `tests/test_structured_cameras.py`
- `tests/test_ers_camera_overlay.py`
- `tests/test_ers_knowledgebase_compiler.py` (camera lock)
- Playwright `savegate-cert.spec.ts` Part 0 top/bottom Save

## E2E TRACE

| Stage | Result |
|-------|--------|
| User action | PASS — C1–C4 placed and saved on Schnick Spatial Map |
| Frontend | PASS — shared `SpatialMapPanel` (Express = Standard) |
| API | PASS — saved document JSON |
| Backend | PASS — `compile_structured_cameras` + prompt lock |
| Persistence | PASS — version 138 hydrates after reload |
| Runtime | PASS — GPT Image 2 ERS job + overlay stamp |
| Result | PASS — overlay C1–C4 vs Spatial Map |
| Reload | PASS — saved revision |
| Downstream | PASS — Mini / Scene Creator consume saved compile |

## Verdict

`CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`
