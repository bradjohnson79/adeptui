"""M2.13 feature-flag helpers (default OFF)."""
from __future__ import annotations

from ... import feature_flags as feature_flags_mod

FLAG_NAME = "virtual_environment_studio_v1"
FLAG_ENV = "STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1"


def virtual_environment_studio_enabled() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))
