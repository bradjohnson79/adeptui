"""Runtime Manager API router.

Setup Wizard uses status and validate-config only.
Settings / Advanced and the startup modal own lifecycle actions.
"""
import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from .preferences import load_preferences, save_preferences
from .schemas import (
    EnableRecommendedBody,
    RuntimeActionResponse,
    RuntimeConfigValidation,
    RuntimeManagerPreferences,
    RuntimeManagerStatus,
)
from .service import (
    enable_recommended_services,
    get_status,
    repair_background_services,
    validate_runtime_configuration,
    restart_api_service,
    restart_comfy_service,
    restart_ollama_service,
    restart_route_a_service,
    restart_services,
    start_ollama_service,
    start_route_a_service,
    start_services,
    stop_ollama_service,
    stop_route_a_service,
    stop_services,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runtime-manager", tags=["runtime-manager"])

_HOSTED_ORIGINS = {
    "https://adeptui.vercel.app",
    "https://adeptui.vercel.app/",
}


def _is_hosted_request(request: Request) -> bool:
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    for pattern in _HOSTED_ORIGINS:
        if origin.startswith(pattern) or referer.startswith(pattern):
            return True
    return bool(os.environ.get("VERCEL"))


def _check_hosted(request: Request):
    if _is_hosted_request(request):
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "HOSTED_UI_LIFECYCLE_NOT_SUPPORTED",
                "message": "Lifecycle actions are not available from browser-hosted Adept UI. "
                           "Use the desktop application for local service management.",
            },
        )


@router.get("/status", response_model=RuntimeManagerStatus)
async def handle_get_status():
    return await get_status()


@router.get("/validate-config", response_model=RuntimeConfigValidation)
async def handle_validate_config():
    """Installation and path check only. Never a service launcher."""
    return await validate_runtime_configuration()


@router.post("/start", response_model=RuntimeActionResponse)
async def handle_start(request: Request):
    _check_hosted(request)
    output = await start_services()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/stop", response_model=RuntimeActionResponse)
async def handle_stop(request: Request):
    _check_hosted(request)
    output = await stop_services()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/restart", response_model=RuntimeActionResponse)
async def handle_restart(request: Request):
    _check_hosted(request)
    output = await restart_services()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/request-qwen", response_model=RuntimeActionResponse)
async def handle_request_qwen(request: Request):
    _check_hosted(request)
    from runtime_supervisor.qwen_residency import request_qwen

    # Residency talks to the owned Comfy process. Do not restart the Runtime
    # Service just to reload a control-plane wrapper, and do not re-enter
    # get_status() on the same worker (self-GET can stall uvicorn --workers 1).
    remote = await asyncio.to_thread(request_qwen)
    ok = bool(remote.get("ok"))
    return RuntimeActionResponse(
        success=ok,
        message=str(remote.get("message") or remote.get("error") or "request-qwen"),
        status=None,
    )


@router.post("/enable-recommended", response_model=RuntimeActionResponse)
async def handle_enable_recommended(request: Request, body: EnableRecommendedBody | None = None):
    _check_hosted(request)
    start_with_windows = True if body is None else bool(body.startWithWindows)
    output = await enable_recommended_services(start_with_windows)
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/restart-api", response_model=RuntimeActionResponse)
async def handle_restart_api(request: Request):
    _check_hosted(request)
    output = await restart_api_service()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=None)


@router.post("/restart-comfy", response_model=RuntimeActionResponse)
async def handle_restart_comfy(request: Request):
    _check_hosted(request)
    output = await restart_comfy_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/start-route-a", response_model=RuntimeActionResponse)
async def handle_start_route_a(request: Request):
    # Unified Runtime Fabric: Route A (MiniMax H3 :8192) is ON DEMAND. Starts when an
    # H3 generation is requested, with GPU handoff from canonical Comfy :8188 (/free,
    # never kill). This is the supervisor-owned lifecycle path — feature pages must
    # call this endpoint instead of spawning workers or probing :8192 directly.
    _check_hosted(request)
    output = await start_route_a_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/stop-route-a", response_model=RuntimeActionResponse)
async def handle_stop_route_a(request: Request):
    _check_hosted(request)
    output = await stop_route_a_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/restart-route-a", response_model=RuntimeActionResponse)
async def handle_restart_route_a(request: Request):
    _check_hosted(request)
    output = await restart_route_a_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/start-ollama", response_model=RuntimeActionResponse)
async def handle_start_ollama(request: Request):
    _check_hosted(request)
    output = await start_ollama_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/stop-ollama", response_model=RuntimeActionResponse)
async def handle_stop_ollama(request: Request):
    _check_hosted(request)
    output = await stop_ollama_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/restart-ollama", response_model=RuntimeActionResponse)
async def handle_restart_ollama(request: Request):
    _check_hosted(request)
    output = await restart_ollama_service()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.post("/repair", response_model=RuntimeActionResponse)
async def handle_repair(request: Request):
    _check_hosted(request)
    output = await repair_background_services()
    status = await get_status()
    return RuntimeActionResponse(success=not output.startswith("ERROR:"), message=output, status=status)


@router.get("/preferences", response_model=RuntimeManagerPreferences)
async def handle_get_preferences():
    from runtime_supervisor.bootstrap import actual_start_with_windows

    prefs = load_preferences()
    prefs.startWithWindows = actual_start_with_windows()
    return prefs


@router.put("/preferences", response_model=RuntimeManagerPreferences)
async def handle_put_preferences(body: RuntimeManagerPreferences):
    from runtime_supervisor.bootstrap import actual_start_with_windows, apply_start_with_windows

    wanted = bool(body.startWithWindows)
    result = apply_start_with_windows(wanted)
    actual = actual_start_with_windows()
    persist = body.model_copy(update={"startWithWindows": actual})
    saved = save_preferences(persist)
    saved.startWithWindows = actual
    if wanted and not actual:
        raise HTTPException(
            status_code=403,
            detail=str(result.get("message") or "Start with Windows is off until AdeptRuntimeService is registered."),
        )
    return saved
