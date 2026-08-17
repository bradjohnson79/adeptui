"""Typed Scriptwriter errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCRIPT_LOAD_FAILED = "SCRIPT_LOAD_FAILED"
SCRIPT_SAVE_FAILED = "SCRIPT_SAVE_FAILED"
SCRIPT_CONFLICT = "SCRIPT_CONFLICT"
SCRIPT_RECOVERY_AVAILABLE = "SCRIPT_RECOVERY_AVAILABLE"
SCRIPT_RECOVERY_UNAVAILABLE = "SCRIPT_RECOVERY_UNAVAILABLE"
SCRIPT_IMPORT_FAILED = "SCRIPT_IMPORT_FAILED"
SCRIPT_EXPORT_FAILED = "SCRIPT_EXPORT_FAILED"
SCRIPT_PARSE_UNCERTAIN = "SCRIPT_PARSE_UNCERTAIN"
SCRIPT_REVISION_LOCKED = "SCRIPT_REVISION_LOCKED"
SCRIPT_SCENE_SYNC_CONFLICT = "SCRIPT_SCENE_SYNC_CONFLICT"
SCRIPT_TIMELINE_PREP_FAILED = "SCRIPT_TIMELINE_PREP_FAILED"
SCRIPT_BIBLE_SYNC_CONFLICT = "SCRIPT_BIBLE_SYNC_CONFLICT"
SCRIPT_CODIRECTOR_CONTEXT_FAILED = "SCRIPT_CODIRECTOR_CONTEXT_FAILED"
SCRIPT_PROPOSAL_STALE = "SCRIPT_PROPOSAL_STALE"
SCRIPT_TRANSACTION_FAILED = "SCRIPT_TRANSACTION_FAILED"
SCRIPT_NOT_REVERSIBLE = "SCRIPT_NOT_REVERSIBLE"


@dataclass
class ScriptwriterError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recovery_action: str = "retry"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoveryAction": self.recovery_action,
        }
