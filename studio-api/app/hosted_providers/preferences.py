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


def _lease_path() -> Path:
    return settings.data_dir / "e2e" / "hosted_preference_lease.json"


def _read_lease() -> dict[str, Any] | None:
    path = _lease_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _write_lease(data: dict[str, Any]) -> None:
    path = _lease_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def begin_preference_lease(
    *,
    preferred_provider: PreferredMode | None = None,
    budget_preference: str | None = None,
) -> dict[str, Any]:
    """Apply a test preference and remember the owner's previous values.

    A second begin (Playwright retry) keeps the original snapshot so cleanup
    restores the owner, not the previous test value.
    """
    current = load_preferences()
    existing = _read_lease()
    original = (existing or {}).get("original")
    if not isinstance(original, dict):
        original = {
            "preferredProvider": current.get("preferredProvider"),
            "budgetPreference": current.get("budgetPreference"),
        }
    applied_preferred = preferred_provider or current.get("preferredProvider")
    applied_budget = budget_preference or current.get("budgetPreference")
    _write_lease(
        {
            "original": original,
            "applied": {
                "preferredProvider": applied_preferred,
                "budgetPreference": applied_budget,
            },
        }
    )
    return save_preferences(
        preferred_provider=applied_preferred,  # type: ignore[arg-type]
        budget_preference=applied_budget,
    )


def restore_preference_lease(
    *,
    fallback_preferred: str | None = None,
    fallback_budget: str | None = None,
) -> dict[str, Any]:
    """Restore the owner preference after a test.

    If the owner changed the preference away from the leased test values,
    keep the owner's newer choice and drop the lease.
    """
    path = _lease_path()
    lease = _read_lease()
    current = load_preferences()
    if not lease:
        if fallback_preferred is None and fallback_budget is None:
            return {**current, "restored": False}
        saved = save_preferences(
            preferred_provider=fallback_preferred,  # type: ignore[arg-type]
            budget_preference=fallback_budget,
        )
        return {**saved, "restored": True, "via": "fallback"}
    applied = lease.get("applied") if isinstance(lease.get("applied"), dict) else {}
    original = lease.get("original") if isinstance(lease.get("original"), dict) else {}
    matches_test = (
        current.get("preferredProvider") == applied.get("preferredProvider")
        and current.get("budgetPreference") == applied.get("budgetPreference")
    )
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    if not matches_test:
        return {**current, "restored": False, "reason": "owner-changed"}
    preferred = original.get("preferredProvider") or current.get("preferredProvider")
    budget = original.get("budgetPreference") or current.get("budgetPreference")
    saved = save_preferences(
        preferred_provider=preferred,  # type: ignore[arg-type]
        budget_preference=str(budget) if budget else None,
    )
    return {**saved, "restored": True}


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
