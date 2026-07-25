"""Vision analysis providers."""

from __future__ import annotations

from .local import LocalVisionProvider
from .mock import MockVisionProvider


def get_provider(provider_id: str) -> MockVisionProvider | LocalVisionProvider:
    if provider_id == "local":
        return LocalVisionProvider()
    return MockVisionProvider()


__all__ = ["MockVisionProvider", "LocalVisionProvider", "get_provider"]
