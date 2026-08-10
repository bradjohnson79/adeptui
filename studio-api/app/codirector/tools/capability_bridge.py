"""Bridge Co-Director tool capability keys to the PSR capability registry.

Tool definitions still declare short keys (`comfyui`, `bible`, ?). Live readiness for those
keys is answered by querying `app.capabilities.service` ? not a parallel hard-coded matrix.
This module only owns the *mapping* from tool keys ? PSR capability ids and the tool-level
readiness vocabulary (`proposal_ready` / `execution_blocked`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...capabilities.models import (
    BLOCKING_STATUSES,
    USABLE_STATUSES,
    CapabilityOut,
    CapabilityStatus,
)
from .definitions import CAPABILITY_KEYS, ToolDefinition


# Tool-key ? PSR capability ids that must be callable for *execution*.
# Mapping only ? status values always come from the shared registry/service.
_TOOL_KEY_TO_PSR_IDS: dict[str, tuple[str, ...]] = {
    "project": ("project.read", "project.scenes.read"),
    "library": ("assets.read",),
    "bible": ("codirector.bible.read",),
    "provider": ("codirector.provider",),
    "comfyui": ("comfyui.health", "storyboard.generate"),
    "references": ("references.timeline_bindings",),
    "source_manager": ("source_manager.read",),
    "preview_engine": ("comfyui.health", "workflows.video.ready"),
    "vision": ("codirector.vision.validate", "codirector.vision.review"),
}

# Capabilities that let a mutating tool create a durable proposal even when execution is blocked.
_PROPOSAL_PATH_IDS: tuple[str, ...] = (
    "references.timeline_bindings",
    "codirector.bible.propose",
    "project.scenes.update",
    "project.read",
    "codirector.vision.review",
)


@dataclass
class ToolReadiness:
    tool: str
    status: str
    callable: bool
    missingCapabilities: list[str] = field(default_factory=list)
    proposalReady: bool = False
    executionBlocked: bool = False
    requiredCapabilities: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "status": self.status,
            "callable": self.callable,
            "missingCapabilities": list(self.missingCapabilities),
            "proposalReady": self.proposalReady,
            "executionBlocked": self.executionBlocked,
            "requiredCapabilities": list(self.requiredCapabilities),
            "detail": dict(self.detail),
        }


def psr_ids_for_tool_key(tool_key: str) -> tuple[str, ...]:
    """Return the PSR capability ids a tool capability key depends on."""

    if tool_key not in CAPABILITY_KEYS:
        return ()
    return _TOOL_KEY_TO_PSR_IDS.get(tool_key, ())


def _by_id(snapshot_capabilities: list[CapabilityOut]) -> dict[str, CapabilityOut]:
    return {item.id: item for item in snapshot_capabilities}


def _is_usable(cap: Optional[CapabilityOut]) -> bool:
    if cap is None:
        return False
    return bool(cap.available) or cap.status in USABLE_STATUSES


def _status_value(cap: Optional[CapabilityOut]) -> str:
    if cap is None:
        return CapabilityStatus.UNKNOWN.value
    return cap.status.value if isinstance(cap.status, CapabilityStatus) else str(cap.status)


class CoDirectorCapabilityBridge:
    """Resolve tool readiness against the shared PSR capability registry."""

    def __init__(self, db: Session, project_id: Optional[str]) -> None:
        self._db = db
        self._project_id = project_id
        self._snapshot = None
        self._caps_by_id: dict[str, CapabilityOut] = {}

    async def _ensure_snapshot(self, *, force: bool = False) -> None:
        if self._snapshot is not None and not force:
            return
        from ...capabilities import service as capability_service

        self._snapshot = await capability_service.get_capabilities(
            project_id=self._project_id,
            force=force,
        )
        self._caps_by_id = _by_id(self._snapshot.capabilities)

    async def refresh(self) -> None:
        await self._ensure_snapshot(force=True)

    def _domain_gate(self, tool_key: str) -> dict[str, Any] | None:
        """Tool-key domain checks the PSR registry cannot answer alone.

        `project` needs an open project id; `bible` needs a current Production Bible version.
        These overlays still fail closed and never invent readiness beyond the registry.
        """
        if tool_key == "project":
            if not self._project_id:
                return {
                    "key": tool_key,
                    "available": False,
                    "status": "not_configured",
                    "configured": False,
                    "reason": "No project is open.",
                    "detail": {"requiredCapabilities": list(psr_ids_for_tool_key(tool_key))},
                }
            from ...db import Project

            if self._db.get(Project, self._project_id) is None:
                return {
                    "key": tool_key,
                    "available": False,
                    "status": "not_configured",
                    "configured": False,
                    "reason": "Project not found.",
                    "detail": {"requiredCapabilities": list(psr_ids_for_tool_key(tool_key))},
                }
            return None
        if tool_key == "bible":
            if not self._project_id:
                return {
                    "key": tool_key,
                    "available": False,
                    "status": "not_configured",
                    "configured": False,
                    "reason": "No project is open.",
                    "detail": {"requiredCapabilities": list(psr_ids_for_tool_key(tool_key))},
                }
            from ..bible import operations as ops

            bible = ops.get_bible(self._db, self._project_id)
            if not bible or not bible.current_version_id:
                return {
                    "key": tool_key,
                    "available": False,
                    "status": "not_configured",
                    "configured": False,
                    "reason": "This project doesn't have a Production Bible yet.",
                    "detail": {"requiredCapabilities": list(psr_ids_for_tool_key(tool_key))},
                }
            return None
        return None

    async def readiness_for_tool_key(self, tool_key: str) -> dict[str, Any]:
        """Legacy-shaped state used by CapabilityAdapter (available / status / configured)."""

        domain = self._domain_gate(tool_key)
        if domain is not None:
            return domain

        await self._ensure_snapshot()
        required = list(psr_ids_for_tool_key(tool_key))
        missing = [cid for cid in required if not _is_usable(self._caps_by_id.get(cid))]
        if not required:
            return {
                "key": tool_key,
                "available": False,
                "status": CapabilityStatus.UNKNOWN.value,
                "configured": False,
                "reason": f"No PSR mapping for tool capability '{tool_key}'.",
                "detail": {"requiredCapabilities": required},
            }

        if missing:
            sample = self._caps_by_id.get(missing[0])
            configured = True if sample is None else bool(sample.configured)
            status = _status_value(sample) if sample else CapabilityStatus.UNKNOWN.value
            if status == CapabilityStatus.NOT_CONFIGURED.value:
                configured = False
            reason = sample.message if sample and sample.message else f"Missing capability '{missing[0]}'."
            return {
                "key": tool_key,
                "available": False,
                "status": "not_configured" if not configured else "unavailable",
                "configured": configured,
                "reason": reason,
                "detail": {
                    "requiredCapabilities": required,
                    "missingCapabilities": missing,
                    "psrStatus": status,
                },
            }

        sample = self._caps_by_id.get(required[0])
        return {
            "key": tool_key,
            "available": True,
            "status": "ready",
            "configured": True,
            "reason": "",
            "detail": {
                "requiredCapabilities": required,
                "psrStatus": _status_value(sample),
                "callable": list(self._snapshot.callable) if self._snapshot else [],
            },
        }

    async def tool_readiness(self, tool_id: str) -> ToolReadiness:
        from . import registry as tool_registry_module

        await self._ensure_snapshot()
        definition = tool_registry_module.find(tool_id)
        if definition is None:
            return ToolReadiness(
                tool=tool_id,
                status=CapabilityStatus.UNKNOWN.value,
                callable=False,
                missingCapabilities=[],
                proposalReady=False,
                executionBlocked=True,
                detail={"reason": "Unknown tool."},
            )
        return await self._readiness_for_definition(definition)

    async def _readiness_for_definition(self, definition: ToolDefinition) -> ToolReadiness:
        domain = self._domain_gate(definition.capability)
        if domain is not None:
            return ToolReadiness(
                tool=definition.tool_id,
                status=str(domain["status"]),
                callable=False,
                missingCapabilities=list((domain.get("detail") or {}).get("missingCapabilities") or []),
                proposalReady=False,
                executionBlocked=True,
                requiredCapabilities=list(psr_ids_for_tool_key(definition.capability)),
                detail={"capabilityKey": definition.capability, "reason": domain.get("reason")},
            )
        await self._ensure_snapshot()
        required = list(psr_ids_for_tool_key(definition.capability))
        missing = [cid for cid in required if not _is_usable(self._caps_by_id.get(cid))]
        proposal_path_ok = any(_is_usable(self._caps_by_id.get(cid)) for cid in _PROPOSAL_PATH_IDS)
        if definition.kind == "mutating" and definition.capability == "bible":
            proposal_path_ok = _is_usable(self._caps_by_id.get("codirector.bible.propose")) or proposal_path_ok

        if not missing:
            status = CapabilityStatus.LOCALLY_VERIFIED.value
            sample = self._caps_by_id.get(required[0]) if required else None
            if sample is not None:
                status = _status_value(sample)
            return ToolReadiness(
                tool=definition.tool_id,
                status=status,
                callable=True,
                missingCapabilities=[],
                proposalReady=True,
                executionBlocked=False,
                requiredCapabilities=required,
                detail={"capabilityKey": definition.capability},
            )

        if definition.kind == "mutating" and proposal_path_ok:
            return ToolReadiness(
                tool=definition.tool_id,
                status="proposal_ready",
                callable=False,
                missingCapabilities=missing,
                proposalReady=True,
                executionBlocked=True,
                requiredCapabilities=required,
                detail={"capabilityKey": definition.capability},
            )

        sample = self._caps_by_id.get(missing[0]) if missing else None
        status = "execution_blocked"
        if sample is not None and sample.status in BLOCKING_STATUSES:
            status = _status_value(sample)
        return ToolReadiness(
            tool=definition.tool_id,
            status=status,
            callable=False,
            missingCapabilities=missing,
            proposalReady=False,
            executionBlocked=True,
            requiredCapabilities=required,
            detail={
                "capabilityKey": definition.capability,
                "psrStatus": _status_value(sample) if sample else CapabilityStatus.UNKNOWN.value,
            },
        )

    async def snapshot_tool_readiness(self) -> list[dict[str, Any]]:
        from . import registry as tool_registry_module

        await self._ensure_snapshot()
        out: list[dict[str, Any]] = []
        for definition in tool_registry_module.all_definitions():
            readiness = await self._readiness_for_definition(definition)
            out.append(readiness.to_dict())
        return out

    def registry_totals(self) -> dict[str, Any]:
        if self._snapshot is None:
            return {"callable": 0, "blocked": 0, "total": 0, "counts": {}}
        blocked = len(self._snapshot.blockers)
        return {
            "callable": len(self._snapshot.callable),
            "blocked": blocked,
            "total": len(self._snapshot.capabilities),
            "counts": dict(self._snapshot.counts),
            "packBlockers": [
                {
                    "capabilityId": b.capabilityId,
                    "message": b.message,
                    "recommendedAction": b.recommendedAction,
                    "componentIds": list(b.componentIds),
                }
                for b in self._snapshot.blockers
                if b.subsystem in ("source_manager", "models", "workflows", "comfyui")
            ],
        }
