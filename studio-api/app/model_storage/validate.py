"""Validate registered model folders and probe drive availability."""

from __future__ import annotations

from pathlib import Path
from typing import Any


STATUSES = (
    "Ready",
    "Ready With Limitations",
    "Runtime Missing",
    "Model Files Incomplete",
    "Unsupported Format",
    "Drive Unavailable",
    "Permission Denied",
)


def validate_registration(path: str, *, runtime_type: str = "unknown") -> dict[str, Any]:
    p = Path(path)
    try:
        exists = p.exists()
    except PermissionError:
        return {
            "status": "Permission Denied",
            "readable": False,
            "exists": False,
            "runtimeAvailable": False,
            "message": "Permission denied when checking this path.",
            "estimates": {},
        }
    except OSError as exc:
        return {
            "status": "Drive Unavailable",
            "readable": False,
            "exists": False,
            "runtimeAvailable": False,
            "message": f"Path unavailable: {exc}",
            "estimates": {},
        }

    if not exists:
        return {
            "status": "Drive Unavailable",
            "readable": False,
            "exists": False,
            "runtimeAvailable": False,
            "message": "Folder not found — drive may be disconnected. Registration kept; use Retry Discovery or Locate Folder.",
            "estimates": {},
            "actions": ["retry_discovery", "locate_folder", "choose_another_model"],
            "silentSwitchForbidden": True,
            "autoRedownloadForbidden": True,
        }

    try:
        readable = os_access_readable(p)
    except PermissionError:
        return {
            "status": "Permission Denied",
            "readable": False,
            "exists": True,
            "runtimeAvailable": False,
            "message": "Path exists but is not readable.",
            "estimates": {},
        }

    if not readable:
        return {
            "status": "Permission Denied",
            "readable": False,
            "exists": True,
            "runtimeAvailable": False,
            "message": "Path exists but is not readable.",
            "estimates": {},
        }

    runtime = (runtime_type or "unknown").lower()
    runtime_ok, runtime_msg = _runtime_available(runtime)
    if runtime == "unknown":
        return {
            "status": "Unsupported Format",
            "readable": True,
            "exists": True,
            "runtimeAvailable": False,
            "message": "Unrecognized model format.",
            "estimates": {},
        }

    incomplete = _files_incomplete(p, runtime)
    if incomplete:
        return {
            "status": "Model Files Incomplete",
            "readable": True,
            "exists": True,
            "runtimeAvailable": runtime_ok,
            "message": incomplete,
            "estimates": _estimates(runtime),
        }

    if not runtime_ok:
        return {
            "status": "Runtime Missing",
            "readable": True,
            "exists": True,
            "runtimeAvailable": False,
            "message": runtime_msg,
            "estimates": _estimates(runtime),
        }

    limitations = runtime in ("onnx", "mlx")
    return {
        "status": "Ready With Limitations" if limitations else "Ready",
        "readable": True,
        "exists": True,
        "runtimeAvailable": True,
        "message": runtime_msg if limitations else "Model folder is ready.",
        "estimates": _estimates(runtime),
        "silentSwitchForbidden": True,
        "autoRedownloadForbidden": True,
    }


def probe_availability(path: str) -> dict[str, Any]:
    return validate_registration(path)


def os_access_readable(p: Path) -> bool:
    import os

    if p.is_dir():
        try:
            next(p.iterdir(), None)
            return True
        except OSError:
            return False
    return os.access(p, os.R_OK)


def _runtime_available(runtime: str) -> tuple[bool, str]:
    if runtime == "ollama":
        try:
            import httpx
            from ..config import settings

            r = httpx.get(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=3.0)
            if r.status_code == 200:
                return True, "Ollama service is reachable."
            return False, f"Ollama responded HTTP {r.status_code}."
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama runtime not reachable: {exc}"
    if runtime in ("gguf", "huggingface", "mlx", "onnx"):
        # Runtime may be external; mark available for registration, limitations disclosed
        return True, f"{runtime} files present — launch via compatible runtime when configured."
    return False, f"No runtime mapped for type '{runtime}'."


def _files_incomplete(p: Path, runtime: str) -> str | None:
    if runtime == "ollama":
        if not (p / "blobs").is_dir() or not (p / "manifests").is_dir():
            return "Ollama store missing blobs/ or manifests/."
        return None
    if runtime == "gguf":
        if p.is_file() and p.suffix.lower() == ".gguf":
            return None
        if p.is_dir() and not list(p.glob("*.gguf")) and not list(p.glob("**/*.gguf")):
            return "No .gguf files found."
        return None
    if runtime == "huggingface":
        if p.is_dir() and not list(p.glob("*.safetensors")) and not (p / "config.json").is_file():
            return "No safetensors or config.json found."
        return None
    return None


def _estimates(runtime: str) -> dict[str, Any]:
    # Honest placeholders — known ranges only, never fabricated certainty
    if runtime == "ollama":
        return {"contextHint": "depends on model", "vramHint": "depends on quant / size"}
    if runtime == "gguf":
        return {"contextHint": "depends on GGUF metadata", "vramHint": "depends on quant"}
    return {}
