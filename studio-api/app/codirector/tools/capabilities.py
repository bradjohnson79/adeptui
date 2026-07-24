"""Thin capability adapter over probes that already exist elsewhere in the app.

This is deliberately *not* a Production Systems Readiness matrix. It answers exactly one
question per capability key — "can a tool that needs this run right now?" — by calling the
existing probe and normalizing its answer into three outcomes:

- `available` — the tool may run.
- `configured=False` — the subsystem was never set up (`CAPABILITY_NOT_CONFIGURED`).
- `configured=True, available=False` — set up but currently unreachable/unhealthy
  (`CAPABILITY_UNAVAILABLE`).

Every probe is wrapped so it can only ever *fail closed*. A probe that raises must never take
down a chat turn, so an exception becomes "unavailable" with a short reason.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Project
from ..errors import (
    CAPABILITY_NOT_CONFIGURED,
    CAPABILITY_UNAVAILABLE,
    CAPABILITY_UNKNOWN,
    CoDirectorError,
)
from .definitions import CAPABILITY_KEYS

# Probe timeout. Tool availability is checked inline in a chat turn, so a hung local service
# must not stall the turn — it degrades to "unavailable" instead.
PROBE_TIMEOUT_SEC = 6.0


@dataclass
class CapabilityState:
    key: str
    available: bool
    status: str
    configured: bool = True
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "available": self.available,
            "status": self.status,
            "configured": self.configured,
            "reason": self.reason,
        }

    def error_code(self) -> Optional[str]:
        if self.available:
            return None
        return CAPABILITY_NOT_CONFIGURED if not self.configured else CAPABILITY_UNAVAILABLE

    def as_error(self, tool_id: str) -> CoDirectorError:
        code = self.error_code() or CAPABILITY_UNAVAILABLE
        return CoDirectorError(
            code,
            self.reason or f"The '{self.key}' capability isn't available right now.",
            details={"toolId": tool_id, "capability": self.key, "capabilityStatus": self.status},
            recoverable=True,
            recommended_action="configure_capability" if code == CAPABILITY_NOT_CONFIGURED else "retry_or_check_service",
        )


def _e2e_overrides() -> dict[str, str]:
    """E2E-only capability forcing, keyed off the existing mock-scenario mechanism.

    Playwright needs deterministic "capability blocked" and "capability not configured" states
    without a real ComfyUI or IC-LoRA install on the runner. Reusing
    `ADEPT_CODIRECTOR_MOCK_SCENARIO` keeps the control surface to the one E2E endpoint that
    already exists, and this whole function is inert unless `STUDIO_E2E` is on.
    """

    from ..service import e2e_enabled

    if not e2e_enabled():
        return {}
    scenario = (os.environ.get("ADEPT_CODIRECTOR_MOCK_SCENARIO") or "").strip().lower()
    if scenario in ("read_tool_blocked_capability", "capability_blocked"):
        return {"comfyui": "unavailable"}
    if scenario == "capability_not_configured":
        return {"references": "not_configured"}
    return {}


class CapabilityAdapter:
    """Per-request capability snapshot. Probes are called at most once each."""

    def __init__(self, db: Session, project_id: Optional[str]) -> None:
        self._db = db
        self._project_id = project_id
        self._cache: dict[str, CapabilityState] = {}
        self._overrides = _e2e_overrides()

    async def state_for(self, key: str) -> CapabilityState:
        if key not in CAPABILITY_KEYS:
            raise CoDirectorError(
                CAPABILITY_UNKNOWN,
                f"Unknown capability '{key}'.",
                details={"capability": key},
                recoverable=False,
                recommended_action="none",
            )
        if key in self._cache:
            return self._cache[key]
        forced = self._overrides.get(key)
        if forced == "unavailable":
            state = CapabilityState(key, False, "unavailable", True, "Simulated unavailable capability (E2E).")
        elif forced == "not_configured":
            state = CapabilityState(key, False, "not_configured", False, "Simulated unconfigured capability (E2E).")
        else:
            state = await self._probe(key)
        self._cache[key] = state
        return state

    def cached_states(self) -> dict[str, CapabilityState]:
        """Capabilities probed so far this turn — what handlers are allowed to read."""

        return dict(self._cache)

    async def snapshot(self) -> dict[str, CapabilityState]:
        for key in CAPABILITY_KEYS:
            await self.state_for(key)
        return dict(self._cache)

    async def snapshot_dict(self) -> dict[str, Any]:
        states = await self.snapshot()
        return {key: state.to_dict() for key, state in states.items()}

    async def _probe(self, key: str) -> CapabilityState:
        probe = getattr(self, f"_probe_{key}")
        try:
            return await asyncio.wait_for(probe(), timeout=PROBE_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            return CapabilityState(key, False, "unavailable", True, "The check timed out.")
        except Exception as exc:  # noqa: BLE001 - a broken probe must never fail a chat turn
            return CapabilityState(key, False, "unavailable", True, f"Check failed: {str(exc)[:120]}")

    # ---------------- individual probes ----------------

    async def _probe_project(self) -> CapabilityState:
        if not self._project_id:
            return CapabilityState("project", False, "not_configured", False, "No project is open.")
        project = self._db.get(Project, self._project_id)
        if not project:
            return CapabilityState("project", False, "not_configured", False, "Project not found.")
        return CapabilityState("project", True, "ready", detail={"projectId": project.id})

    async def _probe_bible(self) -> CapabilityState:
        from ..bible import operations as ops

        if not self._project_id:
            return CapabilityState("bible", False, "not_configured", False, "No project is open.")
        bible = ops.get_bible(self._db, self._project_id)
        if not bible or not bible.current_version_id:
            return CapabilityState(
                "bible",
                False,
                "not_configured",
                False,
                "This project doesn't have a Production Bible yet.",
            )
        return CapabilityState("bible", True, "ready", detail={"currentVersionId": bible.current_version_id})

    async def _probe_provider(self) -> CapabilityState:
        from .. import service as codirector_service

        health = await codirector_service.get_health()
        if not health.reachable:
            return CapabilityState("provider", False, "unavailable", True, health.message or "Provider unreachable.")
        if not health.model_available:
            return CapabilityState("provider", False, "not_configured", False, health.message or "No model selected.")
        return CapabilityState(
            "provider",
            True,
            "ready",
            detail={"selectedModel": health.selected_model, "providerId": health.provider_id},
        )

    async def _probe_comfyui(self) -> CapabilityState:
        from ...comfy_client import comfy

        data = await comfy.health()
        return CapabilityState("comfyui", True, "ready", detail={"systemStats": data})

    async def _probe_references(self) -> CapabilityState:
        from ...references.capabilities import reference_capabilities

        project = self._db.get(Project, self._project_id) if self._project_id else None
        caps = await asyncio.to_thread(
            reference_capabilities,
            configured_model_path=None,
            object_info={},
            vram_gb=getattr(project, "vram_gb", None) if project else None,
        )
        if not caps.get("model_ready"):
            return CapabilityState(
                "references",
                False,
                "not_configured",
                False,
                str(caps.get("model_message") or "Visual references are not installed."),
                detail=caps,
            )
        if not caps.get("nodes_available"):
            return CapabilityState(
                "references",
                False,
                "unavailable",
                True,
                "Required ComfyUI reference nodes are missing.",
                detail=caps,
            )
        return CapabilityState("references", True, "ready", detail=caps)

    async def _probe_source_manager(self) -> CapabilityState:
        from ...source_manager.service import get_overview

        overview = await asyncio.to_thread(get_overview)
        if not isinstance(overview, dict):
            return CapabilityState("source_manager", False, "unavailable", True, "Source Manager returned no data.")
        return CapabilityState("source_manager", True, "ready", detail=overview)

    async def _probe_preview_engine(self) -> CapabilityState:
        from ...preview_bus import preview_bus

        project = self._db.get(Project, self._project_id) if self._project_id else None
        engine = getattr(project, "engine_default", None) or "ltx"
        caps = preview_bus.capabilities_for(engine)
        return CapabilityState("preview_engine", True, "ready", detail={"engine": engine, "capabilities": caps})
