# Scene Assignment

Scene assignment keeps one project, one library, while allowing a saved map to remain linked to the scene it blocks.

## Code paths

- Canonical map assignment: `studio-api/app/spatial_map/service.py`, `studio-api/app/spatial_map/router.py`
- Current Spatial Map workspace assignment button: `studio-web/src/components/spatial-map/SpatialMapStudio.tsx`

## Current behavior

- Maps can be assigned to a scene through the canonical `/assign-scene` API.
- The existing Spatial Map workspace still uses a scene-scoped UI path for its assignment button.
- Image/video integrations consume saved map ids directly and do not create disposable projects.
