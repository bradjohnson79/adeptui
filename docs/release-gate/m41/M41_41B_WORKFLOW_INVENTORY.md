# M41 4.1B — Workflow Inventory

| Field | Value |
|---|---|
| **Phase** | M41 4.1B |
| **Date** | 2026-07-29 |
| **Canonical** | [`docs/video-workflows/workflow_inventory.md`](../../video-workflows/workflow_inventory.md) |
| **JSON** | [`artifacts/video-workflows/workflow_inventory.json`](../../../artifacts/video-workflows/workflow_inventory.json) |

## Permanent WF-IDs (production pipeline)

| WF-ID | workflowKey | Status at inventory |
|---|---|---|
| WF-LTX-001 | `ltx.simple_i2v` | Wired → Blocked pending live cert |
| WF-LTX-002 | `ltx.scene` | Wired → Blocked pending live cert |
| WF-LTX-003 | `ltx.ingredients_ic_lora` | Wired → Blocked pending live cert |
| WF-WAN-001 | `wan.first_last_frame` | Wired → Blocked pending live cert |
| WF-WAN-002 | `wan.three_frame` | Built (dual-segment FLF + stitch) |
| WF-SHOT-001 | `director.shot_render` | Built (orchestration) |
| WF-SCENE-001 | `director.scene_render` | Built (orchestration) |
| WF-TIMELINE-001 | `director.timeline_render` | Built (orchestration) |
| WF-TIMELINE-002 | `director.batch_timeline` | Built (orchestration) |
| WF-EXTEND-001 | `video.extend` | Repaired local I2V path |
| WF-LIPSYNC-001 | `lipsync.latentsync` | Wired → Blocked pending live cert |
| WF-FAL-001…004 | `fal.*` | Wired → Blocked pending live/credentials |
| WF-UPSCALE-001 | `video.upscale` | Deferred |
| WF-DEF-001…007 | research modes | Deferred |

Authority: [`config/video-workflows/certified-registry.json`](../../../config/video-workflows/certified-registry.json).
