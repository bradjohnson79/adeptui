# Export

The current export surface is lightweight: prompt-ready summaries, bundle metadata, storyboard payloads, and project-library assets.

## Code paths

- Spatial bundle export API: `studio-api/app/spatial_map/router.py`
- Spatial workspace creator-facing export actions: `studio-web/src/components/spatial-map/SpatialMapStudio.tsx`
- Storyboard exports: `studio-api/app/storyboard_studio/export.py`

## Current behavior

- Bundles expose reference asset ids, camera state, movement paths, and prompt-ready summaries.
- Storyboard exports remain storyboard-centric and do not yet render a dedicated spatial appendix.
- Certification artifacts for M4.11 should be stored under `docs/release-gate/m411/` and `artifacts/` when generated.
