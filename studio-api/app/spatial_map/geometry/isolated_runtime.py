"""Python-only isolated runtime helpers. No PowerShell install scripts.

Runtimes live under data/runtimes/{name}. Never contaminate Comfy,
Studio API venv, Adept Bots, or MCP.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any

from ...config import settings


def runtime_root(name: str) -> Path:
    return Path(settings.data_dir) / "runtimes" / name


def source_dir(name: str) -> Path:
    return runtime_root(name) / "src"


def venv_dir(name: str) -> Path:
    return runtime_root(name) / "venv"


def venv_python(name: str) -> Path:
    root = venv_dir(name)
    win = root / "Scripts" / "python.exe"
    unix = root / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    return win if os.name == "nt" else unix


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 600,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=merged,
    )


def clone_github(repo_url: str, destination: Path, *, branch: str | None = None) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (destination / ".git").is_dir():
        pulled = run_command(["git", "-C", str(destination), "fetch", "--depth", "1"], timeout=180)
        return {
            "ok": pulled.returncode == 0,
            "action": "reused",
            "path": str(destination),
            "stderr": (pulled.stderr or "")[:400],
        }
    if destination.exists() and any(destination.iterdir()):
        return {"ok": True, "action": "existing", "path": str(destination)}
    args = ["git", "clone", "--depth", "1"]
    if branch:
        args.extend(["--branch", branch])
    args.extend([repo_url, str(destination)])
    cloned = run_command(args, timeout=300)
    return {
        "ok": cloned.returncode == 0,
        "action": "cloned",
        "path": str(destination),
        "stderr": (cloned.stderr or "")[:800],
        "stdout": (cloned.stdout or "")[:400],
    }


def ensure_venv(name: str) -> Path:
    root = venv_dir(name)
    python = venv_python(name)
    if python.is_file():
        return python
    root.parent.mkdir(parents=True, exist_ok=True)
    venv.create(root, with_pip=True, system_site_packages=False)
    python = venv_python(name)
    if not python.is_file():
        raise RuntimeError(f"Isolated venv python missing for {name}: {python}")
    bootstrap = run_command(
        [str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        timeout=180,
    )
    if bootstrap.returncode != 0:
        raise RuntimeError(f"Failed to bootstrap isolated venv for {name}: {(bootstrap.stderr or '')[:400]}")
    return python


def install_requirements(name: str, requirements: Path) -> dict[str, Any]:
    python = ensure_venv(name)
    if not requirements.is_file():
        return {"ok": False, "message": f"requirements missing: {requirements}"}
    result = run_command(
        [str(python), "-m", "pip", "install", "-r", str(requirements)],
        cwd=requirements.parent,
        timeout=900,
    )
    return {
        "ok": result.returncode == 0,
        "stderr": (result.stderr or "")[:800],
        "python": str(python),
    }


def install_gpu_torch(name: str) -> dict[str, Any]:
    """Install CUDA Torch into the isolated venv. Never silent CPU."""
    python = ensure_venv(name)
    result = run_command(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "torch==2.10.0",
            "--index-url",
            "https://download.pytorch.org/whl/cu130",
        ],
        timeout=1200,
    )
    return {
        "ok": result.returncode == 0,
        "stderr": (result.stderr or "")[-600:],
        "python": str(python),
        "index": "https://download.pytorch.org/whl/cu130",
        "requested": "torch==2.10.0+cu130",
    }


def supervisor_python() -> str:
    """Studio API interpreter — never used as the geometry worker."""
    return sys.executable
