"""Environment configuration for Essential pack download providers."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PackProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADEPT_PACK_", env_file=".env", extra="ignore")

    provider: str = "github_releases"
    github_owner: str = ""
    github_repository: str = ""
    github_channel: str = "stable"
    github_token: str = ""
    studio_version: str = "0.1.0"
    cache_ttl_seconds: int = 900


@lru_cache(maxsize=1)
def pack_settings() -> PackProviderSettings:
    return PackProviderSettings()


def clear_pack_settings_cache() -> None:
    pack_settings.cache_clear()


def github_configured() -> bool:
    cfg = pack_settings()
    return bool(cfg.github_owner.strip() and cfg.github_repository.strip())


def github_token() -> str | None:
    token = pack_settings().github_token.strip()
    return token or None
