# Movement Paths

Movement paths are stored in the Spatial Map document and currently matter most for video conditioning.

## Code paths

- Path creation and validation: `studio-api/app/spatial_map/service.py`
- Video bundle inclusion: `studio-api/app/spatial_map/reference_bundle.py`
- Video runtime prompt usage: `studio-api/app/queue_worker.py`

## Current behavior

- Image bundles exclude movement paths.
- Video bundles include them and summarize them as motion guidance in creator-language.
- Current downstream video providers still receive approximate motion translation rather than native camera-path execution.
