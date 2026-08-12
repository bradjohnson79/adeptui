# M4.11 Architecture

Spatial Map now feeds a shared reference-bundle path that image, video, and storyboard consumers can reuse without copying raw scene JSON into prompts.

## Code paths

- Spatial map documents and bundle compilation: `studio-api/app/spatial_map/service.py`, `studio-api/app/spatial_map/reference_bundle.py`, `studio-api/app/spatial_map/router.py`
- Image compile surface: `studio-api/app/image_studio/api.py`, `studio-api/app/image_studio/contracts.py`
- Image Product compile/runtime handoff: `studio-api/app/image_product/compile.py`, `studio-api/app/image_product/service.py`, `studio-api/app/queue_worker.py`
- Web selectors: `studio-web/src/components/spatial-map/SpatialReferenceFieldset.tsx`

## Integration shape

1. The creator selects a saved map by `spatialMapId`.
2. The backend compiles a `SpatialReferenceBundle`.
3. The bundle is summarized into creator-language conditioning and reference asset ids.
4. Image/video jobs persist map id, version, and chosen camera metadata for reopen/provenance.
