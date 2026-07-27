# M3.0c Unified Job System Proof

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Approach | Dual persistence + single inspect/control DTO (no full worker merge) |
| Module | `studio-api/app/codirector/unified_jobs.py` |
| Route | `GET /api/codirector/jobs/{job_id}` |

## Contract

`to_unified_dto(source, row)` normalizes Executive and Studio jobs into one DTO including:

`job_id`, `project_id`, `workspace_id`, `capability_id`, `provider`, `engine`, `model`, `operation`, `status`, `progress_mode`, `progress_value`, timestamps, `provider_request_id` (from `history_json.falRequestId` when present), asset ids, sanitized params/errors, provenance, `approval_id`, `retry_parent_id`, `source`.

Status mapping covers Studio `queued/running/done/failed/cancelled` (+ interrupted recovery stage) and Executive statuses onto the M3.0c normalized set. Progress uses `state` mode when only transitions exist — no invented percentages.

## Inspect bridge

1. Resolve Production Executive `JobStore` first.
2. If missing, resolve Studio `Job` by id (+ optional `projectId`).
3. Return `{ job: unified_dto, source, executive, studio }` with sanitized JSON (no credentials).

History route falls back to Studio `history_json` events when the id is a Studio job.

## Tests

| Test | Result |
|------|--------|
| `tests/test_m30c_unified_jobs.py::test_codirector_inspects_studio_job` | PASSED |

## Restart recovery

Studio `JobQueue.recover_interrupted` and Executive `recover_running_jobs` remain the restart paths. Interrupted Studio jobs are marked failed/`interrupted` honestly rather than silently re-submitting paid work.

## Residual

Cancel/retry Co-Director tools for Studio ids remain available via existing `/api/jobs/{id}/cancel` plus executive actions for executive ids. Further tool unification may continue without blocking inspect.
