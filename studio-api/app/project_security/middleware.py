"""ASGI middleware — deny project-scoped APIs while locked without a valid unlock grant.

Covers:
- /api/projects/{id}/... and /api/codirector/projects/{id}/... (path-derived)
- /api/assets/{id}/... (asset-row-derived project id)
- /media/projects/{id}/... and /media/assets/{id}/... (CDX-069: static-mount media)
- /api/file?path=... pointing into a project media tree (CDX-069)
Unresolvable project-scoped media URLs fail closed (403).
"""

from __future__ import annotations

import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .permissions import (
    OWNER_WRITE_DENY_HEADER,
    file_path_is_ambiguous,
    media_path_is_ambiguous,
    owner_write_denied,
    project_id_from_file_path,
    project_id_from_media_path,
    project_id_from_path,
    resolve_data_file_path,
    should_enforce_lock,
)

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


def _media_unresolvable_response() -> JSONResponse:
    """Fail closed: media URL shaped like project media but the project id
    cannot be resolved, so the lock cannot be verified."""
    return JSONResponse(
        status_code=403,
        content={
            "detail": {
                "code": "MEDIA_SCOPE_UNRESOLVABLE",
                "message": "Media URL does not resolve to a project scope.",
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


def _project_scoped_media_denied(path: str, raw_path: str) -> bool:
    """True when this media request must fail closed even on middleware errors."""
    if bool(project_id_from_media_path(path)) or media_path_is_ambiguous(path):
        return True
    if bool(project_id_from_file_path(raw_path)) or file_path_is_ambiguous(raw_path):
        return True
    return False


class ProjectPasswordLockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        method = request.method or "GET"
        if method == "OPTIONS":
            return await call_next(request)
        raw_file = ""
        if path == "/api/file":
            try:
                raw_file = request.query_params.get("path") or ""
            except Exception:
                raw_file = ""
        if request.headers.get(OWNER_WRITE_DENY_HEADER) == "1" and owner_write_denied(
            method, path, raw_file
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "code": "OWNER_FIXTURE_WRITE_DENIED",
                        "message": "Destructive tests must not write Schnick Coffee or Korri. Use ADEPT_CERT_PROJECT_ID.",
                    }
                },
            )
        try:
            from ..db import Asset, SessionLocal
            from . import service

            db = SessionLocal()
            try:
                project_id = None
                media_ambiguous = False
                if should_enforce_lock(path, method):
                    project_id = project_id_from_path(path)
                else:
                    am = _ASSET_PATH.match(path)
                    if am:
                        asset = db.get(Asset, am.group(1))
                        project_id = getattr(asset, "project_id", None) if asset else None
                    elif path.startswith("/media/"):
                        project_id = project_id_from_media_path(path)
                        if not project_id and media_path_is_ambiguous(path):
                            media_ambiguous = True
                    elif path == "/api/file":
                        raw_path = request.query_params.get("path") or ""
                        from ..config import settings

                        resolved = resolve_data_file_path(raw_path, settings.data_dir)
                        if resolved is None:
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "detail": {
                                        "code": "FILE_API_RESTRICTED",
                                        "message": "path traversal or escape",
                                    }
                                },
                            )
                        project_id = project_id_from_file_path(str(resolved))
                        if not project_id and file_path_is_ambiguous(str(resolved)):
                            media_ambiguous = True
                if media_ambiguous:
                    return _media_unresolvable_response()
                if project_id:
                    denied = _deny_if_locked(db, service, project_id, request)
                    if denied is not None:
                        return denied
            finally:
                db.close()
        except Exception:
            logger.exception("project lock middleware error")
            # Fail closed for project-scoped paths only
            try:
                raw_path = request.query_params.get("path") or ""
            except Exception:
                raw_path = ""
            if (
                should_enforce_lock(path, method)
                or bool(_ASSET_PATH.match(path))
                or _project_scoped_media_denied(path, raw_path)
            ):
                return _locked_response()
        return await call_next(request)
