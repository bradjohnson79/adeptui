"""Discover repo root and executable paths. No PowerShell."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    repo_root: Path
    studio_api_dir: Path
    studio_api_python: Path | None
    comfy_install_root: Path | None
    comfy_root: Path | None
    comfy_python: Path | None
    comfy_main: Path | None
    comfy_shared_paths: Path | None
    comfy_input_dir: Path
    comfy_output_dir: Path
    cloudflared: Path | None
    tunnel_config: Path | None
    tunnel_name: str
    ollama: Path | None
    logs_dir: Path


def repo_root_from(start: Path | None = None) -> Path:
    """Walk up until studio-api/app and studio-api/.venv/Scripts/python.exe exist."""
    cursor = (start or Path(__file__).resolve()).resolve()
    if cursor.is_file():
        cursor = cursor.parent
    while True:
        api = cursor / "studio-api"
        py = api / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = api / ".venv" / "bin" / "python"
        if (api / "app").is_dir() and py.exists():
            return cursor
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    # Fallback: this file lives at studio-api/runtime_supervisor/paths.py
    here = Path(__file__).resolve().parents[2]
    return here


def _first_existing(*candidates: Path) -> Path | None:
    for path in candidates:
        if path and path.exists():
            return path
    return None


def _discover_comfy() -> tuple[Path | None, Path | None, Path | None, Path | None]:
    local = os.environ.get("LOCALAPPDATA") or ""
    desktop_root = Path(local) / "Comfy-Desktop" / "ComfyUI-Installs" if local else None
    if desktop_root and desktop_root.is_dir():
        for install in sorted(desktop_root.iterdir()):
            main_py = install / "ComfyUI" / "main.py"
            venv_py = install / "ComfyUI" / ".venv" / "Scripts" / "python.exe"
            if not venv_py.exists():
                venv_py = install / "ComfyUI" / ".venv" / "bin" / "python"
            if main_py.exists() and venv_py.exists():
                return install, install / "ComfyUI", venv_py, main_py
    return None, None, None, None


def discover_paths(repo: Path | None = None) -> RuntimePaths:
    root = repo or repo_root_from()
    api_dir = root / "studio-api"
    api_py = api_dir / ".venv" / "Scripts" / "python.exe"
    if not api_py.exists():
        api_py = api_dir / ".venv" / "bin" / "python"
    install_root, comfy_root, comfy_py, comfy_main = _discover_comfy()
    launch = os.environ.get("ADEPT_COMFY_LAUNCH", "").strip()
    if not comfy_py and launch:
        # ADEPT_COMFY_LAUNCH is a leftover second launcher. Prefer Desktop.
        # Only used when Desktop install is absent.
        launch_path = Path(launch)
        if launch_path.exists():
            comfy_py = launch_path
    appdata = os.environ.get("APPDATA") or ""
    shared = Path(appdata) / "Comfy Desktop" / "shared_model_paths.yaml" if appdata else None
    shared_base = Path(local_appdata()) / "Comfy-Desktop" / "ComfyUI-Shared"
    cf = shutil.which("cloudflared")
    cf_path = Path(cf) if cf else _first_existing(
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "cloudflared" / "cloudflared.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "cloudflared" / "cloudflared.exe",
    )
    ol = shutil.which("ollama")
    ol_path = Path(ol) if ol else _first_existing(
        Path(local_appdata()) / "Programs" / "Ollama" / "ollama.exe",
    )
    from .constants import TUNNEL_NAME

    return RuntimePaths(
        repo_root=root,
        studio_api_dir=api_dir,
        studio_api_python=api_py if api_py.exists() else None,
        comfy_install_root=install_root,
        comfy_root=comfy_root,
        comfy_python=comfy_py,
        comfy_main=comfy_main,
        comfy_shared_paths=shared if shared and shared.exists() else None,
        comfy_input_dir=shared_base / "input",
        comfy_output_dir=shared_base / "output",
        cloudflared=cf_path,
        tunnel_config=(root / "config" / "cloudflared" / "adept-ui-beta-tunnel.yml")
        if (root / "config" / "cloudflared" / "adept-ui-beta-tunnel.yml").exists()
        else None,
        tunnel_name=os.environ.get("ADEPT_TUNNEL_NAME") or TUNNEL_NAME,
        ollama=ol_path,
        logs_dir=root / "logs" / "runtime" / "supervisor",
    )


def local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))
