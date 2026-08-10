"""Structured capability reason codes and error envelope.

Reason codes are stable strings: the Health Dashboard, Setup Wizard, and Co-Director M2.2 all
branch on them, so they are treated as API surface. Messages are human-facing and must never
contain secrets, absolute user paths beyond the configured data root, or stack traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..codirector.errors import redact_secrets

# --- capability lifecycle ---------------------------------------------------
CAPABILITY_NOT_FOUND = "CAPABILITY_NOT_FOUND"
CAPABILITY_NOT_IMPLEMENTED = "CAPABILITY_NOT_IMPLEMENTED"
CAPABILITY_UI_ONLY = "CAPABILITY_UI_ONLY"
CAPABILITY_UNVERIFIED = "CAPABILITY_UNVERIFIED"
CAPABILITY_PROBE_FAILED = "CAPABILITY_PROBE_FAILED"
CAPABILITY_DEFERRED_VERSION_1_2 = "DEFERRED_VERSION_1_2"

# --- dependencies ----------------------------------------------------------
DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
DEPENDENCY_NOT_CONFIGURED = "DEPENDENCY_NOT_CONFIGURED"
DEPENDENCY_DEGRADED = "DEPENDENCY_DEGRADED"

# --- models / packs --------------------------------------------------------
MODEL_MISSING = "MODEL_MISSING"
MODEL_SOURCE_PENDING = "MODEL_SOURCE_PENDING"
MODEL_UNVERIFIED = "MODEL_UNVERIFIED"

# --- ComfyUI extensions / workflows ---------------------------------------
EXTENSION_MISSING = "EXTENSION_MISSING"
WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
WORKFLOW_MISSING_MODELS = "WORKFLOW_MISSING_MODELS"
WORKFLOW_MISSING_EXTENSIONS = "WORKFLOW_MISSING_EXTENSIONS"
WORKFLOW_READINESS_UNKNOWN = "WORKFLOW_READINESS_UNKNOWN"
WORKFLOW_INVALID_INPUTS = "WORKFLOW_INVALID_INPUTS"

# --- queue / storage ------------------------------------------------------
QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"
QUEUE_BLOCKED = "QUEUE_BLOCKED"
STORAGE_NOT_WRITABLE = "STORAGE_NOT_WRITABLE"
STORAGE_PATH_MISSING = "STORAGE_PATH_MISSING"

# --- scope ----------------------------------------------------------------
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
PROJECT_SCOPE_VIOLATION = "PROJECT_SCOPE_VIOLATION"
SCENE_NOT_FOUND = "SCENE_NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"

_STATUS_BY_CODE = {
    CAPABILITY_NOT_FOUND: 404,
    WORKFLOW_NOT_FOUND: 404,
    PROJECT_NOT_FOUND: 404,
    SCENE_NOT_FOUND: 404,
    PROJECT_SCOPE_VIOLATION: 403,
    VALIDATION_ERROR: 400,
    WORKFLOW_INVALID_INPUTS: 400,
    CAPABILITY_NOT_IMPLEMENTED: 501,
    CAPABILITY_DEFERRED_VERSION_1_2: 403,
    DEPENDENCY_UNAVAILABLE: 503,
    DEPENDENCY_NOT_CONFIGURED: 503,
    QUEUE_UNAVAILABLE: 503,
    QUEUE_BLOCKED: 409,
    STORAGE_NOT_WRITABLE: 500,
    CAPABILITY_PROBE_FAILED: 502,
}


def status_code_for_error(code: str) -> int:
    return _STATUS_BY_CODE.get(code, 500)


@dataclass
class CapabilityError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    recommended_action: str = "review_capability"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": redact_secrets(self.message),
            "details": _clean_details(self.details),
            "recoverable": self.recoverable,
            "recommendedAction": self.recommended_action,
        }


_SECRET_KEY_HINTS = ("token", "secret", "password", "authorization", "api_key", "apikey", "cookie")


def _clean_details(payload: Any) -> Any:
    """Drop secret-shaped keys and redact secret-shaped values, recursively."""
    if isinstance(payload, dict):
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(hint in lowered for hint in _SECRET_KEY_HINTS):
                continue
            clean[str(key)] = _clean_details(value)
        return clean
    if isinstance(payload, (list, tuple)):
        return [_clean_details(item) for item in payload]
    if isinstance(payload, str):
        return redact_secrets(payload)
    return payload


def public_details(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Public entry point for scrubbing probe details before they leave the process."""
    return _clean_details(dict(payload or {}))
