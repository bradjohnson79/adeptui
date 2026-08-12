# Multi-Shot Image Planning Architecture

## Goal

Decompose a single scene into an ordered collection of shots, each with its own image prompt, video/motion prompt, references, and candidate history. The architecture is provider-agnostic: Krea 2 Turbo may be the first recommended engine, but FLUX, Qwen Image, or future providers can back the same plan without rewriting the data model.

## Data Model

Three project-scoped SQL tables in `studio-api/app/image_pipeline/multi_shot/models.py`:

### `multi_shot_plans`

One row per scene decomposition effort.

| Field | Purpose |
|-------|---------|
| `id` | Plan UUID |
| `project_id`, `scene_id` | Ownership |
| `name` | Creator-facing name |
| `provider_id`, `model_id` | Provider hints (plain strings, no registry validation) |
| `shared_visual_context` | Scene-wide visual description |
| `shared_references_json` | Polymorphic reference list with roles |
| `aspect_ratio`, `resolution_label` | Output format hints |
| `status` | `draft` / `active` / `archived` |

### `multi_shots`

Ordered shots inside a plan.

| Field | Purpose |
|-------|---------|
| `id` | Shot UUID |
| `plan_id`, `project_id`, `scene_id` | Ownership (denormalized for deletion sweep) |
| `order_index` | Sort order (mutable) |
| `title`, `prompt`, `image_prompt`, `video_prompt` | Direction |
| `duration_hint` | Suggested Timeline duration |
| `framing`, `camera_angle` | Shot-specific direction |
| `subject_ids_json`, `reference_ids_json` | Linked subjects/references |
| `seed_strategy` | `fixed` / `sequence` / `random` |
| `status` | `pending` / `generating` / `candidate_review` / `approved` / `rejected` / `sent_to_timeline` |
| `approved_asset_id`, `approved_candidate_id` | Approved selection |
| `timeline_batch_block_id` | W46 Timeline lineage |

### `multi_shot_candidates`

Append-only candidate history per shot.

| Field | Purpose |
|-------|---------|
| `id` | Candidate UUID |
| `shot_id`, `plan_id`, `project_id` | Ownership |
| `generation_id`, `provider`, `model`, `seed`, `prompt` | Generation provenance |
| `references_json`, `loras_json`, `settings_json` | Conditioning used |
| `asset_id` | Resulting asset (may be simulated in cert) |
| `status` | `pending` / `approved` / `rejected` |

## API Surface

Mounted under `/api/projects/{project_id}` in `app/image_pipeline/multi_shot/api.py`:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/scenes/{scene_id}/multi-shot-plans` | Create plan |
| GET | `/scenes/{scene_id}/multi-shot-plans` | List plans |
| GET | `/multi-shot-plans/{plan_id}` | Get plan |
| PATCH | `/multi-shot-plans/{plan_id}` | Update plan |
| DELETE | `/multi-shot-plans/{plan_id}` | Delete plan + shots + candidates |
| POST | `/multi-shot-plans/{plan_id}/shots` | Add shot |
| POST | `/multi-shot-plans/{plan_id}/shots/reorder` | Full-set reorder |
| PATCH | `/multi-shot-plans/{plan_id}/shots/{shot_id}` | Update shot |
| DELETE | `/multi-shot-plans/{plan_id}/shots/{shot_id}` | Delete shot |
| POST | `/multi-shot-plans/{plan_id}/shots/{shot_id}/candidates` | Record candidate |
| POST | `/multi-shot-plans/{plan_id}/shots/{shot_id}/approve` | Approve candidate |
| POST | `/multi-shot-plans/{plan_id}/shots/{shot_id}/reject` | Reject candidate |
| POST | `/multi-shot-plans/{plan_id}/send-to-timeline` | Hand off approved shots |
| GET | `/scenes/{scene_id}/multi-shot-ers-recommendation` | ERS advisory |

All lookups are project-scoped: a plan/shot/candidate id from another project returns 404.

## Approval Invariant

At most one approved candidate per shot. Approving a new candidate demotes the previous approved candidate to `pending`. Rejecting the approved candidate clears the shot's approval fields and returns the shot to `candidate_review`. Rejected candidates remain in history.

## Timeline Handoff

`send-to-timeline` iterates over approved shots and, for each, calls the W46 Timeline service:

1. `add_batch` — creates a new `BatchBlock` with the shot's duration hint and label.
2. `add_clip_to_batch` — attaches the approved image as a `visualClip` with `role="start"`.
3. `touch_batch_config` — sets the `promptSegments` to the shot's `video_prompt` (or `image_prompt` / `prompt` fallback).

The created `batchBlockId` is stored on the shot row, and the shot status becomes `sent_to_timeline`. The operation is idempotent via `only_missing=true`.

## ERS Recommendation

When a Krea 2 Multi-Shot plan is selected, the backend checks whether the project has any Environment Reference Sheets. If none exist, it recommends creating one to improve location continuity; if sheets exist, it notes that ERS environment assets are wired as `environment` conditioning through the shared reference path.

## Project Deletion

All three tables carry `project_id`, so the generic project-deletion sweep in `app/project_cleanup.py` removes them automatically. Plan-level delete cascades explicitly in the service layer.

## Co-Director Tools

Closed-registry tools in `app/codirector/tools/handlers/multi_shot_tools.py`:

- `multi_shot.list_plans` — read
- `multi_shot.get_plan` — read
- `multi_shot.ers_recommendation` — read
- `multi_shot.create_plan` — mutating (create plan + shots)
- `multi_shot.add_shots` — mutating
- `multi_shot.send_to_timeline` — mutating

## Creator UI Status

The backend architecture, REST API, and Co-Director tools are complete. A dedicated creator-facing Multi-Shot workspace (shot list, candidate comparison, drag-to-reorder) is the remaining UI layer to be built on top of this verified backend.

## See Also

- `KREA2_INTEGRATION_ARCHITECTURE.md`
- `KREA2_COMFYUI_WORKFLOW.md`
- `KREA2_MULTISHOT_INTEGRATION_FINAL_CERTIFICATION.md`
