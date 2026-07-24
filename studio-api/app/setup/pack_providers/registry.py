"""Pack source provider registry."""

from __future__ import annotations

from ..pack_settings import pack_settings
from .base import PackProviderError, PackSourceProvider
from .github_releases import GitHubReleasePackProvider


def get_pack_provider(provider_id: str | None = None) -> PackSourceProvider:
    cfg = pack_settings()
    pid = (provider_id or cfg.provider or "github_releases").strip()
    if pid == "github_releases":
        return GitHubReleasePackProvider()
    if pid == "fixture_http":
        from .fixture_http import build_fixture_provider

        return build_fixture_provider()
    if pid == "huggingface":
        raise PackProviderError(
            "pack_provider_not_configured",
            "Hugging Face pack provider is not implemented yet.",
        )
    raise PackProviderError(
        "pack_provider_not_configured",
        f"Unknown pack provider: {pid}",
    )
