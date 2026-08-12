"""Identity Preservation Registry — Wave 5 projects continuity domain (compat)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOT = _REPO_ROOT / "config" / "image-identities"


@lru_cache(maxsize=4)
def _load(name: str) -> dict[str, Any]:
    path = _ROOT / name
    if not path.is_file():
        return {"schemaVersion": "1.0.0", "entries": [], "missing": True}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"entries": []}


def list_approved_characters() -> list[dict[str, Any]]:
    return list((_load("approved-characters.json").get("entries") or []))


def list_approved_environments() -> list[dict[str, Any]]:
    return list((_load("approved-environments.json").get("entries") or []))


def list_approved_wardrobes() -> list[dict[str, Any]]:
    return list((_load("approved-wardrobes.json").get("entries") or []))


def identity_registry_snapshot() -> dict[str, Any]:
    """Compatibility projection. Canonical authority is continuity VisualIdentity (W5)."""
    continuity_pkg = _REPO_ROOT / "studio-api" / "app" / "continuity"
    enforced = continuity_pkg.is_dir() and (continuity_pkg / "service.py").is_file()
    return {
        "phase": "M42-W5",
        "enforcementWave": "M42-W5",
        "characters": list_approved_characters(),
        "environments": list_approved_environments(),
        "wardrobes": list_approved_wardrobes(),
        "enforced": enforced,
        "authority": "studio-api/app/continuity" if enforced else "config/image-identities (draft)",
        "note": "Config JSON entries remain empty — no invented references. Use Identity Registry API.",
    }
