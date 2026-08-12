# Video Generator Integration

Text to Video accepts an optional saved spatial map, optional start/end cameras, and an optional precompiled bundle.

## Code paths

- Web request assembly: `studio-web/src/components/Txt2VidPanel.tsx`
- Runtime conditioning and provider refs: `studio-api/app/queue_worker.py`
- fal argument builder: `studio-api/app/fal_catalog.py`

## Current behavior

- Request fields: `spatialMapId`, `spatialMapVersion`, `spatialStartCameraId`, `spatialEndCameraId`, `spatialReferenceBundle`
- The backend appends creator-language spatial guidance to the provider prompt.
- On fal-backed paths, the runtime can upload best-effort spatial still references when images are available.

## Known limit

Local LTX/WAN still operate under the existing start-frame policy and do not consume native spatial coordinates directly.
