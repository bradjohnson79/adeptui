"""Non-destructive MAGI finishing state on the sequence document."""

from __future__ import annotations

from typing import Any

from .sequence.store import get_sequence, save_sequence


def finishing_of(sequence: dict[str, Any] | None) -> dict[str, Any]:
    raw = (sequence or {}).get("finishing")
    return dict(raw) if isinstance(raw, dict) else {}


def merge_finishing(project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_sequence(project_id)
    finishing = finishing_of(current)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(finishing.get(key), dict):
            merged = dict(finishing[key])
            merged.update(value)
            finishing[key] = merged
        else:
            finishing[key] = value
    current["finishing"] = finishing
    return save_sequence(project_id, current)


def set_clip_grade(project_id: str, clip_id: str, preset_id: str | None, params: dict[str, Any] | None) -> dict[str, Any]:
    current = get_sequence(project_id)
    finishing = finishing_of(current)
    grades = dict(finishing.get("clipGrades") or {})
    grades[clip_id] = {"presetId": preset_id or "", "params": dict(params or {})}
    finishing["clipGrades"] = grades
    current["finishing"] = finishing
    return save_sequence(project_id, current)


def clip_grade(sequence: dict[str, Any], clip_id: str | None) -> dict[str, Any]:
    grades = finishing_of(sequence).get("clipGrades") or {}
    if clip_id and isinstance(grades, dict) and clip_id in grades:
        value = grades.get(clip_id) or {}
        return value if isinstance(value, dict) else {}
    if isinstance(grades, dict) and grades:
        first = next(iter(grades.values()))
        return first if isinstance(first, dict) else {}
    return {}
