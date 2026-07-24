"""GitHub Releases pack download provider (sync)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from ..pack_release_cache import get_cached_release, put_cached_release
from ..pack_settings import github_configured, github_token, pack_settings
from .base import PackProviderError, PackRelease, ResolvedPackDownload

GITHUB_API = "https://api.github.com"
USER_AGENT = "AdeptUI-GenStudio-PackProvider/1.0"
ALLOWED_DOWNLOAD_HOSTS = frozenset({
    "github.com",
    "www.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
})
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(value.strip())
    if not match:
        raise PackProviderError("pack_release_manifest_invalid", f"Invalid semantic version: {value}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _version_gte(current: str, minimum: str) -> bool:
    return _parse_semver(current) >= _parse_semver(minimum)


def validate_download_host(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    # Localhost HTTP is reserved for automated fixtures only.
    if host in {"localhost", "127.0.0.1"} and parsed.scheme in ("http", "https"):
        return url
    if parsed.scheme != "https":
        raise PackProviderError("download_url_invalid", "Pack downloads must use HTTPS.")
    if host not in ALLOWED_DOWNLOAD_HOSTS:
        raise PackProviderError("download_url_invalid", f"Download host not approved: {host}")
    return url


def _request_json(client: httpx.Client, method: str, url: str) -> Any:
    try:
        response = client.request(method, url, headers=_headers(), timeout=30.0)
    except httpx.TimeoutException as exc:
        raise PackProviderError("pack_registry_unreachable", "GitHub request timed out.") from exc
    except httpx.HTTPError as exc:
        raise PackProviderError("pack_registry_unreachable", f"GitHub request failed: {exc}") from exc

    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if response.status_code == 403 and (
        "rate limit" in (response.text or "").lower()
        or remaining == "0"
    ):
        raise PackProviderError(
            "github_rate_limited",
            "GitHub temporarily limited release checks. Try again later or configure a GitHub token.",
            details={"remaining": remaining, "reset": reset},
        )
    if response.status_code == 404:
        raise PackProviderError("pack_release_not_found", "GitHub repository or release was not found.")
    if response.status_code >= 400:
        raise PackProviderError(
            "pack_registry_unreachable",
            f"GitHub returned HTTP {response.status_code}.",
            details={"remaining": remaining, "reset": reset},
        )
    return response.json()


def _asset_by_name(assets: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for asset in assets:
        if str(asset.get("name") or "") == name:
            return asset
    return None


def _release_to_cache_payload(release: PackRelease) -> dict[str, Any]:
    return {
        "provider_id": release.provider_id,
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
    }


class GitHubReleasePackProvider:
    provider_id = "github_releases"

    def __init__(self, *, owner: str | None = None, repository: str | None = None) -> None:
        cfg = pack_settings()
        self.owner = (owner if owner is not None else cfg.github_owner).strip()
        self.repository = (repository if repository is not None else cfg.github_repository).strip()

    @property
    def repo_slug(self) -> str:
        return f"{self.owner}/{self.repository}"

    def _ensure_configured(self) -> None:
        if not self.owner or not self.repository:
            raise PackProviderError(
                "pack_provider_not_configured",
                "GitHub pack provider is not configured. Set ADEPT_PACK_GITHUB_OWNER and ADEPT_PACK_GITHUB_REPOSITORY.",
            )

    def release_api_url(self) -> str:
        # Host + path only (no scheme) so diagnostics never look like download URLs.
        return f"api.github.com/repos/{self.repo_slug}/releases"

    def expected_asset_pattern(self, pack_id: str) -> str:
        return f"{pack_id}-*.release.json"

    def diagnose_releases(
        self,
        pack_id: str,
        channel: str,
        current_studio_version: str,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return structured GitHub diagnostics without exposing tokens."""
        self._ensure_configured()
        diag: dict[str, Any] = {
            "github_owner": self.owner,
            "repository": self.repo_slug,
            "release_api_url": self.release_api_url(),
            "repo_found": None,
            "releases_found": 0,
            "draft_count": 0,
            "prerelease_count": 0,
            "selected_release_tag": None,
            "available_asset_names": [],
            "expected_asset_pattern": self.expected_asset_pattern(pack_id),
            "selection_reason": None,
            "release": None,
        }
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            # Probe repository existence separately from releases.
            repo_url = f"{GITHUB_API}/repos/{self.repo_slug}"
            try:
                repo_resp = client.get(repo_url, headers=_headers(), timeout=30.0)
            except httpx.HTTPError as exc:
                raise PackProviderError(
                    "pack_registry_unreachable",
                    f"GitHub request failed: {exc}",
                ) from exc
            if repo_resp.status_code == 404:
                diag["repo_found"] = False
                diag["selection_reason"] = "GitHub repository was not found."
                return diag
            if repo_resp.status_code == 403 and (
                "rate limit" in (repo_resp.text or "").lower()
                or repo_resp.headers.get("X-RateLimit-Remaining") == "0"
            ):
                raise PackProviderError(
                    "github_rate_limited",
                    "GitHub temporarily limited release checks. Try again later or configure a GitHub token.",
                    details={
                        "remaining": repo_resp.headers.get("X-RateLimit-Remaining"),
                        "reset": repo_resp.headers.get("X-RateLimit-Reset"),
                    },
                )
            if repo_resp.status_code >= 400:
                raise PackProviderError(
                    "pack_registry_unreachable",
                    f"GitHub returned HTTP {repo_resp.status_code}.",
                )
            diag["repo_found"] = True

            if not force_refresh:
                cached = get_cached_release(pack_id)
                if cached and cached.get("channel") == channel:
                    release = self._release_from_cache(cached)
                    diag.update({
                        "selected_release_tag": release.tag_name,
                        "available_asset_names": [release.archive_asset_name, release.metadata_asset_name],
                        "selection_reason": "Using cached release metadata.",
                        "release": release,
                    })
                    return diag

            releases = self._list_releases(client)
            diag["releases_found"] = len(releases)
            diag["draft_count"] = sum(1 for item in releases if item.get("draft"))
            diag["prerelease_count"] = sum(1 for item in releases if item.get("prerelease"))
            if not releases:
                diag["selection_reason"] = "Repository exists but has no published releases."
                return diag

            considered_assets: list[str] = []
            last_reason = "No release contained a matching pack metadata asset."
            for release in releases:
                assets = release.get("assets") or []
                names = [str(a.get("name") or "") for a in assets if a.get("name")]
                considered_assets.extend(names)
                if release.get("draft"):
                    last_reason = f"Skipped draft release {release.get('tag_name')}."
                    continue
                if channel == "stable" and release.get("prerelease"):
                    last_reason = f"Skipped prerelease {release.get('tag_name')} for stable channel."
                    continue
                meta_names = [
                    name for name in names
                    if name.startswith(f"{pack_id}-") and name.endswith(".release.json")
                ]
                if not meta_names:
                    last_reason = (
                        f"Release {release.get('tag_name')} has no asset matching "
                        f"{self.expected_asset_pattern(pack_id)}."
                    )
                    continue
                try:
                    parsed = self._try_parse_release(
                        client, pack_id, channel, current_studio_version, release
                    )
                except PackProviderError as exc:
                    last_reason = f"Release {release.get('tag_name')} rejected: {exc.message}"
                    continue
                if parsed is None:
                    last_reason = (
                        f"Release {release.get('tag_name')} did not yield a usable pack asset."
                    )
                    continue
                put_cached_release(pack_id, _release_to_cache_payload(parsed))
                diag.update({
                    "selected_release_tag": parsed.tag_name,
                    "available_asset_names": names,
                    "selection_reason": f"Selected release {parsed.tag_name} with asset {parsed.archive_asset_name}.",
                    "release": parsed,
                })
                return diag

            # Deduplicate asset names for diagnostics.
            seen: list[str] = []
            for name in considered_assets:
                if name not in seen:
                    seen.append(name)
            diag["available_asset_names"] = seen[:50]
            diag["selection_reason"] = last_reason
            return diag

    def get_latest_release(
        self,
        pack_id: str,
        channel: str,
        current_studio_version: str,
        *,
        force_refresh: bool = False,
    ) -> PackRelease | None:
        diag = self.diagnose_releases(
            pack_id,
            channel,
            current_studio_version,
            force_refresh=force_refresh,
        )
        return diag.get("release")

    def resolve_download(self, release: PackRelease) -> ResolvedPackDownload:
        self._ensure_configured()
        with httpx.Client(follow_redirects=False, timeout=30.0) as client:
            url = (
                f"{GITHUB_API}/repos/{self.repo_slug}/releases/assets/{release.archive_asset_id}"
                if release.archive_asset_id
                else None
            )
            # Prefer re-fetching the release to get a fresh browser_download_url.
            releases = self._list_releases(client)
            asset = None
            for item in releases:
                if release.release_id and item.get("id") != release.release_id:
                    continue
                if item.get("tag_name") != release.tag_name and release.tag_name:
                    continue
                asset = _asset_by_name(item.get("assets") or [], release.archive_asset_name)
                if asset:
                    break
            if not asset:
                raise PackProviderError(
                    "pack_release_not_found",
                    f"Archive asset {release.archive_asset_name} was not found on GitHub.",
                )
            browser_url = str(asset.get("browser_download_url") or "")
            auth_headers: dict[str, str] = {}
            if github_token() and asset.get("url"):
                # Private repos: authenticated API asset download.
                download_url = str(asset["url"])
                auth_headers = {
                    **_headers(),
                    "Accept": "application/octet-stream",
                }
            else:
                download_url = browser_url
                validate_download_host(download_url)
            size = int(asset.get("size") or 0)
            if release.expected_bytes and size and size != release.expected_bytes:
                raise PackProviderError(
                    "download_size_mismatch",
                    f"GitHub asset size {size} does not match release metadata {release.expected_bytes}.",
                )
            return ResolvedPackDownload(
                pack_id=release.pack_id,
                version=release.version,
                source_provider=self.provider_id,
                download_url=download_url,
                expected_bytes=release.expected_bytes or size,
                checksum_algorithm=release.checksum_algorithm,
                checksum=release.checksum,
                archive_format=release.archive_format,
                required_files=list(release.required_files),
                tag_name=release.tag_name,
                archive_asset_name=release.archive_asset_name,
                repository=release.repository,
                auth_headers=auth_headers,
            )

    def _list_releases(self, client: httpx.Client) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for page in range(1, 6):
            url = f"{GITHUB_API}/repos/{self.repo_slug}/releases?per_page=30&page={page}"
            payload = _request_json(client, "GET", url)
            if not isinstance(payload, list) or not payload:
                break
            collected.extend(payload)
            if len(payload) < 30:
                break
        return collected

    def _try_parse_release(
        self,
        client: httpx.Client,
        pack_id: str,
        channel: str,
        current_studio_version: str,
        release: dict[str, Any],
    ) -> PackRelease | None:
        assets = release.get("assets") or []
        # Prefer exact metadata asset for this pack.
        meta_assets = [
            asset for asset in assets
            if str(asset.get("name") or "").startswith(f"{pack_id}-")
            and str(asset.get("name") or "").endswith(".release.json")
        ]
        if not meta_assets:
            return None
        # Newest matching metadata asset by name version suffix.
        meta_assets.sort(key=lambda a: str(a.get("name") or ""), reverse=True)
        meta = meta_assets[0]
        meta_name = str(meta["name"])
        meta_url = str(meta.get("browser_download_url") or "")
        if not meta_url:
            return None
        validate_download_host(meta_url)
        try:
            response = client.get(meta_url, headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise PackProviderError("pack_registry_unreachable", f"Failed to download release metadata: {exc}") from exc
        if response.status_code >= 400:
            raise PackProviderError("pack_release_manifest_invalid", "Unable to download .release.json metadata.")
        try:
            raw = response.json()
        except json.JSONDecodeError as exc:
            raise PackProviderError("pack_release_manifest_invalid", "Release metadata is not valid JSON.") from exc
        return self._validate_release_json(
            raw,
            pack_id=pack_id,
            channel=channel,
            current_studio_version=current_studio_version,
            release=release,
            assets=assets,
            metadata_asset_name=meta_name,
        )

    def _validate_release_json(
        self,
        raw: dict[str, Any],
        *,
        pack_id: str,
        channel: str,
        current_studio_version: str,
        release: dict[str, Any],
        assets: list[dict[str, Any]],
        metadata_asset_name: str,
    ) -> PackRelease:
        schema = int(raw.get("schemaVersion") or raw.get("schema_version") or 0)
        if schema != 1:
            raise PackProviderError("pack_release_manifest_invalid", f"Unsupported release schema version: {schema}")
        if str(raw.get("packId") or raw.get("pack_id") or "") != pack_id:
            raise PackProviderError("pack_release_manifest_invalid", "Release metadata packId does not match.")
        version = str(raw.get("version") or "")
        _parse_semver(version)
        meta_channel = str(raw.get("channel") or channel)
        minimum = str(raw.get("minimumStudioVersion") or raw.get("minimum_studio_version") or "0.0.0")
        if not _version_gte(current_studio_version, minimum):
            raise PackProviderError(
                "pack_release_manifest_invalid",
                f"Pack requires Gen Studio {minimum}+ (current {current_studio_version}).",
            )
        archive = raw.get("archive") or {}
        asset_name = str(archive.get("assetName") or archive.get("asset_name") or "")
        if not asset_name:
            raise PackProviderError("pack_release_manifest_invalid", "Release metadata is missing archive.assetName.")
        expected = int(archive.get("expectedBytes") or archive.get("expected_bytes") or 0)
        checksum = str(archive.get("checksum") or "").strip()
        algo = str(archive.get("checksumAlgorithm") or archive.get("checksum_algorithm") or "sha256").lower()
        if not checksum:
            raise PackProviderError("pack_release_manifest_invalid", "Production releases require a SHA-256 checksum.")
        zip_asset = _asset_by_name(assets, asset_name)
        if not zip_asset:
            raise PackProviderError("pack_release_not_found", f"Release is missing archive asset {asset_name}.")
        if expected and int(zip_asset.get("size") or 0) and int(zip_asset["size"]) != expected:
            raise PackProviderError(
                "pack_release_manifest_invalid",
                "Release metadata expectedBytes does not match GitHub asset size.",
            )
        install = raw.get("install") or {}
        required = tuple(
            str(item)
            for item in (install.get("requiredFiles") or install.get("required_files") or ["pack.json"])
        )
        return PackRelease(
            pack_id=pack_id,
            version=version,
            channel=meta_channel,
            tag_name=str(release.get("tag_name") or f"packs-v{version}"),
            release_id=int(release["id"]) if release.get("id") is not None else None,
            published_at=str(raw.get("publishedAt") or release.get("published_at") or "") or None,
            minimum_studio_version=minimum,
            archive_asset_name=asset_name,
            archive_asset_id=int(zip_asset["id"]) if zip_asset.get("id") is not None else None,
            archive_format=str(archive.get("format") or "zip"),
            expected_bytes=expected or int(zip_asset.get("size") or 0),
            checksum_algorithm=algo,
            checksum=checksum,
            required_files=required,
            metadata_asset_name=metadata_asset_name,
            repository=self.repo_slug,
            provider_id=self.provider_id,
        )

    def _release_from_cache(self, cached: dict[str, Any]) -> PackRelease:
        return PackRelease(
            pack_id=str(cached["pack_id"]),
            version=str(cached["version"]),
            channel=str(cached.get("channel") or "stable"),
            tag_name=str(cached.get("tag_name") or ""),
            release_id=cached.get("release_id"),
            published_at=None,
            minimum_studio_version=str(cached.get("minimum_studio_version") or "0.0.0"),
            archive_asset_name=str(cached.get("archive_asset_name") or ""),
            archive_asset_id=cached.get("archive_asset_id"),
            archive_format=str(cached.get("archive_format") or "zip"),
            expected_bytes=int(cached.get("expected_bytes") or 0),
            checksum_algorithm=str(cached.get("checksum_algorithm") or "sha256"),
            checksum=str(cached.get("checksum") or ""),
            required_files=tuple(cached.get("required_files") or ("pack.json",)),
            metadata_asset_name="",
            repository=str(cached.get("repository") or self.repo_slug),
            provider_id=str(cached.get("provider_id") or self.provider_id),
        )


def provider_is_ready() -> bool:
    return github_configured()
