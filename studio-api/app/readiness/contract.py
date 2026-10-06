"""One Ready contract for Setup, Source Manager, and runtime health.

Ready is not a single bit. A component may be installed, running, owned,
or executable independently. Setup must never report Ready when the only
path is a URL or empty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

READY_REQUIRES_FILESYSTEM_PATH = "ready_requires_filesystem_path"
KIND_CREDENTIAL = "credential"
# HTTP services and detect-only probes are ready when the service/engine is
# healthy. They are not folder installs, so a missing filesystem path is not
# a readiness failure.
_PATHLESS_READY_KINDS = frozenset(
    {
        KIND_CREDENTIAL,
        "local_service",
        "detect_only",
        "external_service",
    }
)

_MACHINE_MARKERS = (
    ":\\users\\",
    "/users/",
    "\\appdata\\",
    "/appdata/",
    "d:\\",
    "d:/",
    "e:\\",
    "e:/",
)


def is_filesystem_install_path(value: str | None) -> bool:
    """True only for a real folder or file path. URLs and blanks are not paths."""

    raw = str(value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https", "ws", "wss"}:
        return False
    if raw.lower().startswith(("http://", "https://", "ws://", "wss://")):
        return False
    path = Path(raw)
    return bool(path.drive or raw.startswith(("/", "\\\\")) or path.parts)


def apply_files_ready_gate(status: str, path: str | None, *, kind: str = "") -> str:
    """Ready requires a filesystem path except for credentials and live services."""

    if status != "ready":
        return status
    token = (kind or "").strip().lower()
    if token in _PATHLESS_READY_KINDS:
        return status
    if is_filesystem_install_path(path):
        return status
    return "error"


def readiness_axes(
    *,
    installed: bool = False,
    running: bool = False,
    owned: bool = False,
    executable: bool = False,
) -> dict[str, bool]:
    return {
        "installed": bool(installed),
        "running": bool(running),
        "owned": bool(owned),
        "executable": bool(executable),
    }


def _root_kind(path: Path) -> str:
    blob = str(path).replace("/", "\\").lower()
    if any(marker in blob for marker in _MACHINE_MARKERS):
        return "machine_specific"
    return "portable"


def discover_model_roots(*, settings: Any | None = None) -> dict[str, Any]:
    """Discover Adept and Comfy model roots. Label Brad-shaped paths honestly."""

    if settings is None:
        from ..config import settings as app_settings

        settings = app_settings

    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(root_id: str, raw: Any, *, source: str) -> None:
        text = str(raw or "").strip()
        if not text or not is_filesystem_install_path(text):
            return
        path = Path(text).expanduser()
        key = str(path).replace("\\", "/").lower()
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "id": root_id,
                "path": str(path),
                "kind": _root_kind(path),
                "source": source,
                "exists": path.exists(),
            }
        )

    _add("adept_data_models", getattr(settings, "data_dir", None) and Path(settings.data_dir) / "models", source="adept")
    _add("comfy_models", getattr(settings, "comfy_models_dir", None), source="comfy_shared")
    input_dir = getattr(settings, "comfy_input_dir", None)
    if input_dir:
        _add("comfy_shared", Path(input_dir).parent, source="comfy_shared")

    portable = [row for row in rows if row["kind"] == "portable"]
    machine = [row for row in rows if row["kind"] == "machine_specific"]
    return {
        "roots": rows,
        "portable": portable,
        "machineSpecific": machine,
        "machineSpecificCount": len(machine),
    }
