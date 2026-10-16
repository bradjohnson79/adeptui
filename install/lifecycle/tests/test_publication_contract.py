"""Negative tests for the public catalog signature contract.

The detached signature covers the exact published bytes. Pretty-printing,
corruption, a wrong key, a missing signature, or a stale signature must fail
closed. These tests do not disable verification.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adept_lifecycle.release import ReleaseError, canonical_bytes, verify_catalog_rsa
from adept_lifecycle.trust import generate_keypair, pinned_public_key, verify_sha256

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "install" / "catalog" / "current.json"
SIGNATURE = ROOT / "install" / "catalog" / "current.sig"


def _raw() -> bytes:
    return CATALOG.read_bytes()


def _sig() -> str:
    return SIGNATURE.read_text(encoding="utf-8").strip()


def test_publishable_command_accepts_the_on_disk_catalog():
    script = ROOT / "install" / "lifecycle" / "verify_published_catalog.py"
    result = subprocess.run(
        [sys.executable, str(script), "--publishable"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_pretty_print_and_crlf_fail_the_installer_contract():
    raw = _raw()
    signature = "rsa-sha256:" + _sig()
    key = pinned_public_key()
    assert key is not None
    assert verify_sha256(raw, signature, key)
    pretty = json.dumps(json.loads(raw.decode("utf-8")), indent=2).encode("utf-8") + b"\n"
    assert pretty != raw
    assert not verify_sha256(pretty, signature, key)
    crlf = raw.replace(b"{", b"{\r\n", 1)
    assert not verify_sha256(crlf, signature, key)


def test_invalid_corrupt_missing_and_wrong_key_fail_closed():
    raw = _raw()
    body = json.loads(raw.decode("utf-8"))
    key = pinned_public_key()
    assert key is not None
    signature = _sig()
    assert not verify_sha256(raw, "rsa-sha256:" + signature[:-8] + "AAAAAAAA", key)
    other, _private = generate_keypair()
    assert not verify_sha256(raw, "rsa-sha256:" + signature, other)
    missing = dict(body)
    with pytest.raises(ReleaseError):
        verify_catalog_rsa(missing, key)
    unapproved = dict(body)
    unapproved["approved"] = False
    unapproved["signature"] = "rsa-sha256:" + signature
    with pytest.raises(ReleaseError):
        verify_catalog_rsa(unapproved, key)
    garbage = dict(body)
    garbage["signature"] = "not-a-signature"
    with pytest.raises(ReleaseError):
        verify_catalog_rsa(garbage, key)


def test_previous_release_signature_does_not_verify_this_catalog():
    # The bytes are the public signature from 78a32164. A shallow checkout
    # cannot run git show for that commit, so the fixture is stored beside the test.
    previous = (Path(__file__).resolve().parent / "fixtures" / "78a32164-current.sig").read_text(encoding="utf-8").strip()
    key = pinned_public_key()
    assert key is not None
    assert previous != _sig()
    assert not verify_sha256(_raw(), "rsa-sha256:" + previous, key)


def test_stale_signature_does_not_cover_a_changed_catalog():
    raw = _raw()
    body = json.loads(raw.decode("utf-8"))
    key = pinned_public_key()
    assert key is not None
    bumped = dict(body)
    bumped["version"] = "9.9.9"
    assert not verify_sha256(canonical_bytes(bumped), "rsa-sha256:" + _sig(), key)
    bom = b"\xef\xbb\xbf" + raw
    assert not verify_sha256(bom, "rsa-sha256:" + _sig(), key)


def test_installer_modulus_matches_the_pinned_trust_root():
    text = (ROOT / "install" / "bootstrap" / "install.ps1").read_text(encoding="utf-8")
    marker = '$modulus = "'
    start = text.index(marker) + len(marker)
    modulus = text[start : text.index('"', start)]
    decoded = int.from_bytes(base64.b64decode(modulus, validate=True), "big")
    key = pinned_public_key()
    assert key is not None
    assert decoded == key.modulus
    www = (ROOT / "www" / "public" / "install.ps1").read_bytes()
    bootstrap = (ROOT / "install" / "bootstrap" / "install.ps1").read_bytes()
    assert www == bootstrap
