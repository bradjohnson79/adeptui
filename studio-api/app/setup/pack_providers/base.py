"""Provider-agnostic contracts for Essential pack downloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class PackProviderError(Exception):
    def __init__(self, code: str, message: str, *, recoverable: bool = True, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.details = details or {}


@dataclass(frozen=True)
class PackRelease:
    pack_id: str
    version: str
    channel: str
    tag_name: str
    release_id: int | None
    published_at: str | None
    minimum_studio_version: str
    archive_asset_name: str
    archive_asset_id: int | None
    archive_format: str
    expected_bytes: int
    checksum_algorithm: str
    checksum: str
    required_files: tuple[str, ...]
    metadata_asset_name: str
    repository: str
    provider_id: str = "github_releases"


@dataclass(frozen=True)
class ResolvedPackDownload:
    pack_id: str
    version: str
    source_provider: str
    download_url: str
    expected_bytes: int
    checksum_algorithm: str
    checksum: str
    archive_format: str
    required_files: list[str]
    tag_name: str = ""
    archive_asset_name: str = ""
    repository: str = ""
    auth_headers: dict[str, str] = field(default_factory=dict)


class PackSourceProvider(Protocol):
    provider_id: str

    def get_latest_release(
        self,
        pack_id: str,
        channel: str,
        current_studio_version: str,
        *,
        force_refresh: bool = False,
    ) -> PackRelease | None:
        ...

    def resolve_download(self, release: PackRelease) -> ResolvedPackDownload:
        ...
