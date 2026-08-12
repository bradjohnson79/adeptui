"""Verified Operator channel — wire contracts (Co-Director 2.0 Mission A).

Frozen in `docs/release-gate/codirector-2/CODIRECTOR2_PHASE2_IMPLEMENTATION_CONTRACT.md`
§1. The four operator-capable read tools stay `kind="read"`; during read-tool
execution the service registers an operator request, appends an
`operator_requested` event, and decorates the handler result with an `operator`
block. No new DB table — the append-only conversation event log is the single
authoritative operator ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Operator request timeout in seconds. Evaluated lazily on ack/status read; the
# durable `operator_timeout` event is written when first observed.
OPERATOR_TIMEOUT_SEC = 3.0

# The four operator-capable read tool ids. During `_run_read_tool` the service
# registers an operator request for these and decorates the handler result.
OPERATOR_TOOLS: frozenset[str] = frozenset(
    {
        "timeline.focus_ui",
        "voice_performance.open_workspace",
        "character_creator.open_voice_creator",
        "audio.open_studio",
        "workspace.open_scriptwriter",
    }
)

# Closed set of operator states: `pending → acknowledged | timeout`. A late ack
# after timeout is recorded as `operator_late_ack` and never upgrades the state.
OPERATOR_STATES: frozenset[str] = frozenset({"pending", "acknowledged", "timeout"})

# Event types written to the append-only conversation event log.
OPERATOR_REQUESTED = "operator_requested"
OPERATOR_ACKNOWLEDGED = "operator_acknowledged"
OPERATOR_TIMEOUT = "operator_timeout"
OPERATOR_LATE_ACK = "operator_late_ack"


@dataclass(frozen=True)
class OperatorRecord:
    """Durable operator request record, derived by folding the event log."""

    request_id: str
    tool_id: str
    origin_session_id: str
    state: str
    created_at: Optional[datetime] = None
    workspace: Optional[str] = None
    target: Optional[str] = None
    verified: Optional[bool] = None
    updated_at: Optional[datetime] = None
