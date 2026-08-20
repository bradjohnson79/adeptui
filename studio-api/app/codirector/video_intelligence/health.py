"""Worker health probe. Filename-only is not Setup ready."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .paths import (
    INTERNVIDEO3_MARKERS,
    VIDEOCHAT3_MARKERS,
    internvideo3_dir,
    model_present,
    poll_safe_integrity,
    videochat3_dir,
    worker_python,
)

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SEC = 60.0


def _config_ok(root: Path) -> tuple[bool, str]:
    config = root / "config.json"
    if not config.is_file():
        return False, "CONFIG_MISSING"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except Exception:
        return False, "CONFIG_INVALID"
    if not isinstance(data, dict) or not (data.get("architectures") or data.get("model_type")):
        return False, "CONFIG_INCOMPLETE"
    return True, "ok"


def probe_component(component_id: str, *, spawn_worker: bool | None = None) -> dict[str, Any]:
    dest = videochat3_dir() if component_id == "videochat3_4b" else internvideo3_dir()
    markers = VIDEOCHAT3_MARKERS if component_id == "videochat3_4b" else INTERNVIDEO3_MARKERS
    files_ok = model_present(dest, markers)
    cfg_ok, cfg_reason = _config_ok(dest) if dest.is_dir() else (False, "NOT_INSTALLED")
    integrity = (
        poll_safe_integrity(dest)
        if component_id == "videochat3_4b" and dest.is_dir()
        else {"ok": files_ok and cfg_ok, "reason": None if files_ok and cfg_ok else cfg_reason}
    )
    result: dict[str, Any] = {
        "componentId": component_id,
        "filesPresent": files_ok,
        "configOk": cfg_ok,
        "configReason": cfg_reason,
        "integrity": integrity,
        "workerHealth": None,
        "ok": bool(files_ok and cfg_ok and integrity.get("ok")),
    }
    if not result["ok"]:
        result["reason"] = "NOT_INSTALLED" if not files_ok else cfg_reason
        return result
    cached = _CACHE.get(component_id)
    now = time.time()
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        result["workerHealth"] = cached[1]
        if cached[1].get("ok") is False and cached[1].get("error") == "CPU_ONLY_TORCH":
            result["ok"] = False
            result["reason"] = "CPU_ONLY_TORCH"
        return result
    should_spawn = spawn_worker
    if should_spawn is None:
        should_spawn = not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get(
            "ADEPT_TEMPORAL_PERCEPTION_MODE", ""
        ).strip().lower() not in ("stub", "1", "true", "yes")
    if not should_spawn:
        result["workerHealth"] = {"skipped": True, "cached": False}
        return result
    worker = Path(__file__).with_name("worker.py")
    try:
        proc = subprocess.run(
            [str(worker_python()), str(worker), "--health"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        payload = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)[:240]}
    _CACHE[component_id] = (now, payload)
    result["workerHealth"] = payload
    if payload.get("error") == "CPU_ONLY_TORCH":
        result["ok"] = False
        result["reason"] = "CPU_ONLY_TORCH"
    return result
