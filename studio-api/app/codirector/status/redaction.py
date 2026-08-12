from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_REDACT_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "endpoint",
    "baseurl",
    "password",
    "secret",
    "secretkey",
    "sourceurl",
    "source_url",
    "token",
}


def redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): redact_pair(str(key), inner) for key, inner in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if "bearer " in lowered or "api_key" in lowered or "token" in lowered:
            return "[redacted]"
    return value


def redact_pair(key: str, value: Any) -> Any:
    normalized = key.replace("-", "").replace("_", "").lower()
    if normalized in _REDACT_KEYS:
        return "[redacted]"
    return redact_value(value)


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return redact_value(payload)
