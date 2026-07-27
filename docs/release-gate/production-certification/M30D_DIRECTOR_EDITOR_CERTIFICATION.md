# M3.0d Director â†’ Editor Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Sync model | `director_plan_transformed_into_editor_sequence` |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Certification scope

This document certifies the **bounded** Directorâ†’Editor handoff contract:

- A Director sequence with a known `scene_id` and `asset_id` can be sent to the Editor video track.
- The resulting clip preserves source linkage and length.
- Editor mutations persist across reload.

It does not claim full browser walkthrough of every workspace control or multi-track compositing.

## Sync model

Export and queue worker declare:

```json
"sync_model": "director_plan_transformed_into_editor_sequence"
```

Location: `studio-api/app/queue_worker.py` (export contract metadata).

Semantic meaning: Director plan items are **transformed** into Editor sequence clips â€” not a lossless 1:1 structural clone of every Director track type. The transform preserves:

- `source_director_sequence_id`
- `source_scene_id`
- clip `length` (from handoff request)
- target track assignment (`video` by default)

## API path

```text
POST /api/projects/{projectId}/scenes
POST /api/projects/{projectId}/director-sequences
POST /api/projects/{projectId}/director-sequences/{seqId}/send-to-editor
GET  /api/projects/{projectId}/editor
PUT  /api/projects/{projectId}/editor
```

## Test evidence

`studio-api/tests/test_m30d_closures.py::test_director_to_editor_preserves_scene_and_order`

| Assertion | Verified |
|-----------|----------|
| Handoff HTTP status < 400 | Yes |
| `clip.source_director_sequence_id == seq_id` | Yes |
| `clip.source_scene_id == scene_id` | Yes |
| Clip length matches request (3.5s) | Yes |
| Clip appears on editor video tracks | Yes |
| Reload preserves linkage | Yes |
| Editor mutation (`label: editor-edit`) persists | Yes |

Included in 631/0/6 pytest gate.

## Situation evidence

Production situations S01â€“S12 record approvals, handoffs, and timeline completion in `artifacts/m30-situations/situation-finish.json` (referenced from M3.0c matrix). Export packs validate durable timeline representation via `director_json` in each scene.

## Related register items

| ID | Relationship |
|----|--------------|
| B17 | sceneId preserved through handoff |
| B18 | export reads durable director/editor state |

## Status

Directorâ†’Editor handoff: **Closed (API-proven)** at `43a5c0f0152a39327e87b10de11fd55e5b16ad90`.

Full browser UX certification of Editor workspace keyboard flows remains under accessibility (see `M30D_ACCESSIBILITY_CERTIFICATION.md`).
