from __future__ import annotations

import json
from typing import Any, Literal

LockMode = Literal["locked", "unlocked", "inherit_project", "inherit_previous"]

CONTINUITY_KEYS = (
    "identity",
    "wardrobe",
    "environment",
    "lighting",
    "camera",
    "props",
    "audio_bed",
    "motion_style",
)


def default_continuity() -> dict[str, LockMode]:
    return {k: "inherit_project" for k in CONTINUITY_KEYS}


def parse_continuity(raw: str | None) -> dict[str, LockMode]:
    base = default_continuity()
    if not raw or not str(raw).strip():
        return base
    try:
        data = json.loads(raw)
    except Exception:
        return base
    if not isinstance(data, dict):
        return base
    allowed = {"locked", "unlocked", "inherit_project", "inherit_previous"}
    for key in CONTINUITY_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val in allowed:
            base[key] = val  # type: ignore[assignment]
    return base


def dumps_continuity(data: dict[str, Any] | None) -> str:
    merged = parse_continuity(json.dumps(data) if data else None)
    return json.dumps(merged)


def continuity_summary(data: dict[str, LockMode]) -> dict[str, Any]:
    locked = sum(1 for v in data.values() if v == "locked")
    return {
        "locked": locked,
        "total": len(CONTINUITY_KEYS),
        "keys": data,
    }
