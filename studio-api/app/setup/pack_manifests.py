"""Versioned Essential Creative Asset pack manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PACKS_DIR = Path(__file__).resolve().parent / "packs"
ASSET_PACK_IDS = (
    "pack_essential_photoreal",
    "pack_essential_anime",
    "pack_essential_cinematic",
)

# Hosts allowed for pack downloads. Localhost is permitted for automated tests.
ALLOWED_DOWNLOAD_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
})


@dataclass(frozen=True)
class PackSource:
    type: str
    url: str | None = None
    provider_id: str | None = None
    channel: str | None = None
    owner: str | None = None
    repository: str | None = None
    release: str | None = None
    asset_pattern: str | None = None


@dataclass(frozen=True)
class PackArchive:
    format: str
    checksum_algorithm: str | None = None
    checksum: str | None = None
    expected_download_bytes: int | None = None


@dataclass(frozen=True)
class PackInstallSpec:
    recommended_path: str
    required_files: tuple[str, ...]
    expected_installed_bytes: int | None = None


@dataclass(frozen=True)
class ExplicitPackSource:
    """Per-component source entry (never a global ADEPT_PACK_GITHUB_* assumption)."""

    id: str
    provider: str
    repository: str | None = None
    owner: str | None = None
    revision: str | None = None
    release: str | None = None
    asset_pattern: str | None = None
    url: str | None = None
    files: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class AssetPackManifest:
    id: str
    name: str
    version: str
    source: PackSource
    archive: PackArchive
    install: PackInstallSpec
    distribution_status: str = "published"
    sources: tuple[ExplicitPackSource, ...] = ()
    kind: str = "downloadable_pack"

    def source_url(self) -> str | None:
        url = (self.source.url or "").strip()
        return url or None

    def uses_provider(self) -> bool:
        return (self.source.type or "").lower() == "provider" and bool(self.source.provider_id)

    def is_published(self) -> bool:
        return (self.distribution_status or "published").strip().lower() in {
            "published",
            "available",
        }

    def has_explicit_remote_source(self) -> bool:
        """True when this pack declares a concrete per-component remote (not global env)."""
        if self.source_url():
            return True
        for entry in self.sources:
            if entry.url:
                return True
            if entry.provider in ("huggingface", "hf") and entry.repository:
                return True
            if entry.provider in ("github_release", "github_releases", "github") and (
                (entry.owner and entry.repository) or entry.repository
            ):
                return True
            if entry.provider == "direct_http" and entry.url:
                return True
        # Legacy single source block with pack-specific owner/repo
        if self.source.owner and self.source.repository:
            return True
        return False

    def has_valid_source(self) -> bool:
        """
        True when this pack can be resolved without inventing a shared GitHub repo.

        Resolution priority (callers also check overrides):
        1. Static / explicit URL on the manifest
        2. Explicit per-component sources[]
        3. fixture_http in E2E / developer mode
        4. Legacy ADEPT_PACK_GITHUB_* only when distributionStatus is published
           AND the pack still uses the generic github_releases provider
        """
        url = self.source_url()
        if url:
            try:
                validate_download_url(url)
                return True
            except PackInstallError:
                return False
        if self.has_explicit_remote_source():
            return True

        import os

        from .pack_settings import github_configured, pack_settings

        active = (pack_settings().provider or self.source.provider_id or "").strip()
        if active == "fixture_http":
            return bool(os.environ.get("ADEPT_PACK_FIXTURE_BASE_URL", "").strip())

        # Unpublished / planned packs must not become "valid" via global env alone.
        if not self.is_published():
            return False

        if self.uses_provider():
            if self.source.provider_id == "github_releases" or active == "github_releases":
                return github_configured()
            return True
        return False

    def distribution_label(self) -> str:
        status = (self.distribution_status or "published").strip().lower()
        return {
            "published": "Published",
            "available": "Published",
            "not_published": "Source Pending",
            "planned": "Coming Soon",
            "development_only": "Development Only",
        }.get(status, status.replace("_", " ").title())


class PackInstallError(Exception):
    def __init__(self, code: str, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable


def validate_download_url(url: str) -> str:
    """Validate scheme/host. Does not invent or rewrite URLs."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http"):
        raise PackInstallError(
            "download_url_invalid",
            f"Download URL scheme must be http or https, got {parsed.scheme or 'none'}.",
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise PackInstallError("download_url_invalid", "Download URL is missing a host.")
    if parsed.scheme == "http" and host not in ALLOWED_DOWNLOAD_HOSTS:
        raise PackInstallError(
            "download_url_invalid",
            "HTTP download URLs are only allowed for localhost test fixtures.",
        )
    if parsed.scheme == "https" and host in ("",):
        raise PackInstallError("download_url_invalid", "Download URL host is invalid.")
    # GitHub hosts are also allowed for provider-resolved downloads.
    return url.strip()


def _parse_explicit_sources(raw: dict[str, Any]) -> tuple[ExplicitPackSource, ...]:
    items = raw.get("sources") or []
    if not isinstance(items, list):
        return ()
    parsed: list[ExplicitPackSource] = []
    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            continue
        files_raw = entry.get("files") or []
        files = tuple(dict(f) for f in files_raw if isinstance(f, dict))
        parsed.append(
            ExplicitPackSource(
                id=str(entry.get("id") or f"source_{index}"),
                provider=str(entry.get("provider") or "").strip().lower(),
                repository=(str(entry["repository"]).strip() if entry.get("repository") else None),
                owner=(str(entry["owner"]).strip() if entry.get("owner") else None),
                revision=(str(entry["revision"]).strip() if entry.get("revision") else None),
                release=(str(entry["release"]).strip() if entry.get("release") else None),
                asset_pattern=(
                    str(entry.get("assetPattern") or entry.get("asset_pattern") or "").strip() or None
                ),
                url=(str(entry["url"]).strip() if entry.get("url") else None),
                files=files,
            )
        )
    return tuple(parsed)


def _parse_manifest(raw: dict[str, Any]) -> AssetPackManifest:
    source_raw = raw.get("source") or {}
    archive_raw = raw.get("archive") or {}
    install_raw = raw.get("install") or {}
    required = install_raw.get("requiredFiles") or install_raw.get("required_files") or []
    distribution = str(
        raw.get("distributionStatus") or raw.get("distribution_status") or "published"
    ).strip()
    return AssetPackManifest(
        id=str(raw["id"]),
        name=str(raw["name"]),
        version=str(raw.get("version") or "0.0.0"),
        source=PackSource(
            type=str(source_raw.get("type") or "http"),
            url=(str(source_raw["url"]).strip() if source_raw.get("url") else None),
            provider_id=(
                str(source_raw["providerId"]).strip()
                if source_raw.get("providerId")
                else (str(source_raw["provider_id"]).strip() if source_raw.get("provider_id") else None)
            ),
            channel=(
                str(source_raw["channel"]).strip()
                if source_raw.get("channel")
                else None
            ),
            owner=(str(source_raw["owner"]).strip() if source_raw.get("owner") else None),
            repository=(
                str(source_raw["repository"]).strip() if source_raw.get("repository") else None
            ),
            release=(str(source_raw["release"]).strip() if source_raw.get("release") else None),
            asset_pattern=(
                str(source_raw.get("assetPattern") or source_raw.get("asset_pattern") or "").strip()
                or None
            ),
        ),
        archive=PackArchive(
            format=str(archive_raw.get("format") or "zip"),
            checksum_algorithm=(
                str(archive_raw.get("checksumAlgorithm") or archive_raw.get("checksum_algorithm") or "")
                or None
            ),
            checksum=(str(archive_raw["checksum"]).strip() if archive_raw.get("checksum") else None),
            expected_download_bytes=(
                int(archive_raw["expectedDownloadBytes"])
                if archive_raw.get("expectedDownloadBytes") is not None
                else (
                    int(archive_raw["expected_download_bytes"])
                    if archive_raw.get("expected_download_bytes") is not None
                    else None
                )
            ),
        ),
        install=PackInstallSpec(
            recommended_path=str(
                install_raw.get("recommendedPath") or install_raw.get("recommended_path") or ""
            ),
            required_files=tuple(str(item) for item in required),
            expected_installed_bytes=(
                int(install_raw["expectedInstalledBytes"])
                if install_raw.get("expectedInstalledBytes") is not None
                else (
                    int(install_raw["expected_installed_bytes"])
                    if install_raw.get("expected_installed_bytes") is not None
                    else None
                )
            ),
        ),
        distribution_status=distribution or "published",
        sources=_parse_explicit_sources(raw),
        kind=str(raw.get("kind") or "downloadable_pack"),
    )


@lru_cache(maxsize=32)
def load_pack_manifest(pack_id: str) -> AssetPackManifest:
    path = PACKS_DIR / f"{pack_id}.json"
    if not path.is_file():
        raise KeyError(f"No pack manifest for {pack_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    manifest = _parse_manifest(raw)
    if manifest.id != pack_id:
        raise ValueError(f"Manifest id mismatch: {manifest.id} != {pack_id}")
    return manifest


def clear_manifest_cache() -> None:
    load_pack_manifest.cache_clear()


def is_asset_pack(component_id: str) -> bool:
    return component_id in ASSET_PACK_IDS


_SOURCE_OVERRIDES: dict[str, str | None] = {}


def get_pack_manifest(pack_id: str) -> AssetPackManifest:
    """Load manifest applying optional source URL overrides (memory + persisted)."""
    base = load_pack_manifest(pack_id)
    url: str | None
    if pack_id in _SOURCE_OVERRIDES:
        url = _SOURCE_OVERRIDES[pack_id]
    else:
        url = _persisted_override_url(pack_id)
    if url is None and pack_id not in _SOURCE_OVERRIDES:
        return base
    return AssetPackManifest(
        id=base.id,
        name=base.name,
        version=base.version,
        source=PackSource(
            type="http" if url else base.source.type,
            url=url,
            provider_id=base.source.provider_id,
            channel=base.source.channel,
            owner=base.source.owner,
            repository=base.source.repository,
            release=base.source.release,
            asset_pattern=base.source.asset_pattern,
        ),
        archive=base.archive,
        install=base.install,
        distribution_status=base.distribution_status,
        sources=base.sources,
        kind=base.kind,
    )


def _persisted_override_url(pack_id: str) -> str | None:
    try:
        from .download_sources.overrides import get_override

        item = get_override(pack_id)
        if not item:
            return None
        url = str(item.get("sourceUrl") or "").strip()
        return url or None
    except Exception:  # noqa: BLE001
        return None


def set_source_override(pack_id: str, url: str | None) -> None:
    if url is not None:
        validate_download_url(url)
        _SOURCE_OVERRIDES[pack_id] = url
    else:
        _SOURCE_OVERRIDES.pop(pack_id, None)


def clear_source_overrides() -> None:
    _SOURCE_OVERRIDES.clear()


def public_source_host(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).hostname
    return host


def resolve_pack_download(pack_id: str, *, force_refresh: bool = False):
    """Resolve a concrete download for a pack without persisting the URL."""
    from .pack_providers import PackProviderError, get_pack_provider
    from .pack_providers.base import ResolvedPackDownload
    from .pack_settings import pack_settings

    manifest = get_pack_manifest(pack_id)
    if manifest.source_url():
        url = manifest.source_url()
        assert url is not None
        # Manifest expectedDownloadBytes are estimates only — never hard-enforce for direct URLs.
        # Exact byte counts come from provider release metadata.
        return ResolvedPackDownload(
            pack_id=pack_id,
            version=manifest.version,
            source_provider="direct_url",
            download_url=url,
            expected_bytes=0,
            checksum_algorithm=manifest.archive.checksum_algorithm or "sha256",
            checksum=manifest.archive.checksum or "",
            archive_format=manifest.archive.format,
            required_files=list(manifest.install.required_files),
        )

    if not manifest.uses_provider():
        raise PackInstallError(
            "download_source_missing",
            "This pack does not currently have a valid download source.",
        )

    active = (pack_settings().provider or manifest.source.provider_id or "").strip()
    provider = get_pack_provider(active or manifest.source.provider_id)
    channel = manifest.source.channel or pack_settings().github_channel or "stable"
    try:
        release = provider.get_latest_release(
            pack_id,
            channel,
            pack_settings().studio_version,
            force_refresh=force_refresh,
        )
    except PackProviderError as exc:
        raise PackInstallError(exc.code, exc.message, recoverable=exc.recoverable) from exc
    if release is None:
        raise PackInstallError(
            "pack_release_not_found",
            "No published release was found for this pack.",
        )
    try:
        return provider.resolve_download(release)
    except PackProviderError as exc:
        raise PackInstallError(exc.code, exc.message, recoverable=exc.recoverable) from exc


def refresh_pack_source(pack_id: str, *, force_refresh: bool = True) -> dict[str, Any]:
    """Query pack sources in order: explicit URL → GitHub env → Hugging Face → not configured."""
    clear_manifest_cache()
    manifest = get_pack_manifest(pack_id)
    from .diagnostics import utc_now
    from .pack_settings import github_configured, pack_settings

    base: dict[str, Any] = {
        "component_id": pack_id,
        "pack_id": pack_id,
        "version": manifest.version,
        "source_type": manifest.source.type,
        "provider_id": manifest.source.provider_id,
        "channel": manifest.source.channel or pack_settings().github_channel,
        "retrieved_at": utc_now(),
        "source_available": False,
        "source_valid": False,
        "available_version": None,
        "download_bytes": manifest.archive.expected_download_bytes,
        "installed_bytes": 0,
        "repository": None,
        "tag_name": None,
        "archive_asset_name": None,
        "error": None,
        "github_owner": None,
        "release_api_url": None,
        "repo_found": None,
        "releases_found": None,
        "draft_count": None,
        "prerelease_count": None,
        "selected_release_tag": None,
        "available_asset_names": None,
        "expected_asset_pattern": None,
        "selection_reason": None,
        # Do not imply Link Existing is the normal first-time path when remote fails.
        "link_existing_is_fallback_only": True,
    }

    # 1) Explicit per-pack source URL in pack registry / override.
    if manifest.source_url():
        try:
            validate_download_url(manifest.source_url() or "")
            base.update({
                "source_valid": True,
                "source_available": True,
                "available_version": manifest.version,
                "source_host": public_source_host(manifest.source_url()),
                "selection_reason": "Using explicit pack registry download URL.",
            })
        except PackInstallError as exc:
            base["error"] = {"code": exc.code, "message": exc.message}
        return base

    # 2) Active provider from ADEPT_PACK_PROVIDER (fixture_http for E2E) or GitHub env.
    active_provider = (pack_settings().provider or "").strip()
    if manifest.uses_provider() and active_provider == "fixture_http":
        from .pack_providers import PackProviderError, get_pack_provider
        from .pack_release_cache import put_cached_release

        provider = get_pack_provider("fixture_http")
        try:
            release = provider.get_latest_release(
                pack_id,
                base["channel"] or "stable",
                pack_settings().studio_version,
                force_refresh=force_refresh,
            )
        except PackProviderError as exc:
            base["error"] = {"code": exc.code, "message": exc.message}
            if exc.details:
                for key, value in exc.details.items():
                    if key.lower() in ("token", "authorization", "password"):
                        continue
                    base[key] = value
                base["selection_reason"] = exc.details.get("selection_reason") or exc.message
            return base
        if release is None:
            base["error"] = {
                "code": "pack_release_not_found",
                "message": "No published fixture release was found for this pack.",
            }
            return base
        put_cached_release(
            pack_id,
            {
                "provider_id": "fixture_http",
                "repository": release.repository,
                "release_id": release.release_id,
                "tag_name": release.tag_name,
                "version": release.version,
                "channel": release.channel,
                "archive_asset_id": release.archive_asset_id,
                "archive_asset_name": release.archive_asset_name,
                "expected_bytes": release.expected_bytes,
                "checksum": release.checksum,
                "checksum_algorithm": release.checksum_algorithm,
                "required_files": list(release.required_files),
                "archive_format": release.archive_format,
                "minimum_studio_version": release.minimum_studio_version,
            },
        )
        base.update({
            "source_valid": True,
            "source_available": True,
            "available_version": release.version,
            "download_bytes": release.expected_bytes,
            "repository": release.repository,
            "tag_name": release.tag_name,
            "archive_asset_name": release.archive_asset_name,
            "source_host": "fixture",
            "provider_id": "fixture_http",
            "checksum_algorithm": release.checksum_algorithm,
            "selection_reason": "Matched fixture release asset.",
        })
        return base

    if not manifest.is_published() and not manifest.has_explicit_remote_source() and not manifest.source_url():
        # Skip generic GitHub env resolution for unpublished catalog packs.
        if active_provider != "fixture_http":
            base["error"] = {
                "code": "source_not_published",
                "message": (
                    f"No official distribution has been published for {manifest.name} yet. "
                    "Use Add Source URL or Link Existing Folder."
                ),
            }
            base["distribution_status"] = manifest.distribution_status
            base["selection_reason"] = "Pack distributionStatus is not published."
            return base

    if manifest.uses_provider() and (
        manifest.source.provider_id == "github_releases" or active_provider == "github_releases"
    ):
        if not github_configured() and not manifest.has_explicit_remote_source():
            base["error"] = {
                "code": "source_not_configured",
                "message": (
                    "No official source has been assigned to this component. "
                    "Add a Source URL, or Link Existing Folder."
                ),
            }
            base["selection_reason"] = "No per-component source and no legacy GitHub override."
            return base
        from .pack_providers import PackProviderError, get_pack_provider
        from .pack_providers.github_releases import GitHubReleasePackProvider

        provider = get_pack_provider("github_releases")
        assert isinstance(provider, GitHubReleasePackProvider)
        try:
            diag = provider.diagnose_releases(
                pack_id,
                base["channel"] or "stable",
                pack_settings().studio_version,
                force_refresh=force_refresh,
            )
        except PackProviderError as exc:
            base["error"] = {"code": exc.code, "message": exc.message}
            base["selection_reason"] = exc.message
            if exc.details:
                base["rate_limit"] = {
                    "remaining": exc.details.get("remaining"),
                    "reset": exc.details.get("reset"),
                }
            return base
        base.update({
            "github_owner": diag.get("github_owner"),
            "repository": diag.get("repository"),
            "release_api_url": diag.get("release_api_url"),
            "repo_found": diag.get("repo_found"),
            "releases_found": diag.get("releases_found"),
            "draft_count": diag.get("draft_count"),
            "prerelease_count": diag.get("prerelease_count"),
            "selected_release_tag": diag.get("selected_release_tag"),
            "available_asset_names": diag.get("available_asset_names"),
            "expected_asset_pattern": diag.get("expected_asset_pattern"),
            "selection_reason": diag.get("selection_reason"),
        })
        release = diag.get("release")
        if release is None:
            reason = diag.get("selection_reason") or "No published GitHub release was found for this pack."
            base["error"] = {
                "code": "pack_release_not_found",
                "message": reason,
            }
            return base
        base.update({
            "source_valid": True,
            "source_available": True,
            "available_version": release.version,
            "download_bytes": release.expected_bytes,
            "tag_name": release.tag_name,
            "archive_asset_name": release.archive_asset_name,
            "source_host": "github.com",
            "checksum_algorithm": release.checksum_algorithm,
        })
        return base

    # 3) Optional Hugging Face source (not implemented yet).
    if manifest.uses_provider() and manifest.source.provider_id == "huggingface":
        base["error"] = {
            "code": "pack_provider_not_configured",
            "message": "Hugging Face pack provider is not implemented yet.",
        }
        base["selection_reason"] = "Hugging Face source is not available."
        return base

    # 4) Clear "Download source not configured".
    base["error"] = {
        "code": "download_source_missing",
        "message": "Download source not configured for this pack.",
    }
    base["selection_reason"] = "No explicit URL, GitHub provider, or Hugging Face source is configured."
    return base
