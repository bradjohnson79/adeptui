"""MiniMax H3 opportunistic prewarm — load canonical H3 dependencies when the
creator explicitly selects MiniMax H3, before they press Generate.

Owner law (2026-09-07):
- only when GPU is available (admission-gated; refuses while :8188 is busy);
- cancel if the creator switches generator;
- never evict an ACTIVE workload (a running job on either Comfy);
- never prewarm merely because a page opened — explicit H3 selection only.

Method: a micro-render (5 frames, 1 step, 480x256, fixed seed+prompt, T2V graph —
no first frame needed) submitted directly to Route A :8192 touches all four
canonical H3 models (TE, UNET, video VAE, audio VAE), forcing the cold
disk→RAM→VRAM load BEFORE the real job. Measured value (124-frame production
config, RTX 5090, dynamic-VRAM fork):
  cold Generate: 690s total (TE encode 143.6s, sampling ~102s/it)
  warm Generate: 111s total (TE encode 14.5s, sampling ~20.5s/it)
Fixed inputs make repeat prewarms cache-hit cheap (~3s). The junk micro-render
output file is deleted after completion. Prewarm never runs while a real H3 job
is active, and a real Generate submitted during prewarm simply queues behind the
micro-render — the loading work transfers to the real job either way.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .private_access import runtime_url
from .route_a_adapter import build_t2va_graph

# Fixed micro-render identity — repeat prewarms cache-hit in Comfy (~3s).
_PREWARM_PROMPT = "prewarm — model residency load only, output discarded"
_PREWARM_SEED = 987654321
_PREWARM_PREFIX = "h3_prewarm"
_PREWARM_WIDTH = 480
_PREWARM_HEIGHT = 256
_PREWARM_FRAMES = 5  # minimum 17k+5 grid point
_PREWARM_FPS = 24.0
_PREWARM_STEPS = 1

_state: dict[str, Any] = {
    "status": "idle",  # idle | starting_runtime | loading | warm | cancelled | failed
    "promptId": None,
    "clientId": None,
    "startedAt": None,
    "completedAt": None,
    "reason": None,
}
_lock = threading.Lock()


def _set(**kv: Any) -> None:
    with _lock:
        _state.update(kv)


def prewarm_status() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def _http(method: str, url: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — loopback only
        raw = r.read().decode("utf-8", "replace")
        return json.loads(raw) if raw else {}


def _route_a_queue_running(base: str) -> int:
    try:
        q = _http("GET", f"{base}/queue", timeout=8)
        return len(q.get("queue_running") or [])
    except Exception:
        return -1


def _route_a_healthy(base: str) -> bool:
    try:
        _http("GET", f"{base}/system_stats", timeout=8)
        return True
    except Exception:
        return False


def _gpu_blocked_by_comfy() -> str | None:
    """Refuse prewarm while canonical Comfy :8188 is actively rendering."""
    try:
        from runtime_supervisor.gpu_admission import classify_comfy_residents

        residents = classify_comfy_residents()
        desktop = residents.get("comfyui") or {}
        if desktop.get("healthy") and int(desktop.get("queueRunning") or 0) > 0:
            return "Comfy :8188 is rendering — prewarm would contend for the GPU"
    except Exception:
        pass  # admission probe failure must not block creator intent
    return None


def _ensure_route_a(base: str) -> tuple[bool, str | None]:
    """Ensure Route A :8192 is up via the canonical on-demand control plane."""
    if _route_a_healthy(base):
        return True, None
    try:
        from runtime_supervisor.control_client import call_control, control_plane_reachable

        if not control_plane_reachable():
            return False, "Background Services manager unreachable — cannot start H3 runtime"
        result = call_control("POST", "/start-route-a", timeout=600.0)
        if result.get("ok"):
            return True, None
        return False, str(result.get("message") or result.get("reason") or "Route A start refused")
    except Exception as exc:
        return False, f"Route A start failed: {exc!r}"


def _cleanup_outputs() -> None:
    """Delete prewarm micro-render artifacts from the Route A output dir.

    Same canonical output root the adapter uses (_resolve_output_file). Draft
    prewarm renders are never Library assets — they are load-only artifacts.
    """
    root = Path(r"C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui\output")
    try:
        if root.is_dir():
            for f in root.glob(f"{_PREWARM_PREFIX}*"):
                try:
                    f.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def _watch_completion(base: str, prompt_id: str) -> None:
    """Background: wait for the micro-render, then mark warm + clean artifacts."""
    deadline = time.time() + 900
    while time.time() < deadline:
        time.sleep(3)
        with _lock:
            if _state.get("promptId") != prompt_id or _state.get("status") in ("cancelled", "failed"):
                return
        try:
            h = _http("GET", f"{base}/history/{prompt_id}", timeout=10)
        except Exception:
            continue
        if h.get(prompt_id):
            _cleanup_outputs()
            _set(status="warm", completedAt=time.time(), reason=None)
            return
    _set(status="failed", reason="prewarm timed out")


def start_prewarm(*, surface: str = "one-frame") -> dict[str, Any]:
    """Opportunistically load canonical H3 models onto Route A :8192.

    Idempotent: repeated calls while loading/warm return current state.
    Quiet refusal (ok=False + reason) when the GPU or runtime is unavailable —
    prewarm is an optimization, never a blocker for the creator.
    """
    with _lock:
        if _state.get("status") in ("starting_runtime", "loading"):
            return {"ok": True, "prewarm": dict(_state), "message": "prewarm already in flight"}
    # NOTE: no "warm" short-circuit. Module state cannot see external eviction
    # (GPU-admission /free, Comfy memory pressure), so a stale "warm" would be fake
    # readiness (Build Law #6). The fixed-input micro-render IS the warmth probe:
    # cache-hit cheap (~3-10s) when models are resident, a real reload when not.

    base = runtime_url().rstrip("/")

    blocked = _gpu_blocked_by_comfy()
    if blocked:
        _set(status="idle", reason=blocked)
        return {"ok": False, "prewarm": prewarm_status(), "message": blocked}

    running = _route_a_queue_running(base)
    if running and running > 0:
        msg = "H3 render in progress — prewarm skipped (never contend with a real job)"
        _set(status="idle", reason=msg)
        return {"ok": False, "prewarm": prewarm_status(), "message": msg}

    _set(status="starting_runtime", startedAt=time.time(), reason=None, completedAt=None)
    up, why = _ensure_route_a(base)
    if not up:
        _set(status="idle", reason=why)
        return {"ok": False, "prewarm": prewarm_status(), "message": why}

    graph = build_t2va_graph(
        _PREWARM_PROMPT,
        seed=_PREWARM_SEED,
        filename_prefix=_PREWARM_PREFIX,
        duration_sec=_PREWARM_FRAMES / _PREWARM_FPS,
        width=_PREWARM_WIDTH,
        height=_PREWARM_HEIGHT,
        fps=_PREWARM_FPS,
        steps=_PREWARM_STEPS,
    )
    client_id = f"h3-prewarm-{int(time.time())}"
    try:
        resp = _http("POST", f"{base}/prompt", {"prompt": graph, "client_id": client_id}, timeout=30)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _set(status="failed", reason=f"prewarm submit failed: {exc!r}")
        return {"ok": False, "prewarm": prewarm_status(), "message": "prewarm submit failed"}

    prompt_id = resp.get("prompt_id")
    _set(status="loading", promptId=prompt_id, clientId=client_id)
    threading.Thread(target=_watch_completion, args=(base, prompt_id), daemon=True).start()
    return {
        "ok": True,
        "prewarm": prewarm_status(),
        "message": "MiniMax H3 is warming up in the background — Generate will be faster.",
    }


def cancel_prewarm(*, reason: str = "generator switched") -> dict[str, Any]:
    """Cancel an in-flight prewarm (creator switched generator). No-op if warm/idle."""
    with _lock:
        status = _state.get("status")
        prompt_id = _state.get("promptId")
    if status not in ("starting_runtime", "loading") or not prompt_id:
        return {"ok": True, "prewarm": prewarm_status(), "message": "no prewarm in flight"}

    base = runtime_url().rstrip("/")
    # Remove from queue if pending; interrupt if running. Both are model-load safe —
    # /interrupt stops between nodes, never mid-file-read corruption.
    try:
        _http("POST", f"{base}/queue", {"delete": [prompt_id]}, timeout=8)
    except Exception:
        pass
    try:
        _http("POST", f"{base}/interrupt", timeout=8)
    except Exception:
        pass
    _cleanup_outputs()
    _set(status="cancelled", reason=reason, promptId=None, clientId=None)
    return {"ok": True, "prewarm": prewarm_status(), "message": "prewarm cancelled"}
