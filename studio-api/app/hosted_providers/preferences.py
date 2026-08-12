"""User preferences for Preferred Hosted Provider / Automatic Recommendation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..config import settings
from .registry import PRIORITY_ORDER, ProviderId

PreferredMode = Literal["kie", "wavespeed", "fal", "automatic"]

_PREFS_PATH = settings.data_dir / "hosted_providers" / "preferences.json"


def _default() -> dict[str, Any]:
    return {
        "preferredProvider": "automatic",
        "budgetPreference": "balanced",  # low_cost | balanced | quality
        "updatedAt": None,
        "mock": False,
    }


def load_preferences() -> dict[str, Any]:
    if not _PREFS_PATH.is_file():
        return _default()
    try:
        data = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default()
        pref = str(data.get("preferredProvider") or "automatic").lower()
        if pref not in ("kie", "wavespeed", "fal", "automatic"):
            pref = "automatic"
        out = _default()
        out.update(
            {
                "preferredProvider": pref,
                "budgetPreference": data.get("budgetPreference") or "balanced",
                "updatedAt": data.get("updatedAt"),
            }
        )
        return out
    except Exception:
        return _default()


def save_preferences(
    *,
    preferred_provider: PreferredMode | None = None,
    budget_preference: str | None = None,
) -> dict[str, Any]:
    current = load_preferences()
    if preferred_provider is not None:
        current["preferredProvider"] = preferred_provider
    if budget_preference is not None:
        current["budgetPreference"] = budget_preference
    current["updatedAt"] = datetime.now(timezone.utc).isoformat()
    current["mock"] = False
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    try:
        _PREFS_PATH.chmod(0o600)
    except Exception:
        pass
    return current


def is_automatic(prefs: dict[str, Any] | None = None) -> bool:
    p = prefs or load_preferences()
    return str(p.get("preferredProvider") or "automatic") == "automatic"


def pinned_provider(prefs: dict[str, Any] | None = None) -> ProviderId | None:
    p = prefs or load_preferences()
    pref = str(p.get("preferredProvider") or "automatic")
    if pref in PRIORITY_ORDER:
        return pref  # type: ignore[return-value]
    return None
