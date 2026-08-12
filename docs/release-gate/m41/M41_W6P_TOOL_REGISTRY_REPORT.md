# M41 W6P-3 — Tool Registry Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | `artifacts/m41/w6p/tool_registry_results.json` |
| **Verdict** | **PASS** |

## Added / wired tools

`propose_image_generate`, `propose_video_generate`, `propose_shot_generate`, `propose_scene_generate`, `propose_three_frame_generate`, `propose_timeline_render`, `propose_batch_timeline`, `propose_lipsync`, `propose_voice_generate`, `propose_subtitle_generate`, `editor.place_asset`, `job.cancel`, `job.retry`

`propose_video_extend` now routes through ProductionIntent handlers (no hardcoded workflow bypass).

Handlers: `studio-api/app/codirector/tools/handlers/media_execution.py`

## Honesty

Stub-copy fallbacks removed from Co-Director generation handlers and Generation Tools API. Fail closed with actionable errors.
