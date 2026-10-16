"""Release-catalog verification.

Two modes:

``--publishable`` (sign-exactly-what-you-publish)
    Verifies the on-disk catalog that is about to be published. The signature
    must verify over the exact file bytes, those bytes must be the canonical
    form, ``www/public/releases`` must match ``install/catalog``, and the keys
    embedded in ``install.sh`` / ``install.ps1`` must be the pinned trust root.
    With ``--require-openssl``, the check is the install.sh command:
    ``openssl dgst -sha256 -verify <pem from install.sh> -signature ... current.json``.
    Publication is forbidden when this exits non-zero.

default (live)
    Downloads the production catalog and signature and verifies those exact
    bytes with the launcher's ``verify_catalog_rsa`` procedure.

Exit code 0 = pass. Non-zero = the public release is broken.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adept_lifecycle.release import canonical_bytes, verify_catalog_rsa  # noqa: E402
from adept_lifecycle.trust import (  # noqa: E402
    OFFICIAL_CATALOG_URL,
    OFFICIAL_SIGNATURE_URL,
    pinned_public_key,
)

ROOT = Path(__file__).resolve().parents[2]
WWW_CATALOG = ROOT / "www" / "public" / "releases" / "current.json"
WWW_SIGNATURE = ROOT / "www" / "public" / "releases" / "current.sig"
REPO_CATALOG = ROOT / "install" / "catalog" / "current.json"
REPO_SIGNATURE = ROOT / "install" / "catalog" / "current.sig"
INSTALL_SH = ROOT / "install" / "bootstrap" / "install.sh"
INSTALL_PS1 = ROOT / "install" / "bootstrap" / "install.ps1"
WWW_SH = ROOT / "www" / "public" / "install.sh"
WWW_PS1 = ROOT / "www" / "public" / "install.ps1"


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _pem_from_install_sh(script: Path) -> str:
    text = script.read_text(encoding="utf-8")
    match = re.search(
        r"-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----",
        text,
        re.DOTALL,
    )
    if not match:
        raise SystemExit(f"FAIL: {script} has no pinned public key")
    return match.group(0) + "\n"


def _modulus_from_install_ps1(script: Path) -> int:
    text = script.read_text(encoding="utf-8")
    match = re.search(r'\$modulus = "([^"]+)"', text)
    if not match:
        raise SystemExit(f"FAIL: {script} has no pinned modulus")
    raw = base64.b64decode(match.group(1), validate=True)
    return int.from_bytes(raw, "big")


def _verify_bytes(raw: bytes, signature: str, source: str) -> dict:
    catalog = json.loads(raw.decode("utf-8"))
    if not isinstance(catalog, dict):
        raise SystemExit("FAIL: catalog is not a JSON object")
    if b"\r" in raw:
        raise SystemExit("FAIL: catalog contains CR bytes; installers would hash a different message")
    if raw != canonical_bytes(catalog):
        raise SystemExit(
            "FAIL: catalog bytes are not the canonical form. "
            "Raw-bytes installers and the launcher would verify different messages."
        )
    signed = dict(catalog)
    signed["signature"] = "rsa-sha256:" + signature
    verify_catalog_rsa(signed, pinned_public_key())
    version = catalog.get("version")
    artifacts = catalog.get("artifacts") or []
    print(f"PASS ({source}): catalog v{version} with {len(artifacts)} artifacts verifies over the exact file bytes")
    return catalog


def _openssl_verify(catalog: Path, signature: str, pem_text: str) -> None:
    sig = base64.b64decode(signature, validate=True)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        pem_path = work / "release.pub.pem"
        sig_path = work / "current.sig.bin"
        pem_path.write_text(pem_text, encoding="ascii")
        sig_path.write_bytes(sig)
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(pem_path),
                "-signature",
                str(sig_path),
                str(catalog),
            ],
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "openssl failed").strip()
        raise SystemExit(f"FAIL: install.sh openssl procedure rejected the on-disk catalog: {detail}")
    print("PASS (openssl): install.sh procedure verified the exact on-disk catalog bytes")


def assert_publishable(*, require_openssl: bool) -> None:
    """Fail closed unless the files about to be published match the installer contract."""
    pairs = (
        (WWW_CATALOG, REPO_CATALOG, "catalog"),
        (WWW_SIGNATURE, REPO_SIGNATURE, "signature"),
        (WWW_SH, INSTALL_SH, "install.sh"),
        (WWW_PS1, INSTALL_PS1, "install.ps1"),
    )
    for left, right, label in pairs:
        if left.read_bytes() != right.read_bytes():
            raise SystemExit(f"FAIL: www and install copies of {label} differ; refusing to publish a split catalog")
    raw = WWW_CATALOG.read_bytes()
    signature = WWW_SIGNATURE.read_text(encoding="utf-8").strip()
    _verify_bytes(raw, signature, "on-disk")
    pinned = pinned_public_key()
    if pinned is None:
        raise SystemExit("FAIL: pinned public key is empty")
    for script in (INSTALL_PS1, WWW_PS1):
        modulus = _modulus_from_install_ps1(script)
        if modulus != pinned.modulus:
            raise SystemExit(f"FAIL: {script.name} modulus is not the pinned trust root")
    print("PASS: install.ps1 modulus matches the pinned trust root")
    pem = _pem_from_install_sh(INSTALL_SH)
    if _pem_from_install_sh(WWW_SH) != pem:
        raise SystemExit("FAIL: www/public/install.sh public key differs from install/bootstrap/install.sh")
    if require_openssl:
        _openssl_verify(WWW_CATALOG, signature, pem)
    print("PASS: sign-exactly-what-you-publish invariant holds")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Adept UI release catalog.")
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--signature", type=Path, default=None)
    parser.add_argument("--catalog-url", default=OFFICIAL_CATALOG_URL)
    parser.add_argument("--signature-url", default=OFFICIAL_SIGNATURE_URL)
    parser.add_argument(
        "--publishable",
        action="store_true",
        help="verify the on-disk catalog that is about to be published",
    )
    parser.add_argument(
        "--require-openssl",
        action="store_true",
        help="with --publishable, run the install.sh openssl command and fail if it is unavailable",
    )
    args = parser.parse_args()
    try:
        if args.publishable:
            assert_publishable(require_openssl=args.require_openssl)
            return 0
        source = "live"
        if args.catalog and args.signature:
            raw = args.catalog.read_bytes()
            signature = args.signature.read_text(encoding="utf-8").strip()
            source = "local"
        else:
            raw = _download(args.catalog_url)
            signature = _download(args.signature_url).decode("utf-8").strip()
        _verify_bytes(raw, signature, source)
    except SystemExit as exc:
        if exc.code not in (0, None):
            if exc.args and exc.args[0]:
                print(exc.args[0])
            return int(exc.code) if isinstance(exc.code, int) else 1
        raise
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
