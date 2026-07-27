"""Bridge a fal.ai key that only exists in the environment/.env into the secret store.

The render path reads the credential exclusively from `secrets_store.get_secret("fal_api_key")`
(see `queue_worker`), while readiness checks such as `m29.providers.fal_key_present` also accept
the raw environment. An operator who put `FAL_API_KEY` in `.env` therefore sees "key present" in
diagnostics and "fal.ai API key not configured" the moment a job runs. This module closes that
gap once, at startup, by probing the key and — only if fal does not reject it — writing it into
the encrypted store.

`.env` values are read without the `STUDIO_` prefix that `config.Settings` applies, because the
fal SDK convention is a bare `FAL_KEY`/`FAL_API_KEY`. Nothing here logs, returns, or persists the
key itself: every report carries at most a fingerprint produced by `secrets_store`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Mapping

from .fal_client import validate_fal_key
from .secrets_store import get_secret, secret_fingerprint, set_secret, set_secret_verification

logger = logging.getLogger(__name__)

SECRET_NAME = "fal_api_key"
ENV_KEY_NAMES = ("FAL_API_KEY", "FAL_KEY")
# Hermetic runs (pytest, e2e) set this to 0 so startup never reaches out to fal.
ENABLE_ENV_VAR = "STUDIO_FAL_ENV_BRIDGE"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_ROOT = Path(__file__).resolve().parents[1]


def dotenv_candidates() -> list[Path]:
    """`.env` locations to consult, nearest launch directory first."""
    seen: list[Path] = []
    for candidate in (Path.cwd() / ".env", _API_ROOT / ".env", _REPO_ROOT / ".env"):
        if candidate not in seen:
            seen.append(candidate)
    return seen


def parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal dotenv parse - no dependency, tolerant of quotes and `export` prefixes."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, raw = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        if name:
            values[name] = raw
    return values


def find_env_key(env: Mapping[str, str] | None = None) -> tuple[str | None, str | None]:
    """Return `(key, source)` for the first fal credential found in env, then `.env`.

    `source` is a human-readable origin such as `"FAL_API_KEY"` or `".env:FAL_KEY"` and is
    safe to log; `key` never is.
    """
    environ = os.environ if env is None else env
    for name in ENV_KEY_NAMES:
        value = (environ.get(name) or "").strip()
        if value:
            return value, name
    for path in dotenv_candidates():
        if not path.exists():
            continue
        parsed = parse_dotenv(path)
        for name in ENV_KEY_NAMES:
            value = (parsed.get(name) or "").strip()
            if value:
                return value, f".env:{name}"
    return None, None


async def bridge_fal_key_from_env(*, export_to_environ: bool = True) -> dict[str, Any]:
    """Seed the stored fal credential from the environment when the store is empty.

    Returns a secret-free report whose `action` is one of:

    * ``already-configured`` - a stored key exists; the environment is left untouched
    * ``no-key`` - nothing found in env or `.env`
    * ``stored`` - fal accepted the key and it was written to the store
    * ``stored-unverified`` - fal could not be reached; the key was stored and flagged unverified
    * ``rejected`` - fal actively rejected the key, so nothing was stored
    """
    report: dict[str, Any] = {"action": "no-key", "source": None, "fingerprint": None, "message": ""}

    if get_secret(SECRET_NAME):
        report.update(
            action="already-configured",
            fingerprint=secret_fingerprint(SECRET_NAME),
            message="A fal.ai key is already stored; environment value ignored.",
        )
        return report

    key, source = find_env_key()
    if not key:
        report["message"] = "No FAL_API_KEY/FAL_KEY in the environment or .env."
        return report

    report["source"] = source
    if export_to_environ:
        # Readiness probes read the bare names; make a .env-only key visible process-wide.
        for name in ENV_KEY_NAMES:
            os.environ.setdefault(name, key)

    probe = await validate_fal_key(key)
    probe_detail = {k: v for k, v in probe.items() if k != "valid"}

    if probe.get("valid") is False:
        report.update(
            action="rejected",
            message=probe.get("message") or "fal.ai rejected the key from the environment.",
        )
        return report

    set_secret(SECRET_NAME, key)
    set_secret_verification(
        SECRET_NAME,
        verified=probe.get("valid"),
        message=probe.get("message", ""),
        detail={**probe_detail, "seededFrom": source},
    )
    report.update(
        action="stored" if probe.get("valid") else "stored-unverified",
        fingerprint=secret_fingerprint(SECRET_NAME),
        message=probe.get("message", ""),
    )
    return report


def bridge_enabled(env: Mapping[str, str] | None = None) -> bool:
    environ = os.environ if env is None else env
    return (environ.get(ENABLE_ENV_VAR, "1") or "").strip().lower() not in {"0", "false", "no", "off"}


async def bridge_fal_key_at_startup() -> dict[str, Any]:
    """Lifespan entry point: bridge the key, and never let a failure block startup."""
    if not bridge_enabled():
        return {"action": "disabled", "source": None, "fingerprint": None, "message": ""}
    try:
        report = await bridge_fal_key_from_env()
    except Exception:  # noqa: BLE001 - credential seeding must not stop the API
        logger.exception("fal.ai key bridge failed")
        return {"action": "error", "source": None, "fingerprint": None, "message": ""}

    action = report["action"]
    if action == "stored":
        logger.info("fal.ai key seeded from %s and verified (fingerprint %s)", report["source"], report["fingerprint"])
    elif action == "stored-unverified":
        logger.warning("fal.ai key seeded from %s but could not be verified: %s", report["source"], report["message"])
    elif action == "rejected":
        logger.warning("fal.ai rejected the key found in %s; nothing was stored", report["source"])
    return report
