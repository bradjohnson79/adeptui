"""LOCAL_FIRE3D / CLOUD_FIRE3D reconstruction runtime.

Same input (Library asset) and same output (Fire3DReconstructionPackage).
UI never asks which host ran. Isolated WSL2 Fire3D is LOCAL; remote is CLOUD.
Never installs into the Windows/Comfy CUDA environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .contracts import (
    ADEPT_FIRE3D_32GB_PROFILE,
    ReconstructionJob,
    ReconstructionProgress,
)
from .normalize import normalize_fire3d_output

_JOBS: dict[str, ReconstructionJob] = {}
_LOCK = threading.Lock()


def _wsl_fire3d_root() -> Path:
    raw = os.environ.get("ADEPT_FIRE3D_ROOT") or "/opt/adept/fire3d"
    return Path(raw)


def _decode_proc(raw: str | bytes | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="ignore") or raw.decode("utf-16-le", errors="ignore")
    else:
        text = raw
        if "\x00" in text:
            text = text.replace("\x00", "")
    return " ".join(text.split())


def _gpu_busy() -> tuple[bool, str]:
    """Read-only GPU admission. Never kills Comfy or Route A."""
    try:
        from runtime_supervisor.gpu_admission import nvidia_snapshot
        from runtime_supervisor.health import comfy_queue_running
    except Exception:  # noqa: BLE001
        return False, ""
    if comfy_queue_running():
        return True, "Comfy has a live generation"
    snap = nvidia_snapshot()
    if snap.get("ok") and int(snap.get("utilizationPct") or 0) >= 85:
        return True, f"GPU utilization {snap.get('utilizationPct')}%"
    return False, ""


def local_fire3d_available() -> tuple[bool, str]:
    """Probe isolated WSL2 Fire3D without touching Comfy."""
    if os.name == "nt":
        try:
            probe = subprocess.run(
                ["wsl", "-e", "bash", "-lc", "command -v fire3d || test -x /opt/adept/fire3d/.venv/bin/fire3d"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return False, f"WSL Fire3D probe failed: {exc}"
        detail = _decode_proc(probe.stdout) or _decode_proc(probe.stderr) or "fire3d not installed in WSL"
        if probe.returncode == 0:
            return True, detail or "wsl fire3d"
        return False, detail
    if Path("/usr/local/bin/fire3d").exists() or Path(os.environ.get("ADEPT_FIRE3D_BIN") or "").exists():
        return True, "native fire3d"
    return False, "LOCAL_FIRE3D not installed"


class ReconstructionRuntime:
    def get(self, job_id: str) -> ReconstructionJob | None:
        with _LOCK:
            return _JOBS.get(job_id)

    def start(
        self,
        *,
        project_id: str,
        source_asset_id: str,
        source_type: str = "image",
        provider: str = "LOCAL_FIRE3D",
        work_dir: str | Path | None = None,
    ) -> ReconstructionJob:
        job_id = str(uuid.uuid4())
        if provider == "CLOUD_FIRE3D" and not os.environ.get("ADEPT_FIRE3D_CLOUD_URL"):
            job = ReconstructionJob(
                jobId=job_id,
                projectId=project_id,
                provider="CLOUD_FIRE3D",
                status="unavailable",
                progress=ReconstructionProgress(stage="failed", message="CLOUD_FIRE3D endpoint is not configured.", realEngine=True),
                error="CLOUD_FIRE3D unavailable",
            )
            with _LOCK:
                _JOBS[job_id] = job
            return job

        available, detail = local_fire3d_available() if provider == "LOCAL_FIRE3D" else (True, "cloud")
        job = ReconstructionJob(
            jobId=job_id,
            projectId=project_id,
            provider=provider,  # type: ignore[arg-type]
            status="queued" if available else "unavailable",
            progress=ReconstructionProgress(
                stage="queued" if available else "failed",
                message=detail if available else f"LOCAL_FIRE3D unavailable: {detail}",
                realEngine=True,
            ),
            error="" if available else detail,
        )
        with _LOCK:
            _JOBS[job_id] = job
        if not available:
            return job

        busy, busy_reason = _gpu_busy()
        if busy:
            job.status = "queued"
            job.progress = ReconstructionProgress(
                stage="queued",
                message=f"Waiting for GPU: {busy_reason}. Comfy was not stopped.",
                realEngine=True,
            )
            with _LOCK:
                _JOBS[job_id] = job

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, project_id, source_asset_id, source_type, provider, work_dir),
            daemon=True,
        )
        thread.start()
        return job

    def _update(self, job_id: str, **fields: Any) -> None:
        with _LOCK:
            current = _JOBS.get(job_id)
            if current is None:
                return
            data = current.model_dump()
            data.update(fields)
            _JOBS[job_id] = ReconstructionJob.model_validate(data)

    def _run_job(
        self,
        job_id: str,
        project_id: str,
        source_asset_id: str,
        source_type: str,
        provider: str,
        work_dir: str | Path | None,
    ) -> None:
        root = Path(work_dir or Path(os.environ.get("ADEPT_FIRE3D_WORK") or ".runtime/fire3d-jobs") / job_id)
        root.mkdir(parents=True, exist_ok=True)
        self._update(
            job_id,
            status="running",
            progress=ReconstructionProgress(stage="analyzing", message="Preparing Fire3D single-image layout.", realEngine=True).model_dump(),
        )
        # Isolated official CLI. The Adept adapter writes rgb.jpeg + aligned_pcd.ply
        # then calls `fire3d infer --dataset single_image --skip-render`.
        script = root / "run.json"
        script.write_text(
            json.dumps(
                {
                    "jobId": job_id,
                    "projectId": project_id,
                    "sourceAssetId": source_asset_id,
                    "sourceType": source_type,
                    "provider": provider,
                    "profile": ADEPT_FIRE3D_32GB_PROFILE,
                    "startedAt": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        cmd = os.environ.get("ADEPT_FIRE3D_INFER_CMD")
        if cmd:
            self._update(
                job_id,
                progress=ReconstructionProgress(stage="detecting", message="Running official fire3d infer.", realEngine=True).model_dump(),
            )
            completed = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                self._update(
                    job_id,
                    status="failed",
                    error=(completed.stderr or completed.stdout or "fire3d infer failed")[:2000],
                    progress=ReconstructionProgress(stage="failed", message="Fire3D infer failed.", realEngine=True).model_dump(),
                )
                return
        else:
            # Honest: runtime is queued/available but no infer command was configured
            # and no official Fire3D output exists yet. Do not fake a package.
            example = root / "oriented_bboxes.json"
            if not example.is_file():
                self._update(
                    job_id,
                    status="failed",
                    error=(
                        "LOCAL_FIRE3D is the selected provider, but ADEPT_FIRE3D_INFER_CMD is unset "
                        "and no Fire3D output directory was provided. Install Fire3D in WSL2 and set "
                        "ADEPT_FIRE3D_INFER_CMD. Do not treat this as a reconstructed scene."
                    ),
                    progress=ReconstructionProgress(
                        stage="failed",
                        message="Fire3D native infer is not wired on this host yet.",
                        realEngine=True,
                    ).model_dump(),
                )
                return

        package = normalize_fire3d_output(
            root,
            reconstruction_id=job_id,
            source_asset_id=source_asset_id,
            source_type=source_type,
            provider=provider,
        )
        self._update(
            job_id,
            status="succeeded",
            package=package.model_dump(),
            progress=ReconstructionProgress(
                stage="done",
                objectsDone=len(package.objects),
                objectsTotal=len(package.objects),
                message="Reconstruction package ready.",
                realEngine=True,
            ).model_dump(),
        )
