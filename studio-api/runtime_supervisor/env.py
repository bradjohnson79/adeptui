"""Load Studio/runtime env files without PowerShell.

Order (later overrides earlier):
  config/beta-local.env
  config/beta-local.local.env
  <repo>/.env
  <repo>/.env.local

Called by serve / watch / cli / ensure / studio_api spawn so feature flags
(e.g. STUDIO_FEATURE_CHARACTER_IDENTITY_V1) survive restarts.
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    applied: dict[str, str] = {}
    if not path.is_file():
        return applied
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        eq = line.find("=")
        if eq < 1:
            continue
        key = line[:eq].strip()
        val = line[eq + 1 :].strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        applied[key] = val
    return applied


def load_beta_env(repo_root: Path) -> dict[str, str]:
    """Load canonical env files into os.environ. Returns applied key->value."""
    root = Path(repo_root)
    applied: dict[str, str] = {}
    for path in (
        root / "config" / "beta-local.env",
        root / "config" / "beta-local.local.env",
        root / ".env",
        root / ".env.local",
    ):
        chunk = _parse_env_file(path)
        for key, val in chunk.items():
            os.environ[key] = val
            applied[key] = val
    return applied


load_studio_env = load_beta_env
