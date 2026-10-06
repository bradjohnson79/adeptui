"""Character Creator V3 Character Angles engine registry.

Wonder3D stays license-blocked forever. Production angles use official
Qwen Image Edit 2509 (Apache-2.0) when that runtime is actually Ready.
Files on disk never imply Ready.
"""

from __future__ import annotations

import time
from typing import Any

from . import wonder3d_runtime

_STATUS_CACHE: dict[str, Any] | None = None
_STATUS_CACHE_AT = 0.0
_STATUS_TTL_SEC = 8.0

ENGINE_QWEN_EDIT_2509 = "qwen_image_edit_2509"
ENGINE_WONDER3D = "wonder3d"
PRODUCTION_ENGINE = ENGINE_QWEN_EDIT_2509

QWEN_EDIT_WORKFLOW_KEY = "qwen_edit_2509.edit"
QWEN_EDIT_FAMILY = "qwen_edit_2509"
QWEN_EDIT_LICENSE = "Apache-2.0"
QWEN_EDIT_WEIGHTS = "Qwen/Qwen-Image-Edit-2509"

ANGLE_PROMPTS = {
    "side": (
        "Show this exact same person as one full-body right-side profile view, "
        "standing, same face hair clothing colors and proportions, simple studio background, "
        "no collage, no text, no second person, no contact sheet."
    ),
    "three_quarter": (
        "Show this exact same person as one full-body three-quarter view from the front-right, "
        "standing, same face hair clothing colors and proportions, simple studio background, "
        "no collage, no text, no second person, no contact sheet."
    ),
    "back": (
        "Show this exact same person as one full-body back view facing away from the camera, "
        "head also turned away so the face is hidden, same hair clothing colors and proportions, "
        "simple studio background, no collage, no text, no second person, no contact sheet."
    ),
}

ANGLE_NEGATIVE = (
    "blurry, low quality, deformed anatomy, extra fingers, extra limbs, "
    "watermark, logo, collage, contact sheet, four panel, split screen, "
    "multiple people, text, caption"
)


def wonder3d_status() -> dict[str, Any]:
    return wonder3d_runtime.runtime_status()


def _gpu_probe() -> tuple[bool, str]:
    try:
        import json
        import urllib.request

        from ..config import settings

        url = f"{str(getattr(settings, 'comfy_url', '') or 'http://127.0.0.1:8188').rstrip('/')}/system_stats"
        with urllib.request.urlopen(url, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        devices = data.get("devices") or []
        names: list[str] = []
        for device in devices:
            name = str(device.get("name") or device.get("name") or "")
            kind = str(device.get("type") or "")
            names.append(name or kind)
            blob = f"{name} {kind}".lower()
            if any(token in blob for token in ("cuda", "nvidia", "geforce", "rtx")):
                return True, name or kind or "gpu"
        return False, "The image runtime reported no CUDA GPU."
    except Exception as exc:
        return False, _creator_runtime_message(str(exc), fallback="The local image runtime is offline.")


def _creator_runtime_message(reason: str, *, fallback: str) -> str:
    blob = (reason or "").lower()
    if any(
        token in blob
        for token in (
            "object_info unavailable",
            "connection refused",
            "winerror 10061",
            "actively refused",
            "urlopen error",
            "failed to connect",
            "gpu probe failed",
        )
    ):
        return (
            "The local image runtime is offline. Pictures already made stay as they are. "
            "Start Background Services to make new Side, 3/4, or Back views."
        )
    if "urlopen" in blob or "winerror" in blob or "traceback" in blob:
        return fallback
    return (reason or "").strip() or fallback


def _service_aware_runtime_message(reason: str, *, fallback: str) -> str:
    try:
        from runtime_supervisor.service_status import collect_runtime_view

        view = collect_runtime_view()
        state = str(view.get("comfyState") or "")
        if state in {"starting", "busy"} or str(view.get("worker") or "") == "loading_qwen":
            return "Preparing Qwen Image Edit…"
        if state == "port_conflict":
            return "Another image program is using the local picture engine. Adept will not take it over."
        if state == "ready":
            sanitized = _creator_runtime_message(reason, fallback=fallback)
            if "offline" in sanitized.lower():
                return "Preparing Qwen Image Edit…"
            return sanitized
    except Exception:
        pass
    return _creator_runtime_message(reason, fallback=fallback)


def qwen_edit_status() -> dict[str, Any]:
    try:
        from ..workflows.qwen_image_edit_2509 import discover_qwen_edit_2509

        disc = discover_qwen_edit_2509()
    except Exception as exc:
        disc = {"installed": False, "runtimeReady": False, "reason": str(exc)}
    installed = bool(disc.get("installed"))
    runtime_ready = bool(disc.get("runtimeReady"))
    model_ready = runtime_ready
    license_clear = True
    gpu_ready, gpu_detail = _gpu_probe()
    available = bool(installed and runtime_ready and model_ready and gpu_ready and license_clear)
    if not installed:
        status = "NOT_INSTALLED"
        code = "MODEL_MISSING"
        message = "Character Angles need Qwen Image Edit 2509 installed in Setup."
    elif not runtime_ready or not model_ready:
        status = "RUNTIME_NOT_READY"
        code = "RUNTIME_NOT_READY"
        message = _service_aware_runtime_message(
            str(disc.get("reason") or ""),
            fallback="Character Angles need the local image runtime ready.",
        )
    elif not gpu_ready:
        status = "GPU_NOT_READY"
        code = "GPU_NOT_READY"
        message = "Character Angles need the local image runtime on GPU."
    else:
        status = "READY"
        code = None
        message = "Character Angles are ready. Side, 3/4, and Back will be created from the approved Front."
    return {
        "engine": ENGINE_QWEN_EDIT_2509,
        "role": "multi_view",
        "installed": installed,
        "runtimeReady": runtime_ready,
        "gpuReady": gpu_ready,
        "modelReady": model_ready,
        "licenseClear": license_clear,
        "available": available,
        "status": status,
        "code": code,
        "blocker": None,
        "weightsId": QWEN_EDIT_WEIGHTS,
        "weightsLicense": QWEN_EDIT_LICENSE,
        "workflowKey": QWEN_EDIT_WORKFLOW_KEY,
        "gpuDetail": gpu_detail,
        "creatorMessage": message,
        "reason": disc.get("reason"),
    }


def production_engine_status(*, force: bool = False) -> dict[str, Any]:
    global _STATUS_CACHE, _STATUS_CACHE_AT
    now = time.monotonic()
    if not force and _STATUS_CACHE is not None and now - _STATUS_CACHE_AT < _STATUS_TTL_SEC:
        return dict(_STATUS_CACHE)
    status = qwen_edit_status()
    _STATUS_CACHE = dict(status)
    _STATUS_CACHE_AT = now
    return status


def assert_can_generate() -> dict[str, Any]:
    from fastapi import HTTPException

    status = production_engine_status(force=True)
    if status.get("available") and status.get("status") == "READY":
        return status
    if status.get("status") in {"RUNTIME_NOT_READY", "GPU_NOT_READY"}:
        try:
            from runtime_supervisor.control_client import call_control, control_plane_reachable

            if control_plane_reachable():
                call_control("POST", "/request-qwen")
                status = production_engine_status(force=True)
                if status.get("available") and status.get("status") == "READY":
                    return status
        except Exception:
            pass
    raise HTTPException(
        status_code=409,
        detail={
            "code": status.get("code") or "RUNTIME_NOT_READY",
            "message": status.get("creatorMessage") or "Character Angles are unavailable.",
            "runtime": status,
        },
    )
