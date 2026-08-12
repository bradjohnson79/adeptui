"""M4.8 Cinematic Image Studio — thin contracts and continuity over image_product."""

from .contracts import (
    CinematicGenerateRequest,
    CinematicControls,
    GenerationMode,
    ImageProviderDescriptor,
    ResolutionLabel,
)
from .continuity import (
    VisualContinuitySession,
    create_session,
    get_session,
    inherit_from_scene,
    list_sessions,
    approve_image,
    patch_session,
)
from .providers import family_catalog, list_image_providers, providers_for_mode

__all__ = [
    "CinematicGenerateRequest",
    "CinematicControls",
    "GenerationMode",
    "ImageProviderDescriptor",
    "ResolutionLabel",
    "VisualContinuitySession",
    "create_session",
    "get_session",
    "inherit_from_scene",
    "list_sessions",
    "approve_image",
    "patch_session",
    "family_catalog",
    "list_image_providers",
    "providers_for_mode",
]
