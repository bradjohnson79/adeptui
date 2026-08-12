"""Structured review-note helpers for collaboration flows."""

from __future__ import annotations

from collections import defaultdict

_REJECTED_ALTERNATIVES: dict[str, set[str]] = defaultdict(set)


def _normalize_alternative(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def list_rejected_alternatives(project_id: str) -> list[str]:
    """Return rejected alternatives for the project in sorted order."""

    return sorted(_REJECTED_ALTERNATIVES.get(project_id, set()))


def should_suppress_alternative(project_id: str, alternative: str) -> bool:
    """Return True when an alternative was explicitly rejected before."""

    return _normalize_alternative(alternative) in _REJECTED_ALTERNATIVES.get(project_id, set())


def build_review_notes(
    project_id: str,
    *,
    summary: str,
    accepted: list[str] | None = None,
    concerns: list[str] | None = None,
    rejected_alternatives: list[str] | None = None,
    follow_up: list[str] | None = None,
) -> dict[str, list[str] | str]:
    """Return structured review notes and remember rejected alternatives."""

    rejected = []
    for item in rejected_alternatives or []:
        normalized = _normalize_alternative(item)
        if not normalized:
            continue
        _REJECTED_ALTERNATIVES[project_id].add(normalized)
        rejected.append(normalized)

    return {
        "summary": summary.strip(),
        "accepted": [item.strip() for item in accepted or [] if item.strip()],
        "concerns": [item.strip() for item in concerns or [] if item.strip()],
        "rejectedAlternatives": sorted(set(rejected)),
        "followUp": [item.strip() for item in follow_up or [] if item.strip()],
    }


__all__ = ["build_review_notes", "list_rejected_alternatives", "should_suppress_alternative"]
