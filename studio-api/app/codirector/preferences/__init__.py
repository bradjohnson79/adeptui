"""Generator preference resolver — one place, never guessed in handlers."""

from .resolver import PreferenceResolution, resolve_generator_preference
from .store import load_generator_preferences, save_generator_preference

__all__ = [
    "PreferenceResolution",
    "load_generator_preferences",
    "resolve_generator_preference",
    "save_generator_preference",
]
