# M3.0d Orchestration Honesty Report

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register item | B9 (primary), B21 (timeouts) |
| Module | `studio-api/app/codirector/m211/honesty.py` |
| Function | `normalize_orchestration_response` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Problem (B9)

Orchestration responses could simultaneously report `success: true` / `status: completed` while also listing stage failures, pending approvals, or empty specialist rosters. This contradicted the UI and Co-Director trust contract.

## Honesty contract

A response **must not** claim success while reporting a blocking failure. The normalizer enforces:

| Condition | Normalized behavior |
|-----------|---------------------|
| `failures[]` present with `status: completed` | Downgrade to `completed_with_warnings` or `failed` |
| `pendingApprovals[]` with completed status | Force `pending_approval`, `success: false` |
| Empty specialists + errors | `failed`, `success: false` |
| Specialist timeouts | Promoted to `warnings` (B21) |
| Limited/heuristic analysis | Preserves honesty labels; does not invent `modelUsed` |

## Implementation

```python
# studio-api/app/codirector/m211/honesty.py
def normalize_orchestration_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize top-level status/success/modelUsed/errors for a truthful contract."""
```

Integrated at orchestration response boundaries in M2.11 pipeline (orchestrator applies normalizer before returning to API clients).

## Test evidence

| Test | Assertion |
|------|-----------|
| `test_b9_normalize_rejects_contradictory_success` | completed + failures â†’ not success OR not completed |
| `test_b9_pending_approval_is_not_success` | pendingApprovals â†’ `pending_approval`, success false |
| Full pytest gate | 631/0/6 |

File: `studio-api/tests/test_m30d_closures.py`

## B21 â€” timeout surfacing

Specialist timeouts are no longer silent roster shrinkage. The normalizer appends `timeout:{specialistId}` entries to `warnings[]` and can downgrade status to `completed_with_warnings`.

## Status

| ID | Status | Commit |
|----|--------|--------|
| B9 | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B21 | **Closed (bounded)** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Residual

Four materially different **live** brief digests (B16 intelligence proof) remain a product-evidence gap. The honesty **contract** is code-proven; live provider diversity is not claimed here.
