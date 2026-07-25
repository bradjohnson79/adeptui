"""Thin capability adapter over the PSR capability registry (via CoDirectorCapabilityBridge).

This is deliberately *not* a second readiness matrix. It answers exactly one question per
capability key ? "can a tool that needs this run right now?" ? by mapping the tool key to
PSR capability ids and reading live status from `app.capabilities.service`.

Outcomes normalized for existing tool callers:

- `available` ? the tool may run.
- `configured=False` ? the subsystem was never set up (`CAPABILITY_NOT_CONFIGURED`).
- `configured=True, available=False` ? set up but currently unreachable/unhealthy
  (`CAPABILITY_UNAVAILABLE`).

E2E mock overrides still force deterministic blocked/not-configured states without probing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..errors import (
    CAPABILITY_NOT_CONFIGURED,
    CAPABILITY_UNAVAILABLE,
    CAPABILITY_UNKNOWN,
    CoDirectorError,
)
from .capability_bridge import CoDirectorCapabilityBridge
from .definitions import CAPABILITY_KEYS


@dataclass
class CapabilityState:
    key: str
    available: bool
    status: str
    configured: bool = True
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    proposal_ready: bool = False
    execution_blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "available": self.available,
            "status": self.status,
            "configured": self.configured,
            "reason": self.reason,
            "proposalReady": self.proposal_ready,
            "executionBlocked": self.execution_blocked,
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
            details={
                "toolId": tool_id,
                "capability": self.key,
                "capabilityStatus": self.status,
                "proposalReady": self.proposal_ready,
                "executionBlocked": self.execution_blocked,
            },
            recoverable=True,
            recommended_action="configure_capability" if code == CAPABILITY_NOT_CONFIGURED else "retry_or_check_service",
        )


def _e2e_overrides() -> dict[str, str]:
    """E2E-only capability forcing, keyed off the existing mock-scenario mechanism."""

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
    """Per-request capability snapshot. Live readiness delegates to CoDirectorCapabilityBridge."""

    def __init__(self, db: Session, project_id: Optional[str]) -> None:
        self._db = db
        self._project_id = project_id
        self._cache: dict[str, CapabilityState] = {}
        self._overrides = _e2e_overrides()
        self._bridge = CoDirectorCapabilityBridge(db, project_id)

    @property
    def bridge(self) -> CoDirectorCapabilityBridge:
        return self._bridge

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
            state = CapabilityState(
                key,
                False,
                "unavailable",
                True,
                "Simulated unavailable capability (E2E).",
                execution_blocked=True,
            )
        elif forced == "not_configured":
            state = CapabilityState(
                key,
                False,
                "not_configured",
                False,
                "Simulated unconfigured capability (E2E).",
                execution_blocked=True,
            )
        else:
            try:
                raw = await self._bridge.readiness_for_tool_key(key)
                state = CapabilityState(
                    key=raw["key"],
                    available=bool(raw["available"]),
                    status=str(raw["status"]),
                    configured=bool(raw.get("configured", True)),
                    reason=str(raw.get("reason") or ""),
                    detail=dict(raw.get("detail") or {}),
                    proposal_ready=bool(raw.get("available")),
                    execution_blocked=not bool(raw.get("available")),
                )
            except Exception as exc:  # noqa: BLE001 - probes must fail closed
                state = CapabilityState(
                    key,
                    False,
                    "unavailable",
                    True,
                    f"Check failed: {str(exc)[:120]}",
                    execution_blocked=True,
                )
        self._cache[key] = state
        return state

    async def readiness_for_tool(self, tool_id: str) -> dict[str, Any]:
        """Full tool readiness including proposal_ready vs execution_blocked."""

        forced_keys = set(self._overrides)
        if forced_keys:
            # Keep E2E overrides authoritative for forced keys; otherwise use the bridge.
            from . import registry as tool_registry

            definition = tool_registry.find(tool_id)
            if definition and definition.capability in forced_keys:
                state = await self.state_for(definition.capability)
                return {
                    "tool": tool_id,
                    "status": state.status,
                    "callable": state.available,
                    "missingCapabilities": [] if state.available else [definition.capability],
                    "proposalReady": False,
                    "executionBlocked": not state.available,
                }
        readiness = await self._bridge.tool_readiness(tool_id)
        return readiness.to_dict()

    def cached_states(self) -> dict[str, CapabilityState]:
        """Capabilities probed so far this turn ? what handlers are allowed to read."""

        return dict(self._cache)

    async def snapshot(self) -> dict[str, CapabilityState]:
        for key in CAPABILITY_KEYS:
            await self.state_for(key)
        return dict(self._cache)

    async def snapshot_dict(self) -> dict[str, Any]:
        states = await self.snapshot()
        return {key: state.to_dict() for key, state in states.items()}
