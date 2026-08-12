# M41 4.1B — Output Validation

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Gate** | [`studio-api/app/video_runtime/output_gate.py`](../../../studio-api/app/video_runtime/output_gate.py) |
| **Artifact** | [`artifacts/m41/41b/workflow_output_results.json`](../../../artifacts/m41/41b/workflow_output_results.json) |

## Contract (required for CERTIFIED)

- File exists; container/codec valid
- Duration / resolution / frame count within expected bounds
- Poster + proxy helpers succeed when ffmpeg available
- Asset registration on success paths (`video.extend`, scene renders)
- Browser playback readiness flagged via gate
- Timeline stitch compatibility for orchestration outputs

## Live results

**SKIP** — no live generation outputs to validate. Static graph validation PASS for buildable workflows.
