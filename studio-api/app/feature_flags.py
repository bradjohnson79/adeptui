"""Backend feature flags for additive rollout boundaries.

All flags default off and may be overridden with ``STUDIO_FEATURE_<NAME>``.

Active Co-Director / Director gates include:

* ``STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2``
* ``STUDIO_FEATURE_VISION_VALIDATION_V1``
* ``STUDIO_FEATURE_TIMELINE_REFERENCES_V1``
* ``STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1``
* ``STUDIO_FEATURE_MODEL_RADAR_V1`` (M2.8)
* ``STUDIO_FEATURE_SANDBOX_RUNTIME_V1`` (M2.8)
* ``STUDIO_FEATURE_VIRTUAL_STAGE_V1`` (M2.8)
* ``STUDIO_FEATURE_SHOT_PROFILES_V1`` (M2.8)
* ``STUDIO_FEATURE_PRODUCTION_RECIPE_V1`` (M2.8)
* ``STUDIO_FEATURE_LOCATION_SPIN_V1`` (M2.8)
* ``STUDIO_FEATURE_IMAGE_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_FRAME_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_VIDEO_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_DIRECTOR_TIMELINE_V1`` (M2.9)
* ``STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_AUDIO_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_EDITING_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_RENDER_PRODUCTION_V1`` (M2.9)
* ``STUDIO_FEATURE_CODIRECTOR_PRODUCTION_CONTROL_V1`` (M2.9)
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
    timeline_references_v1: bool = False
    production_executive_v1: bool = False
    model_radar_v1: bool = False
    sandbox_runtime_v1: bool = False
    virtual_stage_v1: bool = False
    shot_profiles_v1: bool = False
    production_recipe_v1: bool = False
    location_spin_v1: bool = False
    image_production_v1: bool = False
    frame_production_v1: bool = False
    video_production_v1: bool = False
    director_timeline_v1: bool = False
    lipsync_production_v1: bool = False
    audio_production_v1: bool = False
    editing_production_v1: bool = False
    render_production_v1: bool = False
    codirector_production_control_v1: bool = False

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
