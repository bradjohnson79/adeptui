"""GPU residency admission — two Comfy stacks must not independently assume the RTX."""

from __future__ import annotations

import subprocess
from typing import Any

from .constants import COMFY_PORT, H3_COMFY_PORT
from .health import comfy_healthy, comfy_queue_running
from .ports import port_owner_pid
from .process import process_command_line


def nvidia_snapshot() -> dict[str, Any]:
    """Best-effort nvidia-smi snapshot. Never kills processes."""
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "reason": "nvidia-smi unavailable"}
    if completed.returncode != 0 or not (completed.stdout or "").strip():
        return {"ok": False, "reason": "nvidia-smi returned no GPU"}
    line = completed.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 4:
        return {"ok": False, "reason": "nvidia-smi parse failed"}
    try:
        used = int(float(parts[1]))
        total = int(float(parts[2]))
        util = int(float(parts[3]))
    except ValueError:
        return {"ok": False, "reason": "nvidia-smi numeric parse failed"}
    return {
        "ok": True,
        "name": parts[0],
        "memoryUsedMiB": used,
        "memoryTotalMiB": total,
        "utilizationPct": util,
    }


def _route_a_is_stub() -> bool:
    """stub8192 answers HTTP but holds no CUDA devices — not a GPU resident."""
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{H3_COMFY_PORT}/system_stats", timeout=3
        ) as resp:
            if int(resp.status) != 200:
                return False
            data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    system = data.get("system") if isinstance(data.get("system"), dict) else {}
    version = str(system.get("comfyui_version") or "").strip().lower()
    if version == "stub" or version.startswith("stub"):
        return True
    devices = data.get("devices")
    return not (isinstance(devices, list) and len(devices) > 0)


def _route_a_healthy() -> bool:
    if _route_a_is_stub():
        return False
    return comfy_healthy(port=H3_COMFY_PORT)


def _route_a_queue_running() -> int:
    return comfy_queue_running(port=H3_COMFY_PORT)


def classify_comfy_residents() -> dict[str, Any]:
    desktop = comfy_healthy()
    route_a = _route_a_healthy()
    desktop_pid = port_owner_pid(COMFY_PORT) if desktop else None
    route_a_pid = port_owner_pid(H3_COMFY_PORT) if route_a else None
    return {
        "comfyui": {
            "healthy": desktop,
            "port": COMFY_PORT,
            "pid": desktop_pid,
            "queueRunning": comfy_queue_running() if desktop else 0,
            "command": process_command_line(desktop_pid) if desktop_pid else "",
        },
        "minimax_h3_route_a": {
            "healthy": route_a,
            "port": H3_COMFY_PORT,
            "pid": route_a_pid,
            "queueRunning": _route_a_queue_running() if route_a else 0,
            "command": process_command_line(route_a_pid) if route_a_pid else "",
        },
        "dualResident": bool(desktop and route_a),
    }


def assess_gpu_admission(requesting: str) -> dict[str, Any]:
    """Decide whether requesting service may start or claim the GPU.

    requesting: comfyui | minimax_h3_route_a
    Reuse of an already-healthy listener is always allowed.
    Spawning a second heavyweight Comfy while the other is busy is refused.
    """
    residents = classify_comfy_residents()
    gpu = nvidia_snapshot()
    desktop = residents["comfyui"]
    route_a = residents["minimax_h3_route_a"]

    if requesting == "minimax_h3_route_a":
        if route_a["healthy"]:
            return {
                "allowed": True,
                "action": "reuse",
                "dualResident": residents["dualResident"],
                "reason": "Route A already healthy — reused",
                "residents": residents,
                "gpu": gpu,
            }
        if desktop["queueRunning"] > 0:
            return {
                "allowed": False,
                "action": "block",
                "dualResident": False,
                "reason": "ComfyUI is using the GPU — wait or finish that job before starting Route A",
                "residents": residents,
                "gpu": gpu,
            }
        if desktop["healthy"]:
            return {
                "allowed": False,
                "action": "handoff_required",
                "dualResident": False,
                "reason": "ComfyUI already holds the GPU. Stop or idle ComfyUI before starting Route A.",
                "residents": residents,
                "gpu": gpu,
            }
        return {
            "allowed": True,
            "action": "start",
            "dualResident": False,
            "reason": "GPU free for Route A",
            "residents": residents,
            "gpu": gpu,
        }

    if requesting == "comfyui":
        if desktop["healthy"]:
            return {
                "allowed": True,
                "action": "reuse",
                "dualResident": residents["dualResident"],
                "reason": "ComfyUI already healthy — reused",
                "residents": residents,
                "gpu": gpu,
            }
        if route_a["queueRunning"] > 0:
            return {
                "allowed": False,
                "action": "block",
                "dualResident": False,
                "reason": "MiniMax Route A is using the GPU — wait or finish that job before starting ComfyUI",
                "residents": residents,
                "gpu": gpu,
            }
        if route_a["healthy"]:
            return {
                "allowed": False,
                "action": "handoff_required",
                "dualResident": False,
                "reason": "MiniMax Route A already holds the GPU. Stop Route A before starting ComfyUI.",
                "residents": residents,
                "gpu": gpu,
            }
        return {
            "allowed": True,
            "action": "start",
            "dualResident": False,
            "reason": "GPU free for ComfyUI",
            "residents": residents,
            "gpu": gpu,
        }

    return {
        "allowed": False,
        "action": "block",
        "reason": f"Unknown GPU requester {requesting}",
        "residents": residents,
        "gpu": gpu,
    }


def free_comfy_models(*, timeout: float = 10.0) -> dict[str, Any]:
    """POST /free to canonical Comfy :8188 to release resident models.

    ComfyUI Protection Law item 14: /free releases models; it is NOT kill, restart,
    or reset. Comfy :8188 stays healthy and is never terminated by this call. This is
    the on-demand GPU handoff mechanism: free VRAM so Route A :8192 can load H3 without
    killing the canonical Comfy. Returns ok=True if /free succeeded or Comfy was down.
    """
    import json as _json
    import urllib.error
    import urllib.request

    if not comfy_healthy():
        return {"ok": True, "reason": "Comfy :8188 not healthy — nothing to free"}
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{COMFY_PORT}/free",
            data=_json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — loopback only
            return {"ok": resp.status == 200}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"ok": False, "reason": f"/free failed: {exc}"}


def free_route_a_models(*, timeout: float = 10.0) -> dict[str, Any]:
    """POST /free to Route A :8192 to release resident H3 models (warm residency offload).

    Mirror of free_comfy_models for the MiniMax H3 stack. /free releases models;
    it is NOT kill/restart/reset — Route A stays healthy and owned by the supervisor.
    Used for selective unload under GPU admission: when another service (canonical
    Comfy :8188, Media Intelligence, …) needs the GPU while Route A sits idle-warm
    holding ~27-29GB, its resident models are released WITHOUT stopping the runtime.
    Refuses while a Route A job is running (never interrupt an active generation).
    """
    import json as _json
    import urllib.error
    import urllib.request

    if not _route_a_healthy():
        return {"ok": True, "reason": "Route A :8192 not healthy — nothing to free"}
    if _route_a_queue_running() > 0:
        return {"ok": False, "reason": "Route A has an active generation — not freeing"}
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{H3_COMFY_PORT}/free",
            data=_json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — loopback only
            return {"ok": resp.status == 200}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"ok": False, "reason": f"Route A /free failed: {exc}"}


def request_comfy_admission_with_route_a_handoff() -> dict[str, Any]:
    """Admission for canonical Comfy :8188 with selective unload of idle-warm Route A.

    Reverse of request_route_a_admission_with_handoff: if Route A :8192 is healthy
    but IDLE (no running generation) and holds the GPU with warm H3 models, release
    them via POST /free (models only — the Route A process stays up) so :8188 can
    load. If Route A is actively generating, refuse — never interrupt a render.
    """
    admission = assess_gpu_admission("comfyui")
    if admission.get("allowed"):
        return admission
    if admission.get("action") == "handoff_required":
        freed = free_route_a_models()
        if not freed.get("ok"):
            return {
                "allowed": False,
                "action": "handoff_failed",
                "reason": f"Route A handoff failed — /free did not succeed: {freed.get('reason')}",
                "handoff": freed,
            }
        # Route A process remains healthy after /free (models only), so
        # assess_gpu_admission would still report handoff_required; allow explicitly —
        # the one-Comfy-at-a-time policy is honored because :8192 no longer holds
        # resident models.
        return {
            "allowed": True,
            "action": "start_after_handoff",
            "reason": "Route A :8192 warm models freed — Comfy :8188 may start (selective unload)",
            "handoff": freed,
        }
    return admission


def request_route_a_admission_with_handoff() -> dict[str, Any]:
    """On-demand admission for Route A with GPU handoff from canonical Comfy :8188.

    If the GPU is free, allow start. If Comfy :8188 holds the GPU while idle
    (handoff_required), POST /free to release its resident models first, then allow
    Route A to start. If :8188 is busy (queue running), refuse — finish that job first.
    Never kills Comfy :8188 (ComfyUI Protection Law). This is the unified-runtime-fabric
    on-demand entry: Route A is ON DEMAND, started when an H3 generation is requested.
    """
    admission = assess_gpu_admission("minimax_h3_route_a")
    if admission.get("allowed"):
        return admission
    if admission.get("action") == "handoff_required":
        freed = free_comfy_models()
        if not freed.get("ok"):
            return {
                "allowed": False,
                "action": "handoff_failed",
                "reason": f"GPU handoff failed — /free did not succeed: {freed.get('reason')}",
                "handoff": freed,
            }
        # After /free, Comfy :8188 is still healthy (we did not kill it) but its models are
        # unloaded and VRAM is released. assess_gpu_admission keys on desktop["healthy"],
        # so it would still return handoff_required; explicitly allow start after a
        # successful /free (on-demand handoff — the one-Comfy-at-a-time policy is honored
        # because :8188 no longer holds resident models).
        return {
            "allowed": True,
            "action": "start_after_handoff",
            "reason": "Comfy :8188 models freed — Route A may start (on-demand handoff)",
            "handoff": freed,
        }
    return admission
