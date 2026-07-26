"""M2.11 feature-flag helpers (default off)."""

from __future__ import annotations

from ...feature_flags import feature_flags

FLAG_NAME = "codirector_production_intelligence_v1"


def production_intelligence_enabled() -> bool:
    return bool(getattr(feature_flags, FLAG_NAME, False))
