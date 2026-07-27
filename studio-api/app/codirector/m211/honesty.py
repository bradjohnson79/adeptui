"""Orchestration response honesty contract (B9 / M3.0d).

A response must not claim success while also reporting a blocking failure.
"""

from __future__ import annotations

from typing import Any


_SUCCESS_STATUSES = frozenset({"completed", "completed_with_warnings"})
_BLOCKING_STATUSES = frozenset({"blocked", "failed", "provider_unavailable"})


def normalize_orchestration_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize top-level status/success/modelUsed/errors for a truthful contract."""
    out = dict(payload)
    errors = list(out.get("errors") or [])
    warnings = list(out.get("warnings") or [])
    failures = list(out.get("failures") or [])
    timeouts = list(out.get("timeouts") or [])
    missing = list(out.get("missingAssets") or [])
    pending = list(out.get("pendingApprovals") or [])

    # Promote structured stage failures into errors when callers omitted them.
    for item in failures:
        if isinstance(item, dict):
            msg = item.get("error") or item.get("message") or str(item)
            sid = item.get("specialistId") or item.get("stageId") or "stage"
            errors.append(f"{sid}: {msg}")
        else:
            errors.append(str(item))

    for item in timeouts:
        if isinstance(item, dict):
            sid = item.get("specialistId") or item.get("stageId") or "specialist"
            warnings.append(f"timeout:{sid}")
        else:
            warnings.append(f"timeout:{item}")

    status = str(out.get("status") or "").strip().lower()
    if not status:
        if errors or failures:
            status = "failed" if not out.get("specialists") else "completed_with_warnings"
        elif pending:
            status = "pending_approval"
        elif timeouts:
            status = "completed_with_warnings"
        else:
            status = "completed"

    # Contradictory success:true with blocking failures/errors is forbidden.
    if status == "completed" and (errors or failures):
        status = "completed_with_warnings" if out.get("specialists") else "failed"
    elif status not in _BLOCKING_STATUSES and errors and not out.get("specialists"):
        status = "failed"

    if pending and status in ("completed", "completed_with_warnings"):
        status = "pending_approval"

    # Failures with an empty specialist roster are never success.
    if status == "completed_with_warnings" and failures and not out.get("specialists"):
        status = "failed"

    success = status in _SUCCESS_STATUSES
    if status in _BLOCKING_STATUSES or status == "pending_approval":
        success = False
    if errors and not out.get("specialists") and status != "completed_with_warnings":
        success = False

    model_used = out.get("modelUsed")
    provider_used = out.get("providerUsed")
    if not out.get("useProvider") and status in ("completed", "completed_with_warnings"):
        # Limited / heuristic path did not run a provider model.
        if out.get("analysisMode") == "limited-analysis" or out.get("honesty") == "limited":
            if model_used in (None, "", "gemma"):
                # Keep declared model only when a provider actually ran.
                if not out.get("useProvider"):
                    model_used = out.get("modelUsed")  # leave as declared intent
            if provider_used in (None, ""):
                provider_used = None

    out["status"] = status
    out["success"] = success
    out["errors"] = errors
    out["warnings"] = warnings
    out["missingAssets"] = missing
    out["modelUsed"] = model_used
    out["providerUsed"] = provider_used
    out["timeouts"] = timeouts
    out["partialRoster"] = bool(timeouts or failures)
    return out
