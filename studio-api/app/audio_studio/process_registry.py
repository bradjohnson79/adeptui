"""Track live ACE-Step / MMAudio worker subprocesses for certified cancel-to-source."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TrackedProcess:
    pid: int
    popen: subprocess.Popen
    runtime: str
    project_id: str
    batch_id: str
    candidate_id: str
    job_id: str
    started_at: float = field(default_factory=time.time)
    cancelled: bool = False


_lock = threading.RLock()
_by_job: dict[str, TrackedProcess] = {}
_by_batch: dict[str, set[str]] = {}
_cancel_flags: dict[str, bool] = {}  # batch_id -> cancelled
_tls = threading.local()


@dataclass
class ExecutionContext:
    project_id: str
    batch_id: str
    candidate_id: str
    job_id: str
    runtime_hint: str = ""


class execution_scope:
    """Thread-local scope so adapters can cancel-to-source without schema churn."""

    def __init__(
        self,
        *,
        project_id: str,
        batch_id: str,
        candidate_id: str,
        job_id: str | None = None,
        runtime_hint: str = "",
    ) -> None:
        import uuid

        self.ctx = ExecutionContext(
            project_id=project_id,
            batch_id=batch_id,
            candidate_id=candidate_id,
            job_id=job_id or str(uuid.uuid4()),
            runtime_hint=runtime_hint,
        )
        self._prev: Optional[ExecutionContext] = None

    def __enter__(self) -> ExecutionContext:
        self._prev = getattr(_tls, "ctx", None)
        _tls.ctx = self.ctx
        return self.ctx

    def __exit__(self, exc_type, exc, tb) -> None:
        _tls.ctx = self._prev


def current_execution() -> Optional[ExecutionContext]:
    return getattr(_tls, "ctx", None)


def mark_batch_cancel_requested(batch_id: str) -> None:
    with _lock:
        _cancel_flags[batch_id] = True


def clear_batch_cancel(batch_id: str) -> None:
    with _lock:
        _cancel_flags.pop(batch_id, None)


def is_batch_cancel_requested(batch_id: str) -> bool:
    with _lock:
        return bool(_cancel_flags.get(batch_id))


def register(
    *,
    job_id: str,
    popen: subprocess.Popen,
    runtime: str,
    project_id: str,
    batch_id: str,
    candidate_id: str,
) -> TrackedProcess:
    assert popen.pid is not None
    tracked = TrackedProcess(
        pid=int(popen.pid),
        popen=popen,
        runtime=runtime,
        project_id=project_id,
        batch_id=batch_id,
        candidate_id=candidate_id,
        job_id=job_id,
    )
    with _lock:
        _by_job[job_id] = tracked
        _by_batch.setdefault(batch_id, set()).add(job_id)
    return tracked


def unregister(job_id: str) -> None:
    with _lock:
        tracked = _by_job.pop(job_id, None)
        if not tracked:
            return
        jobs = _by_batch.get(tracked.batch_id)
        if jobs is not None:
            jobs.discard(job_id)
            if not jobs:
                _by_batch.pop(tracked.batch_id, None)


def _kill_windows_tree(pid: int) -> list[str]:
    notes: list[str] = []
    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        notes.append(f"taskkill pid={pid} code={completed.returncode}")
        if completed.stdout:
            notes.append(completed.stdout.strip()[:300])
        if completed.stderr:
            notes.append(completed.stderr.strip()[:300])
    except Exception as exc:
        notes.append(f"taskkill failed: {exc}")
    return notes


def _kill_posix(popen: subprocess.Popen) -> list[str]:
    notes: list[str] = []
    try:
        if popen.poll() is None:
            popen.send_signal(signal.SIGTERM)
            notes.append(f"SIGTERM pid={popen.pid}")
            try:
                popen.wait(timeout=5)
            except subprocess.TimeoutExpired:
                popen.kill()
                notes.append(f"SIGKILL pid={popen.pid}")
    except Exception as exc:
        notes.append(f"posix kill failed: {exc}")
    return notes


def terminate_job(job_id: str) -> dict[str, Any]:
    with _lock:
        tracked = _by_job.get(job_id)
    if not tracked:
        return {"ok": True, "found": False, "jobId": job_id, "message": "No live worker for job."}
    notes: list[str] = []
    tracked.cancelled = True
    if os.name == "nt":
        notes.extend(_kill_windows_tree(tracked.pid))
    else:
        notes.extend(_kill_posix(tracked.popen))
    try:
        tracked.popen.wait(timeout=10)
    except Exception:
        pass
    unregister(job_id)
    return {
        "ok": True,
        "found": True,
        "jobId": job_id,
        "pid": tracked.pid,
        "runtime": tracked.runtime,
        "notes": notes,
        "sourceCancel": True,
    }


def terminate_batch(batch_id: str) -> dict[str, Any]:
    mark_batch_cancel_requested(batch_id)
    with _lock:
        job_ids = list(_by_batch.get(batch_id) or [])
    results = [terminate_job(jid) for jid in job_ids]
    return {
        "ok": True,
        "batchId": batch_id,
        "sourceCancel": True,
        "terminatedJobs": results,
        "count": len(results),
    }


def terminate_orphan_audio_workers() -> dict[str, Any]:
    """Kill any ace_step_worker / mmaudio_worker processes not necessarily tracked (GPU safety)."""
    killed: list[dict[str, Any]] = []
    patterns = ("ace_step_worker.py", "mmaudio_worker.py")
    if os.name == "nt":
        try:
            import json as _json

            ps = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "$procs = Get-CimInstance Win32_Process | Where-Object { "
                    "$_.CommandLine -match 'ace_step_worker\\.py|mmaudio_worker\\.py' }; "
                    "$procs | ForEach-Object { [PSCustomObject]@{Pid=$_.ProcessId; Cmd=$_.CommandLine} } | "
                    "ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            raw = (ps.stdout or "").strip()
            rows: list[dict[str, Any]] = []
            if raw:
                data = _json.loads(raw)
                rows = data if isinstance(data, list) else [data]
            for row in rows:
                pid = int(row.get("Pid") or 0)
                if not pid:
                    continue
                notes = _kill_windows_tree(pid)
                killed.append({"pid": pid, "cmd": str(row.get("Cmd") or "")[:240], "notes": notes})
        except Exception as exc:
            return {"ok": False, "error": str(exc), "killed": killed, "sourceCancel": True}
    else:
        try:
            ps = subprocess.run(["ps", "ax", "-o", "pid=,command="], capture_output=True, text=True, check=False)
            for line in (ps.stdout or "").splitlines():
                if not any(p in line for p in patterns):
                    continue
                parts = line.strip().split(None, 1)
                if not parts:
                    continue
                pid = int(parts[0])
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed.append({"pid": pid, "cmd": parts[1][:240] if len(parts) > 1 else ""})
                except Exception as exc:
                    killed.append({"pid": pid, "error": str(exc)})
        except Exception as exc:
            return {"ok": False, "error": str(exc), "killed": killed, "sourceCancel": True}
    return {"ok": True, "killed": killed, "count": len(killed), "sourceCancel": True}


def list_live(*, project_id: Optional[str] = None) -> list[dict[str, Any]]:
    with _lock:
        items = list(_by_job.values())
    out = []
    for t in items:
        if project_id and t.project_id != project_id:
            continue
        alive = t.popen.poll() is None
        out.append(
            {
                "jobId": t.job_id,
                "pid": t.pid,
                "runtime": t.runtime,
                "projectId": t.project_id,
                "batchId": t.batch_id,
                "candidateId": t.candidate_id,
                "alive": alive,
                "cancelled": t.cancelled,
                "startedAt": t.started_at,
            }
        )
    return out


def run_tracked(
    cmd: list[str],
    *,
    job_id: str,
    runtime: str,
    project_id: str,
    batch_id: str,
    candidate_id: str,
    timeout: float = 900,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Popen + register so cancel can kill the GPU worker process tree."""
    if is_batch_cancel_requested(batch_id):
        raise RuntimeError(f"Batch {batch_id} already cancelled before worker start")

    popen = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    register(
        job_id=job_id,
        popen=popen,
        runtime=runtime,
        project_id=project_id,
        batch_id=batch_id,
        candidate_id=candidate_id,
    )
    try:
        deadline = time.time() + timeout
        while True:
            if is_batch_cancel_requested(batch_id):
                terminate_job(job_id)
                raise RuntimeError(f"Cancelled at source (batch={batch_id}, job={job_id})")
            rc = popen.poll()
            if rc is not None:
                stdout, stderr = popen.communicate()
                return subprocess.CompletedProcess(cmd, rc, stdout or "", stderr or "")
            if time.time() >= deadline:
                terminate_job(job_id)
                raise TimeoutError(f"Worker timed out after {timeout}s; terminated at source")
            time.sleep(0.25)
    finally:
        unregister(job_id)
