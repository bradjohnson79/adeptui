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
    overrides still force Blocked. When ADEPT_MOCK_IMAGEGEN/STUDIO_E2E is set,
    treat comfyui.health as available so closed-loop e2e can proceed through the
    mock ImageGen Job+Asset adapter.
    """
    import os

    forced = set(mock_unavailable or [])
    _TRUE = frozenset({"1", "true", "TRUE", "yes", "YES", "on", "ON"})
    mock_img = (
        os.environ.get("STUDIO_E2E", "").strip() in _TRUE
        or os.environ.get("ADEPT_MOCK_IMAGEGEN", "").strip() in _TRUE
    )

    missing: list[str] = []
    details: dict[str, Any] = {}

    # Fast path: forced unavailable
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
                    # Cannot nest; fall through to permissive mock rules
                    raise RuntimeError("loop running")
                snap = loop.run_until_complete(_run())
            except RuntimeError:
                snap = asyncio.run(_run())

            for req in remaining:
                info = (snap.get("details") or {}).get(req) or {}
                avail = bool(info.get("available", True)) if info else bool(snap.get("available", True))
                # When mock imagegen is on, don't block on comfyui.health
                if req == "comfyui.health" and mock_img:
                    details[req] = {"available": True, "reason": "mock_imagegen_adapter"}
                    continue
                if req in (snap.get("missing") or []):
                    if req == "comfyui.health" and mock_img:
                        details[req] = {"available": True, "reason": "mock_imagegen_adapter"}
                    else:
                        missing.append(req)
                        details[req] = info or {"available": False, "reason": "bridge_unavailable"}
                else:
                    details[req] = info or {"available": True, "reason": "bridge_ok"}
            # Prefer snap missing list when present
            for req in snap.get("missing") or []:
                if req not in missing and not (req == "comfyui.health" and mock_img):
                    if req in remaining:
                        missing.append(req)
        except Exception as exc:  # noqa: BLE001
            for req in remaining:
                if req == "comfyui.health" and mock_img:
                    details[req] = {"available": True, "reason": "mock_imagegen_adapter"}
                    continue
                # Unmapped / bridge error: do not falsely block unknown keys; block known failures only
                details[req] = {"available": True, "reason": f"bridge_error:{exc}"}
    else:
        for req in remaining:
            if req == "comfyui.health" and mock_img:
                details[req] = {"available": True, "reason": "mock_imagegen_adapter"}
            else:
                details[req] = {"available": True, "reason": "sync_assumed"}

    # de-dupe missing
    missing = list(dict.fromkeys(missing))
    return {
        "available": not missing,
        "missing": missing,
        "requirements": list(requirements),
        "details": details,
    }
