"""Project security HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from . import audit, service
from .production_gate import evaluate_project_password_protection_gate
from .schemas import (
    ChangePasswordBody,
    DisablePasswordBody,
    ResetPasswordBody,
    SetPasswordBody,
    UnlockBody,
)

router = APIRouter()


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for") or ""
    ip = (fwd.split(",")[0] if fwd else "") or (request.client.host if request.client else "local")
    return f"{ip}:{(request.headers.get('user-agent') or '')[:80]}"


@router.get("/project-security/gate/password-protection")
def password_protection_gate():
    g = evaluate_project_password_protection_gate()
    return {**g, "ok": bool(g.get("projectPasswordProtectionGo")), "passed": bool(g.get("projectPasswordProtectionGo"))}


@router.get("/projects/{project_id}/security")
def get_security(project_id: str, request: Request, db: Session = Depends(get_db)):
    return service.status(db, project_id, request)


@router.post("/projects/{project_id}/security/password")
def set_password(project_id: str, body: SetPasswordBody, db: Session = Depends(get_db)):
    return service.enable_password(
        db,
        project_id,
        password=body.password,
        confirm_password=body.confirmPassword,
        password_hint=body.passwordHint or "",
    )


@router.post("/projects/{project_id}/security/unlock")
def unlock_project(project_id: str, body: UnlockBody, request: Request, response: Response, db: Session = Depends(get_db)):
    result = service.unlock(
        db,
        project_id,
        password=body.password,
        remember_for=body.rememberFor,
        session_id=body.sessionId or "",
        client_key=_client_key(request),
    )
    cookie_name = f"{service.UNLOCK_COOKIE_PREFIX}{project_id}"
    response.set_cookie(
        key=cookie_name,
        value=result["unlockToken"],
        httponly=True,
        samesite="lax",
        max_age=12 * 3600 if body.rememberFor == "session" else (900 if body.rememberFor == "15m" else 3600),
        path="/",
    )
    return result


@router.post("/projects/{project_id}/security/lock")
def lock_project(project_id: str, response: Response, db: Session = Depends(get_db)):
    result = service.lock_now(db, project_id)
    response.delete_cookie(f"{service.UNLOCK_COOKIE_PREFIX}{project_id}", path="/")
    return result


@router.patch("/projects/{project_id}/security/password")
def change_password(project_id: str, body: ChangePasswordBody, request: Request, response: Response, db: Session = Depends(get_db)):
    out = service.change_password(
        db,
        project_id,
        current_password=body.currentPassword,
        new_password=body.newPassword,
        confirm_password=body.confirmPassword,
        client_key=_client_key(request),
    )
    response.delete_cookie(f"{service.UNLOCK_COOKIE_PREFIX}{project_id}", path="/")
    return out


@router.delete("/projects/{project_id}/security/password")
@router.post("/projects/{project_id}/security/password/disable")
def disable_password(
    project_id: str,
    request: Request,
    response: Response,
    body: DisablePasswordBody = Body(...),
    db: Session = Depends(get_db),
):
    out = service.disable_password(
        db,
        project_id,
        current_password=body.currentPassword,
        confirm=body.confirm,
        client_key=_client_key(request),
    )
    response.delete_cookie(f"{service.UNLOCK_COOKIE_PREFIX}{project_id}", path="/")
    return out


@router.post("/projects/{project_id}/security/reset")
def reset_password(project_id: str, body: ResetPasswordBody, response: Response, db: Session = Depends(get_db)):
    out = service.reset_password(
        db,
        project_id,
        account_confirmation=body.accountConfirmation,
        new_password=body.newPassword,
        confirm_password=body.confirmPassword,
    )
    response.delete_cookie(f"{service.UNLOCK_COOKIE_PREFIX}{project_id}", path="/")
    return out


@router.get("/projects/{project_id}/security/audit")
def security_audit(project_id: str, request: Request, db: Session = Depends(get_db)):
    # Audit listing requires unlock when protected
    service.require_unlocked(db, project_id, request)
    return {"items": audit.list_audit(db, project_id), "mock": False}
