# Character Placement

Character placement remains canonical in Spatial Map documents, then translates into plain-language prompt hints for downstream generators.

## Code paths

- Placement persistence: `studio-api/app/spatial_map/service.py`
- Position labels and summaries: `studio-api/app/spatial_map/reference_bundle.py`
- Selector summaries: `studio-web/src/contracts/spatialReference.ts`

## Current behavior

- Character counts are limited to four in certified flows.
- The bundle exposes left/center/right and foreground/midground/background creator labels.
- Image/video integrations use those labels in summary strings such as `Korri at foreground left`, not raw coordinates.
