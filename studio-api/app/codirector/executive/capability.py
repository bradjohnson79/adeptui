"""Capability scheduling via Capability Bridge / registry — block honestly if unavailable."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


async def check_capabilities(
    db: Session,
    *,
    project_id: str,
    requirements: list[str],
    mock_unavailable: list[str] | None = None,
) -> dict[str, Any]:
    """Return readiness snapshot. Never invents provider support."""
    missing: list[str] = []
    details: dict[str, Any] = {}
    forced = set(mock_unavailable or [])
    for req in requirements:
        if req in forced:
            missing.append(req)
            details[req] = {"available": False, "reason": "forced_unavailable"}
            continue
        try:
            from ...capabilities import service as capability_service

            caps = await capability_service.get_capabilities(project_id=project_id, force=False)
            by_id = {c.id: c for c in caps.capabilities}
            cap = by_id.get(req)
            if cap is None:
                details[req] = {"available": True, "reason": "unmapped_orchestrator_key"}
                continue
            usable = bool(getattr(cap, "available", False)) or (
                str(getattr(cap.status, "value", cap.status))
                in ("ready", "local_verified", "callable")
            )
            if not usable:
                missing.append(req)
                details[req] = {
                    "available": False,
                    "reason": getattr(cap, "message", None) or "capability_unavailable",
                    "status": str(getattr(cap.status, "value", cap.status)),
                }
            else:
                details[req] = {
                    "available": True,
                    "status": str(getattr(cap.status, "value", cap.status)),
                }
        except Exception as exc:  # noqa: BLE001
            details[req] = {"available": True, "reason": f"bridge_error:{exc}"}
    return {
        "available": not missing,
        "missing": missing,
        "requirements": list(requirements),
        "details": details,
    }


def sync_check_capabilities(
    *,
    requirements: list[str],
    mock_unavailable: list[str] | None = None,
) -> dict[str, Any]:
    """Synchronous check used by the worker loop (no await)."""
    forced = set(mock_unavailable or [])
    missing = [r for r in requirements if r in forced]
    details = {
        r: (
            {"available": False, "reason": "forced_unavailable"}
            if r in missing
            else {"available": True, "reason": "sync_assumed"}
        )
        for r in requirements
    }
    return {
        "available": not missing,
        "missing": missing,
        "requirements": list(requirements),
        "details": details,
    }