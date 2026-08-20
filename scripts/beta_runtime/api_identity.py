"""Studio API currency for Beta supervisor adoption.

A matching git SHA is not enough. The process must also expose the
Revision B perception contract. Isolated :8742 is never a substitute.
"""

from __future__ import annotations

from typing import Any

ROUTE_CONTRACT = ("perception.capability",)


def perception_contract_ok(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    cap = payload.get("capability") if isinstance(payload.get("capability"), dict) else payload
    if not isinstance(cap, dict):
        return False
    scene = cap.get("sceneReview")
    return scene in {"available", "testing", "unavailable"} and cap.get("chatRequired") is False


def should_adopt_studio_api(
    *,
    healthy: bool,
    revision_current: bool,
    perception_ok: bool,
) -> bool:
    """Adopt only a live, current-SHA process that exposes /api/perception/capability."""
    return bool(healthy and revision_current and perception_ok)
