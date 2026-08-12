"""Product install path for Qwen3-TTS Voice Design / Clone (M3.3i).

Orchestrates: sandbox scaffold → short-path venv → pip qwen-tts → HF weights →
runtime-ready manifest. Does not mark installed=true until models + venv ready.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ...config import settings

ProgressCb = Callable[[str, float, str], None]

COMPONENT_SPECS: dict[str, dict[str, str]] = {
    "qwen_voice_design_17b": {
        "registryId": "m2101-voice-design-021",
        "sourceKey": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "venvName": "m210b-qwen-voice-design-venv",
        "enables": "audio.character_voice.design",
    },
    "qwen_voice_clone_17b": {
        "registryId": "m2101-voice-clone-022",
        "sourceKey": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "venvName": "m210b-qwen-voice-clone-venv",
        "enables": "audio.character_voice.clone",
    },
}

REPO_URL = "https://github.com/QwenLM/Qwen3-TTS"
LICENSE = "See Hugging Face model card + Qwen license terms"


@dataclass
class QwenInstallResult:
    ok: bool
    component_id: str
    registry_id: str
    message: str
    evidence: dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_dir() -> Path:
    return Path(settings.data_dir)


def _sandbox(registry_id: str) -> Path:
    return _data_dir() / "m210b-sandbox" / "providers" / registry_id


def _venv_phys(venv_name: str) -> Path:
    return _data_dir() / venv_name


def _venv_python(venv_phys: Path) -> Path:
    if os.name == "nt":
        return venv_phys / "Scripts" / "python.exe"
    return venv_phys / "bin" / "python"


def _link_venv(sandbox: Path, venv_phys: Path) -> None:
    link = sandbox / "venv"
    if link.exists():
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(venv_phys)],
                check=False,
                capture_output=True,
            )
        else:
            link.symlink_to(venv_phys, target_is_directory=True)
    except Exception:
        pass


def _dir_size(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def _write_manifest(sandbox: Path, data: dict[str, Any]) -> None:
    path = sandbox / "install-manifest.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_manifest(sandbox: Path) -> dict[str, Any]:
    path = sandbox / "install-manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def runtime_ready(component_id: str) -> tuple[bool, dict[str, Any]]:
    spec = COMPONENT_SPECS.get(component_id)
    if not spec:
        return False, {"error": "unknown_component"}
    sandbox = _sandbox(spec["registryId"])
    models = sandbox / "models"
    venv_phys = _venv_phys(spec["venvName"])
    py = _venv_python(venv_phys)
    manifest = _read_manifest(sandbox)
    models_ok = models.is_dir() and any(models.iterdir())
    venv_ok = py.is_file()
    installed_flag = bool(manifest.get("installed"))
    ready = installed_flag and models_ok and venv_ok
    disk_usage = int(manifest.get("diskUsageBytes") or 0) or int(manifest.get("modelsDiskUsageBytes") or 0)
    return ready, {
        "componentId": component_id,
        "registryId": spec["registryId"],
        "sourceKey": spec["sourceKey"],
        "sandbox": str(sandbox),
        "venv": str(venv_phys),
        "venvPython": str(py) if venv_ok else None,
        "modelsDir": str(models),
        "modelsPresent": models_ok,
        "manifestInstalled": installed_flag,
        "ready": ready,
        # Status polling reads this path frequently. Reuse persisted install metadata
        # instead of recursively walking multi-GB model folders on every cold poll.
        "diskUsageBytes": disk_usage,
    }


def scaffold(component_id: str) -> Path:
    spec = COMPONENT_SPECS[component_id]
    sandbox = _sandbox(spec["registryId"])
    for sub in ("models", "output", "cache", "logs"):
        (sandbox / sub).mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(sandbox)
    if not manifest:
        manifest = {
            "installed": False,
            "registryId": spec["registryId"],
            "sourceKey": spec["sourceKey"],
            "repositoryUrl": REPO_URL,
            "modelRepository": f"https://huggingface.co/{spec['sourceKey']}",
            "license": LICENSE,
            "createdAt": _now(),
            "enables": [spec["enables"]],
        }
        _write_manifest(sandbox, manifest)
    return sandbox


def ensure_venv(component_id: str, *, on_progress: ProgressCb | None = None) -> Path:
    spec = COMPONENT_SPECS[component_id]
    sandbox = scaffold(component_id)
    venv_phys = _venv_phys(spec["venvName"])
    if on_progress:
        on_progress("venv", 0.05, f"Preparing venv at {venv_phys}")
    if not venv_phys.exists():
        venv.create(venv_phys, with_pip=True)
    py = _venv_python(venv_phys)
    if not py.is_file():
        raise RuntimeError(f"venv python missing: {py}")
    _link_venv(sandbox, venv_phys)
    return py


def pip_install_runtime(py: Path, *, on_progress: ProgressCb | None = None, cancel_check: Callable[[], bool] | None = None) -> None:
    if on_progress:
        on_progress("dependencies", 0.15, "Upgrading pip/wheel")
    cmds = [
        [str(py), "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"],
        [
            str(py),
            "-m",
            "pip",
            "install",
            "huggingface_hub",
            "soundfile",
            "numpy",
            "qwen-tts",
        ],
    ]
    for cmd in cmds:
        if cancel_check and cancel_check():
            raise RuntimeError("cancelled")
        if on_progress:
            on_progress("dependencies", 0.25, " ".join(cmd[-3:]))
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"pip failed ({proc.returncode}): {(proc.stderr or proc.stdout or '')[:1200]}"
            )


def download_weights(
    component_id: str,
    *,
    on_progress: ProgressCb | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    spec = COMPONENT_SPECS[component_id]
    sandbox = scaffold(component_id)
    models = sandbox / "models"
    models.mkdir(parents=True, exist_ok=True)
    if on_progress:
        on_progress("downloading", 0.4, f"Downloading {spec['sourceKey']} (multi-GB)")

    # Prefer venv huggingface_hub if available
    py = _venv_python(_venv_phys(spec["venvName"]))
    revision: str | None = None
    if py.is_file():
        script = (
            "from huggingface_hub import snapshot_download\n"
            f"p=snapshot_download(repo_id={spec['sourceKey']!r}, local_dir={str(models)!r})\n"
            "print(p)\n"
        )
        proc = subprocess.run([str(py), "-c", script], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"HF snapshot_download failed: {(proc.stderr or proc.stdout or '')[:1200]}"
            )
    else:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=spec["sourceKey"], local_dir=str(models))

    if cancel_check and cancel_check():
        raise RuntimeError("cancelled")

    # Best-effort revision from .cache or refs
    ref = models / ".gitattributes"
    # Try to read HF cache commit if present
    for candidate in models.rglob("refs/main"):
        try:
            revision = candidate.read_text(encoding="utf-8").strip()[:64]
            break
        except Exception:
            pass

    size = _dir_size(models)
    if size < 10_000_000:
        raise RuntimeError(f"Models directory too small ({size} bytes); download incomplete.")
    return {
        "sourceKey": spec["sourceKey"],
        "modelsDir": str(models),
        "diskUsageBytes": size,
        "revision": revision,
        "downloadedAt": _now(),
    }


def finalize_manifest(component_id: str, *, weight_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = COMPONENT_SPECS[component_id]
    sandbox = _sandbox(spec["registryId"])
    ready, detail = runtime_ready(component_id)
    # runtime_ready requires installed flag — check pieces first
    models_ok = detail.get("modelsPresent")
    venv_ok = bool(detail.get("venvPython"))
    manifest = _read_manifest(sandbox)
    manifest.update(
        {
            "registryId": spec["registryId"],
            "sourceKey": spec["sourceKey"],
            "repositoryUrl": REPO_URL,
            "modelRepository": f"https://huggingface.co/{spec['sourceKey']}",
            "license": LICENSE,
            "venvPath": detail.get("venv"),
            "venvPython": detail.get("venvPython"),
            "modelsDir": detail.get("modelsDir"),
            "enables": [spec["enables"]],
            "updatedAt": _now(),
        }
    )
    if weight_meta:
        manifest.update(
            {
                "weightsDownloadedAt": weight_meta.get("downloadedAt"),
                "modelRevision": weight_meta.get("revision"),
                "modelsDiskUsageBytes": weight_meta.get("diskUsageBytes"),
            }
        )
    # Only mark installed when both venv and weights exist
    models = sandbox / "models"
    models_ok = models.is_dir() and any(models.iterdir())
    py = detail.get("venvPython")
    if models_ok and py:
        # Probe import
        probe = subprocess.run(
            [str(py), "-c", "import qwen_tts; print('ok')"],
            capture_output=True,
            text=True,
            check=False,
        )
        manifest["importProbe"] = {
            "code": probe.returncode,
            "stdout": (probe.stdout or "")[:500],
            "stderr": (probe.stderr or "")[:500],
        }
        manifest["installed"] = probe.returncode == 0
        manifest["runtimeReady"] = probe.returncode == 0
    else:
        manifest["installed"] = False
        manifest["runtimeReady"] = False
    manifest["diskUsageBytes"] = (
        int(weight_meta.get("diskUsageBytes") or 0) if weight_meta else int(manifest.get("diskUsageBytes") or 0)
    )
    _write_manifest(sandbox, manifest)
    return manifest


def install_component(
    component_id: str,
    *,
    skip_download: bool = False,
    on_progress: ProgressCb | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> QwenInstallResult:
    if component_id not in COMPONENT_SPECS:
        return QwenInstallResult(
            False, component_id, "", f"Unknown component {component_id}", {}
        )
    spec = COMPONENT_SPECS[component_id]
    evidence: dict[str, Any] = {
        "componentId": component_id,
        "startedAt": _now(),
        "sourceKey": spec["sourceKey"],
        "repositoryUrl": REPO_URL,
        "license": LICENSE,
    }
    try:
        if on_progress:
            on_progress("preparing", 0.02, "Scaffolding sandbox")
        sandbox = scaffold(component_id)
        evidence["sandbox"] = str(sandbox)
        py = ensure_venv(component_id, on_progress=on_progress)
        evidence["venvPython"] = str(py)
        pip_install_runtime(py, on_progress=on_progress, cancel_check=cancel_check)
        weight_meta = None
        models = sandbox / "models"
        if not skip_download or not (models.is_dir() and any(models.iterdir())):
            weight_meta = download_weights(
                component_id, on_progress=on_progress, cancel_check=cancel_check
            )
            evidence["weights"] = weight_meta
        else:
            weight_meta = {
                "downloadedAt": _now(),
                "diskUsageBytes": _dir_size(models),
                "revision": None,
            }
            evidence["weights"] = {**weight_meta, "skipped": True}
        if on_progress:
            on_progress("verifying", 0.9, "Finalizing manifest + import probe")
        manifest = finalize_manifest(component_id, weight_meta=weight_meta)
        evidence["manifest"] = manifest
        evidence["finishedAt"] = _now()
        evidence["diskUsageBytes"] = _dir_size(sandbox) + _dir_size(_venv_phys(spec["venvName"]))
        ok = bool(manifest.get("installed") and manifest.get("runtimeReady"))
        if on_progress:
            on_progress("complete" if ok else "failed", 1.0, "Install complete" if ok else "Install incomplete")
        return QwenInstallResult(
            ok=ok,
            component_id=component_id,
            registry_id=spec["registryId"],
            message="READY" if ok else "INSTALL_INCOMPLETE",
            evidence=evidence,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        evidence["finishedAt"] = _now()
        # Ensure installed stays false on failure
        try:
            sandbox = _sandbox(spec["registryId"])
            m = _read_manifest(sandbox)
            m["installed"] = False
            m["runtimeReady"] = False
            m["lastError"] = str(exc)[:1000]
            m["updatedAt"] = _now()
            _write_manifest(sandbox, m)
        except Exception:
            pass
        return QwenInstallResult(
            ok=False,
            component_id=component_id,
            registry_id=spec["registryId"],
            message=str(exc),
            evidence=evidence,
        )


def uninstall_component(component_id: str) -> dict[str, Any]:
    spec = COMPONENT_SPECS[component_id]
    sandbox = _sandbox(spec["registryId"])
    venv_phys = _venv_phys(spec["venvName"])
    removed: list[str] = []
    if sandbox.exists():
        shutil.rmtree(sandbox, ignore_errors=True)
        removed.append(str(sandbox))
    if venv_phys.exists():
        shutil.rmtree(venv_phys, ignore_errors=True)
        removed.append(str(venv_phys))
    return {"componentId": component_id, "removed": removed, "at": _now()}
