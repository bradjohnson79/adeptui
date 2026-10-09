"""ComfyUI is a manual prerequisite. Adept UI detects and checks it. It does not install it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import load_state, update_state

OFFICIAL_COMFY_DOWNLOAD_URL = "https://www.comfy.org/download"


def comfy_main_file(folder: Path) -> Path | None:
    """The ComfyUI entry file inside a folder the user already installed."""
    try:
        folder = folder.expanduser()
    except OSError:
        return None
    if not folder.is_dir():
        return None
    nested = folder / "ComfyUI" / "main.py"
    if nested.is_file():
        return nested
    direct = folder / "main.py"
    if direct.is_file():
        return direct
    return None


def saved_comfy_install_root() -> str | None:
    raw = str(load_state().get("comfy_install_root") or "").strip()
    if not raw or "://" in raw:
        return None
    folder = Path(raw)
    if comfy_main_file(folder) is None:
        return None
    return str(folder)


def _health() -> tuple[bool, str, str | None]:
    from .diagnostics import invalidate_verify_cache, verify_component
    from .status import invalidate_status_cache

    invalidate_verify_cache("comfyui")
    invalidate_status_cache()
    verification = verify_component("comfyui")
    healthy = bool(verification.healthy) and not verification.issue_code
    return healthy, str(verification.summary or ""), verification.path


def rescan_comfy() -> dict[str, Any]:
    """Read health only. This does not download, launch, or modify ComfyUI."""
    healthy, summary, path = _health()
    root = saved_comfy_install_root()
    installed = bool(root and comfy_main_file(Path(root)))
    if healthy:
        message = "ComfyUI is running."
    elif installed:
        message = (
            "ComfyUI is installed, but it is not running. Launch it, then re-scan. "
            "Adept UI will not start it."
        )
    else:
        message = (
            "ComfyUI was not found. Install it from the official download, launch it, "
            "then re-scan or connect the folder."
        )
    return {
        "healthy": healthy,
        "installed": installed,
        "path": path,
        "downloadUrl": OFFICIAL_COMFY_DOWNLOAD_URL,
        "summary": summary,
        "message": message,
    }


def connect_existing_comfy(raw_path: str) -> dict[str, Any]:
    """Remember a ComfyUI folder the user already installed, then check whether it is running."""
    text = str(raw_path or "").strip()
    if not text or "://" in text:
        raise ValueError("Choose a ComfyUI folder on this computer.")
    folder = Path(text).expanduser()
    main = comfy_main_file(folder)
    if main is None:
        raise ValueError(
            "That folder does not contain ComfyUI. Install it from the official download, "
            "then choose the ComfyUI folder."
        )
    install_root = str(main.parent.resolve())
    before = main.read_bytes()

    def mutate(latest: dict[str, Any]) -> None:
        latest["comfy_install_root"] = install_root

    update_state(mutate)
    if main.read_bytes() != before:
        raise RuntimeError("Connecting ComfyUI must not change its files.")
    healthy, summary, path = _health()
    if healthy:
        message = "ComfyUI is running."
    else:
        message = (
            "That folder contains ComfyUI. Launch it, then choose Re-scan ComfyUI. "
            "Adept UI will not start it."
        )
    return {
        "ok": True,
        "healthy": healthy,
        "installed": True,
        "path": path or install_root,
        "downloadUrl": OFFICIAL_COMFY_DOWNLOAD_URL,
        "summary": summary,
        "message": message,
    }
