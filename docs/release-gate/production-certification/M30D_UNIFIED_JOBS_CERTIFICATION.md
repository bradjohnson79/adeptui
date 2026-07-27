# M3.0d Unified Jobs Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Register items | UJ-1, UJ-2, UJ-3 |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |

## Executive summary

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| UJ-1 | Co-Director inspect bridge for Studio jobs | **Closed** | `unified_jobs.py`, `test_m30c_unified_jobs.py` |
| UJ-2 | fal motion through full Studio Job row | **Closed** | M3.0c fal proof reused — no new spend |
| UJ-3 | fal image endpoint | **Closed (docs boundary)** | PRODUCT_APPROVAL_REQUIRED; manifest locked |

## UJ-1 — Unified inspect (Closed)

### Problem

Production Executive jobs and Studio queue jobs lived in separate stores. Co-Director `GET /api/codirector/jobs/{id}` returned 404 for Studio-render and fal txt2vid jobs.

### Fix

Module: `studio-api/app/codirector/unified_jobs.py`

`to_unified_dto(source, row)` normalizes both stores into one DTO:

- `job_id`, `project_id`, `workspace_id`, `capability_id`
- `provider`, `engine`, `model`, `operation`, `status`
- `progress_mode`, `progress_value`, timestamps
- `provider_request_id` (from `history_json.falRequestId` when present)
- asset ids, sanitized params/errors, provenance, `approval_id`, `retry_parent_id`, `source`

Inspect bridge:

1. Resolve Executive `JobStore` first.
2. If missing, resolve Studio `Job` by id (+ optional `projectId`).
3. Return `{ job: unified_dto, source, executive, studio }` with sanitized JSON.

### Test

| Test | Result |
|------|--------|
| `tests/test_m30c_unified_jobs.py::test_codirector_inspects_studio_job` | PASSED (in 631/0/6 gate) |

Prior documentation: `docs/m3.0c/UNIFIED_JOB_SYSTEM_PROOF.md`

## UJ-2 — fal queue job path (Closed)

### Problem

Prior fal proofs could register an asset without a durable Studio Job row observable through Co-Director inspect.

### Fix + proof (reused)

M3.0c Phase 4 executed one intentional Seedance T2V submit (≤$15 budget). M3.0d **does not re-submit** paid fal work.

Evidence chain:

| Step | Proof |
|------|-------|
| Job created before provider submit | `queueSubmit.jobCreatedResponse: true` |
| falRequestId stored | `019fa4f6-7a76-72c1-bfe3-ed8cb5200707` |
| Interrupt recovered honestly | `recover_interrupted` — no silent re-submit |
| Asset linked | 852,802 byte MP4 |
| Co-Director inspect | HTTP 200, `source=studio`, `status=completed` |

Primary artifacts:

- `docs/m3.0c/FAL_UNIFIED_QUEUE_PROOF.md`
- `artifacts/m30c-fal/unified_queue_proof.json`

Situations S01–S12 reuse the reconciled Seedance MP4 for motion; see `M30D_PRODUCTION_SITUATIONS.md`.

## UJ-3 — fal image (Closed — documentation boundary)

The provider manifest SHA `cf99d7e5…` locks `FAL_IMAGE_MODELS` empty. fal image generation is **not** a production capability. The product must disclose `PRODUCT_APPROVAL_REQUIRED` rather than implying fal stills.

This item is closed at the documentation/honesty layer only. No fal image endpoint was registered in M3.0d.

## Restart recovery (related)

Studio `JobQueue.recover_interrupted` and Executive `recover_running_jobs` remain the restart paths. Interrupted Studio jobs are marked failed/`interrupted` rather than silently re-submitting paid work. B14/PW-S3 adds browser-visible proof — see `M30D_FAILURE_RECOVERY_CERTIFICATION.md`.

## Residual

Cancel/retry Co-Director tools for Studio ids remain available via `/api/jobs/{id}/cancel` plus executive actions for executive ids. Further tool unification is optional and does not block UJ-1/UJ-2 closure.
