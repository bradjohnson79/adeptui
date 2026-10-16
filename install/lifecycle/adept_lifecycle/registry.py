"""Installation registry. Uninstall reads this inventory and does not guess."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def read_registry(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def empty_registry(profile_os: str, arch: str, location: str) -> dict[str, Any]:
    return {
        "schema": 1,
        "installedVersion": None,
        "installedRevision": None,
        "channel": None,
        "os": profile_os,
        "arch": arch,
        "location": location,
        "method": "adept-lifecycle",
        "managedFiles": [],
        "managedRuntime": [],
        "desktopShortcut": None,
        "cli": None,
        "modelInventory": None,
        "userData": None,
        "updateHistory": [],
        "updateFailures": {},
        "health": "empty",
        "recovery": {"lastGoodVersion": None, "lastGoodRevision": None},
    }
