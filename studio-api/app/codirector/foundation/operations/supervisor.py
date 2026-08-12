"""Low-noise workflow supervision notifications."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.codirector.foundation.contracts import ActivityEvent


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _values(health: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = health.get(key)
        if value:
            if isinstance(value, list):
                return value
            return [value]
    return []


def _stringify_items(items: Iterable[Any], *, field_names: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = ""
            for field in field_names:
                raw = item.get(field)
                if raw:
                    text = str(raw).strip()
                    break
        else:
            text = str(item).strip()
        if text:
            out.append(text)
    return out


def _event(project_id: str, event_type: str, state: str, title: str, detail: str, count: int) -> ActivityEvent:
    return ActivityEvent(
        eventId=f"evt-{uuid4().hex}",
        projectId=project_id,
        type=event_type,
        state=state,  # type: ignore[arg-type]
        title=title,
        detail=detail,
        timestamp=_timestamp(),
        metadata={"count": count},
    )


def _collapse(summary: list[str], *, limit: int = 2) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for item in summary:
        lowered = item.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(item)
    if len(unique) <= limit:
        return "; ".join(unique)
    shown = "; ".join(unique[:limit])
    return f"{shown}; and {len(unique) - limit} more"


def collect_notifications(project_id: str, project_health: dict[str, Any], *, max_notifications: int = 4) -> list[ActivityEvent]:
    """Convert raw project-health data into a few useful, creator-readable notifications."""

    notifications: list[ActivityEvent] = []

    failed_jobs = _stringify_items(
        _values(project_health, "failedJobs", "failed_jobs"),
        field_names=("title", "jobId", "summary", "message"),
    )
    if failed_jobs:
        notifications.append(
            _event(
                project_id,
                "project_health.failed_jobs",
                "failed",
                "Failed jobs need review",
                _collapse(failed_jobs),
                len(failed_jobs),
            )
        )

    blockers = _stringify_items(_values(project_health, "blockers"), field_names=("title", "summary", "message"))
    if blockers:
        notifications.append(
            _event(
                project_id,
                "project_health.blockers",
                "failed",
                "Project blockers are open",
                _collapse(blockers),
                len(blockers),
            )
        )

    missing_assets = _stringify_items(
        _values(project_health, "missingAssets", "missing_assets"),
        field_names=("title", "assetId", "summary", "message"),
    )
    if missing_assets:
        notifications.append(
            _event(
                project_id,
                "project_health.missing_assets",
                "info",
                "Missing assets may slow progress",
                _collapse(missing_assets),
                len(missing_assets),
            )
        )

    stale_plans = _stringify_items(
        _values(project_health, "stalePlans", "stale_plans"),
        field_names=("title", "planId", "summary", "message"),
    )
    if stale_plans:
        notifications.append(
            _event(
                project_id,
                "project_health.stale_plans",
                "info",
                "Plans may need a refresh",
                _collapse(stale_plans),
                len(stale_plans),
            )
        )

    deduped: list[ActivityEvent] = []
    seen_pairs: set[tuple[str, str]] = set()
    for event in notifications:
        pair = (event.title.casefold(), event.detail.casefold())
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        deduped.append(event)

    return deduped[: max(0, max_notifications)]
