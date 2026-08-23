"""Repo-root launcher so shims do not depend on cwd.

Usage:
  studio-api\\.venv\\Scripts\\python.exe scripts\\run_runtime_supervisor.py start
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

from runtime_supervisor.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
