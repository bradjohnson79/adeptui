# M4.11 Spatial Data Architecture

## Purpose

`studio-api/app/spatial_map/` adds a first-class Spatial Map document model without replacing the existing legacy `spatial.py` or `spatial_scene.py` modules.

This package is the certified backend layer for:

- bounded character / prop / camera blocking
- scene and location assignment
- 360 collage planning
- Spatial reference bundle compilation for image and video workflows
- Co-Director capture planning with one master environment prompt

## Persistence

Spatial Maps persist in `spatial_map_documents`.

Stored columns:

- `id`
- `project_id`
- `scene_id`
- `location_id`
- `title`
- `document_json`
- `created_at`
- `updated_at`

`document_json` is the source of truth for the full document payload. Indexed lookup is preserved through `project_id`, `scene_id`, and `location_id`.

## Document shape

`SpatialMapDocument` stores:

- `bounds` in `adept-world-v1`
- `anchors`
- `characters`
- `props`
- `cameras`
- `paths`
- optional `collage`
- variant lineage via `variantOfId` and `variantIds`
- assignment lineage via `assignedSceneIds`

## Certified limits

- maximum 4 characters
- maximum 4 props
- maximum 8 cameras

Limits are enforced by the service layer and surfaced through typed HTTP errors.

## Interop

This package extends existing spatial features alongside:

- `studio-api/app/spatial.py`
- `studio-api/app/spatial_scene.py`
- `studio-api/app/spatial_prompt_builder.py`

It does not mutate or migrate those legacy contracts.
