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
DEFAULT_EXTENSION_SOURCES: dict[str, dict[str, str]] = {
    "comfyui_hunyuan_nodes": {
        "packageName": "ComfyUI-HunyuanVideoWrapper",
        "defaultUrl": "https://github.com/kijai/ComfyUI-HunyuanVideoWrapper",
        "provides": ",".join(sorted(_KNOWN_HUNYUAN_NODES)),
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
        "requiredNodes": sorted(_KNOWN_HUNYUAN_NODES) if component_id.startswith("comfyui_hunyuan") else [],
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


def install_extension_dependencies(target_dir: Path) -> dict[str, Any]:
    requirements = target_dir / "requirements.txt"
    if not requirements.is_file():
        return {"ok": True, "skipped": True, "message": "No requirements.txt found."}
    python = os.environ.get("STUDIO_COMFY_PYTHON") or os.environ.get("COMFY_PYTHON") or "python"
    method = "pip"
    result = _run([python, "-m", "pip", "install", "-r", str(requirements)], cwd=target_dir)
    output = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
    if result.returncode != 0 and (
        "externally managed" in output or "externally-managed-environment" in output
    ):
        # Comfy Desktop often uses a uv-managed Python where plain pip is blocked by
        # PEP 668. Fall back to uv's system install path instead of failing closed.
        method = "uv_pip_system"
        result = _run(
            [python, "-m", "uv", "pip", "install", "--system", "-r", str(requirements)],
            cwd=target_dir,
        )
        if result.returncode != 0 and "no module named uv" in f"{result.stdout or ''}\n{result.stderr or ''}".lower():
            uv_exe = _find_uv_executable()
            if uv_exe:
                method = "uv_cli_python"
                result = _run(
                    [uv_exe, "pip", "install", "--python", python, "-r", str(requirements)],
                    cwd=target_dir,
                )
    return {
        "ok": result.returncode == 0,
        "skipped": False,
        "message": result.stdout or result.stderr or "Dependency install finished.",
        "returncode": result.returncode,
        "method": method,
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
