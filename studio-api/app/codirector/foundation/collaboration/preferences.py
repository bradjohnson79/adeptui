"""Project-scoped in-memory creator preferences."""

from __future__ import annotations

from collections import defaultdict

from app.codirector.foundation.contracts import CreatorPreference

_PREFERENCES: dict[str, dict[str, CreatorPreference]] = defaultdict(dict)


def _preference_id(project_id: str, key: str) -> str:
    safe_key = "-".join(key.strip().lower().split()) or "preference"
    return f"pref:{project_id}:{safe_key}"


def get_preference(project_id: str, key: str) -> CreatorPreference | None:
    """Return one project preference if present."""

    return _PREFERENCES.get(project_id, {}).get(key)


def list_preferences(project_id: str) -> list[CreatorPreference]:
    """Return project preferences in stable key order."""

    prefs = _PREFERENCES.get(project_id, {})
    return [prefs[key] for key in sorted(prefs)]


def set_preference(
    project_id: str,
    key: str,
    value: str,
    *,
    visible: bool = True,
    editable: bool = True,
    forgettable: bool = True,
    source: str = "explicit",
) -> CreatorPreference:
    """Create or update a project preference."""

    preference = CreatorPreference(
        preferenceId=_preference_id(project_id, key),
        projectId=project_id,
        key=key,
        value=value,
        visible=visible,
        editable=editable,
        forgettable=forgettable,
        source="inferred" if source == "inferred" else "explicit",
    )
    _PREFERENCES[project_id][key] = preference
    return preference


def forget_preference(project_id: str, key: str) -> bool:
    """Forget a preference when it is allowed to be removed."""

    preference = get_preference(project_id, key)
    if preference is None or not preference.forgettable:
        return False
    del _PREFERENCES[project_id][key]
    if not _PREFERENCES[project_id]:
        _PREFERENCES.pop(project_id, None)
    return True


__all__ = ["forget_preference", "get_preference", "list_preferences", "set_preference"]
