"""Readiness evaluation helpers for foundation production steps."""

from __future__ import annotations

from typing import Any


_TERMINAL_STATES = {"completed", "failed", "cancelled", "skipped", "unsupported", "deferred"}
_COMPLETE_STATES = {"completed", "skipped"}


def _normalize_step(step: Any, index: int) -> dict[str, Any]:
    if hasattr(step, "model_dump"):
        raw = step.model_dump(mode="json")
    else:
        raw = dict(step)
    return {
        "stepId": str(raw.get("stepId") or raw.get("id") or f"step-{index + 1}"),
        "title": str(raw.get("title") or raw.get("name") or f"Step {index + 1}"),
        "state": str(raw.get("state") or "pending"),
        "dependsOn": [str(item) for item in raw.get("dependsOn") or [] if str(item).strip()],
        "blockedBy": [str(item) for item in raw.get("blockedBy") or [] if str(item).strip()],
        "requiresApproval": bool(raw.get("requiresApproval", False)),
        "raw": raw,
    }


def evaluate_step_readiness(step: Any, all_steps: list[Any]) -> dict[str, Any]:
    """Evaluate one step while honoring dependency completion."""

    normalized_steps = [_normalize_step(item, index) for index, item in enumerate(all_steps)]
    current = _normalize_step(step, 0)
    by_id = {item["stepId"]: item for item in normalized_steps}

    if current["state"] in _TERMINAL_STATES:
        return {"stepId": current["stepId"], "title": current["title"], "state": current["state"], "ready": current["state"] == "completed", "reason": "terminal_state"}
    if current["blockedBy"]:
        return {"stepId": current["stepId"], "title": current["title"], "state": "blocked", "ready": False, "reason": "blocked_by"}

    incomplete_dependencies = [
        dependency
        for dependency in current["dependsOn"]
        if dependency not in by_id or by_id[dependency]["state"] not in _COMPLETE_STATES
    ]
    if incomplete_dependencies:
        return {
            "stepId": current["stepId"],
            "title": current["title"],
            "state": "pending",
            "ready": False,
            "reason": "dependencies_incomplete",
            "dependsOnIncomplete": incomplete_dependencies,
        }

    if current["requiresApproval"]:
        return {
            "stepId": current["stepId"],
            "title": current["title"],
            "state": "awaiting_approval",
            "ready": False,
            "reason": "approval_required",
        }

    return {"stepId": current["stepId"], "title": current["title"], "state": "ready", "ready": True, "reason": "dependencies_satisfied"}


def annotate_step_readiness(steps: list[Any]) -> list[dict[str, Any]]:
    """Annotate each step with dependency-aware readiness information."""

    normalized_steps = [_normalize_step(step, index) for index, step in enumerate(steps)]
    return [evaluate_step_readiness(step, normalized_steps) for step in normalized_steps]


__all__ = ["annotate_step_readiness", "evaluate_step_readiness"]
