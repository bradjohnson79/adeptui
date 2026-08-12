"""M3.0i Native Audio Platform — production local music/SFX/dialogue routing."""

from .registry import capability_for_kind, resolve_native_audio_provider

__all__ = ["capability_for_kind", "resolve_native_audio_provider"]
