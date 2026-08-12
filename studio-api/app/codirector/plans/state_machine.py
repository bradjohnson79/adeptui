"""Canonical plan and step state transition rules (domain, not UI)."""

from __future__ import annotations

from typing import FrozenSet

from ..errors import PLAN_ALREADY_TERMINAL, PLAN_STATE_TRANSITION_INVALID, CoDirectorError

# Wave 4: production execution states are not entered by plan-management commands.
PLAN_TRANSITIONS: dict[str, FrozenSet[str]] = {
    "draft": frozenset({"proposed", "awaiting_approval", "cancelled"}),
    "proposed": frozenset({"awaiting_approval", "approved", "cancelled", "draft"}),
    "awaiting_approval": frozenset({"approved", "proposed", "cancelled", "draft"}),
    "approved": frozenset({"ready", "blocked", "paused", "cancelled", "proposed"}),
    "ready": frozenset({"blocked", "paused", "cancelled", "approved", "proposed"}),
    "blocked": frozenset({"ready", "paused", "cancelled", "approved", "proposed"}),
    "paused": frozenset({"ready", "blocked", "cancelled", "approved", "proposed"}),
    "in_progress": frozenset({"paused", "blocked", "completed", "failed", "cancelled"}),
    "completed": frozenset({"archived"}),
    "failed": frozenset({"archived", "cancelled"}),
    "cancelled": frozenset({"archived"}),
    "archived": frozenset(),
}

TERMINAL_PLAN_STATES = frozenset({"cancelled", "archived", "completed"})

STEP_TRANSITIONS: dict[str, FrozenSet[str]] = {
    "pending": frozenset({"ready", "blocked", "awaiting_approval", "deferred", "unsupported", "cancelled", "skipped"}),
    "ready": frozenset({"blocked", "awaiting_approval", "deferred", "paused", "in_progress", "cancelled", "skipped"}),
    "blocked": frozenset({"ready", "pending", "deferred", "cancelled", "skipped"}),
    "awaiting_approval": frozenset({"ready", "blocked", "deferred", "cancelled"}),
    "deferred": frozenset({"pending", "ready", "blocked", "unsupported", "cancelled"}),
    "unsupported": frozenset({"deferred", "cancelled", "skipped"}),
    "paused": frozenset({"ready", "blocked", "pending", "cancelled"}),
    "in_progress": frozenset({"completed", "failed", "paused", "blocked", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset({"pending", "ready", "cancelled"}),
    "skipped": frozenset(),
    "cancelled": frozenset(),
}

# Plan-management commands allowed in Wave 4 (never force production completion).
WAVE4_PLAN_COMMAND_STATES = frozenset(
    {
        "draft",
        "proposed",
        "awaiting_approval",
        "approved",
        "ready",
        "blocked",
        "paused",
        "cancelled",
        "archived",
    }
)


def assert_plan_transition(from_state: str, to_state: str, *, command: str = "") -> None:
    if from_state == to_state:
        return
    if from_state in TERMINAL_PLAN_STATES and to_state not in PLAN_TRANSITIONS.get(from_state, frozenset()):
        raise CoDirectorError(
            PLAN_ALREADY_TERMINAL,
            f"Plan is terminal ({from_state}) and cannot transition to '{to_state}'.",
            details={"from": from_state, "to": to_state, "command": command},
            recoverable=False,
            recommended_action="none",
        )
    allowed = PLAN_TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        raise CoDirectorError(
            PLAN_STATE_TRANSITION_INVALID,
            f"Invalid plan transition {from_state} → {to_state}.",
            details={"from": from_state, "to": to_state, "command": command, "allowed": sorted(allowed)},
            recoverable=False,
            recommended_action="none",
        )
    # Wave 4 guard: plan-management must not enter production execution completion.
    if command and command not in {"__fixture__", "__test__"} and to_state in {"in_progress", "completed", "failed"}:
        raise CoDirectorError(
            PLAN_STATE_TRANSITION_INVALID,
            f"Wave 4 cannot enter production execution state '{to_state}'.",
            details={"from": from_state, "to": to_state, "command": command},
            recoverable=False,
            recommended_action="none",
        )


def assert_step_transition(from_state: str, to_state: str) -> None:
    if from_state == to_state:
        return
    allowed = STEP_TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        raise CoDirectorError(
            PLAN_STATE_TRANSITION_INVALID,
            f"Invalid step transition {from_state} → {to_state}.",
            details={"from": from_state, "to": to_state, "allowed": sorted(allowed)},
            recoverable=False,
            recommended_action="none",
        )
