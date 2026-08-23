"""Load config/beta-local.env without PowerShell."""

from __future__ import annotations

import os
from pathlib import Path


def load_beta_env(repo_root: Path) -> dict[str, str]:
    applied: dict[str, str] = {}
    for name in ("beta-local.env", "beta-local.local.env"):
        path = repo_root / "config" / name
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            eq = line.find("=")
            if eq < 1:
                continue
            key = line[:eq].strip()
            val = line[eq + 1 :].strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            os.environ[key] = val
            applied[key] = val
    return applied
