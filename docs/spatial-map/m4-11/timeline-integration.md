# Timeline Integration

Timeline prep remains storyboard-first, but spatial linkage can now survive the panel stage.

## Code paths

- Proposal generation and confirm flow: `studio-api/app/storyboard_studio/timeline_prep.py`
- Storyboard contracts: `studio-api/app/storyboard_studio/contracts.py`

## Current behavior

- Timeline prep proposals carry `spatialMapId` and `spatialMapVersion` when present on the panel.
- Confirmed payloads keep that linkage in the created timeline payload metadata.
- Native timeline camera blocking from Spatial Map is not yet a primary timeline authoring flow.
