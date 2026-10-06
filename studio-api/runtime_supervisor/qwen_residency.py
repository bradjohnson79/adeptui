"""Request Qwen readiness without restarting Comfy.

Unload via /free only when the queue is idle. Never treat a live runtime
with unloaded Qwen as a dead runtime.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .gpu_admission import assess_gpu_admission
from .health import comfy_healthy, comfy_queue_running
from .headless_comfy.service import status as headless_status

QWEN_NODE = "TextEncodeQwenImageEditPlus"


def _comfy_json(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    url = f"http://127.0.0.1:8188{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def qwen_nodes_present() -> bool | None:
    info = _comfy_json("/object_info")
    if info is None:
        return None
    return QWEN_NODE in info


def request_qwen() -> dict[str, Any]:
    headless = headless_status()
    # A healthy external Comfy (e.g. Comfy Desktop) is reused for Qwen, not a
    # conflict. Only a genuinely unreachable runtime is offline.
    if not comfy_healthy():
        return {
            "ok": False,
            "state": "offline",
            "worker": "idle",
            "comfyPid": headless.get("pid"),
            "message": "The local image runtime is offline.",
        }
    pid_before = headless.get("pid")
    if comfy_queue_running() > 0:
        return {
            "ok": True,
            "state": "busy",
            "worker": "busy",
            "samePid": True,
            "comfyPid": pid_before,
            "message": "The local image runtime is busy.",
        }
    admission = assess_gpu_admission("comfyui")
    if not admission.get("allowed"):
        return {
            "ok": False,
            "state": "degraded",
            "worker": "idle",
            "samePid": True,
            "comfyPid": pid_before,
            "message": str(admission.get("reason") or "GPU is not available for Qwen."),
        }
    present = qwen_nodes_present()
    if present is True:
        return {
            "ok": True,
            "state": "ready",
            "worker": "qwen_ready",
            "samePid": True,
            "comfyPid": pid_before,
            "message": "Qwen Image Edit is ready.",
        }
    if comfy_queue_running() == 0:
        _comfy_json("/free", method="POST", payload={"unload_models": True, "free_memory": True})
    after = headless_status()
    same = after.get("pid") == pid_before
    return {
        "ok": True,
        "state": "starting",
        "worker": "loading_qwen",
        "samePid": same,
        "comfyPid": after.get("pid") or pid_before,
        "message": "Preparing Qwen Image Edit…",
    }
