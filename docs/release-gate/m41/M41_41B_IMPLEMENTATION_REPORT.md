# M41 4.1B — Implementation Report

| Field | Value |
|---|---|
| **Branch** | `phase2/video-runtime-m41-41b-certified-workflows` |
| **Date** | 2026-07-29 |
| **Extends** | M41 4.1A Video Runtime (no parallel stack) |

## Delivered architecture

```text
Product UI → WorkflowResolver → Certified Workflow Registry
  → CanonicalWorkflowContract → QueueWorker (execute-only)
  → static validate → fingerprint check → Comfy/fal → Output Gate
```

### New / extended modules

| Module | Role |
|---|---|
| `config/video-workflows/certified-registry.json` | Single authority |
| `video_runtime/certified_registry.py` | Loader + productionReady honesty |
| `video_runtime/fingerprints.py` | graph/builder/node/model hashes + drift |
| `video_runtime/workflow_resolver.py` | Intent → contract |
| `video_runtime/workflow_execute.py` | Build + validate + fingerprint gate |
| `video_runtime/graph_validation.py` | Fail-closed static graph checks |
| `workflows/wan_builder.build_wan_three_frame_workflow` | Dual-segment WAN three-frame |
| `scripts/m41_41b_live_certify.py` | Static + live cert harness |

### QueueWorker changes

- Imperative LTX/WAN selection removed from `_build_and_run_scene`
- Resolver selects leaf; worker builds/executes only
- `wan.three_frame` runs start→mid and mid→end segments then stitches
- `render_shot`, `batch_timeline`, `video_extend` job kinds
- `video.extend` extracts last frame and runs local certified I2V (not fal-only `_txt2vid`)

### API

- `GET /api/video-runtime/certified-registry`
- `POST /api/video-runtime/resolve`
- `POST /api/video-runtime/validate-graph`
- `GET /api/video-runtime/gate` (phase M41-4.1B + certified counts)
- `POST /api/projects/{id}/render` kinds: `shot`, `batch_timeline`

### UI

- Diagnostics shows Certified Workflow Library
- GenTools maps `DEFERRED` → Deferred (not Unknown)

## Automated tests

- `studio-api/tests/test_m41_41b_certified_workflows.py` — **pass**
- `studio-api/tests/test_m41_41a_video_runtime.py` — **pass** (updated honesty)
- Playwright: `tests/e2e/m41/m41-41b-certified-workflows.spec.ts`

## Not claimed

Live Comfy smoke/cancel/VRAM/playback certification — ComfyUI was unreachable at certify time. Workflows remain **Blocked** until `ADEPT_41B_LIVE=1` suites PASS.
