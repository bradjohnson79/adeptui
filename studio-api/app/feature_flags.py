"""Backend feature flags for additive rollout boundaries.

All flags default off and may be overridden with ``STUDIO_FEATURE_<NAME>``.
Nothing in the current application reads these flags yet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import Mapping

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


def _as_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True)
class FeatureFlags:
    unified_generate: bool = False
    story: bool = False
    scene_sheets: bool = False
    jobs: bool = False
    resources: bool = False
    future_rollout: bool = False
    codirector_intelligence_v2: bool = False
    vision_validation_v1: bool = False

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "FeatureFlags":
        """Build flags from an environment mapping without mutating settings."""

        source = os.environ if environ is None else environ
        values: dict[str, bool] = {}
        for item in fields(cls):
            env_name = f"STUDIO_FEATURE_{item.name.upper()}"
            if env_name in source:
                values[item.name] = _as_bool(env_name, source[env_name])
        return cls(**values)


feature_flags = FeatureFlags.from_env()
