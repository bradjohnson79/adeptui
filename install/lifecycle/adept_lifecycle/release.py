"""Approved release catalogs. A commit or CI build is not a release."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from .detect import SystemProfile
from .trust import PublicKey, PrivateKey, sign_sha256, verify_sha256


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


def sign_catalog_rsa(catalog: dict[str, Any], private_key: PrivateKey) -> dict[str, Any]:
    signed = {key: value for key, value in catalog.items() if key != "signature"}
    signed["signature"] = sign_sha256(canonical_bytes(signed), private_key)
    return signed


def verify_catalog_rsa(catalog: dict[str, Any], public_key: PublicKey) -> None:
    if not isinstance(catalog, dict):
        raise ReleaseError("CATALOG_INVALID", "The release catalog is not a document.")
    if catalog.get("approved") is not True:
        raise ReleaseError("NOT_APPROVED", "This catalog is not an owner-approved public release.")
    signature = catalog.get("signature")
    if not isinstance(signature, str) or not verify_sha256(canonical_bytes(catalog), signature, public_key):
        raise ReleaseError("SIGNATURE_INVALID", "The release catalog signature does not match the pinned public key.")
    for artifact in catalog.get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("url"):
            assert_release_url(str(artifact["url"]))


def assert_release_url(url: str) -> None:
    lowered = url.lower()
    if lowered.startswith("file:") or "localhost" in lowered or "127.0.0.1" in lowered:
        raise ReleaseError("UNTRUSTED_URL", "The release catalog points at a local address.")
    if any(token in lowered for token in ("c:\\", "/users/", "/home/", "d:\\")):
        raise ReleaseError("UNTRUSTED_URL", "The release catalog points at a private filesystem path.")
    if "github.com" in lowered and "/releases/download/" not in lowered:
        raise ReleaseError("UNTRUSTED_URL", "A GitHub branch is not an installation source.")


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


# Installations and catalogs published before this field are revision 0.
# A higher revision is a newer build of the same application version.
BASELINE_REVISION = 0


def release_revision(value: Any) -> int:
    """Missing or unusable revisions are the documented baseline, 0."""
    if isinstance(value, bool) or value is None or value == "":
        return BASELINE_REVISION
    try:
        number = int(value)
    except (TypeError, ValueError):
        return BASELINE_REVISION
    if number < 0:
        return BASELINE_REVISION
    return number


def catalog_release_revision(catalog: dict[str, Any] | None, artifact: dict[str, Any] | None) -> int:
    """Artifact revision wins. Otherwise the catalog revision. Otherwise baseline 0."""
    if isinstance(artifact, dict) and "revision" in artifact:
        return release_revision(artifact.get("revision"))
    if isinstance(catalog, dict) and "revision" in catalog:
        return release_revision(catalog.get("revision"))
    return BASELINE_REVISION


def compare_release(
    installed_version: str | None,
    installed_revision: Any,
    candidate_version: str | None,
    candidate_revision: Any,
) -> str:
    """Return upgrade, current, or downgrade. Revisions are compared only for equal versions."""
    installed = parse_version(installed_version)
    candidate = parse_version(candidate_version)
    if candidate is None:
        return "current"
    if installed is None:
        return "upgrade"
    if candidate > installed:
        return "upgrade"
    if candidate < installed:
        return "downgrade"
    installed_rev = release_revision(installed_revision)
    candidate_rev = release_revision(candidate_revision)
    if candidate_rev > installed_rev:
        return "upgrade"
    if candidate_rev < installed_rev:
        return "downgrade"
    return "current"


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
    installed_revision: Any = None,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    best_key: tuple[tuple[int, int, int], int] | None = None
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
        revision = catalog_release_revision(catalog, artifact)
        if installed_version:
            decision = compare_release(
                installed_version,
                installed_revision,
                str(artifact.get("version") or ""),
                revision,
            )
            if decision != "upgrade":
                continue
        if not artifact.get("sha256"):
            continue
        key = (version, revision)
        if best_key is None or key > best_key:
            best = artifact
            best_key = key
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
