# Architecture

Authoritative store: `spatial_map_documents.document_json`.

- Live buffer: `document.characters` / `document.props` = active segment
- Snapshots: `movementSegments[].characterStates` / `propStates`
- Cameras, environment, ERS pointers stay global
- Scene Spatial Profile may point at `movementSegmentId` + revision only
- Co-Director has no shadow movement store
- `SpatialMovementPath` / `document.paths` stay unused for this feature
