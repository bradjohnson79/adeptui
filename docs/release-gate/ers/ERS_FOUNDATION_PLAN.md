# ERS Foundation Plan

## Scope

This foundation adds a project-owned Environment Reference Sheet record that Co-Director can orchestrate through the closed tool registry. It reuses:

- `spatial_map` for north-locked layout and directional prompts
- `image_pipeline` for directional view planning and candidate generation
- Project Library for registered exports
- Production Bible `location` entities for project integration

## Implemented foundation flow

1. Create ERS draft from creator description.
2. Attach Spatial Map and lock north.
3. Prepare North / East / South / West Image Pipeline plans and candidate groups.
4. Approve each direction explicitly.
5. Run metadata-based continuity validation that preserves approved directions.
6. Compose the sheet metadata.
7. Register the ERS back into the project as a location-linked record.
8. Export PNG, PDF, and offline HTML package as project assets.

## Non-goals for this pass

- No new parallel generation stack
- No ComfyUI graph-facing creator workflow
- No fake 3D mesh claims
- No pixel-level continuity claim

## UI surface

- Co-Director `Plans` content now includes an ERS review panel with tabs for Overview, Views, Continuity, and Exports.
- The panel is read-only for canonical creation. Creators still start ERS work through Co-Director approvals.
