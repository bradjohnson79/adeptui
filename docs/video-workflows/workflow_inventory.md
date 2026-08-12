# Adept UI Video Workflow Inventory (M41 Phase 4.1B)

| Field | Value |
|---|---|
| **Phase** | M41 4.1B — Certified ComfyUI Video Workflow Library |
| **Date** | 2026-07-29 |
| **Machine-readable** | [`artifacts/video-workflows/workflow_inventory.json`](../../artifacts/video-workflows/workflow_inventory.json) |
| **Authority** | [`config/video-workflows/certified-registry.json`](../../config/video-workflows/certified-registry.json) |

## Production pipeline (must leave no holes)

| WF-ID | workflowKey | Builder / path | Notes |
|---|---|---|---|
| WF-LTX-001 | `ltx.simple_i2v` | `ltx_builder.build_ltx_simple_i2v` | Local I2V; start frame required |
| WF-LTX-002 | `ltx.scene` | `ltx_builder.build_ltx_scene_workflow` | Director multi-keyframe |
| WF-LTX-003 | `ltx.ingredients_ic_lora` | `ltx_ingredients_compiler` | Blocked without IC-LoRA weights |
| WF-WAN-001 | `wan.first_last_frame` | `wan_builder.build_wan_flf_workflow` | Middle unsupported |
| WF-WAN-002 | `wan.three_frame` | `wan_builder.build_wan_three_frame_workflow` | **New in 4.1B** |
| WF-SHOT-001 | `director.shot_render` | Orchestration → leaf | Shot-scoped render |
| WF-SCENE-001 | `director.scene_render` | Orchestration → leaf | Canonical scene render |
| WF-TIMELINE-001 | `director.timeline_render` | Stitch scene outputs | FFmpeg orchestration |
| WF-TIMELINE-002 | `director.batch_timeline` | Generate missing + stitch | Batch orchestration |
| WF-EXTEND-001 | `video.extend` | Last-frame → certified I2V | Local Comfy path (repaired) |
| WF-LIPSYNC-001 | `lipsync.latentsync` | `lipsync_builder` | LatentSync |
| WF-FAL-001…004 | `fal.*` | fal adapters | Paid cloud |

## Deferred (stable contracts only)

| WF-ID | workflowKey |
|---|---|
| WF-UPSCALE-001 | `video.upscale` |
| WF-DEF-001…007 | motion/camera/character/rife/restoration/local_t2v/pose |

## Execution architecture (4.1B)

```text
Product UI → WorkflowResolver → Certified Workflow Registry
  → CanonicalWorkflowContract → QueueWorker (execute-only)
  → fingerprint check → Comfy/fal → Output Gate
```

Root `workflows/*.json` files are **non-authoritative** documentation mirrors.
