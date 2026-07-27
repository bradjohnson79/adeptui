# M3.0d Vision Approval Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register items | B19 (primary), B11 (Playwright) |
| Module | `studio-api/app/codirector/vision/approval.py` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## B19 — overrideReason required (Closed)

### Problem

Vision validation reports in the `reject` or `corrections_required` band could be silently approved without an explicit override reason, undermining auditability.

### Expected state

Override of a reject-band result requires:

1. `override=true` (decision becomes `override_approve`)
2. Non-empty `overrideReason` (or substantive notes)

### Implementation

`record_decision` in `approval.py`:

```python
if override and band in ("reject", "corrections_required") and not reason:
    raise ValueError(
        f"Vision report band is '{band}'; override requires a non-empty overrideReason."
    )
```

Approved notes append `[overrideReason] {reason}` for audit trail.

### Test evidence

| Test | Result |
|------|--------|
| `test_b19_override_requires_reason` | ValueError when reason empty |
| `test_b19_override_with_reason_records` | approved + reason in saved notes |
| Full gate | 631/0/6 |

## B11 — Vision Playwright (Closed — bounded)

### Problem

Vision validation E2E specs failed or were skipped under strict mode in M3.0b.

### M3.0d state

Full Playwright suite: **111 passed, 0 failed, 6 intentional skips** (see `M30D_PLAYWRIGHT_CERTIFICATION.md`). Vision-related journeys exercised in the captured run are green for their bounded contracts.

Strict-mode pending approvals remain honestly labeled in API responses (B9 `pending_approval` status).

## Situation evidence

All twelve production situations completed image approval/publication steps before export. Handoff and approval evidence recorded in `artifacts/m30-situations/situation-finish.json`.

## Status summary

| ID | Status | Evidence |
|----|--------|----------|
| B19 | **Closed** | `test_m30d_closures.py`, `approval.py` |
| B11 | **Closed (bounded)** | Playwright 111/0/6 |

## Boundary

This certifies approval **API contract** and E2E pass status. It does not claim every vision ML model variant or every band combination has live provider proof.
