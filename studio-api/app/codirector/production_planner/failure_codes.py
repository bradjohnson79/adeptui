"""Failure reason codes for planner retries (machine-readable).

Used to stamp failed ExecutionPlan / PlanStep packs so Retry reads the failed
step pack instead of silently swapping models/providers under STRICT.
"""

from __future__ import annotations

from enum import Enum


class FailureReasonCode(str, Enum):
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    STRICT_MODEL_UNAVAILABLE = "STRICT_MODEL_UNAVAILABLE"
    STRICT_NO_SILENT_SWAP = "STRICT_NO_SILENT_SWAP"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    MISSING_REQUIRED_ASSET = "MISSING_REQUIRED_ASSET"
    CAPABILITY_FAILED = "CAPABILITY_FAILED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED_BY_CREATOR = "CANCELLED_BY_CREATOR"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNKNOWN = "UNKNOWN"


ALL_FAILURE_REASON_CODES: frozenset[str] = frozenset(c.value for c in FailureReasonCode)


def stamp_failure(
    *,
    reason: str = "",
    codes: list[str] | None = None,
    strict: bool = False,
) -> tuple[str, list[str]]:
    """Normalize a failure stamp for a step pack."""
    out = list(codes or [])
    if strict and FailureReasonCode.STRICT_NO_SILENT_SWAP.value not in out:
        # Creator Spec Fidelity: STRICT retries must not silently swap.
        if FailureReasonCode.STRICT_MODEL_UNAVAILABLE.value in out or "STRICT" in (reason or "").upper():
            out.append(FailureReasonCode.STRICT_NO_SILENT_SWAP.value)
        elif FailureReasonCode.PROVIDER_ERROR.value in out:
            out.append(FailureReasonCode.STRICT_NO_SILENT_SWAP.value)
    if not out:
        out.append(FailureReasonCode.UNKNOWN.value)
    # Dedup preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            deduped.append(c)
    return reason or deduped[0], deduped
