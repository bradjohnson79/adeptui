"""Studio API / diagnostics client for the loopback control plane."""

from __future__ import annotations

import json
import time
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
    # Each candidate port gets its own slice of the overall deadline. A cold
    # /status on a fresh runner (schtasks query, Comfy probe, provider probe,
    # first-call DLL warmup) can exceed any fixed cap, so within a port's
    # slice we retry until the slice is spent. A definitive answer — an
    # authenticated Adept status, a refused token (401/403), or any other
    # completed HTTP response — ends that port's attempts immediately; only
    # an unreachable/timed-out call is retried.
    per_port = max(1.0, budget / len(ports))
    for port in ports:
        slice_deadline = time.monotonic() + per_port
        while True:
            remaining = slice_deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                result = call_control("GET", "/status", timeout=max(1.0, remaining), port=port)
            except Exception:
                result = {}
            if not isinstance(result, dict):
                result = {}
            if _status_answers(result):
                return True
            # Only a connection-level failure (no response received: refused,
            # timed out, aborted) is retried — the manager may still be
            # warming up. Any received response is a definitive answer about
            # this port and ends its attempts.
            if not result.get("unreachable"):
                break
            if time.monotonic() >= slice_deadline:
                break
            time.sleep(min(0.5, max(0.0, slice_deadline - time.monotonic())))
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
        return {"ok": False, "unreachable": True, "error": f"Runtime Service control plane unreachable: {exc}"}
