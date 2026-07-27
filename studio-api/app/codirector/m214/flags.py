"""M2.14 feature-flag helpers (default OFF)."""
from __future__ import annotations

from ... import feature_flags as feature_flags_mod

FLAG_NAME = "codirector_unified_experience_v1"
FLAG_ENV = "STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1"


def unified_experience_enabled() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))
