"""Sequential GPU lease: generation first, then perception, then unload."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

MIN_FAST_VISION_VRAM_GB = 6.0
# Qwen2.5-Omni 7B (bf16 weights ~16GB + AV activations). Never admit below this.
MIN_QWEN_OMNI_VRAM_GB = 20.0


def query_free_vram_gb() -> float | None:
    try:
        from ...vram_profiles import query_gpu_stats

        stats = query_gpu_stats()
        if not stats.get("ok") or not stats.get("gpus"):
            return None
        free_mib = max(float(g.get("memory_free_mib") or 0) for g in stats["gpus"])
        if free_mib <= 0:
            return None
        return round(free_mib / 1024.0, 2)
    except Exception:
        return None


def _free_idle_route_a() -> dict[str, Any]:
    """Selective unload of idle-warm H3 models on :8192. Never kills Route A.

    Media Intelligence needs ~20 GB. Warm H3 residency often holds ~27–31 GB.
    Canonical GPU admission already owns this handoff (``free_route_a_models``);
    it refuses while a Route A job is running.
    """
    try:
        from runtime_supervisor.gpu_admission import free_route_a_models

        return dict(free_route_a_models(timeout=30.0))
    except Exception as exc:  # noqa: BLE001 — lease must degrade, not crash
        return {"ok": False, "reason": str(exc)[:240]}


def best_effort_free_generator() -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "comfyFreeRequested": False,
        "vramFullyReleased": False,
        "vramBeforeFreeGb": query_free_vram_gb(),
    }
    try:
        import httpx

        from ...config import settings

        url = str(settings.comfy_url).rstrip("/") + "/free"
        response = httpx.post(
            url,
            json={"unload_models": True, "free_memory": True},
            timeout=30.0,
        )
        evidence["comfyFreeRequested"] = response.status_code < 400
        evidence["comfyFreeStatus"] = int(response.status_code)
    except Exception as exc:
        evidence["comfyFreeError"] = str(exc)[:240]
        logger.info("temporal vision: Comfy /free skipped: %s", evidence["comfyFreeError"])
    evidence["vramAfterFreeGb"] = query_free_vram_gb()
    after = evidence["vramAfterFreeGb"]

    # Comfy :8188 /free does not release Route A :8192. If Qwen still cannot
    # fit, hand off through the existing Route A selective-unload primitive.
    if after is None or after < MIN_QWEN_OMNI_VRAM_GB:
        evidence["routeAFree"] = _free_idle_route_a()
        wait = wait_for_free_vram(min_gb=MIN_QWEN_OMNI_VRAM_GB, timeout_sec=45.0, interval_sec=2.0)
        evidence["vramWait"] = wait
        evidence["vramAfterRouteAFreeGb"] = wait.get("freeVramGb")
        after = evidence["vramAfterRouteAFreeGb"]

    if after is not None and after >= MIN_FAST_VISION_VRAM_GB:
        evidence["vramFullyReleased"] = True
    return evidence


def wait_for_free_vram(
    *,
    min_gb: float,
    timeout_sec: float = 45.0,
    interval_sec: float = 2.0,
) -> dict[str, Any]:
    """Poll device-free VRAM after ``/free``. Unload is worker-async, not instant."""
    started = time.monotonic()
    samples: list[float | None] = []
    while True:
        free = query_free_vram_gb()
        samples.append(free)
        if free is not None and free >= min_gb:
            return {
                "ok": True,
                "freeVramGb": free,
                "waitedSec": round(time.monotonic() - started, 2),
                "samples": samples,
            }
        if (time.monotonic() - started) >= timeout_sec:
            return {
                "ok": False,
                "freeVramGb": free,
                "waitedSec": round(time.monotonic() - started, 2),
                "samples": samples,
            }
        time.sleep(max(0.2, float(interval_sec)))


def preflight_for_review(*, min_gb: float = MIN_FAST_VISION_VRAM_GB) -> dict[str, Any]:
    free = query_free_vram_gb()
    if free is None:
        # Unknown is not permission to load. Stills perception has its own probe.
        return {
            "ok": False,
            "freeVramGb": None,
            "reason": "VRAM_UNKNOWN",
            "unknownVram": True,
        }
    if free < min_gb:
        return {
            "ok": False,
            "freeVramGb": free,
            "reason": "INSUFFICIENT_VRAM",
            "unknownVram": False,
        }
    return {"ok": True, "freeVramGb": free, "reason": None, "unknownVram": False}


# Collapse evidence (2026-09-22, 64 GB machine): Comfy ram_free ~330 MB while
# MiniMax still held ~29 GB VRAM. Heavy unload/load is refused below this reserve.
MIN_SYSTEM_RAM_FREE_GB = 8.0
# ~29 GB H3 footprint on a 32 GB GPU. Free VRAM under this means the generator
# is still resident. Idle Comfy on this machine was ~0.7 GB used.
MIN_MINIMAX_FREE_VRAM_GB = 24.0

_HANDOFF_LOCK = __import__("threading").Lock()
_HANDOFF_OWNERS: dict[tuple[str, str, str], dict[str, Any]] = {}
_ACTIVE_HANDOFF: tuple[str, str, str] | None = None


def handoff_key(scene_id: str, take_id: str, batch_id: str) -> tuple[str, str, str]:
    return (str(scene_id or ""), str(take_id or ""), str(batch_id or ""))


def begin_handoff(key: tuple[str, str, str]) -> dict[str, Any]:
    """One completion pipeline per scene/take/batch. Later polls only observe."""
    global _ACTIVE_HANDOFF
    with _HANDOFF_LOCK:
        row = _HANDOFF_OWNERS.get(key)
        if row is not None:
            return {
                "ok": row.get("state") == "ready",
                "observe": True,
                "state": row.get("state"),
                "reason": row.get("reason") or "",
            }
        handoff_id = uuid.uuid4().hex
        _HANDOFF_OWNERS[key] = {
            "state": "running",
            "reason": "",
            "freeRequested": False,
            "handoffId": handoff_id,
        }
        _ACTIVE_HANDOFF = key
        return {"ok": True, "observe": False, "state": "running", "reason": "", "handoffId": handoff_id}


def release_active_generator_once() -> dict[str, Any] | None:
    """The in-progress handoff's single ``/free``. None when no handoff owns it."""
    with _HANDOFF_LOCK:
        key = _ACTIVE_HANDOFF
    if key is None:
        return None
    return release_generator_once(key)


def reset_handoff_state() -> None:
    """Test helper. Production handoffs are not cleared by polls."""
    global _ACTIVE_HANDOFF
    with _HANDOFF_LOCK:
        _HANDOFF_OWNERS.clear()
        _ACTIVE_HANDOFF = None


def handoff_state(key: tuple[str, str, str]) -> dict[str, Any] | None:
    with _HANDOFF_LOCK:
        row = _HANDOFF_OWNERS.get(key)
        return dict(row) if row else None


def note_handoff(key: tuple[str, str, str], *, state: str, reason: str = "") -> None:
    global _ACTIVE_HANDOFF
    with _HANDOFF_LOCK:
        row = dict(_HANDOFF_OWNERS.get(key) or {})
        row["state"] = state
        row["reason"] = reason
        row.setdefault("freeRequested", False)
        _HANDOFF_OWNERS[key] = row
        if state != "running" and _ACTIVE_HANDOFF == key:
            _ACTIVE_HANDOFF = None


def release_generator_once(key: tuple[str, str, str]) -> dict[str, Any]:
    """One Comfy ``/free``. A second call for the same handoff does not post again."""
    with _HANDOFF_LOCK:
        row = dict(_HANDOFF_OWNERS.get(key) or {"state": "running", "reason": "", "freeRequested": False})
        if row.get("freeRequested"):
            return {"ok": True, "skipped": True, "comfyFreeRequested": False, "reason": "already_released"}
        row["freeRequested"] = True
        _HANDOFF_OWNERS[key] = row
    evidence: dict[str, Any] = {"ok": False, "skipped": False, "comfyFreeRequested": False}
    try:
        import httpx

        from ...config import settings

        url = str(settings.comfy_url).rstrip("/") + "/free"
        response = httpx.post(
            url,
            json={"unload_models": True, "free_memory": True},
            timeout=8.0,
        )
        evidence["comfyFreeRequested"] = True
        evidence["comfyFreeStatus"] = int(response.status_code)
        evidence["ok"] = response.status_code < 400
    except Exception as exc:  # noqa: BLE001 — one attempt, then measure
        evidence["comfyFreeError"] = str(exc)[:240]
    # Timeline MiniMax lives on Route A :8192. Comfy :8188 /free does not release it.
    # One selective unload, then one settle. Not a poll and not a second attempt.
    evidence["routeAFree"] = _free_idle_route_a()
    time.sleep(15)
    evidence["settleSec"] = 15
    return evidence


def probe_handoff_memory(*, timeout_sec: float = 4.0) -> dict[str, Any]:
    """One short VRAM read and one short system-RAM read. Timeout is UNKNOWN."""
    vram = _probe_free_vram_gb(timeout_sec)
    ram = _probe_free_ram_gb(timeout_sec)
    if vram is None:
        return {
            "ok": False,
            "consumed": False,
            "freeVramGb": None,
            "freeRamGb": ram,
            "reason": "VRAM_UNKNOWN",
            "unknownVram": True,
            "unknownRam": ram is None,
        }
    if ram is None:
        return {
            "ok": False,
            "consumed": False,
            "freeVramGb": vram,
            "freeRamGb": None,
            "reason": "RAM_UNKNOWN",
            "unknownVram": False,
            "unknownRam": True,
        }
    return {
        "ok": True,
        "consumed": False,
        "freeVramGb": vram,
        "freeRamGb": ram,
        "reason": None,
        "unknownVram": False,
        "unknownRam": False,
    }


def _vram_need_gb(model: str) -> float:
    name = (model or "").lower()
    if "minimax" in name or name in ("h3", "generator"):
        return MIN_MINIMAX_FREE_VRAM_GB
    if "omni" in name or "qwen" in name:
        return MIN_QWEN_OMNI_VRAM_GB
    return MIN_FAST_VISION_VRAM_GB


def admit_heavyweight(model: str, probe: dict[str, Any] | None) -> dict[str, Any]:
    """A probe admits exactly one model and is consumed when that model starts.

    Worker success is not an argument. A missing or already-consumed probe blocks.
    """
    if not isinstance(probe, dict) or probe.get("consumed"):
        return {"ok": False, "reason": "PROBE_REQUIRED", "admittedModel": None}
    probe["consumed"] = True
    probe["admittedModel"] = None
    if probe.get("ok") is not True or probe.get("unknownVram") or probe.get("unknownRam"):
        return {
            "ok": False,
            "reason": str(probe.get("reason") or "MEMORY_UNKNOWN"),
            "admittedModel": None,
            "freeVramGb": probe.get("freeVramGb"),
            "freeRamGb": probe.get("freeRamGb"),
        }
    try:
        free_vram = float(probe.get("freeVramGb"))
        free_ram = float(probe.get("freeRamGb"))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "MEMORY_UNKNOWN", "admittedModel": None}
    need = _vram_need_gb(model)
    if free_vram < need:
        reason = "GENERATOR_STILL_RESIDENT" if need >= MIN_QWEN_OMNI_VRAM_GB else "INSUFFICIENT_VRAM"
        if "minimax" in (model or "").lower() or model in ("h3", "generator"):
            reason = "PREVIOUS_MODEL_STILL_RESIDENT"
        return {
            "ok": False,
            "reason": reason,
            "admittedModel": None,
            "freeVramGb": free_vram,
            "freeRamGb": free_ram,
            "requiredVramGb": need,
        }
    if free_ram < MIN_SYSTEM_RAM_FREE_GB:
        return {
            "ok": False,
            "reason": "INSUFFICIENT_RAM",
            "admittedModel": None,
            "freeVramGb": free_vram,
            "freeRamGb": free_ram,
            "requiredRamGb": MIN_SYSTEM_RAM_FREE_GB,
        }
    probe["admittedModel"] = model
    return {
        "ok": True,
        "reason": None,
        "admittedModel": model,
        "freeVramGb": free_vram,
        "freeRamGb": free_ram,
    }


def _probe_free_vram_gb(timeout_sec: float) -> float | None:
    import subprocess

    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_sec)),
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        free_mib = max(float(line.split()[0]) for line in lines)
    except ValueError:
        return None
    if free_mib <= 0:
        return None
    return round(free_mib / 1024.0, 2)


def _probe_free_ram_gb(timeout_sec: float) -> float | None:
    try:
        import httpx

        from ...config import settings

        url = str(settings.comfy_url).rstrip("/") + "/system_stats"
        response = httpx.get(url, timeout=max(1.0, float(timeout_sec)))
        if response.status_code >= 400:
            return None
        system = (response.json() or {}).get("system") or {}
        free = system.get("ram_free")
        if free is None:
            return None
        return round(float(free) / (1024.0 ** 3), 2)
    except Exception:
        return None


def comfy_generation_active() -> dict[str, Any]:
    """Read-only Comfy ``/queue`` probe. Media Intelligence must never load a
    heavy model while a generation is running or queued (GPU admission law).

    Returns ``active=True`` when work is running/queued, ``active=False`` when
    idle, ``active=None`` when the queue state cannot be determined (caller
    decides; Comfy unreachable means no Comfy generation can be active).
    """
    evidence: dict[str, Any] = {"active": None, "running": None, "pending": None}
    try:
        import httpx

        from ...config import settings

        url = str(settings.comfy_url).rstrip("/") + "/queue"
        response = httpx.get(url, timeout=8.0)
        evidence["status"] = int(response.status_code)
        if response.status_code >= 400:
            evidence["active"] = None
            evidence["error"] = f"HTTP {response.status_code}"
            return evidence
        data = response.json()
        running = len(data.get("queue_running") or [])
        pending = len(data.get("queue_pending") or [])
        evidence["running"] = running
        evidence["pending"] = pending
        evidence["active"] = (running + pending) > 0
        return evidence
    except Exception as exc:  # noqa: BLE001 — probe must degrade, not crash
        evidence["error"] = str(exc)[:240]
        return evidence


def probe_comfy_generation_ready() -> dict[str, Any]:
    """Distinguish SOCKET_PRESENT / HTTP_RESPONSIVE / WORKFLOW_READY. Port listen is not ready."""
    import socket

    from ...config import settings

    raw = str(settings.comfy_url or "http://127.0.0.1:8188").rstrip("/")
    host = "127.0.0.1"
    port = 8188
    try:
        from urllib.parse import urlparse

        parsed = urlparse(raw)
        host = parsed.hostname or host
        port = int(parsed.port or 8188)
    except Exception:
        pass
    evidence: dict[str, Any] = {
        "url": raw,
        "tier": "DOWN",
        "socketPresent": False,
        "httpResponsive": False,
        "workflowReady": False,
    }
    try:
        with socket.create_connection((host, port), timeout=2.0):
            evidence["socketPresent"] = True
            evidence["tier"] = "SOCKET_PRESENT"
    except OSError as exc:
        evidence["socketError"] = str(exc)[:160]
        return evidence
    try:
        import httpx

        stats = httpx.get(f"{raw}/system_stats", timeout=8.0)
        evidence["systemStatsStatus"] = int(stats.status_code)
        if stats.status_code < 400:
            evidence["httpResponsive"] = True
            evidence["tier"] = "HTTP_RESPONSIVE"
        info = httpx.get(f"{raw}/object_info", timeout=12.0)
        evidence["objectInfoStatus"] = int(info.status_code)
        payload = info.json() if info.status_code < 400 else {}
        nodes = payload if isinstance(payload, dict) else {}
        evidence["objectInfoKeys"] = len(nodes)
        if info.status_code < 400 and len(nodes) > 0:
            evidence["workflowReady"] = True
            evidence["tier"] = "WORKFLOW_READY"
    except Exception as exc:
        evidence["httpError"] = str(exc)[:240]
    return evidence
