# Storyboard Integration

Spatial-aware image frames can carry their map linkage into Storyboard panels.

## Code paths

- Panel add/replace metadata: `studio-api/app/storyboard_studio/api.py`, `studio-api/app/storyboard_studio/add_from_image.py`
- Workspace hydration: `studio-api/app/storyboard_studio/documents.py`
- Image Studio handoff: `studio-web/src/components/image-studio/CinematicImageStudio.tsx`

## Current behavior

- Panels now preserve `spatialMapId` and `spatialMapVersion` alongside continuity metadata.
- Replace/undo keeps prior spatial linkage when restoring the previous panel asset.
- Storyboard UI payloads expose the linkage through `StoryboardPanelLink`.
