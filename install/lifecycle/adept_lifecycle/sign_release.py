"""Owner release-catalog signing helper.

Signs a release catalog with the owner release-signing PEM and writes the raw
base64 signature every verifier expects in ``current.sig`` (no ``rsa-sha256:``
prefix — the launcher prepends that itself before verifying against the pinned
public key).

THE SIGNING CONTRACT (authoritative, P0 2026-10-15):
The detached signature MUST cover the exact bytes of the published
``current.json`` file. The public installers verify the raw downloaded bytes:

- ``install.sh``: ``openssl dgst -sha256 -verify release.pub.pem -signature
  current.sig.bin current.json`` (raw file bytes)
- ``install.ps1``: .NET ``RSA.VerifyData`` over the downloaded content bytes
- launcher: ``verify_catalog_rsa`` over ``canonical_bytes(parsed catalog)``

To satisfy every verifier with one signature, this tool rewrites the catalog
file to its canonical byte form (sorted keys, compact separators, no embedded
``signature`` field, no trailing newline) BEFORE signing, so the raw file
bytes and the canonical bytes are the identical message. It then self-checks
the produced signature against the pinned public key over the exact file
bytes — the installers' procedure — and refuses to write a signature that the
production installers would reject.

Key material is loaded in-process only and is never printed, logged, or
committed. The PEM stays outside the repository at
``%USERPROFILE%/.adept/release-signing.pem``.

Usage::

    python -m adept_lifecycle.sign_release catalog.json --key ~/.adept/release-signing.pem --out current.sig
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from .release import canonical_bytes
from .trust import PrivateKey, pinned_public_key, sign_sha256, verify_sha256


def _load_private_key(pem_path: Path) -> PrivateKey:
    """Parse a PKCS#8 RSA PEM into the repo's PrivateKey (modulus, private_exponent).

    Uses ``cryptography`` solely for PEM/DER parsing; the actual RSA sign uses the
    repo's own ``trust.sign_sha256`` so the signature is byte-identical to what the
    launcher verifies. Never prints or returns key material beyond the two ints.
    """
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        load_pem_private_key,
    )

    raw = pem_path.read_bytes()
    key = load_pem_private_key(raw, password=None)
    numbers = key.private_numbers()
    public = numbers.public_numbers
    return PrivateKey(
        modulus=public.n,
        exponent=public.e,
        private_exponent=numbers.d,
    )


def sign_catalog_file(catalog_path: Path, key_path: Path, out_path: Path) -> str:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict):
        raise SystemExit("catalog is not a JSON object")
    # Rewrite the catalog to its canonical byte form so the served file bytes
    # ARE the signed message for every verifier (openssl/.NET raw bytes and
    # the launcher's canonical form). Any embedded signature field is dropped.
    canonical = canonical_bytes(catalog)
    catalog_path.write_bytes(canonical)
    private = _load_private_key(key_path)
    full = sign_sha256(canonical, private)  # "rsa-sha256:<base64>"
    raw_b64 = full.split(":", 1)[1]
    # Validate it round-trips as strict base64 before writing.
    base64.b64decode(raw_b64, validate=True)
    # Self-check with the installers' exact contract: the signature must verify
    # against the pinned public key over the exact bytes of the file on disk.
    public = pinned_public_key()
    if public is None or not verify_sha256(catalog_path.read_bytes(), full, public):
        raise SystemExit(
            "signing self-check failed: the signature does not verify against the "
            "pinned public key over the exact catalog file bytes; refusing to "
            "publish a catalog the production installers would reject"
        )
    out_path.write_text(raw_b64, encoding="utf-8")
    return raw_b64


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign a release catalog (raw base64 sig for current.sig).")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sign_catalog_file(args.catalog, args.key, args.out)
    # Report only the signature length, never the signature or key material.
    print(f"signed: wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
