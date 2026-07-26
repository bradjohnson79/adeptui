"""Co-Director M2.9 Complete Native Production Suite package."""

from __future__ import annotations

import os


def fixture_mode_enabled() -> bool:
    """Return True when ADEPT_M29_FIXTURE_MODE requests deterministic fixtures."""
    return os.environ.get("ADEPT_M29_FIXTURE_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
