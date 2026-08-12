"""Project password hashing — Argon2id preferred, PBKDF2-HMAC-SHA256 fallback."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any


ALGORITHM_ARGON2ID = "argon2id"
ALGORITHM_PBKDF2 = "pbkdf2_sha256"
PASSWORD_VERSION = 1
MIN_PASSWORD_LENGTH = 12


def _argon2_available() -> bool:
    try:
        import argon2  # noqa: F401

        return True
    except Exception:
        return False


def hash_password(password: str) -> dict[str, Any]:
    """Return storage fields — never log or return the plaintext."""
    if _argon2_available():
        from argon2 import PasswordHasher
        from argon2.low_level import Type

        ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, type=Type.ID)
        digest = ph.hash(password)
        return {
            "password_hash": digest,
            "password_algorithm": ALGORITHM_ARGON2ID,
            "password_params": {"time_cost": 3, "memory_cost": 65536, "parallelism": 2},
            "password_version": PASSWORD_VERSION,
        }
    salt = secrets.token_bytes(16)
    rounds = 310_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return {
        "password_hash": f"{salt.hex()}${dk.hex()}",
        "password_algorithm": ALGORITHM_PBKDF2,
        "password_params": {"rounds": rounds, "hash": "sha256"},
        "password_version": PASSWORD_VERSION,
    }


def verify_password(password: str, *, password_hash: str, algorithm: str, params: dict[str, Any] | None = None) -> bool:
    if not password_hash or not algorithm:
        return False
    try:
        if algorithm == ALGORITHM_ARGON2ID:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError

            ph = PasswordHasher()
            try:
                return bool(ph.verify(password_hash, password))
            except VerifyMismatchError:
                return False
        if algorithm == ALGORITHM_PBKDF2:
            salt_hex, dk_hex = password_hash.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            rounds = int((params or {}).get("rounds") or 310_000)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
            return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False
    return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_grant_token() -> str:
    return secrets.token_urlsafe(32)
