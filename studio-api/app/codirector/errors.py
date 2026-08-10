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


# Absolute filesystem paths (Windows drive/UNC, common POSIX roots) must never reach the
# browser inside error envelopes. Mirrors the pattern in tools/sanitize.py — kept local
# because sanitize.py imports from this module.
_ABS_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/]|(?<![\w.])/(?:usr|home|etc|var|opt|mnt|root|tmp|Users)/)[^\s\"'<>|]*")


def scrub_sensitive(text: str) -> str:
    """Redact secret-shaped substrings and absolute filesystem paths from a string."""
    if not text:
        return text
    return _ABS_PATH_RE.sub("<path>", redact_secrets(text))


def _scrub_detail_value(value: Any, depth: int = 0) -> Any:
    """Bounded recursive scrub of an error-details value (keys preserved, values cleaned)."""
    if depth > 4:
        return "[omitted]"
    if isinstance(value, str):
        return scrub_sensitive(value)
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_scrub_detail_value(item, depth + 1) for item in list(value)[:50]]
    if isinstance(value, dict):
        return {str(k): _scrub_detail_value(v, depth + 1) for k, v in list(value.items())[:60]}
    return scrub_sensitive(str(value)[:400])


def category_for_code(code: str) -> str:
    """Phase 4.1 error category for structured envelopes."""
    if code in {
        MODEL_NOT_FOUND,
        MODEL_NOT_SELECTED,
        NO_MODELS_INSTALLED,
    }:
        return "model"
    if code in {
        PROJECT_NOT_FOUND,
        PROJECT_REQUIRED,
        PROJECT_SCOPE_VIOLATION,
        PROJECT_LOCKED,
    }:
        return "project"
    if code.startswith("TOOL_") or code.startswith("CAPABILITY_"):
        return "tool"
    if code in {
        VALIDATION_ERROR,
        BIBLE_VALIDATION_ERROR,
        TOOL_ARGUMENTS_INVALID,
        TOOL_KIND_MISMATCH,
        PLAN_INVALID,
        PROMPT_INVALID,
        CONTEXT_INCOMPLETE,
        LIFECYCLE_INVALID,
    }:
        return "validation"
    if code in {
        PROVIDER_NOT_CONFIGURED,
        PROVIDER_UNAVAILABLE,
        CONNECTION_REFUSED,
        PROVIDER_RESPONSE_INVALID,
        NO_MODELS_INSTALLED,
    }:
        return "provider"
    return "runtime"


def _safe_evidence(details: dict[str, Any]) -> dict[str, Any]:
    """Redacted, bounded technical evidence — never secrets or full raw payloads."""
    skip = {
        "token",
        "accessToken",
        "apiKey",
        "secret",
        "password",
        "authorization",
        "raw",
        "payload",
        "toolPayload",
        "arguments",
        "stack",
        "traceback",
    }
    out: dict[str, Any] = {}
    for key, value in list(details.items())[:24]:
        if key in skip or key.lower() in skip:
            continue
        if isinstance(value, str):
            out[key] = scrub_sensitive(value[:400])
        elif isinstance(value, (int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, (list, tuple)):
            out[key] = list(value)[:20]
        elif isinstance(value, dict):
            # nested dicts are summarized, not dumped raw
            out[key] = {str(k): "[omitted]" for k in list(value.keys())[:12]}
        else:
            out[key] = scrub_sensitive(str(value)[:200])
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
        # M3.0F: stable code + messageKey for localized UI mapping (never parse prose).
        # M41 Wave 1: Phase 4.1 envelope fields (keep legacy keys for existing clients).
        explicit_key = self.details.get("messageKey") if isinstance(self.details, dict) else None
        # Defense-in-depth: details values are scrubbed at emission (secrets + absolute
        # paths), even though raise sites are expected to pre-scrub. Keys are preserved
        # so existing clients keep their structured fields.
        details = {str(k): _scrub_detail_value(v) for k, v in self.details.items()} if isinstance(self.details, dict) else {}
        partial = bool(details.get("partialWorkCreated") or details.get("partial_work_created") or False)
        return {
            "code": self.code,
            "error_code": self.code,
            "category": category_for_code(self.code),
            "message": self.message,
            "messageKey": explicit_key or f"errors.code.{self.code}",
            "details": details,
            "recoverable": self.recoverable,
            "retryable": self.recoverable,
            "project_id": details.get("projectId") or details.get("project_id"),
            "provider": details.get("provider"),
            "model": details.get("model"),
            "technical_evidence": _safe_evidence(details),
            "partial_work_created": partial,
            "recommendedAction": self.recommended_action,
            "recommended_action": self.recommended_action,
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
# Runtime / outage classification (highest-level failure wins in the UI)
STUDIO_API_OFFLINE = "STUDIO_API_OFFLINE"
STUDIO_API_CONNECTION_RESET = "STUDIO_API_CONNECTION_RESET"
API_PROXY_UNAVAILABLE = "API_PROXY_UNAVAILABLE"
OLLAMA_OFFLINE = "OLLAMA_OFFLINE"
OLLAMA_MODEL_NOT_FOUND = "OLLAMA_MODEL_NOT_FOUND"
OLLAMA_MODEL_LOADING = "OLLAMA_MODEL_LOADING"
OLLAMA_EMPTY_RESPONSE = "OLLAMA_EMPTY_RESPONSE"
OLLAMA_STREAM_INTERRUPTED = "OLLAMA_STREAM_INTERRUPTED"
CO_DIRECTOR_REQUEST_CANCELLED = "CO_DIRECTOR_REQUEST_CANCELLED"
CO_DIRECTOR_PROVIDER_TIMEOUT = "CO_DIRECTOR_PROVIDER_TIMEOUT"
CONTEXT_TOO_LARGE = "CONTEXT_TOO_LARGE"
UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
PROJECT_REQUIRED = "PROJECT_REQUIRED"
VALIDATION_ERROR = "VALIDATION_ERROR"
CONFLICT = "CONFLICT"  # Wave A persistent memory: optimistic-concurrency / deprecated-replace guard

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
PROJECT_LOCKED = "PROJECT_LOCKED"
STRUCTURED_OUTPUT_INVALID = "STRUCTURED_OUTPUT_INVALID"
RECEIPT_NOT_FOUND = "RECEIPT_NOT_FOUND"

# --------------------------------------------------------------------------
# M2.3: Production Bible domain layer.
# --------------------------------------------------------------------------
ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
LOCKED_ENTITY_REQUIRES_APPROVAL = "LOCKED_ENTITY_REQUIRES_APPROVAL"
CONCURRENT_MODIFICATION = "CONCURRENT_MODIFICATION"
CANON_CONFLICT = "CANON_CONFLICT"
LIFECYCLE_INVALID = "LIFECYCLE_INVALID"
# c2-routing: handler-level read-before-write gates for Bible mutations.
SUPERSEDED_NOT_CURRENT = "SUPERSEDED_NOT_CURRENT"
REFERENCE_LINK_EXISTS = "REFERENCE_LINK_EXISTS"
REFERENCE_TARGET_MISSING = "REFERENCE_TARGET_MISSING"
REFERENCE_ASSET_MISSING = "REFERENCE_ASSET_MISSING"
DUPLICATE_CONTINUITY_ENTITY = "DUPLICATE_CONTINUITY_ENTITY"

# --------------------------------------------------------------------------
# M2.2: bounded tool registry + approved project actions.
# --------------------------------------------------------------------------
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
TOOL_DISABLED = "TOOL_DISABLED"
TOOL_KIND_MISMATCH = "TOOL_KIND_MISMATCH"
TOOL_ARGUMENTS_INVALID = "TOOL_ARGUMENTS_INVALID"
TOOL_ARGUMENT_INVALID = "TOOL_ARGUMENT_INVALID"  # Wave 3 alias of TOOL_ARGUMENTS_INVALID
TOOL_TARGET_NOT_FOUND = "TOOL_TARGET_NOT_FOUND"
TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
TOOL_RESULT_TOO_LARGE = "TOOL_RESULT_TOO_LARGE"
TOOL_LOOP_LIMIT_REACHED = "TOOL_LOOP_LIMIT_REACHED"
TOOL_SCHEMA_VERSION_MISMATCH = "TOOL_SCHEMA_VERSION_MISMATCH"
TOOL_VERSION_UNSUPPORTED = "TOOL_VERSION_UNSUPPORTED"
TOOL_PAYLOAD_INVALID = "TOOL_PAYLOAD_INVALID"
PROJECT_ACCESS_DENIED = "PROJECT_ACCESS_DENIED"
RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
RETRIEVAL_PARTIAL = "RETRIEVAL_PARTIAL"
CAPABILITY_NOT_CONFIGURED = "CAPABILITY_NOT_CONFIGURED"
CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"

# --------------------------------------------------------------------------
# M2.4: production intelligence, prompt library, specialist orchestration.
# --------------------------------------------------------------------------
INTENT_CLASSIFICATION_FAILED = "INTENT_CLASSIFICATION_FAILED"
PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"
PROMPT_INVALID = "PROMPT_INVALID"
SPECIALIST_NOT_FOUND = "SPECIALIST_NOT_FOUND"
SPECIALIST_TIMEOUT = "SPECIALIST_TIMEOUT"
SPECIALIST_OUTPUT_INVALID = "SPECIALIST_OUTPUT_INVALID"
CONTEXT_INCOMPLETE = "CONTEXT_INCOMPLETE"
SYNTHESIS_FAILED = "SYNTHESIS_FAILED"
PLAN_INVALID = "PLAN_INVALID"
PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
PLAN_ACCESS_DENIED = "PLAN_ACCESS_DENIED"
PLAN_VERSION_CONFLICT = "PLAN_VERSION_CONFLICT"
PLAN_STATE_TRANSITION_INVALID = "PLAN_STATE_TRANSITION_INVALID"
PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"
PLAN_DEPENDENCY_CYCLE = "PLAN_DEPENDENCY_CYCLE"
PLAN_DEPENDENCY_MISSING = "PLAN_DEPENDENCY_MISSING"
PLAN_STEP_NOT_FOUND = "PLAN_STEP_NOT_FOUND"
PLAN_BLOCKER_NOT_FOUND = "PLAN_BLOCKER_NOT_FOUND"
PLAN_APPROVAL_REQUIRED = "PLAN_APPROVAL_REQUIRED"
PLAN_ALREADY_TERMINAL = "PLAN_ALREADY_TERMINAL"
PLAN_COMMAND_DUPLICATE = "PLAN_COMMAND_DUPLICATE"
PLAN_COMMAND_FAILED = "PLAN_COMMAND_FAILED"
PLAN_CAPABILITY_UNAVAILABLE = "PLAN_CAPABILITY_UNAVAILABLE"
PLAN_EXECUTION_DEFERRED = "PLAN_EXECUTION_DEFERRED"


_STATUS_BY_CODE = {
    CONNECTION_REFUSED: 503,
    PROVIDER_UNAVAILABLE: 503,
    BACKEND_UNAVAILABLE: 503,
    STUDIO_API_OFFLINE: 503,
    STUDIO_API_CONNECTION_RESET: 503,
    API_PROXY_UNAVAILABLE: 503,
    OLLAMA_OFFLINE: 503,
    OLLAMA_MODEL_LOADING: 503,
    PROVIDER_NOT_CONFIGURED: 503,
    REQUEST_TIMEOUT: 504,
    CO_DIRECTOR_PROVIDER_TIMEOUT: 504,
    MODEL_NOT_FOUND: 400,
    OLLAMA_MODEL_NOT_FOUND: 400,
    MODEL_NOT_SELECTED: 400,
    NO_MODELS_INSTALLED: 400,
    CONTEXT_TOO_LARGE: 400,
    VALIDATION_ERROR: 400,
    CONFLICT: 409,
    PROJECT_NOT_FOUND: 404,
    PROJECT_REQUIRED: 400,
    REQUEST_CANCELLED: 499,
    CO_DIRECTOR_REQUEST_CANCELLED: 499,
    STREAM_INTERRUPTED: 502,
    OLLAMA_STREAM_INTERRUPTED: 502,
    OLLAMA_EMPTY_RESPONSE: 502,
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
    PROJECT_LOCKED: 403,
    STRUCTURED_OUTPUT_INVALID: 502,
    RECEIPT_NOT_FOUND: 404,
    ENTITY_NOT_FOUND: 404,
    LOCKED_ENTITY_REQUIRES_APPROVAL: 409,
    CONCURRENT_MODIFICATION: 409,
    CANON_CONFLICT: 409,
    LIFECYCLE_INVALID: 400,
    SUPERSEDED_NOT_CURRENT: 409,
    REFERENCE_LINK_EXISTS: 409,
    REFERENCE_TARGET_MISSING: 404,
    REFERENCE_ASSET_MISSING: 404,
    DUPLICATE_CONTINUITY_ENTITY: 409,
    TOOL_NOT_FOUND: 404,
    TOOL_DISABLED: 403,
    TOOL_KIND_MISMATCH: 400,
    TOOL_ARGUMENTS_INVALID: 400,
    TOOL_ARGUMENT_INVALID: 400,
    TOOL_TARGET_NOT_FOUND: 404,
    TOOL_EXECUTION_FAILED: 502,
    TOOL_RESULT_TOO_LARGE: 502,
    TOOL_LOOP_LIMIT_REACHED: 409,
    TOOL_SCHEMA_VERSION_MISMATCH: 409,
    TOOL_VERSION_UNSUPPORTED: 400,
    TOOL_PAYLOAD_INVALID: 502,
    PROJECT_ACCESS_DENIED: 403,
    RETRIEVAL_FAILED: 502,
    RETRIEVAL_PARTIAL: 200,
    CAPABILITY_NOT_CONFIGURED: 409,
    CAPABILITY_UNAVAILABLE: 503,
    CAPABILITY_UNKNOWN: 400,
    INTENT_CLASSIFICATION_FAILED: 502,
    PROMPT_NOT_FOUND: 404,
    PROMPT_INVALID: 400,
    SPECIALIST_NOT_FOUND: 404,
    SPECIALIST_TIMEOUT: 504,
    SPECIALIST_OUTPUT_INVALID: 502,
    CONTEXT_INCOMPLETE: 400,
    SYNTHESIS_FAILED: 502,
    PLAN_INVALID: 400,
    PLAN_NOT_FOUND: 404,
    PLAN_ACCESS_DENIED: 403,
    PLAN_VERSION_CONFLICT: 409,
    PLAN_STATE_TRANSITION_INVALID: 409,
    PLAN_VALIDATION_FAILED: 400,
    PLAN_DEPENDENCY_CYCLE: 400,
    PLAN_DEPENDENCY_MISSING: 400,
    PLAN_STEP_NOT_FOUND: 404,
    PLAN_BLOCKER_NOT_FOUND: 404,
    PLAN_APPROVAL_REQUIRED: 409,
    PLAN_ALREADY_TERMINAL: 409,
    PLAN_COMMAND_DUPLICATE: 200,
    PLAN_COMMAND_FAILED: 502,
    PLAN_CAPABILITY_UNAVAILABLE: 409,
    PLAN_EXECUTION_DEFERRED: 409,
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
