"""Local fixture pack provider for Playwright / deterministic tests.

Selected via ADEPT_PACK_PROVIDER=fixture_http and ADEPT_PACK_FIXTURE_BASE_URL.
Talks to the E2E fixture HTTP server — never GitHub and never exposes tokens.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx

from .base import PackProviderError, PackRelease, PackSourceProvider, ResolvedPackDownload

USER_AGENT = "AdeptUI-FixturePackProvider/1.0"


class FixtureHttpPackProvider:
    provider_id = "fixture_http"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("ADEPT_PACK_FIXTURE_BASE_URL") or "").rstrip("/") + "/"

    def _require_base(self) -> str:
        if not self.base_url or self.base_url == "/":
            raise PackProviderError(
                "pack_provider_not_configured",
                "Fixture pack provider requires ADEPT_PACK_FIXTURE_BASE_URL.",
            )
        return self.base_url

    def get_latest_release(
        self,
        pack_id: str,
        channel: str,
        current_studio_version: str,
        *,
        force_refresh: bool = False,
    ) -> PackRelease | None:
        base = self._require_base()
        url = urljoin(base, f"releases/{pack_id}")
        try:
            with httpx.Client(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(url, params={"channel": channel, "studio": current_studio_version})
        except httpx.HTTPError as exc:
            raise PackProviderError(
                "pack_registry_unreachable",
                f"Fixture release server unreachable: {exc}",
            ) from exc

        if response.status_code == 404:
            raise PackProviderError(
                "pack_release_not_found",
                "No published fixture release was found for this pack.",
                details=self._diag(pack_id, url, response),
            )
        if response.status_code >= 400:
            raise PackProviderError(
                "pack_registry_unreachable",
                f"Fixture release server returned HTTP {response.status_code}.",
                details=self._diag(pack_id, url, response),
            )
        payload = response.json()
        if payload.get("release") is None:
            raise PackProviderError(
                "pack_release_not_found",
                str(payload.get("message") or "No published fixture release was found for this pack."),
                details=payload.get("diagnostics") or self._diag(pack_id, url, response),
            )
        raw = payload["release"]
        return PackRelease(
            pack_id=str(raw["pack_id"]),
            version=str(raw["version"]),
            channel=str(raw.get("channel") or channel),
            tag_name=str(raw.get("tag_name") or f"v{raw['version']}"),
            release_id=raw.get("release_id"),
            published_at=raw.get("published_at"),
            minimum_studio_version=str(raw.get("minimum_studio_version") or "0.0.0"),
            archive_asset_name=str(raw["archive_asset_name"]),
            archive_asset_id=raw.get("archive_asset_id"),
            archive_format=str(raw.get("archive_format") or "zip"),
            expected_bytes=int(raw.get("expected_bytes") or 0),
            checksum_algorithm=str(raw.get("checksum_algorithm") or "sha256"),
            checksum=str(raw.get("checksum") or ""),
            required_files=tuple(raw.get("required_files") or ("pack.json",)),
            metadata_asset_name=str(raw.get("metadata_asset_name") or f"{pack_id}-meta.release.json"),
            repository=str(raw.get("repository") or "fixture/local"),
            provider_id=self.provider_id,
        )

    def resolve_download(self, release: PackRelease) -> ResolvedPackDownload:
        base = self._require_base()
        download_url = urljoin(base, f"assets/{release.pack_id}/{release.archive_asset_name}")
        return ResolvedPackDownload(
            pack_id=release.pack_id,
            version=release.version,
            source_provider=self.provider_id,
            download_url=download_url,
            expected_bytes=release.expected_bytes,
            checksum_algorithm=release.checksum_algorithm,
            checksum=release.checksum,
            archive_format=release.archive_format,
            required_files=list(release.required_files),
            tag_name=release.tag_name,
            archive_asset_name=release.archive_asset_name,
            repository=release.repository,
            auth_headers={},
        )

    def _diag(self, pack_id: str, url: str, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
            diag = body.get("diagnostics") if isinstance(body, dict) else None
            if isinstance(diag, dict):
                return diag
        except Exception:  # noqa: BLE001
            pass
        return {
            "resolved_owner": "fixture",
            "resolved_repository": "local",
            "release_api_url": url,
            "repository_found": response.status_code != 404,
            "releases_found": 0,
            "expected_asset_pattern": f"{pack_id}-*.zip",
            "selection_reason": "fixture_server_error",
        }


def build_fixture_provider() -> PackSourceProvider:
    return FixtureHttpPackProvider()
