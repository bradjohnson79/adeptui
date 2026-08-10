"""Runtime Manager preferences persistence.

Stored as JSON in data/runtime_manager/preferences.json.
"""
import json
import os
from pathlib import Path

from .schemas import RuntimeManagerPreferences


DEFAULT_PREFERENCES = RuntimeManagerPreferences(
    comfyuiBackgroundManagerEnabled=False,
    localhostBackgroundManagerEnabled=False,
    startWithWindows=False,
    remoteAccessEnabled=False,
)


def _get_data_dir() -> Path:
    studio_data = os.environ.get("STUDIO_DATA_DIR", "")
    if studio_data:
        base = Path(studio_data)
    else:
        repo_root = Path(__file__).resolve().parents[3]
        base = repo_root / "data"
    return base


def _prefs_path() -> Path:
    d = _get_data_dir() / "runtime_manager"
    d.mkdir(parents=True, exist_ok=True)
    return d / "preferences.json"


def load_preferences() -> RuntimeManagerPreferences:
    path = _prefs_path()
    if not path.exists():
        return DEFAULT_PREFERENCES.model_copy(deep=True)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        merged = DEFAULT_PREFERENCES.model_copy(deep=True)
        for field in merged.model_fields_set:
            if field in raw:
                setattr(merged, field, raw[field])
        return merged
    except (json.JSONDecodeError, KeyError, TypeError):
        return DEFAULT_PREFERENCES.model_copy(deep=True)


def save_preferences(prefs: RuntimeManagerPreferences) -> RuntimeManagerPreferences:
    path = _prefs_path()
    data = prefs.model_dump()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
    return prefs
