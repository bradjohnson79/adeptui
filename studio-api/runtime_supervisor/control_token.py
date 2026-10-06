"""Local control-plane token. Not a creator setting. Never in VITE_* or git."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from .canonical_config import localappdata_dir, try_load_runtime_config


TOKEN_HEADER = "X-Adept-Runtime-Token"


def token_path() -> Path:
    override = (os.environ.get("ADEPT_RUNTIME_TOKEN_FILE") or "").strip()
    if override:
        return Path(override)
    cfg = try_load_runtime_config()
    if cfg and cfg.stateDir:
        return Path(cfg.stateDir) / "control.token"
    return localappdata_dir() / "control.token"


def _restrict_current_user(path: Path) -> None:
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError:
            return
        return
    user = (os.environ.get("USERNAME") or "").strip()
    if not user:
        return
    try:
        import subprocess

        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(R,W)"],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def read_token() -> str | None:
    path = token_path()
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return raw or None


def ensure_token() -> str:
    existing = read_token()
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    _restrict_current_user(path)
    return token


def token_matches(provided: str | None) -> bool:
    expected = read_token()
    if not expected or not provided:
        return False
    return secrets.compare_digest(provided.strip(), expected)
