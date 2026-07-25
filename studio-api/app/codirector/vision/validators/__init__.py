"""Modular vision validators."""

from __future__ import annotations

from .camera_validator import CameraValidator
from .color_validator import ColorValidator
from .composition_validator import CompositionValidator
from .continuity_validator import ContinuityValidator
from .identity_validator import IdentityValidator
from .lighting_validator import LightingValidator
from .motion_validator import MotionValidator
from .technical_validator import TechnicalValidator

ALL_VALIDATORS = (
    TechnicalValidator(),
    IdentityValidator(),
    ContinuityValidator(),
    LightingValidator(),
    CameraValidator(),
    CompositionValidator(),
    ColorValidator(),
    MotionValidator(),
)

VALIDATOR_BY_ID = {v.validator_id: v for v in ALL_VALIDATORS}

IMAGE_VALIDATOR_IDS = (
    "technical",
    "identity",
    "continuity",
    "lighting",
    "camera",
    "composition",
    "color",
)

VIDEO_VALIDATOR_IDS = IMAGE_VALIDATOR_IDS + ("motion",)

__all__ = [
    "ALL_VALIDATORS",
    "VALIDATOR_BY_ID",
    "IMAGE_VALIDATOR_IDS",
    "VIDEO_VALIDATOR_IDS",
    "TechnicalValidator",
    "IdentityValidator",
    "ContinuityValidator",
    "LightingValidator",
    "CameraValidator",
    "CompositionValidator",
    "ColorValidator",
    "MotionValidator",
]
