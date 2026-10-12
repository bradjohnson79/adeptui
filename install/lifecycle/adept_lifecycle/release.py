"""Approved release catalogs. A commit or CI build is not a release."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from .detect import SystemProfile


class ReleaseError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_bytes(catalog: dict[str, Any]) -> bytes:
    body = {key: value for key, value in catalog.items() if key != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_catalog(catalog: dict[str, Any], key: bytes) -> dict[str, Any]:
    signed = {key: value for key, value in catalog.items() if key != "signature"}
    signed["signature"] = hmac.new(key, canonical_bytes(signed), hashlib.sha256).hexdigest()
    return signed


def verify_catalog(catalog: dict[str, Any], key: bytes | None) -> None:
    if not isinstance(catalog, dict):
        raise ReleaseError("CATALOG_INVALID", "The release catalog is not a document.")
    if catalog.get("approved") is not True:
        raise ReleaseError("NOT_APPROVED", "This catalog is not an owner-approved public release.")
    signature = catalog.get("signature")
    if not key or not isinstance(signature, str) or not signature:
        raise ReleaseError("SIGNATURE_MISSING", "The release catalog has no verifiable signature.")
    expected = hmac.new(key, canonical_bytes(catalog), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ReleaseError("SIGNATURE_INVALID", "The release catalog signature does not match.")


def parse_version(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    parts = str(value).strip().split(".")
    if len(parts) != 3:
        return None
    try:
        numbers = tuple(int(part) for part in parts)
    except ValueError:
        return None
    return numbers  # type: ignore[return-value]


def select_artifact(
    catalog: dict[str, Any],
    profile: SystemProfile,
    installed_version: str | None,
) -> dict[str, Any]:
    installed = parse_version(installed_version) if installed_version else None
    best: dict[str, Any] | None = None
    best_version: tuple[int, int, int] | None = None
    for artifact in catalog.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("platform") != profile.os_name:
            continue
        if artifact.get("arch") != profile.arch:
            continue
        families = artifact.get("distributions")
        if profile.os_name == "linux" and families:
            if profile.linux_family not in families:
                continue
        version = parse_version(str(artifact.get("version") or ""))
        if version is None:
            continue
        if installed is not None and version <= installed:
            continue
        if not artifact.get("sha256"):
            continue
        if best_version is None or version > best_version:
            best = artifact
            best_version = version
    if best is None:
        raise ReleaseError("NO_UPDATE", "No approved update is available for this computer.")
    return best


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    token = expected.lower().removeprefix("sha256:")
    if not hmac.compare_digest(actual, token):
        raise ReleaseError("CHECKSUM_MISMATCH", "The downloaded file does not match the approved checksum.")
