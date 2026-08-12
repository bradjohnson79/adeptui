"""Law 26 GPU preflight for Docker runtimes — host + in-container proof."""

from __future__ import annotations

import subprocess
from typing import Any

from .contracts import RuntimeGpuStatus
from .manager import get_manager
from .platform import detect_platform
from .registry import get_runtime, upsert_runtime


def _run(cmd: list[str], timeout: float = 20.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or p.stderr or "").strip()
    except Exception as exc:
        return 127, str(exc)


def check_gpu(runtime_id: str) -> RuntimeGpuStatus:
    plat = detect_platform()
    desc = get_runtime(runtime_id)
    evidence: dict[str, Any] = {"platform": {k: plat.get(k) for k in ("daemonRunning", "nvidiaContainerToolkit", "simulate")}}
    host = bool(plat.get("hostGpuVisible"))
    mgr = get_manager()

    if not desc:
        return RuntimeGpuStatus(hostGpuVisible=host, evidence=evidence)

    if desc.executionClass == "native_local":
        # Native path uses host CUDA (Law 26 audio/video patterns)
        cuda = host
        status = RuntimeGpuStatus(
            hostGpuVisible=host,
            containerGpuVisible=False,
            cudaAvailable=cuda,
            frameworkAccelerator=cuda,
            gpuModel=plat.get("gpuModel"),
            cpuFallback=False,
            evidence={**evidence, "path": "native_host"},
        )
        desc.gpuReady = bool(cuda)
        upsert_runtime(desc)
        return status

    if mgr._simulate() or plat.get("simulate"):  # noqa: SLF001
        ready = desc.lifecycle == "running" and host
        status = RuntimeGpuStatus(
            hostGpuVisible=host,
            containerGpuVisible=ready,
            cudaAvailable=ready,
            frameworkAccelerator=ready,
            gpuModel=plat.get("gpuModel") or "Simulated GPU",
            cpuFallback=False,
            evidence={**evidence, "path": "simulated_container", "note": "framework_accelerator_assumed_in_simulate"},
        )
        desc.gpuReady = ready
        upsert_runtime(desc)
        return status

    container_gpu = False
    cuda = False
    framework = False
    if desc.containerId and desc.lifecycle == "running":
        code, out = _run(
            ["docker", "exec", desc.containerId, "nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]
        )
        container_gpu = code == 0 and bool(out)
        evidence["nvidiaSmi"] = out[:200]
        # Framework proof (torch)
        tcode, tout = _run(
            [
                "docker",
                "exec",
                desc.containerId,
                "python",
                "-c",
                "import torch; print(torch.cuda.is_available(), torch.version.cuda)",
            ]
        )
        if tcode == 0 and "True" in tout:
            cuda = True
            framework = True
            evidence["torch"] = tout[:200]
        else:
            evidence["torch"] = tout[:200] or "torch_probe_failed"
            # Device nodes alone are insufficient
            if container_gpu and not framework:
                evidence["warning"] = "gpu_devices_visible_but_framework_not_accelerated"

    status = RuntimeGpuStatus(
        hostGpuVisible=host,
        containerGpuVisible=container_gpu,
        cudaAvailable=cuda,
        frameworkAccelerator=framework,
        gpuModel=plat.get("gpuModel"),
        cpuFallback=False,
        evidence=evidence,
    )
    desc.gpuReady = bool(framework and container_gpu)
    if not desc.gpuReady and desc.lifecycle == "running":
        desc.readiness = "requires_repair"
    upsert_runtime(desc)
    return status
