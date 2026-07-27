"""M2.13 feature-flag helpers (default OFF)."""
from __future__ import annotations

import os

from ... import feature_flags as feature_flags_mod

FLAG_NAME = "virtual_environment_studio_v1"
FLAG_ENV = "STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1"
FIXTURE_ENV = "ADEPT_M213_FIXTURE_MODE"

_TRUE = {"1", "true", "TRUE", "yes", "YES", "on"}


def virtual_environment_studio_enabled() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))


def fixtures_enabled() -> bool:
    """Whether synthetic M2.13 environment data may be produced.

    Granted by the environment only (ADEPT_M213_FIXTURE_MODE / STUDIO_E2E), never by a
    request field: a client asking for `fixture: true` is a request, not authorisation.
    """
    return any(
        os.environ.get(key, "").strip() in _TRUE for key in (FIXTURE_ENV, "STUDIO_E2E")
    )
