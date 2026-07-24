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

    # whoami is non-destructive when available
    who_code, who_out, who_err = _run([path, "auth", "whoami"])
    if who_code != 0:
        who_code, who_out, who_err = _run([path, "whoami"])
    who_text = f"{who_out}\n{who_err}".strip()
    authenticated = who_code == 0 and bool(who_text) and "not logged in" not in who_text.lower()
    account = None
    if authenticated:
        # Prefer first non-empty line that looks like a username
        for line in who_text.splitlines():
            line = line.strip()
            if line and "token" not in line.lower() and "http" not in line.lower():
                account = line.split()[-1].strip("'\"")
                break

    token_env = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    # Never read or return token values — only availability.
    token_available = authenticated or token_env

    if authenticated:
        status = "Ready"
        message = "Hugging Face CLI is ready and authenticated."
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
        token_available=token_available and authenticated,
        last_verified_at=_now(),
        message=message,
        diagnostics={
            "exit_code": who_code,
            "command": f"{name} auth whoami",
            "sanitized_summary": f"{name} auth whoami (output redacted)",
            "python": sys.executable,
        },
    )


def detect_package_managers_windows() -> list[str]:
    found: list[str] = []
    for name in ("winget", "choco", "scoop"):
        if shutil.which(name):
            found.append(name)
    return found
