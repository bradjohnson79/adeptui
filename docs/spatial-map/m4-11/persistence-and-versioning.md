# Persistence And Versioning

M4.11 uses the saved Spatial Map document id plus its update timestamp as the lightweight version handshake for downstream jobs.

## Code paths

- Document persistence: `studio-api/app/spatial_map/service.py`
- Bundle version field: `studio-api/app/spatial_map/schemas.py`, `studio-api/app/spatial_map/reference_bundle.py`
- Image provenance reopen: `studio-api/app/image_studio/provenance.py`

## Current behavior

- `spatialMapId` identifies the source map.
- `spatialMapVersion` tracks the saved `updatedAt` value used at compile time.
- Reopen payloads restore the saved map id/version/camera from provenance when available.
