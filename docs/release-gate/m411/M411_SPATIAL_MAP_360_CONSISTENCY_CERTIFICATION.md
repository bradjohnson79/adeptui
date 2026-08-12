# M4.11 — Spatial Map + 360 Scene Consistency Studio Certification

## Identity

| Field | Value |
| --- | --- |
| Milestone | M4.11 |
| Feature | Spatial Map + 360 Scene Consistency Studio |
| Starting branch | `feature/m4-10-voice-performance-index-tts2` |
| Starting SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Feature branch | `feature/m4-11-spatial-map-360-consistency` |
| Final SHA | *(uncommitted working tree — commit when requested)* |
| Adept UI version | local beta stack |
| Spatial Map schema version | `schemaVersion: 1` + document `version` counter |
| 360 Collage schema version | collage embedded in Spatial Map document v1 |
| Reference Bundle version | `SpatialReferenceBundle` v1 |
| Co-Director spatial tool version | `spatial.*` M4.11 |
| Subagent law | Law #27 — specialized subagents use `gpt-5.4-medium` |

## Architecture

- **Coordinate system:** `adept-world-v1` (X left/right, Y up/down, Z forward/back). Primary UI uses filmmaker language; exact coords live under Advanced.
- **Placement model:** up to 4 characters, 4 props, 8 cameras; typed 409 errors on overflow.
- **Camera model:** saved cameras with lens/height/shot type; hero camera anchors 360 capture.
- **360 collage:** 8 required directions; optional ceiling/floor/hero; one master environment prompt + yaw rotation only.
- **Scene assignment:** maps assignable to scenes without overwriting variants.
- **Library/tags:** document `tags[]` + project-scoped map list.
- **Generator translation:** `SpatialReferenceBundle` for image/video; provider honesty defaults to `approximate_translation`.
- **Co-Director tools:** read + proposal-gated `spatial.*` mutations including `spatial.generate_360_plan`.
- **Versioning:** document `version` bumps on save; image provenance stores `spatialMapId` + `spatialMapVersion`.

## Feature Matrix

| Feature | Status | Evidence |
| --- | ---: | --- |
| Spatial Map | Done | `studio-web/.../SpatialMapStudio.tsx`, `/api/spatial-map` |
| Scene bounds | Done | `SpatialBounds` |
| Character placement | Done | place/move/delete endpoints |
| Four-character limit | Done | `test_m411_spatial_map.py` |
| Prop placement | Done | place/move/delete endpoints |
| Four-prop limit | Done | `test_m411_spatial_map.py` |
| Cameras | Done | up to 8 |
| Camera preview | Partial | simplified inspector / facing arrow |
| Movement paths | Done | create path API + schema |
| 360 Collage | Done | collage panel + capture plan |
| Consistency check | Done | heuristic adjacent validation |
| Scene assignment | Done | assign-scene + assignedSceneIds |
| Tags | Done | document tags |
| Library selection | Partial | project map list + Image Generator selector |
| Image Generator integration | Done | `spatialMapId` + bundle merge + provenance |
| Video Generator integration | Done | Txt2Vid spatial field + queue conditioning |
| Storyboard integration | Done | panel spatialMapId/version linkage |
| Timeline preparation | Partial | storyboard timeline prep carries spatial ids |
| Co-Director integration | Done | `spatial.*` tools + tests |
| Export | Partial | reference bundle + export tab summary |

## Test Results

| Suite | Command | Outcome |
| --- | --- | --- |
| Unit / API | `cd studio-api && python -m pytest tests/test_m411_spatial_map.py tests/test_m411_codirector_spatial_tools.py -q` | **11 passed** |
| Image contracts (spatial slice) | `pytest ... -k "spatial or cinematic_maps_to_image_product_body"` | **9 passed** (sibling suite has unrelated defaults drift) |
| FE build | `cd studio-web && npm run build` | **passed** (prior agent run) |
| Playwright | `npx playwright test tests/e2e/m411/m411-spatial-map-360-consistency.spec.ts --project=chromium --retries=0` | **1 passed** (E2E harness / live map API) |
| Live image generation with Spatial Map | pending human/CI live provider pass | not claimed |
| Live video generation | pending healthy provider | not claimed |
| Manual UX stamp | pending human review at 1366×768 / 1920×1080 | not claimed |

## Evidence Paths

- Audit: `docs/release-gate/m411/M411_REPOSITORY_AND_SPATIAL_AUDIT.md`
- Data: `docs/release-gate/m411/M411_DATA_AND_PERSISTENCE.md`
- Architecture pack: `docs/spatial-map/m4-11/`
- Backend package: `studio-api/app/spatial_map/`
- Co-Director handler: `studio-api/app/codirector/tools/handlers/spatial_m411.py`
- FE studio: `studio-web/src/components/spatial-map/`
- Playwright: `tests/e2e/m411/m411-spatial-map-360-consistency.spec.ts`

## Known Limitations

- Coordinate conditioning is **approximate translation** for current providers (honest metadata).
- Occlusion / visibility uses approximate bearing logic, not pixel-perfect geometry.
- Panorama stitching is not a certified geometric equirectangular pipeline.
- Camera preview is simplified (map proxies / facing), not photoreal.
- Full Project Library browse/search for Spatial Maps is light (list + tags), not a dedicated library module.
- Manual UX certification and live image-with-spatial provenance run remain open.
- Broader legacy Co-Director / image_product suites have pre-existing unrelated failures on this branch.

## Verdict

```text
CONDITIONAL GO
```

### Why not full GO

1. Human Manual UX certification not stamped.
2. Live image generation with Spatial Map provenance (real provider output + provenance record) not yet stamped.
3. Several export / camera-preview / library surfaces remain partial vs the full mission matrix.

### What already meets GO intent

- Spatial Map + 360 Collage as one production workspace.
- Hard 4/4/8 limits with typed errors.
- Co-Director 360 capture intelligence: one master environment + camera rotation.
- Image Generator Spatial Reference selector + provenance fields.
- Video Generator spatial context handoff.
- Storyboard spatial linkage fields.
- Persistence + version bump + scene assignment + variants.
