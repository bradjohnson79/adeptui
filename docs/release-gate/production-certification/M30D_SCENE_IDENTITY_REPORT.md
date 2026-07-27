# M3.0d Scene Identity Report

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register item | B17 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Problem (B17)

Video I2V and export paths could drop `sceneId` from job payloads and exported scene records, breaking continuity between Director plans, scene-scoped assets, and export packs.

## Expected state

`sceneId` must flow:

1. From scene creation through I2V/txt2vid job params
2. Into queue worker handlers (`_m29_run`, render/export)
3. Into export pack `project.json` scene entries including `director_json`

## Root cause

Job enqueue paths omitted `scene_id` in params; export serializer did not always emit scene-scoped director state.

## Implementation

- I2V/txt2vid routes accept and persist `sceneId` on Studio Job rows.
- `queue_worker.py` handlers resolve `job.scene_id` and attach scene context to asset linkage.
- Export contract `m30d-canonical-timeline-v1` includes per-scene `director_json` (B18 coupling).

Key surfaces:

- `studio-api/app/codirector/m29/api.py` — scene_id on generation requests
- `studio-api/app/queue_worker.py` — scene lookup and export scene keys
- `studio-api/tests/test_m30d_closures.py::test_director_to_editor_preserves_scene_and_order` — handoff preserves `source_scene_id`

## Test and artifact evidence

| Evidence | Result |
|----------|--------|
| `phase18-final-validation.json` — all 12 exports | `sceneKeys` includes `id`, `director_json`, `engine`, `prompt`, etc. |
| `directorJson: true` on every situation | PASSED |
| Director→Editor API test | `source_scene_id` matches originating scene |
| Full pytest gate | 631/0/6 |

Example scene keys from S01 export validation:

```json
"sceneKeys": [
  "director_json",
  "duration_sec",
  "engine",
  "id",
  "index",
  "lipsync_output_path",
  "name",
  "output_path",
  "prompt"
]
```

## Status

**B17: Closed** at `43a5c0f0152a39327e87b10de11fd55e5b16ad90`.

## Boundary

Multi-scene editorial continuity across complex reorder operations is not live-proven beyond the twelve bounded situation exports. Scene identity within each situation's export pack is proven.
