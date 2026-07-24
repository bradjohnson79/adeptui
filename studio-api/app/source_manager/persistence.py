"""Persist SourceRecords and ComponentSourceAssignments in setup_state."""

from __future__ import annotations

from typing import Any

from ..setup.state import load_state, update_state
from .models import normalize_assignment, normalize_source_record, strip_secrets, utc_now


def list_sources() -> dict[str, dict[str, Any]]:
    state = load_state()
    raw = state.get("sources") or {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        record = normalize_source_record(value if isinstance(value, dict) else None)
        if record:
            out[str(key)] = record
    return out


def get_source(source_id: str) -> dict[str, Any] | None:
    return list_sources().get(source_id)


def upsert_source(record: dict[str, Any]) -> dict[str, Any]:
    clean = normalize_source_record(record)
    if not clean:
        raise ValueError("Invalid source record.")
    clean["updatedAt"] = utc_now()

    def mutate(state: dict[str, Any]) -> None:
        sources = state.setdefault("sources", {})
        existing = sources.get(clean["id"])
        if isinstance(existing, dict) and existing.get("createdAt"):
            clean["createdAt"] = existing["createdAt"]
        sources[clean["id"]] = strip_secrets(clean)

    update_state(mutate)
    return clean


def remove_source(source_id: str) -> bool:
    existed = {"ok": False}

    def mutate(state: dict[str, Any]) -> None:
        sources = state.setdefault("sources", {})
        if source_id in sources:
            sources.pop(source_id, None)
            existed["ok"] = True
        assignments = state.setdefault("component_sources", {})
        for component_id, assignment in list(assignments.items()):
            if isinstance(assignment, dict) and assignment.get("sourceId") == source_id:
                assignments.pop(component_id, None)

    update_state(mutate)
    return existed["ok"]


def list_assignments() -> dict[str, dict[str, Any]]:
    state = load_state()
    raw = state.get("component_sources") or {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        assignment = normalize_assignment(value if isinstance(value, dict) else None)
        if assignment:
            out[str(key)] = assignment
    return out


def get_assignment(component_id: str) -> dict[str, Any] | None:
    return list_assignments().get(component_id)


def upsert_assignment(assignment: dict[str, Any]) -> dict[str, Any]:
    clean = normalize_assignment(assignment)
    if not clean:
        raise ValueError("Invalid component source assignment.")
    clean["updatedAt"] = utc_now()

    def mutate(state: dict[str, Any]) -> None:
        items = state.setdefault("component_sources", {})
        existing = items.get(clean["componentId"])
        if isinstance(existing, dict) and existing.get("createdAt"):
            clean["createdAt"] = existing["createdAt"]
        items[clean["componentId"]] = strip_secrets(clean)

    update_state(mutate)
    return clean


def remove_assignment(component_id: str) -> bool:
    existed = {"ok": False}

    def mutate(state: dict[str, Any]) -> None:
        items = state.setdefault("component_sources", {})
        if component_id in items:
            items.pop(component_id, None)
            existed["ok"] = True

    update_state(mutate)
    return existed["ok"]


def components_using_source(source_id: str) -> list[str]:
    return [
        component_id
        for component_id, assignment in list_assignments().items()
        if assignment.get("sourceId") == source_id
    ]
