"""Fixture download executor — wraps pack_install for deterministic E2E packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....setup.pack_install import (
    _sha256_file,
    atomic_promote,
    download_to_file,
    extract_archive,
    required_files_present,
    staging_root,
)
from ....setup.pack_manifests import PackInstallError, get_pack_manifest, resolve_pack_download
from .base import DownloadCapabilities, DownloadExecutionContext, DownloadExecutionResult


class FixtureDownloadExecutor:
    provider_id = "fixture"

    def get_capabilities(self, plan: dict[str, Any]) -> DownloadCapabilities:
        return DownloadCapabilities(
            can_pause=False,
            can_resume=False,
            can_cancel=True,
            supports_range_requests=False,
            message="Pause is not supported by this source. You may cancel and retry.",
        )

    def cancel(self, operation: dict[str, Any]) -> None:
        return None

    def execute(
        self, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        component_id = str(plan.get("componentId") or "")
        destination = str(plan.get("destinationRoot") or "")
        if context.cancel_event.is_set():
            return DownloadExecutionResult(
                ok=False, phase="cancelled", message="Cancelled", error_category="cancelled"
            )
        try:
            manifest = get_pack_manifest(component_id)
        except Exception as exc:  # noqa: BLE001
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=str(exc),
                error_category="provider_error",
            )
        try:
            resolved = resolve_pack_download(component_id, force_refresh=True)
        except Exception as exc:  # noqa: BLE001
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=str(exc),
                error_category="source_missing",
            )

        stage = Path(context.staging_dir or staging_root(component_id, context.operation_id, destination=destination))
        downloads = stage / "downloads"
        extracted = stage / "extracted"
        downloads.mkdir(parents=True, exist_ok=True)
        extracted.mkdir(parents=True, exist_ok=True)
        archive_path = downloads / (resolved.archive_asset_name or "pack.zip")

        def on_progress(phase: str, percent: float, done: int, total: int | None) -> None:
            if context.cancel_event.is_set():
                raise PackInstallError("cancelled", "Download cancelled.")
            if context.on_progress:
                context.on_progress(done, total)

        try:
            downloaded = download_to_file(
                resolved.download_url,
                archive_path,
                expected_bytes=resolved.expected_bytes or manifest.archive.expected_download_bytes,
                on_progress=on_progress,
                headers=resolved.auth_headers or None,
            )
            if context.cancel_event.is_set():
                return DownloadExecutionResult(
                    ok=False, phase="cancelled", message="Cancelled", error_category="cancelled"
                )
            if resolved.checksum:
                digest = _sha256_file(archive_path)
                if digest.lower() != resolved.checksum.lower():
                    return DownloadExecutionResult(
                        ok=False,
                        phase="failed",
                        message="Checksum mismatch.",
                        error_category="checksum_mismatch",
                        bytes_downloaded=downloaded,
                    )
            extract_archive(archive_path, extracted, manifest.archive.format)
            ok, missing = required_files_present(extracted, manifest.install.required_files)
            if not ok:
                return DownloadExecutionResult(
                    ok=False,
                    phase="failed",
                    message=f"Missing required files: {', '.join(missing)}",
                    error_category="validation_failed",
                    bytes_downloaded=downloaded,
                )
            final = Path(destination)
            atomic_promote(extracted, final)
            files = []
            for rel in manifest.install.required_files:
                path = final / rel
                size = path.stat().st_size if path.is_file() else None
                files.append(
                    {
                        "relativePath": rel,
                        "size": size,
                        "ownership": "installed_by_adept",
                        "role": "pack",
                    }
                )
            return DownloadExecutionResult(
                ok=True,
                phase="installed",
                message="Installed via fixture provider.",
                files=files,
                bytes_downloaded=downloaded,
                archive_path=str(archive_path),
            )
        except PackInstallError as exc:
            category = "cancelled" if exc.code == "cancelled" else "provider_error"
            if "checksum" in (exc.code or ""):
                category = "checksum_mismatch"
            if "timeout" in (exc.code or "") or "http" in (exc.code or ""):
                category = "network_unavailable"
            if "archive" in (exc.code or ""):
                category = "archive_invalid"
            return DownloadExecutionResult(
                ok=False,
                phase="cancelled" if category == "cancelled" else "failed",
                message=str(exc),
                error_category=category,
            )
        except Exception as exc:  # noqa: BLE001
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=str(exc),
                error_category="unknown",
            )
