"""User-editable Co-Director runtime configuration (endpoint / model / timeout).

Persisted as a small JSON file under the data dir, separate from `setup_state.json`
because Co-Director config is user-tunable at any time (not tied to install state)
and never contains secrets (Ollama has no auth). Falls back to `Settings` env
defaults when no override has been saved yet.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..config import settings

_LOCK = threading.RLock()


def config_path() -> Path:
    return settings.data_dir / "codirector_config.json"


def _defaults() -> dict[str, Any]:
    return {
        "endpoint": settings.ollama_url,
        "selectedModel": settings.ollama_model or None,
        "timeoutSec": settings.ollama_timeout_sec,
    }


def load_config() -> dict[str, Any]:
    with _LOCK:
        path = config_path()
        if not path.exists():
            return _defaults()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return _defaults()
        if not isinstance(raw, dict):
            return _defaults()
        merged = _defaults()
        merged.update({k: v for k, v in raw.items() if k in merged})
        return merged


def save_config(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge `patch` onto the persisted config (or defaults) and write it atomically."""
    with _LOCK:
        current = load_config()
        for key in ("endpoint", "selectedModel", "timeoutSec"):
            if key in patch and patch[key] is not None:
                current[key] = patch[key]
            elif key in patch and patch[key] is None and key == "selectedModel":
                current[key] = None
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(current, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
        return current


def reset_config() -> dict[str, Any]:
    with _LOCK:
        path = config_path()
        if path.exists():
            path.unlink()
        return _defaults()
