"""Frozen/runtime path helpers for the Adept Launcher.

When the launcher is frozen with PyInstaller, ``sys.frozen`` is set and
``sys._MEIPASS`` points at the unpacked onefile bundle that contains the
``adept_lifecycle`` package and the brand emblem. In a source checkout these
helpers resolve against the repository layout so tests can run unfrozen.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repository root for source execution: install/launcher/adept_launcher/_paths.py
_REPO_ROOT = Path(__file__).resolve().parents[3]


def meipass() -> Path | None:
    """PyInstaller onefile unpack directory, or None when running from source."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle)
    return None


def brand_emblem() -> Path | None:
    """Path to the brand emblem served by the updater page.

    Frozen: ``sys._MEIPASS/brand/adept-ui-emblem.webp`` (added via the spec).
    Source: ``studio-web/public/brand/adept-ui-emblem.webp``.
    """
    bundle = meipass()
    if bundle is not None:
        candidate = bundle / "brand" / "adept-ui-emblem.webp"
        if candidate.is_file():
            return candidate
    source = _REPO_ROOT / "studio-web" / "public" / "brand" / "adept-ui-emblem.webp"
    return source if source.is_file() else None
