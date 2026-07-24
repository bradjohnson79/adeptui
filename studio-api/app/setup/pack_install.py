"""Staging download / extract / verify pipeline for Essential asset packs."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import settings
from .pack_manifests import (
    AssetPackManifest,
    PackInstallError,
    get_pack_manifest,
    public_source_host,
    validate_download_url,
)
from .paths import default_models_root

ProgressCallback = Callable[[str, float, int, int | None], None]

# Common system / protected roots that must not be used as pack destinations.
_PROTECTED_DIR_NAMES = frozenset({
    "windows",
    "system32",
    "syswow64",
    "program files",
    "program files (x86)",
    "programdata",
    "recovery",
    "$recycle.bin",
})


def directory_byte_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def required_files_present(root: Path, required: tuple[str, ...]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for relative in required:
        candidate = root / relative
        if not candidate.is_file():
            missing.append(relative)
    return not missing, missing


def final_install_path(manifest: AssetPackManifest, override: str | None = None) -> Path:
    if override and override.strip():
        return Path(override).expanduser()
    relative = manifest.install.recommended_path.strip().replace("\\", "/")
    return default_models_root() / Path(relative)


def staging_root(
    pack_id: str,
    operation_id: str,
    *,
    destination: str | Path | None = None,
) -> Path:
    """Prefer ``<pack-root>/.adept-staging/<operation-id>``; fall back to data_dir downloads."""
    if destination:
        root = Path(destination).expanduser()
        return root / ".adept-staging" / operation_id
    return settings.data_dir / "downloads" / pack_id / operation_id


def _is_protected_path(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser().absolute()
    parts = {part.lower() for part in resolved.parts}
    if parts & _PROTECTED_DIR_NAMES:
        return True
    # Drive root (C:\) and well-known roots
    if len(resolved.parts) <= 1:
        return True
    if str(resolved).lower() in {"/", "\\"}:
        return True
    return False


def _parse_pack_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackInstallError("pack_json_invalid", "pack.json is missing or invalid.") from exc
    if not isinstance(raw, dict):
        raise PackInstallError("pack_json_invalid", "pack.json must be a JSON object.")
    return raw


def _version_supported(installed: str, expected: str) -> bool:
    """Require a non-empty version; prefer exact match to the pack manifest version."""
    installed = (installed or "").strip()
    expected = (expected or "").strip()
    if not installed:
        return False
    if not expected:
        return True
    return installed == expected


def validate_install_destination(pack_id: str, path: str) -> dict[str, Any]:
    """Validate a folder as a *new* download/install destination (empty folders allowed)."""
    manifest = get_pack_manifest(pack_id)
    target = Path(path).expanduser()
    if _is_protected_path(target):
        raise PackInstallError(
            "path_protected",
            "Choose a different folder. System and protected directories cannot be used as install locations.",
        )

    if target.exists() and not target.is_dir():
        raise PackInstallError("path_missing", "Install destination must be a directory.")

    if not target.exists():
        # Ensure parent is creatable/writable without leaving an empty pack root
        # that could be mistaken for an install after a failed download.
        parent = target.parent if target.parent != target else target
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PackInstallError(
                "path_not_writable",
                f"Could not create install folder: {exc}",
            ) from exc
        try:
            probe = parent / ".adept-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise PackInstallError(
                "path_not_writable",
                f"Install folder is not writable: {exc}",
            ) from exc
        empty = True
    else:
        # Reject folders that already contain a different pack's manifest.
        existing_manifest = target / "pack.json"
        if existing_manifest.is_file():
            try:
                raw = _parse_pack_json(existing_manifest)
            except PackInstallError:
                raise PackInstallError(
                    "incompatible_pack",
                    "This folder already contains an invalid pack.json. Choose an empty folder or link it via Link Existing Folder.",
                )
            existing_id = str(raw.get("id") or raw.get("packId") or "")
            if existing_id and existing_id != pack_id:
                raise PackInstallError(
                    "incompatible_pack",
                    f"This folder already contains pack '{existing_id}', not '{pack_id}'.",
                )
        try:
            probe = target / ".adept-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise PackInstallError(
                "path_not_writable",
                f"Install folder is not writable: {exc}",
            ) from exc
        if not os.access(target, os.W_OK):
            raise PackInstallError("path_not_writable", "Install folder is not writable.")
        empty = not any(p for p in target.iterdir() if p.name != ".adept-staging")

    return {
        "pack_id": pack_id,
        "destination": str(target),
        "empty": empty,
        "version": manifest.version,
    }


def _looks_like_html(data: bytes, content_type: str | None) -> bool:
    ctype = (content_type or "").lower()
    if "text/html" in ctype or "application/xhtml" in ctype:
        return True
    head = data[:256].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


_GITHUB_REDIRECT_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "github.com",
    "www.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "api.github.com",
})


def download_to_file(
    url: str,
    destination: Path,
    *,
    expected_bytes: int | None = None,
    on_progress: ProgressCallback | None = None,
    timeout: float = 60.0,
    max_retries: int = 2,
    headers: dict[str, str] | None = None,
) -> int:
    validate_download_url(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    request_headers = dict(headers or {})
    for attempt in range(max_retries + 1):
        try:
            with httpx.stream(
                "GET", url, timeout=timeout, follow_redirects=True, headers=request_headers or None
            ) as response:
                # Redirect host check
                final_host = (urlparse(str(response.url)).hostname or "").lower()
                original_host = (urlparse(url).hostname or "").lower()
                if final_host and original_host and final_host != original_host:
                    if final_host not in _GITHUB_REDIRECT_HOSTS:
                        raise PackInstallError(
                            "download_url_invalid",
                            "Download redirected to a disallowed host.",
                        )
                    if not str(response.url).startswith("https://") and final_host not in {"localhost", "127.0.0.1"}:
                        raise PackInstallError(
                            "download_url_invalid",
                            "Download redirected to a disallowed host.",
                        )
                if response.status_code in (403, 404):
                    raise PackInstallError(
                        "download_http_error",
                        f"The server returned HTTP {response.status_code}.",
                    )
                if response.status_code >= 400:
                    raise PackInstallError(
                        "download_http_error",
                        f"The server returned HTTP {response.status_code}.",
                    )
                content_type = response.headers.get("content-type")
                content_length = response.headers.get("content-length")
                total = int(content_length) if content_length and content_length.isdigit() else expected_bytes
                downloaded = 0
                first_chunk: bytes | None = None
                with destination.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        if not chunk:
                            continue
                        if first_chunk is None:
                            first_chunk = chunk
                            if _looks_like_html(chunk, content_type):
                                raise PackInstallError(
                                    "download_content_invalid",
                                    "Download response looks like an HTML page, not a pack archive.",
                                )
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            percent = (downloaded / total) if total else 0.0
                            on_progress("downloading", min(percent, 0.99), downloaded, total)
                if downloaded <= 0:
                    raise PackInstallError("download_zero_bytes", "Download produced zero bytes.")
                if total is not None and downloaded != total and content_length:
                    raise PackInstallError(
                        "download_size_mismatch",
                        f"Downloaded {downloaded} bytes but expected {total}.",
                    )
                return downloaded
        except PackInstallError:
            if destination.exists():
                destination.unlink(missing_ok=True)
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if destination.exists():
                destination.unlink(missing_ok=True)
            if attempt >= max_retries:
                raise PackInstallError("download_timeout", "Download timed out.") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if destination.exists():
                destination.unlink(missing_ok=True)
            if attempt >= max_retries:
                raise PackInstallError("download_http_error", f"Download failed: {exc}") from exc
    raise PackInstallError("download_http_error", f"Download failed: {last_error}")


MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXTRACTED_BYTES = 4 * 1024 * 1024 * 1024
MAX_ARCHIVE_FILES = 5000


def _safe_zip_extract(archive_path: Path, content_dir: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_FILES:
            raise PackInstallError("archive_invalid", "Archive contains too many files.")
        total = 0
        for info in infos:
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
                raise PackInstallError("archive_invalid", "Archive contains unsafe paths.")
            if name.endswith("/") or info.is_dir():
                continue
            # Symlink / special bits
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise PackInstallError("archive_invalid", "Archive contains symlink entries.")
            total += int(info.file_size)
            if total > MAX_EXTRACTED_BYTES:
                raise PackInstallError("archive_invalid", "Archive extracted size exceeds the limit.")
            target = (content_dir / name).resolve()
            if not str(target).startswith(str(content_dir.resolve())):
                raise PackInstallError("archive_invalid", "Archive path escapes the staging directory.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def extract_archive(archive_path: Path, content_dir: Path, fmt: str) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PackInstallError("archive_invalid", "Archive exceeds the maximum allowed size.")
    fmt = (fmt or "zip").lower()
    try:
        if fmt == "zip":
            _safe_zip_extract(archive_path, content_dir)
        elif fmt in ("tar", "tar.gz", "tgz"):
            mode = "r:gz" if fmt in ("tar.gz", "tgz") else "r:"
            with tarfile.open(archive_path, mode) as tf:
                tf.extractall(content_dir)
        elif fmt == "none":
            shutil.copy2(archive_path, content_dir / archive_path.name)
        else:
            raise PackInstallError("archive_invalid", f"Unsupported archive format: {fmt}")
    except PackInstallError:
        raise
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
        raise PackInstallError("archive_invalid", f"Archive extraction failed: {exc}") from exc


def _validate_internal_pack_json(content_dir: Path, pack_id: str, version: str) -> None:
    import json

    pack_json = content_dir / "pack.json"
    if not pack_json.is_file():
        raise PackInstallError("required_files_missing", "Downloaded pack is missing pack.json.")
    try:
        raw = json.loads(pack_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackInstallError("archive_invalid", "Internal pack.json is invalid.") from exc
    if str(raw.get("id") or raw.get("packId") or "") != pack_id:
        raise PackInstallError("archive_invalid", "Internal pack.json id does not match the requested pack.")
    if str(raw.get("version") or "") != version:
        raise PackInstallError("archive_invalid", "Internal pack.json version does not match the release.")



def atomic_promote(content_dir: Path, final_dir: Path) -> None:
    final_dir = final_dir.expanduser()
    parent = final_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp_final = parent / f".{final_dir.name}.installing"
    if temp_final.exists():
        shutil.rmtree(temp_final, ignore_errors=True)
    shutil.copytree(content_dir, temp_final)
    if final_dir.exists():
        backup = parent / f".{final_dir.name}.bak"
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        final_dir.rename(backup)
        try:
            temp_final.rename(final_dir)
        except OSError:
            backup.rename(final_dir)
            raise
        shutil.rmtree(backup, ignore_errors=True)
    else:
        temp_final.rename(final_dir)


def install_asset_pack(
    pack_id: str,
    operation_id: str,
    *,
    destination: str | None = None,
    on_progress: ProgressCallback | None = None,
    resolved=None,
) -> dict[str, Any]:
    from .pack_manifests import resolve_pack_download

    manifest = get_pack_manifest(pack_id)
    download = resolved or resolve_pack_download(pack_id, force_refresh=True)
    url = download.download_url
    validate_download_url(url)

    # Exact byte counts come from provider release metadata only. Manifest sizes are estimates.
    expected = int(download.expected_bytes or 0)
    estimate = expected or int(manifest.archive.expected_download_bytes or 0)
    required = tuple(download.required_files or manifest.install.required_files)
    checksum = download.checksum or manifest.archive.checksum
    checksum_algo = (download.checksum_algorithm or manifest.archive.checksum_algorithm or "").lower()
    archive_format = download.archive_format or manifest.archive.format
    version = download.version or manifest.version

    try:
        free = shutil.disk_usage(settings.data_dir).free
        if estimate and free < estimate:
            raise PackInstallError(
                "insufficient_disk_space",
                "There is not enough free disk space for this pack download.",
                recoverable=False,
            )
    except OSError:
        pass

    final_dir = final_install_path(manifest, destination)
    validate_install_destination(pack_id, str(final_dir))
    stage = staging_root(pack_id, operation_id, destination=final_dir)
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    archive_path = stage / f"payload.{archive_format.replace('.', '_')}"
    content_dir = stage / "content"
    downloaded = 0

    def progress(phase: str, percent: float, done: int, total: int | None) -> None:
        if on_progress:
            on_progress(phase, percent, done, total)

    try:
        progress("validating", 0.02, 0, expected)
        downloaded = download_to_file(
            url,
            archive_path,
            expected_bytes=expected,
            on_progress=progress,
            headers=getattr(download, "auth_headers", None) or None,
        )
        if expected and downloaded != expected:
            raise PackInstallError(
                "download_size_mismatch",
                f"Downloaded {downloaded} bytes but expected {expected}.",
            )
        progress("verifying_download", 0.7, downloaded, downloaded)
        if checksum and checksum_algo == "sha256":
            digest = _sha256_file(archive_path)
            if digest.lower() != checksum.lower():
                raise PackInstallError(
                    "download_checksum_failed",
                    "Downloaded pack checksum did not match the release metadata.",
                )
        progress("extracting", 0.8, downloaded, downloaded)
        extract_archive(archive_path, content_dir, archive_format)
        progress("verifying_install", 0.9, downloaded, downloaded)
        ok, missing = required_files_present(content_dir, required)
        if not ok:
            raise PackInstallError(
                "required_files_missing",
                "Downloaded pack is missing required files: " + ", ".join(missing),
            )
        _validate_internal_pack_json(content_dir, pack_id, version)
        installed_bytes = directory_byte_size(content_dir)
        if installed_bytes <= 0:
            raise PackInstallError(
                "required_files_missing",
                "Downloaded pack content is empty after extraction.",
            )
        atomic_promote(content_dir, final_dir)
        progress("completed", 1.0, downloaded, downloaded)
        return {
            "pack_id": pack_id,
            "version": version,
            "destination": str(final_dir),
            "downloaded_bytes": downloaded,
            "installed_bytes": directory_byte_size(final_dir),
            "source_host": public_source_host(url),
            "source_provider": download.source_provider,
            "tag_name": download.tag_name,
            "archive_asset_name": download.archive_asset_name,
            "repository": download.repository,
        }
    except PackInstallError:
        raise
    except Exception as exc:
        # Never let unexpected errors escape as bare exceptions that could take down the worker.
        raise PackInstallError("extract_failed", f"Pack installation failed: {exc}") from exc
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        # Remove empty staging parent when safe.
        try:
            parent = stage.parent
            if parent.name == ".adept-staging" and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
        # Do not leave an empty destination that looks like a linked install.
        try:
            if final_dir.exists() and final_dir.is_dir():
                leftovers = [p for p in final_dir.iterdir() if p.name != ".adept-staging"]
                staging = final_dir / ".adept-staging"
                if staging.exists() and not any(staging.iterdir()):
                    staging.rmdir()
                if not leftovers and not (final_dir / ".adept-staging").exists():
                    # Only remove if pack.json never landed (failed before promote).
                    if not (final_dir / "pack.json").exists():
                        final_dir.rmdir()
        except OSError:
            pass


def link_existing_pack(pack_id: str, path: str) -> dict[str, Any]:
    """Bind an existing pack folder. Requires valid pack.json; rejects empty folders."""
    manifest = get_pack_manifest(pack_id)
    target = Path(path).expanduser()
    if not target.exists():
        raise PackInstallError("path_missing", f"Path not found: {path}")
    if not target.is_dir():
        raise PackInstallError("path_missing", "Pack link path must be a directory.")
    try:
        entries = [p for p in target.iterdir() if p.name != ".adept-staging"]
    except OSError as exc:
        raise PackInstallError("path_missing", f"Cannot read folder: {exc}") from exc
    if not entries:
        raise PackInstallError(
            "empty_folder",
            "Empty folders are not accepted for Link Existing Folder. "
            "Choose a folder that already contains this pack (required: pack.json).",
        )

    pack_json = target / "pack.json"
    if not pack_json.is_file():
        raise PackInstallError(
            "pack_json_missing",
            "A valid pack.json manifest is required to link an existing pack folder.",
        )
    raw = _parse_pack_json(pack_json)
    found_id = str(raw.get("id") or raw.get("packId") or "")
    if found_id != pack_id:
        raise PackInstallError(
            "pack_id_mismatch",
            f"pack.json id '{found_id or 'missing'}' does not match '{pack_id}'.",
        )
    found_version = str(raw.get("version") or "")
    if not _version_supported(found_version, manifest.version):
        raise PackInstallError(
            "pack_version_unsupported",
            f"Pack version '{found_version or 'missing'}' is not supported "
            f"(expected {manifest.version}).",
        )

    ok, missing = required_files_present(target, manifest.install.required_files)
    if not ok:
        raise PackInstallError(
            "required_files_missing",
            "Selected directory is missing required pack files: " + ", ".join(missing),
        )
    installed_bytes = directory_byte_size(target)
    if installed_bytes <= 0:
        raise PackInstallError(
            "required_files_missing",
            "Selected directory has no measurable pack files.",
        )
    return {
        "pack_id": pack_id,
        "destination": str(target),
        "downloaded_bytes": 0,
        "installed_bytes": installed_bytes,
        "version": found_version or manifest.version,
    }


def make_test_zip_bytes(
    required_files: tuple[str, ...],
    payload: bytes = b"pack-data",
    *,
    pack_id: str = "pack_essential_photoreal",
    version: str = "1.0.0",
) -> bytes:
    import json

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for relative in required_files:
            if relative.replace("\\", "/").endswith("pack.json"):
                zf.writestr(
                    relative,
                    json.dumps({"id": pack_id, "version": version, "schemaVersion": 1}),
                )
            else:
                zf.writestr(relative, payload)
    return buffer.getvalue()
