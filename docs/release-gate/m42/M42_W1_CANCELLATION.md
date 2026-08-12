# M42 W1-9 — Image Cancellation Strategy

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |

## Supported stages

queued · preparing · loading models · sampling · saving · validating · registration

## Cancel path

```text
cancel_requested → cancelling → runtime stop confirmed → cancelled
```

Optimistic cancel forbidden. No completion asset after cancel.

## Recovery policies

| Policy | When |
|---|---|
| retry_same | Transient timeout / interrupt |
| retry_lower_profile | VRAM / OOM |
| wait_for_runtime | Comfy unavailable |
| request_missing_input | Model / node / reference missing |
| manual_review | Validation / registration failure |
| blocked_no_safe_fallback | Workflow Blocked / Deferred |

Deep cancel enforcement for image jobs is **Wave 2** ownership (reuse `cancel_and_halt`).
