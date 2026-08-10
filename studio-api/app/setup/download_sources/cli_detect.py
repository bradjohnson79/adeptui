"""Detect GitHub CLI and Hugging Face CLI executables (no secrets)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


@dataclass
class CliDetection:
    provider: str  # github | huggingface
    status: str  # Ready | Installed but not authenticated | Not installed | Misconfigured | Unavailable | Verification failed
    cli_detected: bool
    executable_path: str | None
    executable_name: str | None
    version: str | None
    authenticated: bool
    account_name: str | None
    token_available: bool
    last_verified_at: str | None
    message: str
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _e2e_mock() -> dict[str, Any] | None:
    """Optional JSON mock from ADEPT_CLI_MOCK_JSON for Playwright."""
    raw = os.environ.get("ADEPT_CLI_MOCK_JSON", "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _run(cmd: list[str], *, timeout: float = 12.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", "executable not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:
        return 1, "", str(exc)[:200]


def _studio_api_venv_scripts() -> Path | None:
    """studio-api/.venv/{Scripts|bin} even when the API was launched with another Python."""
    # cli_detect.py -> download_sources -> setup -> app -> studio-api
    studio_api = Path(__file__).resolve().parents[3]
    scripts = studio_api / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    return scripts if scripts.is_dir() else None


def _common_cli_candidates(name: str) -> list[Path]:
    """Known install locations when PATH is incomplete (common on Windows services)."""
    candidates: list[Path] = []
    if name == "gh":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.extend(
            [
                Path(pf) / "GitHub CLI" / "gh.exe",
                Path(pf86) / "GitHub CLI" / "gh.exe",
            ]
        )
        if local:
            candidates.append(Path(local) / "Programs" / "GitHub CLI" / "gh.exe")
    if name in {"hf", "huggingface-cli"}:
        # Check Adept UI venv first (canonical install), then the running interpreter's Scripts.
        script_dirs: list[Path] = []
        venv_scripts = _studio_api_venv_scripts()
        if venv_scripts is not None:
            script_dirs.append(venv_scripts)
        script_dirs.append(Path(sys.executable).resolve().parent)
        seen: set[str] = set()
        for scripts in script_dirs:
            key = str(scripts).lower()
            if key in seen:
                continue
            seen.add(key)
            if os.name == "nt":
                candidates.extend(
                    [
                        scripts / f"{name}.exe",
                        scripts / f"{name}.cmd",
                        scripts / "hf.exe",
                        scripts / "huggingface-cli.exe",
                    ]
                )
            else:
                candidates.extend([scripts / name, scripts / "hf", scripts / "huggingface-cli"])
    return candidates


def _which_many(names: list[str]) -> tuple[str | None, str | None]:
    override_key = {
        "gh": "ADEPT_GITHUB_CLI_PATH",
        "hf": "ADEPT_HF_CLI_PATH",
        "huggingface-cli": "ADEPT_HF_CLI_PATH",
    }
    for name in names:
        env_key = override_key.get(name)
        if env_key:
            override = os.environ.get(env_key, "").strip()
            if override:
                path = Path(override)
                if path.is_file():
                    return str(path), name
                return override, name  # misconfigured override
        found = shutil.which(name)
        if found:
            return found, name
        for candidate in _common_cli_candidates(name):
            if candidate.is_file():
                return str(candidate), name
    return None, None


def detect_github_cli() -> CliDetection:
    mock = _e2e_mock()
    if mock and "github" in mock:
        data = mock["github"]
        return CliDetection(
            provider="github",
            status=str(data.get("status") or "Not installed"),
            cli_detected=bool(data.get("cli_detected")),
            executable_path=data.get("executable_path"),
            executable_name=data.get("executable_name") or "gh",
            version=data.get("version"),
            authenticated=bool(data.get("authenticated")),
            account_name=data.get("account_name"),
            token_available=bool(data.get("token_available")),
            last_verified_at=data.get("last_verified_at") or _now(),
            message=str(data.get("message") or ""),
            diagnostics={"mocked": True, **(data.get("diagnostics") or {})},
        )

    path, name = _which_many(["gh"])
    if not path:
        return CliDetection(
            provider="github",
            status="Not installed",
            cli_detected=False,
            executable_path=None,
            executable_name=None,
            version=None,
            authenticated=False,
            account_name=None,
            token_available=False,
            last_verified_at=None,
            message="GitHub CLI (gh) was not found on PATH.",
            diagnostics={"lookup": "which_failed"},
        )
    if not Path(path).is_file() and not shutil.which(path):
        return CliDetection(
            provider="github",
            status="Misconfigured",
            cli_detected=False,
            executable_path=path,
            executable_name=name,
            version=None,
            authenticated=False,
            account_name=None,
            token_available=False,
            last_verified_at=_now(),
            message="Configured GitHub CLI path is invalid.",
            diagnostics={"lookup": "override_invalid"},
        )

    code, out, err = _run([path, "--version"])
    version_match = VERSION_RE.search(out or err or "")
    version = version_match.group(1) if version_match else None
    if code != 0:
        return CliDetection(
            provider="github",
            status="Verification failed",
            cli_detected=True,
            executable_path=path,
            executable_name=name,
            version=version,
            authenticated=False,
            account_name=None,
            token_available=False,
            last_verified_at=_now(),
            message="GitHub CLI was found but `gh --version` failed.",
            diagnostics={"exit_code": code, "command": "gh --version"},
        )

    auth_code, auth_out, auth_err = _run([path, "auth", "status"])
    auth_text = f"{auth_out}\n{auth_err}"
    authenticated = auth_code == 0 and "Logged in" in auth_text
    account = None
    m = re.search(r"Logged in to github\.com account (\S+)", auth_text)
    if m:
        account = m.group(1).strip().strip("'\"")
    token_available = authenticated or "Token:" in auth_text or "token" in auth_text.lower()

    if authenticated:
        status = "Ready"
        message = "GitHub CLI is ready and authenticated."
    else:
        status = "Installed but not authenticated"
        message = "The CLI is installed, but this source may require you to sign in."

    return CliDetection(
        provider="github",
        status=status,
        cli_detected=True,
        executable_path=path,
        executable_name=name,
        version=version,
        authenticated=authenticated,
        account_name=account,
        token_available=bool(token_available and authenticated),
        last_verified_at=_now(),
        message=message,
        diagnostics={
            "exit_code": auth_code,
            "command": "gh auth status",
            "sanitized_summary": "gh auth status (output redacted)",
        },
    )


def _hf_cache_dirs() -> list[Path]:
    dirs: list[Path] = []
    for key in ("HF_HOME", "HUGGINGFACE_HUB_CACHE"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            dirs.append(Path(raw))
    home = Path.home()
    dirs.extend(
        [
            home / ".cache" / "huggingface",
            home / ".huggingface",
        ]
    )
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def _hf_local_token_present() -> bool:
    """True when a local HF token/env credential exists. Never returns token values."""
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return True
    for base in _hf_cache_dirs():
        for candidate in (base / "token", base / "stored_tokens"):
            try:
                if candidate.is_file() and candidate.stat().st_size > 0:
                    return True
            except OSError:
                continue
    return False


def _parse_hf_account(who_text: str) -> str | None:
    for line in who_text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("traceback"):
            continue
        if "token" in line.lower() or "http" in line.lower():
            continue
        # hf auth whoami prints `user=<name>`
        if line.lower().startswith("user="):
            name = line.split("=", 1)[1].strip().strip("'\"")
            return name or None
        return line.split()[-1].strip("'\"") or None
    return None


def detect_huggingface_cli() -> CliDetection:
    mock = _e2e_mock()
    if mock and "huggingface" in mock:
        data = mock["huggingface"]
        return CliDetection(
            provider="huggingface",
            status=str(data.get("status") or "Not installed"),
            cli_detected=bool(data.get("cli_detected")),
            executable_path=data.get("executable_path"),
            executable_name=data.get("executable_name"),
            version=data.get("version"),
            authenticated=bool(data.get("authenticated")),
            account_name=data.get("account_name"),
            token_available=bool(data.get("token_available")),
            last_verified_at=data.get("last_verified_at") or _now(),
            message=str(data.get("message") or ""),
            diagnostics={"mocked": True, **(data.get("diagnostics") or {})},
        )

    path, name = _which_many(["hf", "huggingface-cli"])
    if not path:
        return CliDetection(
            provider="huggingface",
            status="Not installed",
            cli_detected=False,
            executable_path=None,
            executable_name=None,
            version=None,
            authenticated=False,
            account_name=None,
            token_available=False,
            last_verified_at=None,
            message="Hugging Face CLI (hf / huggingface-cli) was not found on PATH.",
            diagnostics={"lookup": "which_failed"},
        )
    if not Path(path).is_file() and shutil.which(path) is None:
        return CliDetection(
            provider="huggingface",
            status="Misconfigured",
            cli_detected=False,
            executable_path=path,
            executable_name=name,
            version=None,
            authenticated=False,
            account_name=None,
            token_available=False,
            last_verified_at=_now(),
            message="Configured Hugging Face CLI path is invalid.",
            diagnostics={"lookup": "override_invalid"},
        )

    code, out, err = _run([path, "version"])
    if code != 0:
        code, out, err = _run([path, "--version"])
    version_match = VERSION_RE.search(out or err or "")
    version = version_match.group(1) if version_match else None

    # Local credentials first. `hf auth whoami` hits the network and can fail even when
    # a valid token is stored (flaky TLS / WinError 10054), which must not look signed-out.
    token_available = _hf_local_token_present()
    who_code, who_out, who_err = _run([path, "auth", "whoami"])
    if who_code != 0 and not token_available:
        # Legacy binary only; skip when we already know a local token exists.
        who_code, who_out, who_err = _run([path, "whoami"])
    who_text = f"{who_out}\n{who_err}".strip()
    who_lower = who_text.lower()
    explicitly_logged_out = any(
        marker in who_lower
        for marker in (
            "not logged in",
            "not authenticated",
            "no token",
            "token is required",
            "please login",
            "please log in",
        )
    )
    network_error = who_code != 0 and any(
        marker in who_lower
        for marker in (
            "connecterror",
            "connectionerror",
            "timeout",
            "temporarily unavailable",
            "winerror",
            "connection reset",
            "forcibly closed",
            "name or service not known",
            "getaddrinfo",
        )
    )
    online_ok = (
        who_code == 0
        and bool(who_text)
        and not explicitly_logged_out
        and "traceback" not in who_lower
    )
    authenticated = online_ok or (token_available and not explicitly_logged_out)
    account = _parse_hf_account(who_text) if online_ok else None

    if online_ok:
        status = "Ready"
        message = "Hugging Face CLI is ready and authenticated."
    elif authenticated and network_error:
        status = "Ready"
        message = (
            "Hugging Face CLI has local credentials. Online account check failed; "
            "downloads may still work."
        )
    elif authenticated:
        status = "Ready"
        message = "Hugging Face CLI has local credentials configured."
    elif Path(path).exists() or shutil.which(path):
        status = "Installed but not authenticated"
        message = "The CLI is installed, but this source may require you to sign in."
    else:
        status = "Unavailable"
        message = "Hugging Face CLI is unavailable."

    return CliDetection(
        provider="huggingface",
        status=status,
        cli_detected=True,
        executable_path=path,
        executable_name=name,
        version=version,
        authenticated=authenticated,
        account_name=account,
        token_available=bool(token_available or authenticated),
        last_verified_at=_now(),
        message=message,
        diagnostics={
            "exit_code": who_code,
            "command": f"{name} auth whoami",
            "sanitized_summary": f"{name} auth whoami (output redacted)",
            "python": sys.executable,
            "local_token": token_available,
            "online_verified": online_ok,
            "network_error": network_error,
        },
    )


def detect_package_managers_windows() -> list[str]:
    found: list[str] = []
    for name in ("winget", "choco", "scoop"):
        if shutil.which(name):
            found.append(name)
    return found
