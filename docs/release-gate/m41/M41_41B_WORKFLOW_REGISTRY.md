# M41 4.1B — Certified Workflow Registry

| Field | Value |
|---|---|
| **Authority** | [`config/video-workflows/certified-registry.json`](../../../config/video-workflows/certified-registry.json) |
| **Loader** | [`studio-api/app/video_runtime/certified_registry.py`](../../../studio-api/app/video_runtime/certified_registry.py) |
| **HTTP** | `GET /api/video-runtime/certified-registry` |
| **Artifacts** | [`artifacts/m41/41b/workflow_registry.json`](../../../artifacts/m41/41b/workflow_registry.json) |

## Single source of truth

The Certified Workflow Registry replaces split ownership between:

- `workflows/registry.py` (now builder binding view)
- `compatibility-catalog.json` (now projection via `compatibility_projection()`)
- Ad-hoc `queue_worker` selection (replaced by WorkflowResolver)

## Record shape

Each entry includes: `workflowId`, `workflowKey`, semver `workflowVersion`, modality, engine, status, builder path, nodes/models/extensions, inputs/outputs, limitations, VRAM profile, cancellation/output/playback flags, API contract, **fingerprints** (`graphHash`, `builderHash`, `nodeInventoryHash`, `modelInventoryHash`), and optional **Certification Record**.

## Status enum

`Draft | Built | SmokeTested | Certified | Deferred | Blocked | Retired`

Bare `Certified` without a Certification Record is invalid and coerced to `Blocked`.

## Compatibility projection honesty

| Registry status | capabilityState |
|---|---|
| Certified | `production_ready` |
| Deferred | `deferred` |
| Blocked / Built / SmokeTested | `blocked` / `pending_certification` |
| Retired | `retired` |

## 4.1C readiness

`modality` is first-class (`video` now; `image` later) so 4.1C can reuse registry/resolver/fingerprint/cert infrastructure without forking.
