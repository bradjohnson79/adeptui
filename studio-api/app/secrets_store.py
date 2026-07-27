from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

SECRETS_DIR = settings.data_dir / "secrets"
MASTER_KEY_FILE = SECRETS_DIR / "master.key"


def _ensure_dir() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)


def _fernet() -> Fernet:
    _ensure_dir()
    if MASTER_KEY_FILE.exists():
        key = MASTER_KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        MASTER_KEY_FILE.write_bytes(key)
        try:
            MASTER_KEY_FILE.chmod(0o600)
        except Exception:
            pass
    return Fernet(key)


def secret_path(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    return SECRETS_DIR / f"{safe}.enc"


def set_secret(name: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        clear_secret(name)
        return
    token = _fernet().encrypt(value.encode("utf-8"))
    path = secret_path(name)
    path.write_bytes(token)
    try:
        path.chmod(0o600)
    except Exception:
        pass


def get_secret(name: str) -> str | None:
    path = secret_path(name)
    if not path.exists():
        return None
    try:
        return _fernet().decrypt(path.read_bytes()).decode("utf-8")
    except (InvalidToken, Exception):
        return None


def clear_secret(name: str) -> None:
    path = secret_path(name)
    if path.exists():
        path.unlink()
    verification_path(name).unlink(missing_ok=True)


def secret_hint(name: str) -> str | None:
    raw = get_secret(name)
    if not raw:
        return None
    if len(raw) <= 8:
        return "••••••••"
    return f"{raw[:4]}••••{raw[-4:]}"


def secret_fingerprint(name: str) -> str | None:
    raw = get_secret(name)
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def verification_path(name: str) -> Path:
    return secret_path(name).with_suffix(".verified.json")


def set_secret_verification(
    name: str,
    *,
    verified: bool | None,
    message: str = "",
    detail: dict | None = None,
) -> dict:
    """Record the outcome of a live probe against the stored credential.

    The record is bound to the key fingerprint, so replacing the key invalidates it
    instead of letting a stale "verified" badge describe a different secret. Only
    non-secret metadata is written — never the key or any prefix of it.
    """
    _ensure_dir()
    record = {
        "verified": verified,
        "message": message,
        "checkedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fingerprint": secret_fingerprint(name),
        "detail": {k: v for k, v in (detail or {}).items() if k not in {"key", "api_key"}},
    }
    path = verification_path(name)
    path.write_text(json.dumps(record), encoding="utf-8")
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return record


def get_secret_verification(name: str) -> dict:
    path = verification_path(name)
    if not path.exists():
        return {}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(record, dict):
        return {}
    if record.get("fingerprint") != secret_fingerprint(name):
        return {}
    return record


def secret_status(name: str) -> dict:
    hint = secret_hint(name)
    verification = get_secret_verification(name) if hint else {}
    verified = verification.get("verified")
    if not hint:
        state = "missing"
    elif verified is True:
        state = "verified"
    elif verified is False:
        state = "invalid"
    else:
        state = "unverified"
    return {
        "configured": bool(hint),
        "hint": hint,
        "fingerprint": secret_fingerprint(name) if hint else None,
        "state": state,
        "verified": verified,
        "verifiedAt": verification.get("checkedAt"),
        "message": verification.get("message", ""),
    }


# Encode helper used nowhere critical — keeps import of base64 available for tests
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()
