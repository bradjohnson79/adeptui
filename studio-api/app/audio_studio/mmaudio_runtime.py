"""Warm MMAudio residency for Audio Studio.

Keeps one --serve worker alive for a bounded idle window so take 2 and the
next SFX request skip torch/checkpoint reload. Does not own Comfy or create
a second GPU authority. Higher-priority image/video work may call
unload_resident() to evict VRAM.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

IDLE_SEC = 10 * 60
READY_TIMEOUT_SEC = 300
JOB_TIMEOUT_SEC = 900

_LOCK = threading.Lock()
_SERVE: dict[str, Any] | None = None
_BUSY_BATCH: str | None = None
_WATCH_STARTED = False


class WarmUnavailable(RuntimeError):
    """Serve is not usable; caller should fall back to one-shot."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _venv_python() -> Path | None:
    root = _repo_root()
    for candidate in (
        root / "data" / "m210b-sfx-venv" / "Scripts" / "python.exe",
        root / "data" / "m210b-sandbox" / "providers" / "m2101-sfx-031" / "venv" / "Scripts" / "python.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def _worker_and_repo() -> tuple[Path, Path]:
    worker = Path(__file__).resolve().parents[1] / "codirector" / "native_audio" / "mmaudio_worker.py"
    repo = (
        _repo_root()
        / "data"
        / "m210b-sandbox"
        / "providers"
        / "m2101-sfx-031"
        / "src"
        / "MMAudio"
    )
    return worker, repo


def status() -> dict[str, Any]:
    with _LOCK:
        serve = _SERVE
        alive = bool(serve and serve["proc"].poll() is None)
        return {
            "resident": alive,
            "pid": int(serve["proc"].pid) if alive else None,
            "device": (serve.get("ready") or {}).get("device") if serve else None,
            "model": (serve.get("ready") or {}).get("model") if serve else None,
            "lastUsedAt": serve.get("last_used") if serve else None,
            "idleSec": IDLE_SEC,
            "busyBatchId": _BUSY_BATCH,
        }


def unload_resident(reason: str = "idle") -> dict[str, Any]:
    """Evict the warm MMAudio process. Safe for higher-priority GPU work."""
    global _SERVE, _BUSY_BATCH
    with _LOCK:
        serve = _SERVE
        _SERVE = None
        _BUSY_BATCH = None
    if not serve:
        return {"ok": True, "unloaded": False, "reason": reason}
    proc: subprocess.Popen = serve["proc"]
    try:
        if proc.poll() is None and proc.stdin:
            proc.stdin.write(json.dumps({"cmd": "unload"}) + "\n")
            proc.stdin.flush()
            proc.wait(timeout=8)
    except Exception:
        pass
    if proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
    return {"ok": True, "unloaded": True, "reason": reason, "pid": serve.get("pid")}


def interrupt_in_flight(batch_id: str) -> dict[str, Any]:
    """Kill the resident only when it is serving this batch (true cancel)."""
    with _LOCK:
        busy = _BUSY_BATCH
    if busy and busy == batch_id:
        return {**unload_resident("cancel"), "interrupted": True}
    return {"ok": True, "interrupted": False, "reason": "idle-or-other-batch"}


def _ensure_watch() -> None:
    global _WATCH_STARTED
    if _WATCH_STARTED:
        return
    _WATCH_STARTED = True

    def _loop() -> None:
        while True:
            time.sleep(30)
            with _LOCK:
                serve = _SERVE
                last = float(serve.get("last_used") or 0) if serve else 0.0
                busy = _BUSY_BATCH
            if serve and not busy and last and (time.time() - last) >= IDLE_SEC:
                unload_resident("idle-timeout")

    thread = threading.Thread(target=_loop, name="mmaudio-idle-unload", daemon=True)
    thread.start()


def _start_locked() -> dict[str, Any]:
    py = _venv_python()
    worker, repo = _worker_and_repo()
    if not py:
        raise WarmUnavailable("MMAudio venv python is missing")
    if not worker.is_file() or not repo.is_dir():
        raise WarmUnavailable("MMAudio worker or repo is missing")
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [str(py), str(worker), "--serve", "--repo", str(repo)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(repo),
        creationflags=flags,
    )
    assert proc.stdout is not None
    deadline = time.time() + READY_TIMEOUT_SEC
    ready: dict[str, Any] | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else "") or ""
            raise WarmUnavailable(f"MMAudio serve failed to start: {err[-800:]}")
        line = proc.stdout.readline()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if payload.get("type") == "ready":
            ready = payload
            break
        if payload.get("type") == "error":
            raise WarmUnavailable(str(payload.get("message") or "MMAudio serve error"))
    if ready is None:
        proc.kill()
        raise WarmUnavailable("MMAudio serve did not become ready in time")
    return {
        "proc": proc,
        "ready": ready,
        "last_used": time.time(),
        "pid": proc.pid,
        "started_at": time.time(),
    }


def _serve() -> dict[str, Any]:
    global _SERVE
    _ensure_watch()
    with _LOCK:
        current = _SERVE
        if current and current["proc"].poll() is None:
            return current
        _SERVE = _start_locked()
        return _SERVE


def generate_warm(
    *,
    prompt: str,
    out: Path,
    duration: float,
    seed: int,
    negative: str = "",
    cfg_strength: float = 4.5,
    batch_id: str | None = None,
    event_count: int | None = None,
) -> dict[str, Any]:
    """Generate on the resident worker. Raises WarmUnavailable on serve failure."""
    global _BUSY_BATCH
    serve = _serve()
    proc: subprocess.Popen = serve["proc"]
    if proc.stdin is None or proc.stdout is None:
        raise WarmUnavailable("MMAudio serve pipes are missing")
    job_id = uuid.uuid4().hex[:10]
    job = {
        "id": job_id,
        "prompt": prompt,
        "negative": negative or "",
        "duration": float(duration),
        "seed": int(seed),
        "out": str(out),
        "cfg_strength": float(cfg_strength),
        "event_count": int(event_count) if event_count is not None else None,
    }
    with _LOCK:
        _BUSY_BATCH = batch_id
        serve["last_used"] = time.time()
    try:
        proc.stdin.write(json.dumps(job) + "\n")
        proc.stdin.flush()
        deadline = time.time() + JOB_TIMEOUT_SEC
        while time.time() < deadline:
            if proc.poll() is not None:
                err = ""
                try:
                    err = (proc.stderr.read() if proc.stderr else "") or ""
                except Exception:
                    pass
                raise WarmUnavailable(f"MMAudio serve exited during generate: {err[-600:]}")
            line = proc.stdout.readline()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("id") and payload.get("id") != job_id:
                continue
            if payload.get("type") == "done":
                serve["last_used"] = time.time()
                return payload
            if payload.get("type") == "error":
                raise RuntimeError(str(payload.get("message") or "MMAudio generate failed"))
        raise TimeoutError("MMAudio warm generate timed out")
    finally:
        with _LOCK:
            if _BUSY_BATCH == batch_id:
                _BUSY_BATCH = None
            if _SERVE is serve:
                serve["last_used"] = time.time()
