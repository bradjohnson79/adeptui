"""Verified Operator channel — request/ack/timeout ledger (Co-Director 2.0 Mission A).

The four operator-capable read tools stay `kind="read"`; during `_run_read_tool`
the service registers an operator request, appends an `operator_requested`
event, and decorates the handler result with an `operator` block. Acks and
timeouts are folded from the append-only conversation event log (Law 8).
"""

from .contracts import (
    OPERATOR_TOOLS,
    OPERATOR_TIMEOUT_SEC,
    OPERATOR_STATES,
    OperatorRecord,
)
from .service import (
    acknowledge_operator_request,
    get_operator_record,
    has_operator_ack,
    register_operator_request,
    resolve_operator_project,
)

__all__ = [
    "OPERATOR_TOOLS",
    "OPERATOR_TIMEOUT_SEC",
    "OPERATOR_STATES",
    "OperatorRecord",
    "acknowledge_operator_request",
    "get_operator_record",
    "has_operator_ack",
    "register_operator_request",
    "resolve_operator_project",
]
