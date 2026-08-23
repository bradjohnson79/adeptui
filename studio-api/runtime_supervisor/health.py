"""HTTP and process health probes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .constants import (
    API_HEALTH_PATH,
    API_HOST,
    API_PORT,
    COMFY_PORT,
    COMFY_QUEUE_PATH,
    COMFY_STATS_PATH,
    OLLAMA_PORT,
    OLLAMA_TAGS_PATH,
)
from .process import process_alive
from .state import SupervisorState


def _get(url: str, timeout: float) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return int(resp.status), body
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, ""


def http_ok(url: str, timeout: float = 5.0) -> bool:
    status, _ = _get(url, timeout)
    return status == 200


def studio_api_healthy(host: str = API_HOST, port: int = API_PORT, timeout: float = 5.0) -> bool:
    return http_ok(f"http://{host}:{port}{API_HEALTH_PATH}", timeout)


def comfy_healthy(host: str = API_HOST, port: int = COMFY_PORT) -> bool:
    if http_ok(f"http://{host}:{port}{COMFY_STATS_PATH}", timeout=15.0):
        return True
    return http_ok(f"http://{host}:{port}{COMFY_QUEUE_PATH}", timeout=15.0)


def comfy_queue_running(host: str = API_HOST, port: int = COMFY_PORT) -> int:
    status, body = _get(f"http://{host}:{port}{COMFY_QUEUE_PATH}", timeout=15.0)
    if status != 200:
        return 0
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return 0
    running = data.get("queue_running") if isinstance(data, dict) else None
    if isinstance(running, list):
        return len(running)
    return 0


def ollama_healthy(host: str = API_HOST, port: int = OLLAMA_PORT) -> bool:
    return http_ok(f"http://{host}:{port}{OLLAMA_TAGS_PATH}", timeout=5.0)


def tunnel_process_healthy(state: SupervisorState) -> bool:
    rec = state.read_pid("cloudflared")
    if rec and process_alive(rec.pid):
        return True
    return False


def fetch_json(url: str, timeout: float = 8.0) -> dict[str, Any] | None:
    status, body = _get(url, timeout)
    if status != 200:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
