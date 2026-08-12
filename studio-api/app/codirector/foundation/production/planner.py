"""Snapshot-aware roadmap builder for foundation production planning."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def _step_id(step: dict[str, Any], fallback_index: int) -> str:
    return str(step.get("stepId") or step.get("id") or f"step-{fallback_index + 1}")


def _normalize_step(step: Any, index: int) -> dict[str, Any]:
    if hasattr(step, "model_dump"):
        raw = step.model_dump(mode="json")
    else:
        raw = dict(step)
    step_id = _step_id(raw, index)
    title = str(raw.get("title") or raw.get("name") or step_id.replace("-", " ").title())
    return {
        "stepId": step_id,
        "title": title,
        "dependsOn": [str(item) for item in raw.get("dependsOn") or [] if str(item).strip()],
        "state": str(raw.get("state") or "pending"),
        "category": str(raw.get("category") or "system"),
        "order": int(raw.get("order") or index),
        "raw": raw,
    }


def _project_steps(project_snapshot: dict[str, Any] | None, steps: list[Any] | None) -> list[dict[str, Any]]:
    if steps is not None:
        source = steps
    else:
        source = []
        if isinstance(project_snapshot, dict):
            source = project_snapshot.get("steps") or project_snapshot.get("planSteps") or []
    return [_normalize_step(step, index) for index, step in enumerate(source)]


def _snapshot_blockers(project_snapshot: dict[str, Any] | None, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not isinstance(project_snapshot, dict):
        return blockers

    has_script = bool(project_snapshot.get("scriptId") or project_snapshot.get("scriptReady") or project_snapshot.get("script"))
    has_shot_plan = bool(project_snapshot.get("shotListId") or project_snapshot.get("shots") or project_snapshot.get("storyboardId"))
    has_audio_plan = bool(project_snapshot.get("audioPlanId") or project_snapshot.get("audioReady"))

    categories = {step["category"] for step in steps}
    if "scene" in categories or "script" in categories:
        if not has_script:
            blockers.append(
                {
                    "blockerId": "project:missing-script",
                    "planId": str(project_snapshot.get("planId") or ""),
                    "stepId": None,
                    "category": "script",
                    "severity": "blocking",
                    "title": "Script context is missing",
                    "description": "Roadmap includes script-sensitive work, but no script artifact is present in the snapshot.",
                    "sourceType": "foundation.production.planner",
                    "resolutionType": "creator_input",
                    "recommendedAction": "Create or attach a script before planning downstream scene work.",
                    "state": "open",
                }
            )
    if "video" in categories and not has_shot_plan:
        blockers.append(
            {
                "blockerId": "project:missing-shot-plan",
                "planId": str(project_snapshot.get("planId") or ""),
                "stepId": None,
                "category": "video",
                "severity": "warning",
                "title": "Shot planning context is thin",
                "description": "Video-oriented steps exist without a storyboard, shot list, or explicit shots in the snapshot.",
                "sourceType": "foundation.production.planner",
                "resolutionType": "creator_input",
                "recommendedAction": "Outline shots or storyboard anchors before committing to generation-heavy work.",
                "state": "open",
            }
        )
    if "audio" in categories and not has_audio_plan:
        blockers.append(
            {
                "blockerId": "project:missing-audio-plan",
                "planId": str(project_snapshot.get("planId") or ""),
                "stepId": None,
                "category": "audio",
                "severity": "info",
                "title": "Audio plan has not been defined yet",
                "description": "Audio work can proceed, but tone and ownership will be clearer with an explicit audio goal.",
                "sourceType": "foundation.production.planner",
                "resolutionType": "creator_input",
                "recommendedAction": "Decide whether dialogue, music, or ambience is the primary audio deliverable.",
                "state": "open",
            }
        )
    return blockers


def _dependency_blockers(steps: list[dict[str, Any]], plan_id: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    known_ids = {step["stepId"] for step in steps}
    for step in steps:
        missing = [dependency for dependency in step["dependsOn"] if dependency not in known_ids]
        if not missing:
            continue
        blockers.append(
            {
                "blockerId": f"{step['stepId']}:missing-dependencies",
                "planId": plan_id,
                "stepId": step["stepId"],
                "category": "dependency",
                "severity": "blocking",
                "title": f"{step['title']} is missing prerequisites",
                "description": f"Missing dependencies: {', '.join(missing)}.",
                "sourceType": "foundation.production.planner",
                "resolutionType": "plan_repair",
                "recommendedAction": "Add or rename the missing prerequisite step before treating this step as actionable.",
                "state": "open",
            }
        )
    return blockers


def _topological_titles(steps: list[dict[str, Any]]) -> list[str]:
    indegree: dict[str, int] = {step["stepId"]: 0 for step in steps}
    edges: dict[str, list[str]] = defaultdict(list)
    by_id = {step["stepId"]: step for step in steps}
    missing_dependency_steps: set[str] = set()
    for step in steps:
        for dependency in step["dependsOn"]:
            if dependency in indegree:
                edges[dependency].append(step["stepId"])
                indegree[step["stepId"]] += 1
            else:
                missing_dependency_steps.add(step["stepId"])

    queue = deque(
        step["stepId"]
        for step in sorted(steps, key=lambda item: (item["order"], item["title"]))
        if indegree[step["stepId"]] == 0 and step["stepId"] not in missing_dependency_steps
    )
    ordered_ids: list[str] = []
    while queue:
        current = queue.popleft()
        ordered_ids.append(current)
        for neighbor in sorted(edges[current], key=lambda sid: by_id[sid]["order"]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered_ids) < len(steps):
        for step in sorted(steps, key=lambda item: (item["order"], item["title"])):
            if step["stepId"] not in ordered_ids:
                ordered_ids.append(step["stepId"])

    return [by_id[step_id]["title"] for step_id in ordered_ids]


def build_ordered_roadmap_titles(
    project_snapshot: dict[str, Any] | None = None,
    steps: list[Any] | None = None,
) -> list[str]:
    """Return roadmap titles in dependency-aware order."""

    normalized = _project_steps(project_snapshot, steps)
    return _topological_titles(normalized)


def build_production_roadmap(
    project_snapshot: dict[str, Any] | None = None,
    steps: list[Any] | None = None,
) -> dict[str, Any]:
    """Inspect a snapshot-like payload and return ordered titles plus blockers."""

    normalized = _project_steps(project_snapshot, steps)
    plan_id = ""
    if isinstance(project_snapshot, dict):
        plan_id = str(project_snapshot.get("planId") or "")
    blockers = _dependency_blockers(normalized, plan_id)
    blockers.extend(_snapshot_blockers(project_snapshot, normalized))
    ordered_titles = _topological_titles(normalized)
    return {
        "orderedTitles": ordered_titles,
        "steps": normalized,
        "blockers": blockers,
    }


__all__ = ["build_ordered_roadmap_titles", "build_production_roadmap"]
