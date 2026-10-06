"""Adept-owned :8188 identity. Re-verify before reuse or stop. Never adopt Desktop."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..process import is_comfy_command, is_route_a_command

OWNED_NAME = "owned.json"
DEATH_NAME = "last_death.json"


def owned_path(config_dir: Path) -> Path:
    return Path(config_dir) / OWNED_NAME


def death_path(config_dir: Path) -> Path:
    return Path(config_dir) / DEATH_NAME


def command_is_adept_headless(cmd: str, yaml: Path) -> bool:
    if not is_comfy_command(cmd) or is_route_a_command(cmd):
        return False
    norm = (cmd or "").lower().replace("/", "\\")
    yaml_norm = str(yaml).lower().replace("/", "\\")
    if yaml_norm not in norm:
        return False
    if "8188" not in norm:
        return False
    return "extra-model-paths-config" in norm


def read_record(config_dir: Path) -> dict[str, Any] | None:
    path = owned_path(config_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_record(config_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    dest = owned_path(config_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["owned"] = True
    body["writtenAt"] = datetime.now(timezone.utc).isoformat()
    dest.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return body


def clear_record(config_dir: Path) -> None:
    path = owned_path(config_dir)
    if path.exists():
        path.unlink()


def write_death(config_dir: Path, payload: dict[str, Any], extra_log: Path | None = None) -> None:
    dest = death_path(config_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["capturedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(body, indent=2)
    dest.write_text(text, encoding="utf-8")
    if extra_log is not None:
        extra_log.parent.mkdir(parents=True, exist_ok=True)
        extra_log.write_text(text, encoding="utf-8")
