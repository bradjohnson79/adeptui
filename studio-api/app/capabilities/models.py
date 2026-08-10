"""Capability status vocabulary and public payload shapes.

The status vocabulary is deliberately small and fixed. Every value has one meaning and
one owner, so no consumer (Health Dashboard, Setup Wizard, Co-Director M2.2) has to guess
what "ready" was supposed to imply:

| Status | Meaning |
|--------|---------|
| `not_implemented` | The capability does not exist in this build. Absent, not broken. |
| `ui_only` | A UI affordance exists with no durable backend behind it. |
| `backend_only` | A working backend surface exists that no UI reaches yet. |
| `partially_wired` | UI and backend both exist but the slice is not proven end to end. |
| `mock_verified` | Only proven against a mock/fixture double. Never a production claim. |
| `locally_verified` | Full vertical slice exercised against real local storage/providers. |
| `production_ready` | `locally_verified` plus a documented contract and real E2E proof. |
| `blocked` | Implemented, but a real dependency is missing (model, extension, service). |
| `degraded` | Usable with reduced function or a fallback path. |
| `not_configured` | Implemented, but the operator has not supplied required configuration. |
| `unknown` | Not yet probed in this environment. |
| `deferred_version_1_2` | Intentionally out of Version 1.1 scope; planned for Version 1.2. Not a failure. |
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CapabilityStatus(str, Enum):
    NOT_IMPLEMENTED = "not_implemented"
    UI_ONLY = "ui_only"
    BACKEND_ONLY = "backend_only"
    PARTIALLY_WIRED = "partially_wired"
    MOCK_VERIFIED = "mock_verified"
    LOCALLY_VERIFIED = "locally_verified"
    PRODUCTION_READY = "production_ready"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"
    DEFERRED_VERSION_1_2 = "deferred_version_1_2"


#: Statuses that mean "a caller may invoke this now".
USABLE_STATUSES = frozenset(
    {
        CapabilityStatus.LOCALLY_VERIFIED,
        CapabilityStatus.PRODUCTION_READY,
        CapabilityStatus.DEGRADED,
    }
)

#: Statuses that mean "something must change in the environment before this can be used".
BLOCKING_STATUSES = frozenset(
    {
        CapabilityStatus.BLOCKED,
        CapabilityStatus.NOT_CONFIGURED,
    }
)

#: Statuses that must never be presented to an agent as callable, even though code exists.
UNPROVEN_STATUSES = frozenset(
    {
        CapabilityStatus.NOT_IMPLEMENTED,
        CapabilityStatus.UI_ONLY,
        CapabilityStatus.BACKEND_ONLY,
        CapabilityStatus.PARTIALLY_WIRED,
        CapabilityStatus.MOCK_VERIFIED,
        CapabilityStatus.UNKNOWN,
        CapabilityStatus.DEFERRED_VERSION_1_2,
    }
)

#: Roadmap-deferred rows: listed for honesty, excluded from Version 1.1 readiness denominator.
DEFERRED_FROM_READINESS_STATUSES = frozenset(
    {
        CapabilityStatus.DEFERRED_VERSION_1_2,
    }
)

# SceneCraft is a planned future module — not part of the current release gate.
# It must never appear in CAPABILITIES, UI exposure, Co-Director tools, or blocker counts.
SCENECRAFT_RELEASE_EXCLUSION = {
    "capabilityId": "scenecraft",
    "releaseStatus": "PLANNED_FUTURE_MODULE",
    "notPartOfCurrentRelease": True,
    "exposedInUi": False,
    "exposedToCoDirector": False,
    "requiredForCurrentGate": False,
    "includedInBlockedCount": False,
    "includedInDeferredCount": False,
}


@dataclass(frozen=True)
class CapabilityDefinition:
    """Static, environment-independent facts about one capability."""

    id: str
    display_name: str
    subsystem: str
    #: Baseline status from code inspection. Live probes may only *lower* confidence
    #: (e.g. `locally_verified` → `blocked`) or resolve `unknown`; a probe never invents
    #: a stronger claim than the baseline recorded here.
    baseline_status: CapabilityStatus
    summary: str = ""
    dependencies: tuple[str, ...] = ()
    read_only: bool = True
    requires_approval: bool = False
    #: Setup/Source Manager component ids a blocker should point at, when known.
    component_ids: tuple[str, ...] = ()
    #: Dotted path of the application service entry point Co-Director would call.
    service_ref: Optional[str] = None
    #: HTTP surface, for documentation and for FE deep links.
    http_ref: Optional[str] = None
    #: Why the baseline is not `production_ready`/`locally_verified`, when applicable.
    baseline_reason: str = ""
    scope: str = "global"


@dataclass
class CapabilityEvaluation:
    """Result of evaluating one capability against a probe snapshot."""

    status: CapabilityStatus
    available: bool = False
    configured: bool = True
    healthy: bool = True
    reason_code: Optional[str] = None
    message: str = ""
    recommended_action: Optional[str] = None
    component_ids: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


class CapabilityOut(BaseModel):
    """Public capability payload. Contains no secrets and no stack traces."""

    id: str
    displayName: str
    subsystem: str
    status: CapabilityStatus
    available: bool
    configured: bool
    healthy: bool
    readOnly: bool
    requiresApproval: bool
    dependencies: list[str] = Field(default_factory=list)
    reasonCode: Optional[str] = None
    message: str = ""
    recommendedAction: Optional[str] = None
    componentIds: list[str] = Field(default_factory=list)
    serviceRef: Optional[str] = None
    httpRef: Optional[str] = None
    scope: str = "global"
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    lastCheckedAt: str


class CapabilityBlockerOut(BaseModel):
    capabilityId: str
    displayName: str
    subsystem: str
    status: CapabilityStatus
    reasonCode: Optional[str] = None
    message: str = ""
    recommendedAction: Optional[str] = None
    componentIds: list[str] = Field(default_factory=list)


class CapabilitySnapshotOut(BaseModel):
    schemaVersion: int = 1
    projectId: Optional[str] = None
    generatedAt: str
    correlationId: str
    counts: dict[str, int] = Field(default_factory=dict)
    capabilities: list[CapabilityOut] = Field(default_factory=list)
    blockers: list[CapabilityBlockerOut] = Field(default_factory=list)
    #: Capability ids that a caller (including Co-Director) may invoke right now.
    callable: list[str] = Field(default_factory=list)
    #: Version 1.1 readiness denominator — excludes DEFERRED_VERSION_1_2 rows.
    readinessTotal: int = 0
    #: Deferred capability ids (roadmap only; not in readinessTotal).
    deferred: list[str] = Field(default_factory=list)
    probeWarnings: list[str] = Field(default_factory=list)
