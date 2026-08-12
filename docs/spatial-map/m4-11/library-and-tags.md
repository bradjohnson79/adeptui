# Library And Tags

Spatial integrations reuse the open project library. They do not create new projects or hidden asset stores.

## Code paths

- Spatial bundle asset collection: `studio-api/app/spatial_map/reference_bundle.py`
- Image asset registration: `studio-api/app/queue_worker.py`
- Video asset registration: `studio-api/app/queue_worker.py`

## Current behavior

- Background plates, character refs, prop refs, and captured 360 stills are read from project assets.
- Generated image/video outputs remain tagged in the same project library.
- Spatial linkage is persisted as provenance metadata, not as a separate library namespace.
