"""Runtime Manager API router.

Provides Setup Wizard and Settings UI with background service status and control.
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from .preferences import load_preferences, save_preferences
from .schemas import (
    RuntimeActionResponse,
    RuntimeManagerPreferences,
    RuntimeManagerStatus,
)
from .service import (
    get_status,
    restart_services,
    start_services,
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


@router.post("/start", response_model=RuntimeActionResponse)
async def handle_start(request: Request):
    _check_hosted(request)
    output = await start_services()
    status = await get_status()
    return RuntimeActionResponse(success=True, message=output, status=status)


@router.post("/stop", response_model=RuntimeActionResponse)
async def handle_stop(request: Request):
    _check_hosted(request)
    output = await stop_services()
    status = await get_status()
    return RuntimeActionResponse(success=True, message=output, status=status)


@router.post("/restart", response_model=RuntimeActionResponse)
async def handle_restart(request: Request):
    _check_hosted(request)
    output = await restart_services()
    status = await get_status()
    return RuntimeActionResponse(success=True, message=output, status=status)


@router.get("/preferences", response_model=RuntimeManagerPreferences)
async def handle_get_preferences():
    return load_preferences()


@router.put("/preferences", response_model=RuntimeManagerPreferences)
async def handle_put_preferences(body: RuntimeManagerPreferences):
    return save_preferences(body)
