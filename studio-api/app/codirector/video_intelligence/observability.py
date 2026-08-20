"""Diagnostics-only temporal continuity events. Never flood creator UI."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("adept.temporal_continuity")


def emit(kind: str, **fields: Any) -> dict[str, Any]:
    payload = {"kind": kind, **fields}
    logger.info("temporal_continuity %s", payload)
    return payload
