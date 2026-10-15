"""Frozen entry point for the Universal Adept Launcher.

PyInstaller bundles this module as the launcher executable. It delegates to the
real orchestration in :mod:`adept_launcher.launcher` so the logic is importable
and testable without a frozen binary.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running unfrozen from a source checkout during tests by putting the
# launcher package and the lifecycle package on sys.path.
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent / "lifecycle"):
    if _candidate.is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from adept_launcher.launcher import main

if __name__ == "__main__":
    main()
