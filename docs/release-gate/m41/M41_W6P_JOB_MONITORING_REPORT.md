# M41 W6P-11 — Job Monitoring Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | `artifacts/m41/w6p/job_monitoring_results.json` |
| **Verdict** | **PASS** |

## Projection

`job_projection.project_job` unifies studio Job → product card fields (operation, workflow, stage, cancel state, retry).

Numeric progress only when runtime provides credible values; otherwise stage-based.

Cancel path: `cancel_requested → cancelling → runtime stop confirmed → cancelled`. UI must not report completion after cancellation.
