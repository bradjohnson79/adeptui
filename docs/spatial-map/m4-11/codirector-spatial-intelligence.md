# M4.11 Co-Director Spatial Intelligence

This milestone adds Co-Director `spatial.*` tools to the closed tool registry so the assistant can read, stage, and prepare Spatial Map work without bypassing creator approval.

## Tool groups

Read tools:

- `spatial.list_maps`
- `spatial.get_map`
- `spatial.inspect_scene`
- `spatial.list_cameras`
- `spatial.get_camera_view`
- `spatial.check_visibility`
- `spatial.check_consistency`
- `spatial.build_reference_bundle`

Proposal-gated mutation tools:

- `spatial.create_map`
- `spatial.update_bounds`
- `spatial.place_character`
- `spatial.place_prop`
- `spatial.move_placement`
- `spatial.create_camera`
- `spatial.update_camera`
- `spatial.create_path`
- `spatial.generate_360_plan`
- `spatial.assign_to_scene`
- `spatial.prepare_image_generation`
- `spatial.prepare_video_generation`

## Backend usage

The handler lives at `studio-api/app/codirector/tools/handlers/spatial_m411.py` and uses the Spatial Map backend directly:

- `studio-api/app/spatial_map/service.py`
- `studio-api/app/spatial_map/capture_intelligence.py`
- `studio-api/app/spatial_map/collage.py`
- `studio-api/app/spatial_map/reference_bundle.py`

All mutating tools follow the same proposal-first pattern as M4.10 voice tools:

1. Preview with a creator-readable summary.
2. Wait for explicit approval.
3. Apply the change or return the approved prep packet.

## 360 capture intelligence

`spatial.generate_360_plan` is intentionally constrained:

- It builds one `masterEnvironmentPrompt`.
- It rotates a virtual camera through `0/45/90/135/180/225/270/315`.
- It locks camera height and lens across the full set.
- It supports `environment_only` and `include_characters`.
- It does not invent eight unrelated worlds.

The plan is created through `capture_intelligence.build_scene_capture_plan` via `service.create_capture_plan`, and the approved apply step also persists a matching collage shell with the same locked settings.

## Visibility and consistency

`spatial.check_visibility` uses an approximate camera-space estimate and reports:

- `visible`
- `partially`
- `occluded`
- `outside`
- `unknown`

This is a creator guidance layer, not a claim of true 3D reconstruction or physically exact occlusion.

## Generation prep

`spatial.prepare_image_generation` and `spatial.prepare_video_generation` stay proposal-gated so the creator explicitly approves the handoff packet before downstream generation work begins. The apply step returns:

- the selected/hero camera framing
- a Spatial Map reference bundle
- a prompt packet grounded in the same environment and staged assets

They do not silently generate media on approval.
