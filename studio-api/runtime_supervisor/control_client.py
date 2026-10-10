"""Studio API / diagnostics client for the loopback control plane."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .canonical_config import try_load_runtime_config
from .constants import CONTROL_PORT, CONTROL_PORT_FALLBACK
from .control_token import TOKEN_HEADER, read_token


def control_port() -> int:
    cfg = try_load_runtime_config()
    return int(cfg.controlPort) if cfg else CONTROL_PORT


def control_candidate_ports() -> list[int]:
    """Configured port first, then the packaged ports. A live manager may be on either."""
    ordered: list[int] = []
    for port in (control_port(), CONTROL_PORT, CONTROL_PORT_FALLBACK):
        if port not in ordered:
            ordered.append(port)
    return ordered


def control_base_url() -> str:
    return f"http://127.0.0.1:{control_port()}"


def authenticated_adept_status(result: dict[str, Any]) -> bool:
    """True only for a token-accepted Adept Background Services status.

    A refused token, a generic ok flag, or an open socket is not identification.
    """
    if result.get("httpStatus") in {401, 403}:
        return False
    if result.get("ok") is not True:
        return False
    pid = result.get("managerPid")
    state = result.get("serviceState")
    return (isinstance(pid, int) and pid > 0) or (isinstance(state, str) and bool(state.strip()))


def _status_answers(result: dict[str, Any]) -> bool:
    return authenticated_adept_status(result)


def control_plane_reachable(timeout: float = 15.0) -> bool:
    """True only when a candidate control port returns the manager status.

    A saved PID or an open socket is not enough. The configured port is tried
    first, then 8759 and the packaged fallback 8779. An occupied port that
    does not answer is left alone.
    """
    budget = max(1.0, float(timeout))
    ports = control_candidate_ports()
    per_port = max(1.0, min(6.0, budget / len(ports)))
    for port in ports:
        try:
            result = call_control("GET", "/status", timeout=per_port, port=port)
        except Exception:
            result = {}
        if isinstance(result, dict) and _status_answers(result):
            return True
    return False


def call_control(method: str, path: str, *, timeout: float = 30.0, port: int | None = None) -> dict[str, Any]:
    token = read_token()
    if not token:
        return {"ok": False, "error": "control token missing — Runtime Service is not running"}
    url = (f"http://127.0.0.1:{int(port)}" if port else control_base_url()) + path
    req = urllib.request.Request(
        url,
        method=method,
        headers={TOKEN_HEADER: token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw) if raw else {}
            return data if isinstance(data, dict) else {"ok": False, "error": "invalid control response"}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"error": body or str(exc)}
        if isinstance(parsed, dict):
            parsed.setdefault("ok", False)
            parsed.setdefault("httpStatus", exc.code)
            return parsed
        return {"ok": False, "error": str(exc), "httpStatus": exc.code}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": f"Runtime Service control plane unreachable: {exc}"}
