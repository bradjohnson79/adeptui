"""Vision analysis providers."""

from __future__ import annotations

import os

from .local import LocalVisionProvider
from .mock import MockVisionProvider

_TRUE = {"1", "true", "TRUE", "yes", "YES", "on"}


class VisionProviderUnavailable(RuntimeError):
    """Requested vision provider cannot be used in this environment."""


def e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in _TRUE


def get_provider(provider_id: str) -> MockVisionProvider | LocalVisionProvider:
    """Resolve a vision provider.

    The mock provider emits fixture findings, so a production run must never fall into it
    — not by asking for it, and not by naming a provider that does not exist. This mirrors
    the Co-Director guard in `codirector/service.py:build_provider`.
    """
    if provider_id == "mock":
        if not e2e_enabled():
            raise VisionProviderUnavailable(
                "The mock vision provider produces fixture findings and is only available "
                "in E2E/test runs. Use provider='local'."
            )
        return MockVisionProvider()
    return LocalVisionProvider()


__all__ = [
    "MockVisionProvider",
    "LocalVisionProvider",
    "VisionProviderUnavailable",
    "get_provider",
    "e2e_enabled",
]
