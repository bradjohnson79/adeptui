"""Structured Co-Director provider errors (never expose secrets)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Patterns for values that must never reach the browser (or logs) verbatim inside error
# `details` — bearer/API tokens, long hex/opaque tokens, and common `key=value` secret
# shapes that could leak from a proxy, auth header, or upstream error body.
_SECRET_PATTERNS = [
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_.]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^\s'\"]{4,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{6,}"),
    re.compile(r"\b[0-9a-fA-F]{16,}\b"),
]


def redact_secrets(text: str) -> str:
    """Best-effort scrub of secret-shaped substrings before an error reaches details/logs."""
    if not text:
        return text
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out


@dataclass
class CoDirectorError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    recommended_action: str = "retry"

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
            "recoverable": self.recoverable,
            "recommendedAction": self.recommended_action,
        }


PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
CONNECTION_REFUSED = "CONNECTION_REFUSED"
REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
MODEL_NOT_SELECTED = "MODEL_NOT_SELECTED"
MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
NO_MODELS_INSTALLED = "NO_MODELS_INSTALLED"
PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
STREAM_INTERRUPTED = "STREAM_INTERRUPTED"
REQUEST_CANCELLED = "REQUEST_CANCELLED"
BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
CONTEXT_TOO_LARGE = "CONTEXT_TOO_LARGE"
UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"

# --------------------------------------------------------------------------
# M2.1: Production Bible + durable proposals/approvals/execution.
# --------------------------------------------------------------------------
BIBLE_NOT_FOUND = "BIBLE_NOT_FOUND"
BIBLE_VERSION_NOT_FOUND = "BIBLE_VERSION_NOT_FOUND"
BIBLE_ALREADY_EXISTS = "BIBLE_ALREADY_EXISTS"
BIBLE_VALIDATION_ERROR = "BIBLE_VALIDATION_ERROR"
PROPOSAL_NOT_FOUND = "PROPOSAL_NOT_FOUND"
PROPOSAL_INVALID_STATE = "PROPOSAL_INVALID_STATE"
PROPOSAL_STALE = "PROPOSAL_STALE"
APPROVAL_ALREADY_RECORDED = "APPROVAL_ALREADY_RECORDED"
EXECUTION_FAILED = "EXECUTION_FAILED"
EXECUTION_ALREADY_APPLIED = "EXECUTION_ALREADY_APPLIED"
PROJECT_SCOPE_VIOLATION = "PROJECT_SCOPE_VIOLATION"
STRUCTURED_OUTPUT_INVALID = "STRUCTURED_OUTPUT_INVALID"
RECEIPT_NOT_FOUND = "RECEIPT_NOT_FOUND"


_STATUS_BY_CODE = {
    CONNECTION_REFUSED: 503,
    PROVIDER_UNAVAILABLE: 503,
    BACKEND_UNAVAILABLE: 503,
    PROVIDER_NOT_CONFIGURED: 503,
    REQUEST_TIMEOUT: 504,
    MODEL_NOT_FOUND: 400,
    MODEL_NOT_SELECTED: 400,
    NO_MODELS_INSTALLED: 400,
    CONTEXT_TOO_LARGE: 400,
    VALIDATION_ERROR: 400,
    PROJECT_NOT_FOUND: 404,
    REQUEST_CANCELLED: 499,
    STREAM_INTERRUPTED: 502,
    PROVIDER_RESPONSE_INVALID: 502,
    UNKNOWN_PROVIDER_ERROR: 502,
    BIBLE_NOT_FOUND: 404,
    BIBLE_VERSION_NOT_FOUND: 404,
    BIBLE_ALREADY_EXISTS: 409,
    BIBLE_VALIDATION_ERROR: 400,
    PROPOSAL_NOT_FOUND: 404,
    PROPOSAL_INVALID_STATE: 409,
    PROPOSAL_STALE: 409,
    APPROVAL_ALREADY_RECORDED: 409,
    EXECUTION_FAILED: 502,
    EXECUTION_ALREADY_APPLIED: 409,
    PROJECT_SCOPE_VIOLATION: 403,
    STRUCTURED_OUTPUT_INVALID: 502,
    RECEIPT_NOT_FOUND: 404,
}


def status_code_for_error(code: str) -> int:
    return _STATUS_BY_CODE.get(code, 500)


def classify_httpx_error(exc: BaseException, *, endpoint: str, provider: str = "ollama") -> CoDirectorError:
    import httpx

    details = {"provider": provider, "endpoint": endpoint}
    if isinstance(exc, httpx.ConnectError):
        return CoDirectorError(
            CONNECTION_REFUSED,
            f"Co-Director could not reach Ollama at {endpoint}.",
            details=details,
            recommended_action="retry_or_check_service",
        )
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.TimeoutException)):
        return CoDirectorError(
            REQUEST_TIMEOUT,
            "The model took too long to respond. You can retry or choose another model.",
            details=details,
            recommended_action="retry",
        )
    text = str(exc)
    if "Connection refused" in text or "ConnectError" in text:
        return CoDirectorError(
            CONNECTION_REFUSED,
            f"Co-Director could not reach Ollama at {endpoint}.",
            details=details,
            recommended_action="retry_or_check_service",
        )
    return CoDirectorError(
        UNKNOWN_PROVIDER_ERROR,
        "The local model provider returned an unexpected error.",
        details={**details, "reason": redact_secrets(text[:200])},
        recommended_action="retry_or_check_service",
    )
