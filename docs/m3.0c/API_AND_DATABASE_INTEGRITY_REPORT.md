# API and Database Integrity Report

Date: 2026-07-27

Status: **PENDING certification**.

## Available evidence

- The full Playwright suite completed with 111 passed, 0 failed, and 6 intentional skips.
- The captured API logs show successful health checks and successful project, scene, job, asset, render, export, and Co-Director endpoint responses during the E2E run.
- The available backend pytest evidence is not green: 622 passed, 2 failed, and 6 skipped. The failures were `test_global_github_env_does_not_validate_unpublished_pack` and `test_queue_order_by_priority`.

## Not yet certified

A dedicated Phase 13-14 API contract, persistence-integrity, migration, foreign-key, transaction, and database-recovery run has not been completed for this report. E2E traffic is useful supporting evidence but is not a substitute for that focused certification.

Required follow-up:

```text
cd studio-api
python -m pytest -q
```

Record the complete exit code, totals, failure details, migration status, and database cleanup/integrity checks before changing this status to GREEN.
