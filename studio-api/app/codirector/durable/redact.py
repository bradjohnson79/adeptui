"""Strip secret-shaped values before they reach a trace, log, or journal payload."""

from __future__ import annotations

from typing import Any

_SECRET_KEYS = ("secret", "token", "password", "authorization", "api_key", "apikey", "credential")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if any(part in str(key).lower() for part in _SECRET_KEYS):
                cleaned[str(key)] = "[redacted]"
            else:
                cleaned[str(key)] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
