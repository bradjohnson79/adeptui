"""Studio API / diagnostics client for the loopback control plane."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .canonical_config import try_load_runtime_config
from .constants import CONTROL_PORT
from .control_token import TOKEN_HEADER, read_token


def control_base_url() -> str:
    cfg = try_load_runtime_config()
    port = int(cfg.controlPort) if cfg else CONTROL_PORT
    return f"http://127.0.0.1:{port}"


def control_plane_reachable(timeout: float = 15.0) -> bool:
    try:
        result = call_control("GET", "/status", timeout=timeout)
    except Exception:
        return False
    return bool(result.get("ok") or result.get("serviceState") or result.get("comfyState"))


def call_control(method: str, path: str, *, timeout: float = 30.0) -> dict[str, Any]:
    token = read_token()
    if not token:
        return {"ok": False, "error": "control token missing — Runtime Service is not running"}
    url = control_base_url() + path
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
