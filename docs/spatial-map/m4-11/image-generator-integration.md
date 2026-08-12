# Image Generator Integration

The Cinematic Image Generator accepts an optional saved spatial map and folds it into creator-facing conditioning.

## Code paths

- Request contract and compile preview: `studio-api/app/image_studio/contracts.py`, `studio-api/app/image_studio/api.py`
- Prompt/build metadata: `studio-api/app/image_product/compile.py`, `studio-api/app/image_product/service.py`
- Reopen provenance: `studio-api/app/image_studio/provenance.py`
- Web UI selector: `studio-web/src/components/image-studio/CinematicImageStudio.tsx`

## Current behavior

- Request fields: `spatialMapId`, `spatialMapVersion`, `spatialCameraId`
- The backend builds a `SpatialReferenceBundle`, merges reference asset ids, and writes a plain-language spatial summary into creative context.
- Provenance preserves map id/version/camera so an image can be reopened with the same spatial reference selected.
