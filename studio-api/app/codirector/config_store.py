"""User-editable Co-Director runtime configuration (endpoint / model / timeout).

Persisted as a small JSON file under the data dir, separate from `setup_state.json`
because Co-Director config is user-tunable at any time (not tied to install state)
and never contains secrets (Ollama has no auth). Falls back to `Settings` env
defaults when no override has been saved yet.

M2.10b extends defaults with primaryModel / fallbackModel and
allowAutomaticModelDownload=False while keeping selectedModel backward compatible.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..config import settings

_LOCK = threading.RLock()

_CONFIG_KEYS = (
    "endpoint",
    "selectedModel",
    "primaryModel",
    "fallbackModel",
    "allowAutomaticModelDownload",
    "timeoutSec",
)


def config_path() -> Path:
    return settings.data_dir / "codirector_config.json"


def _defaults() -> dict[str, Any]:
    primary = settings.ollama_model or None
    return {
        "endpoint": settings.ollama_url,
        "selectedModel": primary,
        "primaryModel": primary,
        "fallbackModel": "gemma4:12b",
        "allowAutomaticModelDownload": False,
        "timeoutSec": settings.ollama_timeout_sec,
    }


def _normalize(cfg: dict[str, Any]) -> dict[str, Any]:
    """Keep selectedModel and primaryModel aliased; download flag always explicit."""
    primary = cfg.get("primaryModel")
    selected = cfg.get("selectedModel")
    if primary is None and selected is not None:
        cfg["primaryModel"] = selected
    elif selected is None and primary is not None:
        cfg["selectedModel"] = primary
    elif primary is not None and selected is not None and primary != selected:
        # Prefer explicit primaryModel as source of truth for M2.10b.
        cfg["selectedModel"] = primary
    if "fallbackModel" not in cfg or cfg.get("fallbackModel") is None:
        cfg["fallbackModel"] = "gemma4:12b"
    cfg["allowAutomaticModelDownload"] = bool(cfg.get("allowAutomaticModelDownload", False))
    return cfg


def load_config() -> dict[str, Any]:
    with _LOCK:
        path = config_path()
        if not path.exists():
            return _normalize(_defaults())
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return _normalize(_defaults())
        if not isinstance(raw, dict):
            return _normalize(_defaults())
        merged = _defaults()
        merged.update({k: v for k, v in raw.items() if k in merged})
        return _normalize(merged)


def save_config(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge `patch` onto the persisted config (or defaults) and write it atomically."""
    with _LOCK:
        current = load_config()
        for key in _CONFIG_KEYS:
            if key not in patch:
                continue
            value = patch[key]
            if value is None and key in {"selectedModel", "primaryModel", "fallbackModel"}:
                current[key] = None
            elif value is not None:
                current[key] = value
        # Alias sync: primaryModel wins when provided; else selectedModel updates primary.
        if "primaryModel" in patch and patch["primaryModel"] is not None:
            current["selectedModel"] = patch["primaryModel"]
            current["primaryModel"] = patch["primaryModel"]
        elif "selectedModel" in patch and patch["selectedModel"] is not None:
            current["primaryModel"] = patch["selectedModel"]
            current["selectedModel"] = patch["selectedModel"]
        current = _normalize(current)
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
        return _normalize(_defaults())
