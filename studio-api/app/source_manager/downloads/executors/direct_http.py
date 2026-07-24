"""Direct HTTP download executor with optional Range resume."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ....setup.download_sources.security import SourceSecurityError, validate_remote_url
from ....setup.pack_install import download_to_file, PackInstallError
from .base import DownloadCapabilities, DownloadExecutionContext, DownloadExecutionResult


def probe_range_support(url: str) -> bool:
    try:
        validate_remote_url(url)
    except SourceSecurityError:
        return False
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            head = client.head(url)
            accept = (head.headers.get("accept-ranges") or "").lower()
            if "bytes" in accept:
                # Confirm with a tiny range GET
                resp = client.get(url, headers={"Range": "bytes=0-0"})
                return resp.status_code == 206
    except Exception:  # noqa: BLE001
        return False
    return False


class DirectHttpDownloadExecutor:
    provider_id = "direct_http"

    def get_capabilities(self, plan: dict[str, Any]) -> DownloadCapabilities:
        artifacts = plan.get("artifacts") or []
        url = None
        for art in artifacts:
            if isinstance(art, dict) and art.get("downloadUrl"):
                url = art["downloadUrl"]
                break
        url = url or (plan.get("metadata") or {}).get("downloadUrl")
        supports = bool(url and probe_range_support(str(url)))
        return DownloadCapabilities(
            can_pause=supports,
            can_resume=supports,
            can_cancel=True,
            supports_range_requests=supports,
            message=(
                "Range resume supported."
                if supports
                else "Pause is not supported by this source. You may cancel and retry."
            ),
        )

    def cancel(self, operation: dict[str, Any]) -> None:
        return None

    def execute(
        self, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        artifacts = [a for a in (plan.get("artifacts") or []) if isinstance(a, dict)]
        if not artifacts:
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message="No artifacts selected.",
                error_category="artifact_missing",
            )
        stage = Path(context.staging_dir)
        downloads = stage / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        files: list[dict[str, Any]] = []
        total_downloaded = 0
        dest_root = Path(str(plan.get("destinationRoot") or stage / "final"))
        dest_root.mkdir(parents=True, exist_ok=True)

        for art in artifacts:
            if context.cancel_event.is_set():
                return DownloadExecutionResult(
                    ok=False, phase="cancelled", message="Cancelled", error_category="cancelled"
                )
            url = str(art.get("downloadUrl") or (plan.get("metadata") or {}).get("downloadUrl") or "")
            if not url:
                return DownloadExecutionResult(
                    ok=False,
                    phase="failed",
                    message="Artifact missing download URL.",
                    error_category="artifact_missing",
                )
            try:
                validate_remote_url(url)
            except SourceSecurityError as exc:
                return DownloadExecutionResult(
                    ok=False, phase="failed", message=exc.message, error_category="provider_error"
                )
            rel = str(art.get("destinationRelativePath") or art.get("remotePath") or "download.bin")
            # download into staging then copy to dest relative
            archive_name = Path(rel).name
            staging_file = downloads / archive_name
            resume_from = 0
            if staging_file.exists() and context.metadata.get("resume"):
                resume_from = staging_file.stat().st_size

            def on_progress(phase: str, percent: float, done: int, total: int | None) -> None:
                if context.cancel_event.is_set():
                    raise PackInstallError("cancelled", "Download cancelled.")
                if context.on_progress:
                    context.on_progress(resume_from + done, (total + resume_from) if total else None)

            try:
                if resume_from > 0 and probe_range_support(url):
                    downloaded = self._download_range(
                        url, staging_file, resume_from, on_progress=on_progress, cancel=context.cancel_event
                    )
                else:
                    downloaded = download_to_file(
                        url,
                        staging_file,
                        expected_bytes=art.get("expectedSize"),
                        on_progress=on_progress,
                    )
            except PackInstallError as exc:
                cat = "cancelled" if exc.code == "cancelled" else "network_unavailable"
                return DownloadExecutionResult(
                    ok=False,
                    phase="cancelled" if cat == "cancelled" else "failed",
                    message=str(exc),
                    error_category=cat,
                )

            total_downloaded += downloaded
            final_path = dest_root / rel
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if final_path.resolve() != staging_file.resolve():
                final_path.write_bytes(staging_file.read_bytes())
            files.append(
                {
                    "relativePath": rel,
                    "size": downloaded,
                    "ownership": "installed_by_adept",
                    "role": art.get("role"),
                    "artifactId": art.get("artifactId"),
                }
            )

        return DownloadExecutionResult(
            ok=True,
            phase="installed",
            message="Direct HTTP install complete.",
            files=files,
            bytes_downloaded=total_downloaded,
        )

    def _download_range(
        self,
        url: str,
        destination: Path,
        resume_from: int,
        *,
        on_progress,
        cancel,
    ) -> int:
        headers = {"Range": f"bytes={resume_from}-"}
        with httpx.stream("GET", url, headers=headers, timeout=60.0, follow_redirects=True) as response:
            if response.status_code == 200:
                # Server ignored range — restart safely
                destination.unlink(missing_ok=True)
                return download_to_file(url, destination, on_progress=on_progress)
            if response.status_code != 206:
                raise PackInstallError("download_http_error", f"HTTP {response.status_code}")
            host = (urlparse(str(response.url)).hostname or "").lower()
            if host not in {"localhost", "127.0.0.1"} and not str(response.url).startswith("https://"):
                raise PackInstallError("download_url_invalid", "Insecure redirect blocked.")
            mode = "ab"
            downloaded = resume_from
            with destination.open(mode) as handle:
                for chunk in response.iter_bytes():
                    if cancel.is_set():
                        raise PackInstallError("cancelled", "Download cancelled.")
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress("downloading", 0.0, downloaded - resume_from, None)
            return downloaded
