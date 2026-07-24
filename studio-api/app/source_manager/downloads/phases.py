"""Central DownloadOperation phase vocabulary and valid transitions."""

from __future__ import annotations

TERMINAL_PHASES = frozenset(
    {
        "installed",
        "failed",
        "cancelled",
        "interrupted",
        "rolled_back",
    }
)

ACTIVE_PHASES = frozenset(
    {
        "queued",
        "preflighting",
        "resolving",
        "verifying_source",
        "waiting_for_auth",
        "waiting_for_disk_space",
        "downloading",
        "pausing",
        "paused",
        "resuming",
        "extracting",
        "validating",
        "finalizing",
        "cancelling",
        "cleaning_up",
        "rolling_back",
    }
)

# From-phase -> allowed next phases
TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"preflighting", "cancelling", "interrupted", "failed"}),
    "preflighting": frozenset(
        {
            "resolving",
            "waiting_for_disk_space",
            "waiting_for_auth",
            "cancelling",
            "failed",
            "interrupted",
        }
    ),
    "resolving": frozenset(
        {"verifying_source", "waiting_for_auth", "cancelling", "failed", "interrupted"}
    ),
    "verifying_source": frozenset(
        {"downloading", "waiting_for_auth", "cancelling", "failed", "interrupted"}
    ),
    "waiting_for_auth": frozenset(
        {"verifying_source", "downloading", "cancelling", "failed", "interrupted"}
    ),
    "waiting_for_disk_space": frozenset(
        {"preflighting", "resolving", "cancelling", "failed", "interrupted"}
    ),
    "downloading": frozenset(
        {
            "pausing",
            "extracting",
            "validating",
            "cancelling",
            "failed",
            "interrupted",
        }
    ),
    "pausing": frozenset({"paused", "cancelling", "failed", "interrupted"}),
    "paused": frozenset({"resuming", "cancelling", "failed", "interrupted"}),
    "resuming": frozenset({"downloading", "cancelling", "failed", "interrupted"}),
    "extracting": frozenset({"validating", "cancelling", "failed", "interrupted"}),
    "validating": frozenset({"finalizing", "cancelling", "failed", "interrupted"}),
    "finalizing": frozenset({"installed", "cleaning_up", "failed", "interrupted"}),
    "cleaning_up": frozenset({"installed", "cancelled", "failed", "interrupted"}),
    "cancelling": frozenset({"cancelled", "cleaning_up", "failed", "interrupted"}),
    "rolling_back": frozenset({"rolled_back", "failed", "interrupted"}),
    # Terminal — only allow re-entry via new attempt (retry clones phase to queued)
    "installed": frozenset(),
    "failed": frozenset({"queued"}),  # retry resets via controlled path
    "cancelled": frozenset(),
    "interrupted": frozenset({"queued", "resuming", "cancelling", "cleaning_up"}),
    "rolled_back": frozenset(),
}


class InvalidPhaseTransition(ValueError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Invalid phase transition: {current} -> {target}")
        self.current = current
        self.target = target


def can_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    allowed = TRANSITIONS.get(current)
    if allowed is None:
        return False
    return target in allowed


def transition(current: str, target: str) -> str:
    if current == target:
        return target
    if not can_transition(current, target):
        raise InvalidPhaseTransition(current, target)
    return target


def is_terminal(phase: str) -> bool:
    return phase in TERMINAL_PHASES


def is_active(phase: str) -> bool:
    return phase in ACTIVE_PHASES
