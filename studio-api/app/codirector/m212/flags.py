"""M2.12 feature-flag helpers (default OFF)."""

from __future__ import annotations

from ... import feature_flags as feature_flags_mod

FLAG_NAME = "codirector_adaptive_learning_v1"
FLAG_ENV = "STUDIO_FEATURE_CODIRECTOR_ADAPTIVE_LEARNING_V1"


def adaptive_learning_enabled() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))
