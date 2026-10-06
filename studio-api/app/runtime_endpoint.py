"""Studio API endpoint for this process.

Electron sets ADEPT_RUNTIME_MODE and ADEPT_STUDIO_API_PORT before it starts
the packaged API. An unset process is the browser/dev API on 8758.
"""

from __future__ import annotations

import os

_MODES = {"web-development", "electron-development", "electron-packaged"}
_DEV_PORT = 8758


def resolve_studio_api_endpoint() -> dict[str, str | int]:
    mode = (os.environ.get("ADEPT_RUNTIME_MODE") or "web-development").strip()
    if mode not in _MODES:
        mode = "web-development"
    raw = (os.environ.get("ADEPT_STUDIO_API_PORT") or "").strip()
    port = int(raw) if raw.isdigit() else _DEV_PORT
    host = "127.0.0.1"
    return {
        "studioApiHost": host,
        "studioApiPort": port,
        "studioApiBaseUrl": f"http://{host}:{port}",
        "runtimeMode": mode,
    }
