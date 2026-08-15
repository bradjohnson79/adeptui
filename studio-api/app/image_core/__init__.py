"""Adept Image Generation Core — provider-agnostic facade over M42 compile/runtime.

Scene Creator (and later Character/Prop) send purpose + operation + modelId +
creativeContext. This package chooses workflow, adapter, resolution, and
normalized errors. Callers must not pick workflow keys.
"""

from .capability import family_region_edit_capability, certified_visual_edit_path, normalize_family
from .errors import ImageCoreError, UNSUPPORTED_OPERATION
from .flag import scene_image_core_enabled
from .generate import generate
from .preflight import preflight
from .recommend import recommend
from .request import ImageCoreRequest, CapabilityDecision, NormalizedEnqueue
from .resolution import resolve_resolution

__all__ = [
    "ImageCoreError",
    "UNSUPPORTED_OPERATION",
    "ImageCoreRequest",
    "CapabilityDecision",
    "NormalizedEnqueue",
    "scene_image_core_enabled",
    "preflight",
    "generate",
    "recommend",
    "resolve_resolution",
    "family_region_edit_capability",
    "certified_visual_edit_path",
    "normalize_family",
]
