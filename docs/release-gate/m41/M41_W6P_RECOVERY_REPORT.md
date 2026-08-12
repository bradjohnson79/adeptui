# M41 W6P-13/14 — Recovery & Degraded Runtime Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | `artifacts/m41/w6p/recovery_results.json` |
| **Verdict** | **PASS** |

## Policies

`retry_same`, `retry_lower_profile`, `wait_for_runtime`, `request_missing_input`, `request_user_approval`, `manual_review`, `resume_from_completed_children`, `blocked_no_safe_fallback`

Rules enforced: no uncertified fallback; no silent provider switch; unresolved failures remain visible; Comfy offline → wait_for_runtime.
