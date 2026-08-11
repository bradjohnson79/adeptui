"""ASGI middleware — deny project-scoped APIs while locked without a valid unlock grant."""

from __future__ import annotations

import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .permissions import project_id_from_path, should_enforce_lock

logger = logging.getLogger(__name__)

_ASSET_PATH = re.compile(r"^/api/assets/([0-9a-fA-F-]{36})(/.*)?$")


def _locked_response() -> JSONResponse:
    """Build a fresh locked response so outer CORS middleware can attach headers."""
    return JSONResponse(
        status_code=403,
        content={
            "detail": {
                "code": "PROJECT_LOCKED",
                "message": "This project is password protected. Unlock it before accessing production data.",
            }
        },
    )


def _deny_if_locked(db, service, project_id: str, request: Request):
    if not project_id or not service.is_protected(db, project_id):
        return None
    token = service.extract_unlock_token_for_project(request, project_id)
    if service.is_unlocked(db, project_id, token):
        return None
    return _locked_response()


class ProjectPasswordLockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        method = request.method or "GET"
        if method == "OPTIONS":
            return await call_next(request)
        try:
            from ..db import Asset, SessionLocal
            from . import service

            db = SessionLocal()
            try:
                project_id = None
                if should_enforce_lock(path, method):
                    project_id = project_id_from_path(path)
                else:
                    am = _ASSET_PATH.match(path)
                    if am:
                        asset = db.get(Asset, am.group(1))
                        project_id = getattr(asset, "project_id", None) if asset else None
                if project_id:
                    denied = _deny_if_locked(db, service, project_id, request)
                    if denied is not None:
                        return denied
            finally:
                db.close()
        except Exception:
            logger.exception("project lock middleware error")
            # Fail closed for project-scoped paths only
            if should_enforce_lock(path, method) or _ASSET_PATH.match(path):
                return _locked_response()
        return await call_next(request)
