"""RSA-SHA256 release signatures. The public key is pinned. The private key is not stored here."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

OFFICIAL_CATALOG_URL = "https://adeptui.org/releases/current.json"
# Empty until the owner pins the production public key at publication time.
PINNED_PUBLIC_MODULUS = ""
PINNED_PUBLIC_EXPONENT = 65537
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


@dataclass(frozen=True)
class PublicKey:
    modulus: int
    exponent: int = 65537


@dataclass(frozen=True)
class PrivateKey:
    modulus: int
    exponent: int
    private_exponent: int


def _is_probable_prime(number: int, rounds: int = 8) -> bool:
    if number < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31)
    for prime in small_primes:
        if number % prime == 0:
            return number == prime
    difference = number - 1
    shift = 0
    while difference % 2 == 0:
        difference //= 2
        shift += 1
    for _ in range(rounds):
        witness = secrets.randbelow(number - 3) + 2
        value = pow(witness, difference, number)
        if value in {1, number - 1}:
            continue
        for _ in range(shift - 1):
            value = pow(value, 2, number)
            if value == number - 1:
                break
        else:
            return False
    return True


def _prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(candidate):
            return candidate


def _inverse(value: int, modulus: int) -> int:
    return pow(value, -1, modulus)


def generate_keypair(bits: int = 512) -> tuple[PublicKey, PrivateKey]:
    half = bits // 2
    first = _prime(half)
    second = _prime(half)
    while second == first:
        second = _prime(half)
    modulus = first * second
    phi = (first - 1) * (second - 1)
    public_exponent = 65537
    private_exponent = _inverse(public_exponent, phi)
    return PublicKey(modulus, public_exponent), PrivateKey(modulus, public_exponent, private_exponent)


def public_key_from_decimal(modulus: str, exponent: int = 65537) -> PublicKey | None:
    text = (modulus or "").strip()
    if not text:
        return None
    return PublicKey(int(text), exponent)


def pinned_public_key() -> PublicKey | None:
    return public_key_from_decimal(PINNED_PUBLIC_MODULUS, PINNED_PUBLIC_EXPONENT)


def sign_sha256(message: bytes, private_key: PrivateKey) -> str:
    encoded = _pkcs1_sha256(message, (private_key.modulus.bit_length() + 7) // 8)
    signature = pow(int.from_bytes(encoded, "big"), private_key.private_exponent, private_key.modulus)
    raw = signature.to_bytes((private_key.modulus.bit_length() + 7) // 8, "big")
    return "rsa-sha256:" + base64.b64encode(raw).decode("ascii")


def verify_sha256(message: bytes, signature: str, public_key: PublicKey) -> bool:
    prefix = "rsa-sha256:"
    if not signature.startswith(prefix):
        return False
    try:
        raw = base64.b64decode(signature[len(prefix) :], validate=True)
    except ValueError:
        return False
    width = (public_key.modulus.bit_length() + 7) // 8
    if len(raw) != width:
        return False
    value = int.from_bytes(raw, "big")
    if value >= public_key.modulus:
        return False
    decoded = pow(value, public_key.exponent, public_key.modulus).to_bytes(width, "big")
    expected = _pkcs1_sha256(message, width)
    return hmac.compare_digest(decoded, expected)


def _pkcs1_sha256(message: bytes, width: int) -> bytes:
    digest = hashlib.sha256(message).digest()
    padding = b"\xff" * (width - len(SHA256_DIGEST_INFO) - len(digest) - 3)
    return b"\x00\x01" + padding + b"\x00" + SHA256_DIGEST_INFO + digest
