"""Failure-informed Retry — reads failed pack; STRICT never silent-swaps.

Retry is not a second brain. It reconstructs a retry brief from the failed
ExecutionPlan / planned_steps stamp so the creator (or ACT path) can re-run
the same route under Creator Spec Fidelity.
"""

from __future__ import annotations

from typing import Any, Optional

from .failure_codes import FailureReasonCode, stamp_failure


def extract_failed_step(pack: Any) -> Optional[dict[str, Any]]:
    """Pick the failed planned step (or pack-level failure) for Retry."""
    if pack is None:
        return None
    planned = getattr(pack, "planned_steps", None) or []
    if isinstance(pack, dict):
        planned = pack.get("planned_steps") or []
    for s in planned:
        if isinstance(s, dict):
            life = str(s.get("lifecycle_status") or "")
            status = str(s.get("status") or "")
            codes = list(s.get("failure_reason_codes") or [])
            if life == "FAILED" or status == "failed" or codes:
                return dict(s)
        else:
            life = str(getattr(getattr(s, "lifecycle_status", None), "value", getattr(s, "lifecycle_status", "")) or "")
            status = str(getattr(getattr(s, "status", None), "value", getattr(s, "status", "")) or "")
            codes = list(getattr(s, "failure_reason_codes", None) or [])
            if life == "FAILED" or status == "failed" or codes:
                return s.model_dump(mode="json") if hasattr(s, "model_dump") else {
                    "step_id": getattr(s, "step_id", ""),
                    "capability": getattr(s, "capability", ""),
                    "failure_reason_codes": codes,
                    "failure_reason": getattr(s, "failure_reason", None),
                    "parent_execution_id": getattr(s, "parent_execution_id", None),
                    "plan_id": getattr(s, "plan_id", ""),
                    "metadata": getattr(s, "metadata", {}) or {},
                }
    # Pack-level
    err = getattr(pack, "error", None) if not isinstance(pack, dict) else pack.get("error")
    codes = (
        list(getattr(pack, "failure_reason_codes", None) or [])
        if not isinstance(pack, dict)
        else list(pack.get("failure_reason_codes") or [])
    )
    if err or codes:
        return {
            "step_id": "",
            "capability": getattr(pack, "capability", None) if not isinstance(pack, dict) else pack.get("capability"),
            "failure_reason": err,
            "failure_reason_codes": codes,
            "parent_execution_id": getattr(pack, "execution_id", None) if not isinstance(pack, dict) else pack.get("execution_id"),
            "plan_id": getattr(pack, "plan_id", "") if not isinstance(pack, dict) else pack.get("plan_id", ""),
            "metadata": {},
        }
    return None


def build_retry_brief(
    pack: Any,
    *,
    strict: bool = False,
    allow_provider_swap: bool = False,
) -> dict[str, Any]:
    """Build a Retry brief from a failed pack.

    STRICT + no allow_provider_swap → stamps STRICT_NO_SILENT_SWAP and preserves
    routeLock from the pack. Never silently swaps provider/model.
    """
    failed = extract_failed_step(pack)
    if failed is None:
        return {
            "ok": False,
            "reasonCodes": ["RETRY_NO_FAILED_STEP"],
            "retryAllowed": False,
        }

    codes = list(failed.get("failure_reason_codes") or [])
    reason = str(failed.get("failure_reason") or failed.get("error") or "")
    _, stamped = stamp_failure(reason=reason, codes=codes, strict=strict)
    if strict and not allow_provider_swap:
        if FailureReasonCode.STRICT_NO_SILENT_SWAP.value not in stamped:
            stamped.append(FailureReasonCode.STRICT_NO_SILENT_SWAP.value)

    meta = dict(failed.get("metadata") or {})
    route_lock = dict(meta.get("routeLock") or {})
    if isinstance(pack, dict):
        plan_data = pack.get("plan_data") or {}
    else:
        plan_data = getattr(pack, "plan_data", None) or {}
    if not route_lock and isinstance(plan_data, dict):
        route_lock = dict(plan_data.get("routeLock") or plan_data.get("route_lock") or {})

    parent_exec = (
        failed.get("parent_execution_id")
        or (getattr(pack, "execution_id", None) if not isinstance(pack, dict) else pack.get("execution_id"))
    )

    # Silent swap guard: under STRICT, provider/model in retry params must match lock.
    retry_params = dict(meta.get("params") or {})
    if strict and not allow_provider_swap and route_lock:
        locked_provider = route_lock.get("provider")
        locked_model = route_lock.get("modelId") or route_lock.get("model")
        if locked_provider:
            retry_params["provider"] = locked_provider
        if locked_model:
            retry_params["model"] = locked_model
            retry_params["modelId"] = locked_model

    return {
        "ok": True,
        "retryAllowed": True,
        "silentSwapForbidden": bool(strict and not allow_provider_swap),
        "reasonCodes": stamped,
        "capability": failed.get("capability") or "",
        "stepId": failed.get("step_id") or "",
        "planId": failed.get("plan_id") or "",
        "parentExecutionId": parent_exec,
        "routeLock": route_lock,
        "params": retry_params,
        "failureReason": reason,
        "sourcePackId": parent_exec,
    }
