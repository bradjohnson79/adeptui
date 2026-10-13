"""RSA-SHA256 release signatures. The public key is pinned. The private key is not stored here."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

OFFICIAL_CATALOG_URL = "https://adeptui.org/releases/current.json"
OFFICIAL_SIGNATURE_URL = "https://adeptui.org/releases/current.sig"
# Public modulus of the owner release key. The private key stays outside the repository.
PINNED_PUBLIC_MODULUS_HEX = (
    "B6EBBF9B0DDF769B3928BFF37831ECAD4141FBEC75ECE12196A4E10649EAA781"
    "2997467ADC7FC0DAF2E511D493FE97E86B576A29B22934085D73F477AC038F597"
    "46CB5B82DC54FB4D99ABF666E9D0C72D9004BE6CF02A09F3BAF3DCF3791E7B8B88"
    "C6A24CCF37183E810AFDC28CB570DA93B9F753E0F68A3D753F60BDE84A262DD070"
    "5F981750F663A873C31BC63FD55AF38BC7154C64FCB6C2210F7AF7818DB3FA9A11"
    "BCB6EB26E331D43C8A2FAD9C7D54B92BDBEE6F7F9CA601793468925924E15A0D86"
    "59F1896B4CD79FEB71B4EBE8509A032D1D2E456F1B000B3B54C48671D397BAF42D"
    "F520AD7CB0C3F207E532FB55B60C6E7F5460C1AF1524AE5F4BCC6E88CF9F799FED"
    "2E7846E73B62D7B04E4A51D0B2BCF0A636C260D1C8AE331A1D7B3315555C23D26E"
    "8239A058E08551C171D248F6129C6604DA817418A97A44F544687C414C6F6BB146"
    "37A7E7A0193625FF04882103E64229EFFE856A5B3D3A0E1A572ADB399DF5A5FF99"
    "8AAE5F9A30DBBFBFF03224879A37BF14C72BA65BA476B"
)
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
    text = PINNED_PUBLIC_MODULUS_HEX.strip()
    if not text:
        return None
    return PublicKey(int(text, 16), PINNED_PUBLIC_EXPONENT)


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
