from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ...config import settings
from ...source_manager.persistence import get_assignment, get_source
from .errors import InstallJobError, InstallJobErrorCode
from .requirements import _KNOWN_HUNYUAN_NODES, _live_node_types, resolve_requirements

# Official / recommended Hunyuan ComfyUI node sources (user may override via Source Manager).
_KNOWN_SENSENOVA_NODES = (
    "SenseNovaU1LocalLoader",
    "SenseNovaU1LocalTextToImage",
    "SenseNovaU1LocalImageEdit",
)

DEFAULT_EXTENSION_SOURCES: dict[str, dict[str, str]] = {
    "comfyui_hunyuan_nodes": {
        "packageName": "ComfyUI-HunyuanVideoWrapper",
        "defaultUrl": "https://github.com/kijai/ComfyUI-HunyuanVideoWrapper",
        "provides": ",".join(sorted(_KNOWN_HUNYUAN_NODES)),
    },
    "comfyui_sensenova_nodes": {
        "packageName": "ComfyUI-SenseNova-U1",
        "defaultUrl": "https://github.com/OpenSenseNova/ComfyUI-SenseNova-U1",
        "revision": "v0.2.0",
        "provides": ",".join(_KNOWN_SENSENOVA_NODES),
    },
}


def resolve_custom_nodes_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("STUDIO_COMFY_CUSTOM_NODES") or os.environ.get("COMFY_CUSTOM_NODES")
    if env:
        return Path(env)
    # Prefer sibling of ComfyUI-Shared → Installs tree when present.
    shared_parent = Path(settings.comfy_input_dir).resolve().parent
    desktop_root = shared_parent.parent if shared_parent.name.lower().endswith("shared") else shared_parent
    candidates = [
        desktop_root / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI" / "custom_nodes",
        desktop_root / "ComfyUI" / "custom_nodes",
        Path(settings.comfy_input_dir).resolve().parent.parent / "custom_nodes",
        Path(settings.data_dir) / "comfyui" / "custom_nodes",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    # Default writable location under data dir for managed installs / tests.
    fallback = Path(settings.data_dir) / "comfyui" / "custom_nodes"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def resolve_extension_source(component_id: str, source_url: str | None = None) -> dict[str, Any]:
    meta = DEFAULT_EXTENSION_SOURCES.get(component_id, {})
    assignment = get_assignment(component_id) or {}
    source = get_source(str(assignment.get("sourceId") or "")) or {}
    url = (
        source_url
        or source.get("sourceUrl")
        or meta.get("defaultUrl")
        or ""
    ).strip()
    if not url:
        raise ValueError("A source URL is required before this ComfyUI extension can be installed.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "git"}:
        raise ValueError("Unsupported source URL scheme for ComfyUI extensions.")
    package = meta.get("packageName") or Path(parsed.path).stem.replace(".git", "") or component_id
    return {
        "url": url,
        "revision": source.get("revision") or meta.get("revision"),
        "packageName": package,
        "provider": source.get("provider") or "git",
        "sourceId": source.get("id"),
        "officialDefault": bool(not source_url and not source and meta.get("defaultUrl")),
        "executesCode": True,
        "provides": meta.get("provides") or "",
    }


def preflight_extension(
    component_id: str,
    *,
    source_url: str | None = None,
    install_path: str | None = None,
) -> dict[str, Any]:
    custom_nodes = resolve_custom_nodes_dir(install_path)
    source = resolve_extension_source(component_id, source_url=source_url)
    target = custom_nodes / str(source["packageName"])
    writable = None
    try:
        custom_nodes.mkdir(parents=True, exist_ok=True)
        writable = os.access(custom_nodes, os.W_OK)
    except OSError as exc:
        return {
            "ok": False,
            "customNodesDir": str(custom_nodes),
            "error": str(exc),
        }
    return {
        "ok": bool(writable),
        "customNodesDir": str(custom_nodes),
        "targetDir": str(target),
        "source": source,
        "destinationWritable": writable,
        "executesCode": True,
        "requiresRestart": True,
        "requiredNodes": (
            sorted(_KNOWN_HUNYUAN_NODES)
            if component_id.startswith("comfyui_hunyuan")
            else list(_KNOWN_SENSENOVA_NODES)
            if component_id.startswith("comfyui_sensenova")
            else []
        ),
    }


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def _find_uv_executable() -> str | None:
    candidates = [
        shutil.which("uv"),
        str((Path(os.environ.get("LOCALAPPDATA") or "") / "hermes" / "bin" / "uv.exe")),
        str((Path.home() / "AppData" / "Local" / "hermes" / "bin" / "uv.exe")),
        str((Path.home() / "AppData" / "Roaming" / "uv" / "bin" / "uv.exe")),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def clone_or_update_extension(
    *,
    target_dir: Path,
    source_url: str,
    revision: str | None = None,
) -> dict[str, Any]:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if (target_dir / ".git").is_dir():
        fetch = _run(["git", "fetch", "--all", "--tags"], cwd=target_dir)
        if fetch.returncode != 0:
            return {
                "ok": False,
                "step": "fetch",
                "message": fetch.stderr or fetch.stdout or "git fetch failed",
            }
        if revision:
            checkout = _run(["git", "checkout", revision], cwd=target_dir)
            if checkout.returncode != 0:
                return {
                    "ok": False,
                    "step": "checkout",
                    "message": checkout.stderr or checkout.stdout or "git checkout failed",
                }
        pull = _run(["git", "pull", "--ff-only"], cwd=target_dir)
        return {
            "ok": pull.returncode == 0 or revision is not None,
            "step": "update",
            "message": pull.stdout or pull.stderr or "Extension repository updated.",
            "path": str(target_dir),
        }

    clone_cmd = ["git", "clone", "--depth", "1", source_url, str(target_dir)]
    clone = _run(clone_cmd)
    if clone.returncode != 0:
        # Retry without --depth for hosts that reject shallow clones.
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        clone = _run(["git", "clone", source_url, str(target_dir)])
    if clone.returncode != 0:
        return {
            "ok": False,
            "step": "clone",
            "message": clone.stderr or clone.stdout or "git clone failed",
        }
    if revision:
        checkout = _run(["git", "checkout", revision], cwd=target_dir)
        if checkout.returncode != 0:
            return {
                "ok": False,
                "step": "checkout",
                "message": checkout.stderr or checkout.stdout or "git checkout failed",
            }
    return {
        "ok": True,
        "step": "clone",
        "message": "Extension repository cloned into custom_nodes.",
        "path": str(target_dir),
    }


# Official sensenova-u1 metadata pins torch==2.8.0. A plain `pip install -r`
# previously replaced Comfy's CUDA 2.10.0+cu130 with 2.8.0+cpu. Never let a
# node pack uninstall or replace the Comfy torch stack.
_PROTECTED_TORCH_PACKAGES = frozenset({"torch", "torchvision", "torchaudio"})
_FILTERED_REQUIREMENTS_NAME = "requirements.adept-no-torch.txt"


def _requirements_mentions_torch_stack(requirements: Path) -> bool:
    """Any torch / torchvision / torchaudio pin can replace Comfy CUDA torch."""
    text = requirements.read_text(encoding="utf-8", errors="ignore").lower()
    for raw in text.splitlines():
        if is_protected_torch_requirement(raw):
            return True
    return "sensenova-u1" in text


def pip_should_isolate_torch(component_id: str = "", requirements: Path | None = None) -> bool:
    if "sensenova" in str(component_id or "").lower():
        return True
    if requirements is not None and requirements.is_file():
        return _requirements_mentions_torch_stack(requirements)
    return False


def _requirement_package_name(line: str) -> str:
    raw = line.split("#", 1)[0].strip()
    if not raw or raw.startswith("-"):
        return ""
    token = raw.split()[0]
    if token.lower() in {"-r", "-c", "-e", "--requirement", "--constraint", "--editable"}:
        return ""
    name = token.split("[", 1)[0]
    for sep in ("===", "==", "!=", "<=", ">=", "~=", "<", ">"):
        if sep in name:
            name = name.split(sep, 1)[0]
            break
    return name.strip().lower()


def is_protected_torch_requirement(line: str) -> bool:
    return _requirement_package_name(line) in _PROTECTED_TORCH_PACKAGES


def write_torch_isolated_requirements(source: Path, destination: Path | None = None) -> Path:
    """Write a requirements file with torch/torchvision/torchaudio lines removed."""
    dest = destination or (source.parent / _FILTERED_REQUIREMENTS_NAME)
    kept: list[str] = []
    for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
        if is_protected_torch_requirement(line):
            continue
        kept.append(line)
    dest.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")
    return dest


def prepare_extension_requirements(requirements: Path, *, isolate: bool) -> Path:
    if not isolate:
        return requirements
    return write_torch_isolated_requirements(requirements)


def build_extension_pip_install_cmd(
    python: str,
    requirements: Path,
    *,
    component_id: str = "",
    extra_prefix: list[str] | None = None,
) -> list[str]:
    """Build a pip/uv-compatible install command that cannot replace Comfy CUDA torch."""
    isolate = pip_should_isolate_torch(component_id, requirements)
    req_file = prepare_extension_requirements(requirements, isolate=isolate)
    cmd = [python, "-m", "pip", "install"]
    if extra_prefix:
        cmd.extend(extra_prefix)
    if isolate:
        cmd.append("--no-deps")
    cmd.extend(["-r", str(req_file)])
    return cmd


def install_extension_dependencies(target_dir: Path, *, component_id: str = "") -> dict[str, Any]:
    requirements = target_dir / "requirements.txt"
    if not requirements.is_file():
        return {"ok": True, "skipped": True, "message": "No requirements.txt found."}
    python = os.environ.get("STUDIO_COMFY_PYTHON") or os.environ.get("COMFY_PYTHON") or "python"
    isolate = pip_should_isolate_torch(component_id, requirements)
    req_file = prepare_extension_requirements(requirements, isolate=isolate)
    method = "pip_no_deps" if isolate else "pip"
    result = _run(build_extension_pip_install_cmd(python, requirements, component_id=component_id), cwd=target_dir)
    output = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
    if result.returncode != 0 and (
        "externally managed" in output or "externally-managed-environment" in output
    ):
        # Comfy Desktop often uses a uv-managed Python where plain pip is blocked by
        # PEP 668. Fall back to uv's system install path instead of failing closed.
        extra = ["--system"]
        if isolate:
            extra.append("--no-deps")
        method = "uv_pip_system_no_deps" if isolate else "uv_pip_system"
        result = _run(
            [python, "-m", "uv", "pip", "install", *extra, "-r", str(req_file)],
            cwd=target_dir,
        )
        if result.returncode != 0 and "no module named uv" in f"{result.stdout or ''}\n{result.stderr or ''}".lower():
            uv_exe = _find_uv_executable()
            if uv_exe:
                uv_extra = ["--python", python]
                if isolate:
                    uv_extra.append("--no-deps")
                method = "uv_cli_python_no_deps" if isolate else "uv_cli_python"
                result = _run(
                    [uv_exe, "pip", "install", *uv_extra, "-r", str(req_file)],
                    cwd=target_dir,
                )
    return {
        "ok": result.returncode == 0,
        "skipped": False,
        "message": result.stdout or result.stderr or "Dependency install finished.",
        "returncode": result.returncode,
        "method": method,
        "requirementsFile": str(req_file),
        "torchIsolated": isolate,
    }


def probe_required_nodes(required_nodes: list[str] | None = None) -> dict[str, Any]:
    needed = list(required_nodes or sorted(_KNOWN_HUNYUAN_NODES))
    live = _live_node_types()
    if live is None:
        return {
            "ok": False,
            "available": False,
            "required": needed,
            "detected": [],
            "missing": needed,
            "message": "ComfyUI node catalogue is unavailable. Start or restart ComfyUI, then verify again.",
        }
    detected = sorted(node for node in needed if node in live)
    missing = sorted(node for node in needed if node not in live)
    return {
        "ok": not missing,
        "available": True,
        "required": needed,
        "detected": detected,
        "missing": missing,
        "detectedCount": len(detected),
        "requiredCount": len(needed),
        "message": (
            f"{len(detected)} of {len(needed)} nodes detected"
            if needed
            else "No required nodes listed."
        ),
    }


def restart_comfyui_best_effort() -> dict[str, Any]:
    """Attempt a managed restart; always honest about whether nodes were re-probed."""
    attempts: list[dict[str, Any]] = []
    # Docker / managed runtime restart when a Comfy runtime is registered.
    try:
        from ...docker_runtime.manager import get_manager

        manager = get_manager()
        for runtime in getattr(manager, "list", lambda: [])() or []:
            runtime_id = str(runtime.get("id") or runtime.get("runtimeId") or "")
            if not runtime_id:
                continue
            if "comfy" not in runtime_id.lower() and runtime.get("kind") not in {"comfyui", "comfy"}:
                continue
            result = manager.restart(runtime_id)
            attempts.append({"runtimeId": runtime_id, "result": result})
            if result.get("ok"):
                return {"ok": True, "method": "docker_runtime", "attempts": attempts}
    except Exception as exc:  # noqa: BLE001
        attempts.append({"method": "docker_runtime", "error": str(exc)})

    # Soft signal via Comfy HTTP — many builds ignore this; we still report honestly.
    try:
        import httpx

        url = str(settings.comfy_url).rstrip("/") + "/interrupt"
        response = httpx.post(url, timeout=5.0)
        attempts.append({"method": "http_interrupt", "status": response.status_code})
    except Exception as exc:  # noqa: BLE001
        attempts.append({"method": "http_interrupt", "error": str(exc)})

    return {
        "ok": False,
        "method": "manual_required",
        "message": "ComfyUI must be restarted before new nodes become available.",
        "attempts": attempts,
    }


def extension_error(code: InstallJobErrorCode, message: str, **kwargs: Any) -> InstallJobError:
    return InstallJobError(
        code=code,
        userMessage=message,
        message=message,
        retryable=True,
        repairable=True,
        **kwargs,
    )


def capability_ids_for_extension(component_id: str) -> list[str]:
    if component_id.startswith("comfyui_hunyuan"):
        return ["hunyuan15", "hunyuan_video_15", "hunyuan_video_13b"]
    return [component_id]


def refresh_capabilities_after_probe() -> None:
    try:
        from ...capabilities.service import invalidate_cache

        invalidate_cache()
    except Exception:
        return


def summarize_capability_shift(component_id: str) -> dict[str, Any]:
    shifts = []
    for capability_id in capability_ids_for_extension(component_id):
        resolution = resolve_requirements(capability_id)
        shifts.append(
            {
                "capabilityId": capability_id,
                "status": resolution.status,
                "missingNodeTypes": resolution.missing_node_types,
            }
        )
    return {"capabilities": shifts}
