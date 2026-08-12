"""DockerRuntimeManager — all daemon ops go through here (never React)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from typing import Any, Optional

from .contracts import DockerRuntimeDescriptor, RuntimeLifecycleState
from .platform import detect_platform
from .registry import get_runtime, upsert_runtime


def _run(cmd: list[str], timeout: float = 120.0) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 127, "", str(exc)


class DockerRuntimeManager:
    def __init__(self) -> None:
        self._sim_containers: dict[str, dict[str, Any]] = {}

    def platform(self) -> dict[str, Any]:
        return detect_platform()

    def _simulate(self) -> bool:
        return bool(self.platform().get("simulate"))

    def pull_image(self, image: str) -> dict[str, Any]:
        if self._simulate():
            digest = "sha256:" + hashlib.sha256(image.encode()).hexdigest()
            return {"ok": True, "image": image, "digest": digest, "simulated": True}
        code, out, err = _run(["docker", "pull", image], timeout=600)
        digest = None
        if code == 0:
            ic, iout, _ = _run(["docker", "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"])
            if ic == 0 and iout:
                digest = iout.split("@")[-1] if "@" in iout else iout
        return {"ok": code == 0, "image": image, "digest": digest, "stdout": out, "stderr": err}

    def create_container(
        self,
        *,
        runtime_id: str,
        image: str,
        internal_port: int,
        host_port: Optional[int] = None,
        env: Optional[dict[str, str]] = None,
        mounts: Optional[list[tuple[str, str, str]]] = None,
        gpu: bool = True,
    ) -> dict[str, Any]:
        host_port = host_port or self._allocate_port(internal_port)
        if self._simulate():
            cid = f"sim-{uuid.uuid4().hex[:12]}"
            self._sim_containers[runtime_id] = {
                "id": cid,
                "image": image,
                "hostPort": host_port,
                "state": "created",
                "gpu": gpu,
            }
            return {"ok": True, "containerId": cid, "hostPort": host_port, "simulated": True}

        cmd = [
            "docker",
            "create",
            "--name",
            f"adept-rt-{runtime_id}"[:63],
            "-p",
            f"{host_port}:{internal_port}",
            "--restart",
            "unless-stopped",
        ]
        if gpu:
            cmd.extend(["--gpus", "all"])
        for k, v in (env or {}).items():
            cmd.extend(["-e", f"{k}={v}"])
        for host, container, mode in mounts or []:
            flag = "ro" if mode == "read_only" else "rw"
            cmd.extend(["-v", f"{host}:{container}:{flag}"])
        cmd.append(image)
        code, out, err = _run(cmd, timeout=120)
        return {
            "ok": code == 0,
            "containerId": out if code == 0 else None,
            "hostPort": host_port,
            "stderr": err,
        }

    def start(self, runtime_id: str) -> dict[str, Any]:
        desc = get_runtime(runtime_id)
        if not desc:
            return {"ok": False, "error": "runtime_not_found"}
        if desc.classification == "core_mandatory" and desc.executionClass == "native_local":
            desc.lifecycle = "running"
            desc.healthOk = True
            upsert_runtime(desc)
            return {"ok": True, "lifecycle": "running", "native": True}

        if self._simulate():
            sim = self._sim_containers.get(runtime_id) or {"id": desc.containerId or f"sim-{runtime_id}"}
            sim["state"] = "running"
            self._sim_containers[runtime_id] = sim
            desc.lifecycle = "running"
            desc.containerId = sim["id"]
            desc.healthOk = True
            desc.gpuReady = bool(sim.get("gpu"))
            upsert_runtime(desc)
            return {"ok": True, "lifecycle": "running", "simulated": True}

        if not desc.containerId:
            return {"ok": False, "error": "container_missing"}
        code, _, err = _run(["docker", "start", desc.containerId])
        desc.lifecycle = "running" if code == 0 else "error"
        desc.lastError = None if code == 0 else err
        upsert_runtime(desc)
        return {"ok": code == 0, "lifecycle": desc.lifecycle, "stderr": err}

    def stop(self, runtime_id: str) -> dict[str, Any]:
        desc = get_runtime(runtime_id)
        if not desc:
            return {"ok": False, "error": "runtime_not_found"}
        if desc.classification == "core_mandatory" and desc.executionClass == "native_local":
            return {"ok": False, "error": "core_stop_restricted", "lifecycle": desc.lifecycle}

        if self._simulate():
            sim = self._sim_containers.get(runtime_id)
            if sim:
                sim["state"] = "stopped"
            desc.lifecycle = "stopped"
            desc.healthOk = False
            upsert_runtime(desc)
            return {"ok": True, "lifecycle": "stopped", "simulated": True}

        if not desc.containerId:
            return {"ok": False, "error": "container_missing"}
        code, _, err = _run(["docker", "stop", desc.containerId])
        desc.lifecycle = "stopped" if code == 0 else "error"
        desc.healthOk = False
        desc.lastError = None if code == 0 else err
        upsert_runtime(desc)
        return {"ok": code == 0, "lifecycle": desc.lifecycle, "stderr": err}

    def restart(self, runtime_id: str) -> dict[str, Any]:
        stop = self.stop(runtime_id)
        if not stop.get("ok") and stop.get("error") not in {None, "core_stop_restricted"}:
            # allow restart of optional even if already stopped
            if stop.get("error") not in {"container_missing"}:
                pass
        return self.start(runtime_id)

    def remove_container(self, runtime_id: str) -> dict[str, Any]:
        desc = get_runtime(runtime_id)
        if not desc:
            return {"ok": False, "error": "runtime_not_found"}
        if desc.classification == "core_mandatory":
            return {"ok": False, "error": "core_mandatory_uninstall_blocked"}
        if self._simulate():
            self._sim_containers.pop(runtime_id, None)
            desc.containerId = None
            desc.lifecycle = "absent"
            upsert_runtime(desc)
            return {"ok": True, "simulated": True}
        if desc.containerId:
            _run(["docker", "rm", "-f", desc.containerId])
        desc.containerId = None
        desc.lifecycle = "absent"
        upsert_runtime(desc)
        return {"ok": True}

    def remove_image(self, image: str) -> dict[str, Any]:
        if self._simulate():
            return {"ok": True, "simulated": True}
        code, out, err = _run(["docker", "rmi", image])
        return {"ok": code == 0, "stdout": out, "stderr": err}

    def logs(self, runtime_id: str, *, tail: int = 200) -> dict[str, Any]:
        desc = get_runtime(runtime_id)
        if not desc:
            return {"ok": False, "lines": [], "error": "runtime_not_found"}
        if self._simulate() or desc.executionClass == "native_local":
            return {
                "ok": True,
                "lines": [f"[adept] runtime={runtime_id} lifecycle={desc.lifecycle} health={desc.healthOk}"],
                "simulated": self._simulate(),
            }
        if not desc.containerId:
            return {"ok": False, "lines": [], "error": "container_missing"}
        code, out, err = _run(["docker", "logs", "--tail", str(tail), desc.containerId])
        lines = (out or err or "").splitlines()
        return {"ok": code == 0, "lines": lines}

    def inspect(self, runtime_id: str) -> dict[str, Any]:
        desc = get_runtime(runtime_id)
        if not desc:
            return {"ok": False, "error": "runtime_not_found"}
        return {"ok": True, "runtime": desc.model_dump(mode="json"), "platform": self.platform()}

    def _allocate_port(self, internal: int) -> int:
        # Deterministic offset band 19000+
        return 19000 + (internal % 1000)


_MANAGER: Optional[DockerRuntimeManager] = None


def get_manager() -> DockerRuntimeManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = DockerRuntimeManager()
    return _MANAGER
