# M4.11 Data and Persistence

## Scope

This wave adds `studio-api/app/spatial_map/` as the M4.11 backend package for Spatial Map documents, 360 collage planning, scene assignment, variants, capture intelligence, and reference bundles.

## Persistence contract

- table: `spatial_map_documents`
- primary key: `id`
- indexed columns: `project_id`, `scene_id`, `location_id`
- payload: `document_json`

The JSON payload holds the full Spatial Map document while the indexed columns support project, scene, and location lookups.

## Non-breaking rule

Existing modules stay intact:

- `studio-api/app/spatial.py`
- `studio-api/app/spatial_scene.py`

M4.11 extends the backend alongside those modules rather than rewriting or replacing them.

## Limits

- 4 characters per map
- 4 props per map
- 8 cameras per map

Typed HTTP errors are raised when certified limits are exceeded.

## 360 capture contract

- one master environment prompt
- camera rotation only for the required 8 directions
- fixed lens and camera height across the set
- optional character inclusion mode

## Routing

FastAPI router prefix:

- `/api/spatial-map/*`

## Test coverage

`studio-api/tests/test_m411_spatial_map.py` covers:

- certified limits
- reference bundle compilation
- 360 plan generation
- variant lineage
- scene assignment
