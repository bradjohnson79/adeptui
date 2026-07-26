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
    db: Session | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Synchronous capability check used by the worker loop.

    Prefer the real Capability Bridge when a Session is available. Mock-unavailable
    overrides still force Blocked. Never fakes comfyui.health for ADEPT_MOCK_IMAGEGEN/STUDIO_E2E.
    """
    forced = set(mock_unavailable or [])

    missing: list[str] = []
    details: dict[str, Any] = {}

    for req in requirements:
        if req in forced:
            missing.append(req)
            details[req] = {"available": False, "reason": "forced_unavailable"}

    remaining = [r for r in requirements if r not in forced]

    if remaining and db is not None and project_id:
        try:
            import asyncio

            async def _run():
                return await check_capabilities(
                    db, project_id=project_id, requirements=remaining, mock_unavailable=None
                )

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    raise RuntimeError("loop running")
                snap = loop.run_until_complete(_run())
            except RuntimeError:
                snap = asyncio.run(_run())

            for req in remaining:
                info = (snap.get("details") or {}).get(req) or {}
                if req in (snap.get("missing") or []):
                    missing.append(req)
                    details[req] = info or {"available": False, "reason": "bridge_unavailable"}
                else:
                    details[req] = info or {"available": True, "reason": "bridge_ok"}
            for req in snap.get("missing") or []:
                if req not in missing and req in remaining:
                    missing.append(req)
        except Exception as exc:  # noqa: BLE001
            for req in remaining:
                details[req] = {"available": True, "reason": f"bridge_error:{exc}"}
    else:
        for req in remaining:
            details[req] = {"available": True, "reason": "sync_assumed"}

    missing = list(dict.fromkeys(missing))
    return {
        "available": not missing,
        "missing": missing,
        "requirements": list(requirements),
        "details": details,
    }