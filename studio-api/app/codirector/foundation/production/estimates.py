"""Non-guarantee effort estimates for foundation production planning."""

from __future__ import annotations

from math import ceil
from typing import Any


def _step_list(project_snapshot: dict[str, Any] | None, steps: list[Any] | None) -> list[dict[str, Any]]:
    source = steps
    if source is None and isinstance(project_snapshot, dict):
        source = project_snapshot.get("steps") or project_snapshot.get("planSteps") or []
    normalized: list[dict[str, Any]] = []
    for item in source or []:
        if hasattr(item, "model_dump"):
            normalized.append(item.model_dump(mode="json"))
        else:
            normalized.append(dict(item))
    return normalized


def _count_from_snapshot(project_snapshot: dict[str, Any] | None, key: str) -> int:
    if not isinstance(project_snapshot, dict):
        return 0
    value = project_snapshot.get(key)
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return max(value, 0)
    return 0


def estimate_plan_effort(
    project_snapshot: dict[str, Any] | None = None,
    steps: list[Any] | None = None,
) -> dict[str, Any]:
    """Return rough effort estimates for planning conversations."""

    normalized_steps = _step_list(project_snapshot, steps)
    asset_steps = sum(1 for step in normalized_steps if str(step.get("category") or "").lower() in {"asset", "image", "video", "audio"})
    review_steps = sum(1 for step in normalized_steps if str(step.get("category") or "").lower() in {"review", "approval", "editor", "director"})

    explicit_assets = _count_from_snapshot(project_snapshot, "assets")
    explicit_shots = _count_from_snapshot(project_snapshot, "shots")
    explicit_batches = _count_from_snapshot(project_snapshot, "batches")

    assets = explicit_assets or max(asset_steps, 1)
    shots = explicit_shots or max(sum(1 for step in normalized_steps if str(step.get("category") or "").lower() in {"scene", "video", "image"}), 1)
    batches = explicit_batches or max(1, ceil(assets / 3))
    review_stages = max(1, review_steps or ceil(len(normalized_steps or [1]) / 3))

    return {
        "estimateType": "rough_non_guarantee",
        "assets": assets,
        "shots": shots,
        "batches": batches,
        "reviewStages": review_stages,
        "assumptions": [
            "These counts are heuristics for planning conversations and do not predict runtime cost or delivery speed.",
            "The estimate assumes one approved direction at a time instead of parallel exploration across many branches.",
        ],
    }


def estimate_scope(
    project_snapshot: dict[str, Any] | None = None,
    steps: list[Any] | None = None,
) -> dict[str, Any]:
    """Alias for estimate_plan_effort to keep the helper easy to discover."""

    return estimate_plan_effort(project_snapshot=project_snapshot, steps=steps)


__all__ = ["estimate_plan_effort", "estimate_scope"]
