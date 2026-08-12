"""Docker / WSL2 / NVIDIA Container Toolkit platform detection."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 127, "", str(exc)


def detect_platform() -> dict[str, Any]:
    docker_bin = shutil.which("docker")
    code, out, err = _run(["docker", "info", "--format", "{{.ServerVersion}}"]) if docker_bin else (127, "", "docker not found")
    daemon_ok = code == 0 and bool(out)
    version = out if daemon_ok else None

    # WSL 2 (Windows)
    wsl_ok = False
    if os.name == "nt":
        wsl_code, wsl_out, _ = _run(["wsl", "-l", "-v"])
        wsl_ok = wsl_code == 0 and ("Version 2" in wsl_out or "VERSION 2" in wsl_out.upper() or "2" in wsl_out)

    # NVIDIA Container Toolkit / GPU in docker
    nct_code, nct_out, _ = _run(["docker", "info", "--format", "{{json .Runtimes}}"]) if daemon_ok else (127, "", "")
    nvidia_runtime = "nvidia" in (nct_out or "").lower()

    host_gpu = False
    gpu_model = None
    smi_code, smi_out, _ = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if smi_code == 0 and smi_out:
        host_gpu = True
        gpu_model = smi_out.splitlines()[0].strip()

    e2e = os.environ.get("STUDIO_E2E", "").strip() in {"1", "true", "TRUE", "yes"}
    simulate = os.environ.get("ADEPT_DOCKER_RUNTIME_SIMULATE", "").strip() in {"1", "true", "TRUE", "yes"} or (
        e2e and not daemon_ok
    )

    return {
        "dockerBinary": bool(docker_bin),
        "daemonRunning": daemon_ok,
        "dockerVersion": version,
        "wsl2": wsl_ok if os.name == "nt" else None,
        "nvidiaContainerToolkit": nvidia_runtime,
        "hostGpuVisible": host_gpu,
        "gpuModel": gpu_model,
        "simulate": simulate,
        "error": None if daemon_ok or simulate else (err or "Docker daemon unavailable"),
        "readyForInstall": bool(daemon_ok or simulate),
    }
