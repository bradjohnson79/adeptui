# Camera System

Spatial cameras provide the creator-facing bridge between blocking and image/video framing.

## Code paths

- Camera placement and hero selection: `studio-api/app/spatial_map/service.py`
- Bundle camera selection: `studio-api/app/spatial_map/reference_bundle.py`
- Web camera pickers: `studio-web/src/components/spatial-map/SpatialReferenceFieldset.tsx`

## Current behavior

- Image Generator can optionally target one saved camera with `spatialCameraId`.
- Video Generator can optionally declare start and end cameras for motion-aware conditioning.
- When no explicit camera is chosen, the hero camera is used, then the first saved camera as fallback.
