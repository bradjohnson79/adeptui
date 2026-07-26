"""M2.10b feature-flag helpers (default off)."""

from __future__ import annotations

import os

from ...feature_flags import feature_flags

_TRUE = frozenset({"1", "true", "yes", "on"})


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def m210b_audio_sandbox_enabled() -> bool:
    """``STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1`` (default False)."""
    if "STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1" in os.environ:
        return _env_bool("STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1", False)
    return bool(getattr(feature_flags, "m210b_audio_sandbox_v1", False))


def m210b_camera_metadata_enabled() -> bool:
    """``STUDIO_FEATURE_M210B_CAMERA_METADATA_V1`` (default False)."""
    if "STUDIO_FEATURE_M210B_CAMERA_METADATA_V1" in os.environ:
        return _env_bool("STUDIO_FEATURE_M210B_CAMERA_METADATA_V1", False)
    return bool(getattr(feature_flags, "m210b_camera_metadata_v1", False))


def fixture_mode_enabled() -> bool:
    """CI fixture mode for M2.9 or M2.10b."""
    for name in ("ADEPT_M210B_FIXTURE_MODE", "ADEPT_M29_FIXTURE_MODE"):
        if _env_bool(name, False):
            return True
    return False
