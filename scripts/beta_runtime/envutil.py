"""Load Beta env files and resolve repo paths."""

from __future__ import annotations

import os
from pathlib import Path


RUNTIME_TAG = "ADEPT_UI_BETA_RUNTIME"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_data_dir(raw: str | None, root: Path | None = None) -> Path:
    root = root or repo_root()
    value = (raw or os.environ.get("STUDIO_DATA_DIR") or "data").strip()
    p = Path(value)
    if not p.is_absolute():
        p = (root / p).resolve()
    return p


def load_env_file(path: Path, *, override: bool = False) -> dict[str, str]:
    """Parse KEY=VALUE lines into os.environ. Returns applied map."""
    applied: dict[str, str] = {}
    if not path.is_file():
        return applied
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        if not override and key in os.environ and str(os.environ.get(key, "")).strip() != "":
            continue
        os.environ[key] = val
        applied[key] = val
    return applied


def load_beta_env(root: Path | None = None) -> dict[str, str]:
    root = root or repo_root()
    applied: dict[str, str] = {}
    # Beta contract wins over leftover shell/Playwright ports (e.g. STUDIO_API_PORT=8793).
    applied.update(load_env_file(root / "config" / "beta-local.env", override=True))
    applied.update(load_env_file(root / "config" / "beta-local.local.env", override=True))
    # Always stamp Beta tag
    os.environ[RUNTIME_TAG] = "1"
    # Resolve relative data dir to absolute for child processes
    data = resolve_data_dir(os.environ.get("STUDIO_DATA_DIR"), root)
    os.environ["STUDIO_DATA_DIR"] = str(data)
    # Strip fixture / e2e modes for production Beta
    for forbidden in (
        "STUDIO_E2E",
        "ADEPT_M29_FIXTURE_MODE",
        "ADEPT_M28_FIXTURE_MODE",
    ):
        if os.environ.get(forbidden, "").strip() in ("1", "true", "TRUE", "yes", "YES"):
            os.environ[forbidden] = "0"
    return applied


def runtime_dirs(root: Path | None = None) -> dict[str, Path]:
    root = root or repo_root()
    data = resolve_data_dir(os.environ.get("STUDIO_DATA_DIR"), root)
    beta = data / "runtime" / "beta"
    logs = data / "runtime" / "logs" / "beta"
    pids = beta / "pids"
    for d in (beta, logs, pids):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "root": root,
        "data": data,
        "beta": beta,
        "logs": logs,
        "pids": pids,
        "status": beta / "status.json",
        "shutdown": beta / "shutdown.flag",
        "dist": root / "studio-web" / "dist",
        "api_dir": root / "studio-api",
        "venv_python": root
        / "studio-api"
        / ".venv"
        / ("Scripts" if os.name == "nt" else "bin")
        / ("python.exe" if os.name == "nt" else "python"),
    }
