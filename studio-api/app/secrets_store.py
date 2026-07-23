from __future__ import annotations

import base64
import hashlib
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


def secret_status(name: str) -> dict:
    hint = secret_hint(name)
    return {
        "configured": bool(hint),
        "hint": hint,
        "fingerprint": secret_fingerprint(name) if hint else None,
    }


# Encode helper used nowhere critical — keeps import of base64 available for tests
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()
