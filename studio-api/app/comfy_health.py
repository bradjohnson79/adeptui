"""Structured ComfyUI health.

Replaces the previous all-or-nothing check (a raw exception string plus three hardcoded
model-path probes against one developer's `%LOCALAPPDATA%`) with a payload that separates
three independent questions:

1. Is the ComfyUI service reachable at the configured URL?
2. Can we read its node catalogue (`/object_info`) so extension gaps are knowable?
3. Which catalogued model components are verified on disk?

Model presence is answered by the Setup component verifiers — the same source the Setup
Wizard and Source Manager use — so the answer stays consistent and points at real
component ids instead of prose labels.

Reason codes are duplicated as literals here (rather than imported from
`app.capabilities.errors`) to keep this module importable from the capability probes without
an import cycle.
"""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .config import settings

_TRANSIENT_ERROR_MARKERS = (
    "timed out",
    "timeout",
    "temporarily",
    "reset",
    "aborted",
    "broken pipe",
    "disconnected",
    "winerror 10054",
    "winerror 10053",
    "winerror 10060",
    "remote protocol",
    "network is unreachable",
    "connecterror",
    "connecttimeout",
    "readtimeout",
    "writetimeout",
    "pooltimeout",
)
_REFUSED_MARKERS = (
    "connection refused",
    "actively refused",
    "winerror 10061",
    "errno 111",
    "errno 61",
    "connectionrefusederror",
)

DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
DEPENDENCY_DEGRADED = "DEPENDENCY_DEGRADED"
MODEL_MISSING = "MODEL_MISSING"

#: Catalogued components that carry local generation weights, in priority order.
MODEL_COMPONENT_IDS: tuple[str, ...] = (
    "ltx_2_5_checkpoint",
    "ltx_2_5_text_encoder",
    "ltx_2_5_video_vae",
    "ltx_2_5_audio_vae",
    "zimage_models",
    "krea2_models",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _devices(stats: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for device in stats.get("devices") or []:
        if not isinstance(device, dict):
            continue
        total = device.get("vram_total")
        free = device.get("vram_free")
        out.append(
            {
                "name": str(device.get("name") or "")[:120],
                "type": str(device.get("type") or ""),
                "vramTotalMb": round(float(total) / (1024 * 1024)) if isinstance(total, (int, float)) else None,
                "vramFreeMb": round(float(free) / (1024 * 1024)) if isinstance(free, (int, float)) else None,
            }
        )
    return out


def _version(stats: dict[str, Any]) -> str | None:
    system = stats.get("system")
    if isinstance(system, dict):
        for key in ("comfyui_version", "comfy_version", "version"):
            value = system.get(key)
            if value:
                return str(value)[:64]
    return None


def model_component_states() -> list[dict[str, Any]]:
    """Verified state of each catalogued model component (no absolute paths for missing ones)."""
    from .setup.catalog import get_component, dependency_type_for
    from .setup.diagnostics import verify_component

    states: list[dict[str, Any]] = []
    for component_id in MODEL_COMPONENT_IDS:
        try:
            definition = get_component(component_id)
            verification = verify_component(component_id)
        except Exception:  # noqa: BLE001 - a broken probe must not break health
            states.append(
                {
                    "componentId": component_id,
                    "name": component_id,
                    "required": False,
                    "present": False,
                    "issueCode": "verification_failed",
                    "summary": "Component verification could not be completed.",
                    "dependencyType": "UNKNOWN",
                    "filename": None,
                    "expectedPath": None,
                }
            )
            continue
        meta = _component_filename_and_path(component_id, definition)
        states.append(
            {
                "componentId": component_id,
                "name": definition.name,
                "required": bool(definition.required),
                "present": bool(verification.healthy),
                "issueCode": verification.issue_code,
                "summary": verification.summary,
                "version": verification.version,
                "dependencyType": dependency_type_for(component_id),
                "filename": meta["filename"],
                "expectedPath": meta["expectedPath"],
            }
        )
    return states


def _component_filename_and_path(component_id: str, definition: Any) -> dict[str, Any]:
    """Best-effort mapping of a catalogued component to its expected filename + subpath.

    Used so the readiness contract can surface the exact missing dependency file
    (e.g. `gemma4-12b-...safetensors` under `models/text_encoders/`) without the
    frontend inferring from counts. Returns None when no static mapping is known
    (e.g. composite still-image components like `zimage_models`).
    """
    from .config import settings

    mapping = {
        "ltx_2_5_checkpoint": (settings.ltx_2_5_checkpoint, ("diffusion_models", "checkpoints")),
        "ltx_2_5_text_encoder": (settings.ltx_2_5_text_encoder, ("text_encoders",)),
        "ltx_2_5_video_vae": (settings.ltx_2_5_video_vae, ("vae",)),
        "ltx_2_5_audio_vae": (settings.ltx_2_5_audio_vae, ("vae",)),
    }
    spec = mapping.get(component_id)
    if not spec:
        return {"filename": None, "expectedPath": None}
    filename, extra_dirs = spec
    expected_path = "models/" + "/".join(extra_dirs) + "/"
    return {"filename": filename, "expectedPath": expected_path}


async def comfy_health(*, include_nodes: bool = True) -> dict[str, Any]:
    """Probe ComfyUI and return a structured, secret-free health payload."""
    from .comfy_client import comfy

    payload: dict[str, Any] = {
        "reachable": False,
        "status": "unreachable",
        "baseUrl": settings.comfy_url,
        "version": None,
        "devices": [],
        "nodeCatalogAvailable": False,
        "nodeTypeCount": 0,
        "reasonCode": DEPENDENCY_UNAVAILABLE,
        "message": "",
        "recommendedAction": "start_comfyui",
        "models": [],
        "missingModelComponentIds": [],
        "missingRequiredModelComponentIds": [],
        "missingOptionalModelComponentIds": [],
        "checkedAt": _now(),
    }

    try:
        stats = await comfy.health()
    except Exception:  # noqa: BLE001 - the reason is reported, never the stack trace
        payload["message"] = (
            f"ComfyUI is not reachable at {settings.comfy_url}. Start ComfyUI, then refresh."
        )
        payload["models"] = await asyncio.to_thread(model_component_states)
        payload["missingModelComponentIds"] = [
            item["componentId"] for item in payload["models"] if not item["present"]
        ]
        payload["missingRequiredModelComponentIds"] = [
            item["componentId"] for item in payload["models"] if item["required"] and not item["present"]
        ]
        payload["missingOptionalModelComponentIds"] = [
            item["componentId"]
            for item in payload["models"]
            if (not item["required"]) and not item["present"]
        ]
        return payload

    stats = stats if isinstance(stats, dict) else {}
    payload["reachable"] = True
    payload["version"] = _version(stats)
    payload["devices"] = _devices(stats)
    payload["reasonCode"] = None
    payload["recommendedAction"] = None
    payload["status"] = "ready"
    payload["message"] = "ComfyUI is reachable."

    if include_nodes:
        try:
            catalogue = await comfy.get_object_info()
        except Exception:  # noqa: BLE001
            catalogue = None
        if isinstance(catalogue, dict) and catalogue:
            payload["nodeCatalogAvailable"] = True
            payload["nodeTypeCount"] = len(catalogue)
        else:
            payload["status"] = "degraded"
            payload["reasonCode"] = DEPENDENCY_DEGRADED
            payload["recommendedAction"] = "review_comfyui_logs"
            payload["message"] = (
                "ComfyUI is reachable but its node catalogue could not be read, so extension "
                "gaps cannot be detected."
            )

    # Model disk verification is sync filesystem work — keep it off the event loop.
    payload["models"] = await asyncio.to_thread(model_component_states)
    missing = [item["componentId"] for item in payload["models"] if not item["present"]]
    payload["missingModelComponentIds"] = missing
    missing_required = [
        item["componentId"] for item in payload["models"] if item["required"] and not item["present"]
    ]
    missing_optional = [
        item["componentId"]
        for item in payload["models"]
        if (not item["required"]) and not item["present"]
    ]
    # Expose the required-only subset explicitly so downstream consumers (status probe,
    # capability layer, UI) can distinguish "a required model is missing" (runtime-relevant)
    # from "an optional/generator-specific component is missing" (generator-relevant only).
    payload["missingRequiredModelComponentIds"] = missing_required
    payload["missingOptionalModelComponentIds"] = missing_optional
    if missing_required:
        payload["status"] = "degraded"
        payload["reasonCode"] = MODEL_MISSING
        payload["recommendedAction"] = "open_source_manager"
        payload["message"] = (
            "ComfyUI is reachable but required local model components are missing: "
            + ", ".join(missing_required)
            + "."
        )
    payload["checkedAt"] = _now()
    return payload


def classify_comfy_probe_error(exc: BaseException) -> str:
    """Classify a probe exception: timeout | transient | refused | other.

    Connection refused is true-death candidate. Timeouts and reset/abort
    ConnectErrors are transient (busy inference and /free included).
    """
    chain: list[BaseException] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    names = " ".join(type(item).__name__.lower() for item in chain)
    texts = " ".join(str(item).lower() for item in chain)
    blob = f"{names} {texts}"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in names or "timed out" in texts:
        return "timeout"
    if any(marker in blob for marker in _REFUSED_MARKERS) or any(
        isinstance(item, ConnectionRefusedError) for item in chain
    ):
        return "refused"
    if any(marker in blob for marker in _TRANSIENT_ERROR_MARKERS):
        return "transient"
    return "other"


def comfy_port_listening(url: str | None = None) -> bool:
    """True when something accepts TCP on the configured Comfy host:port."""
    raw = str(url or settings.comfy_url or "http://127.0.0.1:8188").rstrip("/")
    host = "127.0.0.1"
    port = 8188
    try:
        parsed = urlparse(raw)
        host = parsed.hostname or host
        port = int(parsed.port or 8188)
    except Exception:  # noqa: BLE001
        pass
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _apply_stats(payload: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    payload["reachable"] = True
    payload["timeout"] = False
    payload["trueDeath"] = False
    payload["version"] = _version(stats)
    payload["devices"] = _devices(stats)
    payload["gpuAvailable"] = bool(payload["devices"])
    payload["status"] = "ready"
    payload["message"] = "ComfyUI is reachable and GPU is available."
    payload["checkedAt"] = _now()
    return payload


def authoritative_comfy_health(*, timeout_sec: float = 3.0) -> dict[str, Any]:
    """The one Comfy health read for Boot and Comfy Manager.

    System stats come from ComfyClient. Process identity comes from the
    existing runtime port owner. This does not start or restart Comfy.
    """
    from runtime_supervisor.ports import listening_pids

    from .comfy_client import comfy

    status, stats = comfy.read_system_stats(timeout_sec)
    try:
        pids = list(listening_pids(8188))
    except Exception:
        pids = []
    devices = stats.get("devices") if isinstance(stats.get("devices"), list) else []
    device = devices[0] if devices and isinstance(devices[0], dict) else {}
    error = None
    if status != 200:
        error = str(stats.get("error") or (f"HTTP {status}" if status else "ComfyUI did not answer"))
    return {
        "healthy": status == 200,
        "endpoint": str(getattr(comfy, "base_url", "http://127.0.0.1:8188")).rstrip("/"),
        "httpStatus": status,
        "pids": pids,
        "pid": pids[0] if pids else None,
        "gpu": device.get("name"),
        "vramTotal": device.get("vram_total"),
        "vramFree": device.get("vram_free"),
        "checkedAt": _now(),
        "error": error,
        "stats": stats if isinstance(stats, dict) else {},
    }


async def _system_stats_once(timeout_sec: float) -> dict[str, Any]:
    from .comfy_client import comfy

    stats = await asyncio.wait_for(comfy.health(), timeout=timeout_sec)
    if not isinstance(stats, dict):
        raise RuntimeError("ComfyUI /system_stats returned an unexpected payload.")
    return stats


async def comfy_health_fast(
    *, timeout_sec: float = 4.0
) -> dict[str, Any]:
    """Fast ComfyUI reachability check (target 3s).

    Checks only that /system_stats responds 200 with GPU info and version.
    Unlike comfy_health, this does NOT inspect the node catalogue or
    verify model components on disk. Use the deep probe for those.

    Transient connect/timeout errors retry once. Busy inference and /free
    slowness are timeouts, not death. True death is connection refused
    with no TCP listener on :8188.
    """
    payload: dict[str, Any] = {
        "reachable": False,
        "status": "unreachable",
        "version": None,
        "devices": [],
        "gpuAvailable": False,
        "message": "",
        "checkedAt": _now(),
        "attempts": 0,
        "transientRetry": False,
        "listenerPresent": None,
        "errorKind": None,
        "trueDeath": False,
        "timeout": False,
        "connectionRefused": False,
        "confirmedAfterRetry": False,
    }

    last_kind: str | None = None
    stats: dict[str, Any] | None = None
    retry_timeout = min(float(timeout_sec), 3.0)
    for attempt in range(1, 3):
        payload["attempts"] = attempt
        this_timeout = float(timeout_sec) if attempt == 1 else retry_timeout
        try:
            stats = await _system_stats_once(this_timeout)
            last_kind = None
            break
        except asyncio.TimeoutError:
            last_kind = "timeout"
        except Exception as exc:  # noqa: BLE001
            last_kind = classify_comfy_probe_error(exc)
        if attempt == 1 and last_kind in {"timeout", "transient"}:
            payload["transientRetry"] = True
            continue
        break

    if stats is not None:
        payload["errorKind"] = None
        payload["listenerPresent"] = True
        return _apply_stats(payload, stats)

    listener = comfy_port_listening()
    payload["listenerPresent"] = listener
    payload["errorKind"] = last_kind
    payload["connectionRefused"] = last_kind == "refused"
    payload["trueDeath"] = last_kind == "refused" and not listener

    # Confirm /system_stats only after a cheap connect miss. A full timeout
    # retry already spent the budget; busy inference / /free stay timed_out.
    if not payload["trueDeath"] and last_kind != "timeout":
        try:
            stats = await _system_stats_once(retry_timeout)
            payload["confirmedAfterRetry"] = True
            payload["listenerPresent"] = True
            return _apply_stats(payload, stats)
        except Exception:  # noqa: BLE001
            payload["confirmedAfterRetry"] = False

    if last_kind == "timeout" or (last_kind in {"transient", "other"} and listener):
        payload["status"] = "timeout"
        payload["timeout"] = True
        payload["trueDeath"] = False
        payload["message"] = f"ComfyUI timed out at {settings.comfy_url}."
        payload["checkedAt"] = _now()
        return payload

    payload["status"] = "unreachable"
    payload["timeout"] = False
    payload["message"] = f"ComfyUI is not reachable at {settings.comfy_url}."
    payload["checkedAt"] = _now()
    return payload


async def node_types(*, timeout_sec: float = 30.0) -> set[str] | None:
    """Return the live ComfyUI node type names, or None when the catalogue is unavailable."""
    from .comfy_client import comfy

    try:
        catalogue = await asyncio.wait_for(comfy.get_object_info(), timeout=timeout_sec)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(catalogue, dict) or not catalogue:
        return None
    return {str(key) for key in catalogue.keys()}
