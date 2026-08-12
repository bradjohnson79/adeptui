"""Project password protection service — server-side only."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db import Project
from . import audit, grants
from .hashing import MIN_PASSWORD_LENGTH, hash_password, verify_password
from .models import ProjectSecurityRow, ProjectUnlockAttemptRow
from .schemas import DEFAULT_POLICY, ProjectProtectionPolicy, SecurityStatusOut

UNLOCK_HEADER = "X-Adept-Project-Unlock"
UNLOCK_COOKIE_PREFIX = "adept_unlock_"


def ensure_tables() -> None:
    from ..db import Base, engine

    # Import models so metadata is registered
    from . import models as _models  # noqa: F401

    Base.metadata.create_all(
        bind=engine,
        tables=[
            _models.ProjectSecurityRow.__table__,
            _models.ProjectUnlockGrantRow.__table__,
            _models.ProjectSecurityAuditRow.__table__,
            _models.ProjectUnlockAttemptRow.__table__,
        ],
    )


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "") if raw else default
    except Exception:
        return default


def get_or_create_security(db: Session, project_id: str) -> ProjectSecurityRow:
    row = db.get(ProjectSecurityRow, project_id)
    if row:
        return row
    row = ProjectSecurityRow(
        project_id=project_id,
        password_protected=0,
        password_hash=None,
        password_algorithm=None,
        password_params_json="{}",
        password_version=1,
        password_hint=None,
        protection_policy_json=DEFAULT_POLICY.model_dump_json(),
        protection_updated_at=None,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def is_protected(db: Session, project_id: str) -> bool:
    row = db.get(ProjectSecurityRow, project_id)
    return bool(row and row.password_protected and row.password_hash)


def policy_for(row: ProjectSecurityRow | None) -> ProjectProtectionPolicy:
    if not row:
        return DEFAULT_POLICY
    data = _loads(row.protection_policy_json, {})
    try:
        return ProjectProtectionPolicy(**data)
    except Exception:
        return DEFAULT_POLICY


def extract_unlock_token(request) -> str:
    """Read unlock token from header or cookie (never password)."""
    if request is None:
        return ""
    header = request.headers.get(UNLOCK_HEADER) or request.headers.get("x-adept-project-unlock") or ""
    if header.strip():
        return header.strip()
    # Cookie may be per-project: adept_unlock_<projectId>=token — caller passes project via path
    return ""


def extract_unlock_token_for_project(request, project_id: str) -> str:
    token = extract_unlock_token(request)
    if token:
        return token
    if request is None:
        return ""
    cookie_name = f"{UNLOCK_COOKIE_PREFIX}{project_id}"
    return (request.cookies.get(cookie_name) or "").strip()


def is_unlocked(db: Session, project_id: str, token: str) -> bool:
    if not is_protected(db, project_id):
        return True
    row = get_or_create_security(db, project_id)
    if not token:
        return False
    grant = grants.find_valid_grant(
        db, project_id=project_id, token=token, password_version=row.password_version
    )
    return grant is not None


def require_unlocked(db: Session, project_id: str, request) -> None:
    if not is_protected(db, project_id):
        return
    token = extract_unlock_token_for_project(request, project_id)
    if is_unlocked(db, project_id, token):
        return
    raise _err(
        "PROJECT_LOCKED",
        "This project is password protected. Unlock it before accessing production data.",
        403,
    )


def status(db: Session, project_id: str, request=None) -> SecurityStatusOut:
    project = db.get(Project, project_id)
    if not project:
        raise _err("NOT_FOUND", "Project not found.", 404)
    row = get_or_create_security(db, project_id)
    token = extract_unlock_token_for_project(request, project_id) if request else ""
    unlocked = (not bool(row.password_protected)) or is_unlocked(db, project_id, token)
    hint = row.password_hint if row.password_protected else None
    return SecurityStatusOut(
        projectId=project_id,
        passwordProtected=bool(row.password_protected),
        unlocked=unlocked,
        passwordHint=hint,
        passwordVersion=int(row.password_version or 0),
        protectionUpdatedAt=row.protection_updated_at.isoformat() if row.protection_updated_at else None,
        policy=policy_for(row),
        mock=False,
    )


def _validate_password_pair(password: str, confirm: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise _err("PASSWORD_TOO_SHORT", f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if password != confirm:
        raise _err("PASSWORD_MISMATCH", "Passwords do not match.")
    # Hint must not equal password — checked by caller when hint provided


def _check_throttle(db: Session, project_id: str, client_key: str) -> None:
    now = datetime.utcnow()
    row = (
        db.query(ProjectUnlockAttemptRow)
        .filter(
            ProjectUnlockAttemptRow.project_id == project_id,
            ProjectUnlockAttemptRow.client_key == client_key,
        )
        .first()
    )
    if row and row.locked_until and row.locked_until > now:
        secs = max(1, int((row.locked_until - now).total_seconds()))
        raise _err(
            "RATE_LIMITED",
            f"Too many attempts. Try again in {secs} seconds.",
            429,
        )


def _record_failure(db: Session, project_id: str, client_key: str) -> None:
    now = datetime.utcnow()
    row = (
        db.query(ProjectUnlockAttemptRow)
        .filter(
            ProjectUnlockAttemptRow.project_id == project_id,
            ProjectUnlockAttemptRow.client_key == client_key,
        )
        .first()
    )
    if not row:
        row = ProjectUnlockAttemptRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            client_key=client_key,
            failed_count=0,
            window_started_at=now,
            locked_until=None,
        )
        db.add(row)
    # Reset window after 15 minutes
    if row.window_started_at and (now - row.window_started_at) > timedelta(minutes=15):
        row.failed_count = 0
        row.window_started_at = now
        row.locked_until = None
    row.failed_count = int(row.failed_count or 0) + 1
    # Exponential-ish backoff: 5 fails → 30s, 8 → 60s, 12 → 120s
    if row.failed_count >= 12:
        row.locked_until = now + timedelta(seconds=120)
    elif row.failed_count >= 8:
        row.locked_until = now + timedelta(seconds=60)
    elif row.failed_count >= 5:
        row.locked_until = now + timedelta(seconds=30)


def _clear_failures(db: Session, project_id: str, client_key: str) -> None:
    row = (
        db.query(ProjectUnlockAttemptRow)
        .filter(
            ProjectUnlockAttemptRow.project_id == project_id,
            ProjectUnlockAttemptRow.client_key == client_key,
        )
        .first()
    )
    if row:
        row.failed_count = 0
        row.locked_until = None
        row.window_started_at = datetime.utcnow()


def enable_password(
    db: Session,
    project_id: str,
    *,
    password: str,
    confirm_password: str,
    password_hint: str = "",
) -> SecurityStatusOut:
    project = db.get(Project, project_id)
    if not project:
        raise _err("NOT_FOUND", "Project not found.", 404)
    row = get_or_create_security(db, project_id)
    if row.password_protected and row.password_hash:
        raise _err("ALREADY_PROTECTED", "Project is already password protected. Use change password.")
    _validate_password_pair(password, confirm_password)
    hint = (password_hint or "").strip()
    if hint and hint == password:
        raise _err("HINT_INVALID", "Password hint must not contain the password.")
    stored = hash_password(password)
    row.password_protected = 1
    row.password_hash = stored["password_hash"]
    row.password_algorithm = stored["password_algorithm"]
    row.password_params_json = json.dumps(stored["password_params"])
    row.password_version = int(stored["password_version"])
    row.password_hint = hint or None
    row.protection_updated_at = datetime.utcnow()
    grants.revoke_grants(db, project_id)
    audit.record_audit(db, project_id, "project_password_enabled", {"algorithm": stored["password_algorithm"]})
    db.commit()
    return status(db, project_id)


def unlock(
    db: Session,
    project_id: str,
    *,
    password: str,
    remember_for: str = "session",
    session_id: str = "",
    client_key: str = "local",
) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        raise _err("NOT_FOUND", "Project not found.", 404)
    row = get_or_create_security(db, project_id)
    if not row.password_protected or not row.password_hash:
        raise _err("NOT_PROTECTED", "Project is not password protected.")
    _check_throttle(db, project_id, client_key)
    params = _loads(row.password_params_json, {})
    ok = verify_password(
        password,
        password_hash=row.password_hash or "",
        algorithm=row.password_algorithm or "",
        params=params,
    )
    if not ok:
        _record_failure(db, project_id, client_key)
        audit.record_audit(db, project_id, "project_unlock_failed", {"client": client_key[:32]})
        db.commit()
        raise _err("UNLOCK_FAILED", "The password is incorrect.", 401)
    _clear_failures(db, project_id, client_key)
    token, grant = grants.create_grant(
        db,
        project_id=project_id,
        password_version=row.password_version,
        remember_for=remember_for,
        session_id=session_id,
    )
    audit.record_audit(db, project_id, "project_unlock_succeeded", {"rememberFor": remember_for})
    db.commit()
    return {
        "ok": True,
        "projectId": project_id,
        "unlockToken": token,
        "expiresAt": grant.expires_at.isoformat(),
        "passwordProtected": True,
        "mock": False,
    }


def lock_now(db: Session, project_id: str) -> dict[str, Any]:
    n = grants.revoke_grants(db, project_id)
    audit.record_audit(db, project_id, "project_locked", {"grantsRevoked": n})
    audit.record_audit(db, project_id, "project_unlock_grants_revoked", {"count": n})
    db.commit()
    return {"ok": True, "projectId": project_id, "grantsRevoked": n, "mock": False}


def change_password(
    db: Session,
    project_id: str,
    *,
    current_password: str,
    new_password: str,
    confirm_password: str,
    client_key: str = "local",
) -> SecurityStatusOut:
    row = get_or_create_security(db, project_id)
    if not row.password_protected or not row.password_hash:
        raise _err("NOT_PROTECTED", "Project is not password protected.")
    _check_throttle(db, project_id, client_key)
    params = _loads(row.password_params_json, {})
    if not verify_password(
        current_password,
        password_hash=row.password_hash or "",
        algorithm=row.password_algorithm or "",
        params=params,
    ):
        _record_failure(db, project_id, client_key)
        audit.record_audit(db, project_id, "project_unlock_failed", {"reason": "change_password"})
        db.commit()
        raise _err("UNLOCK_FAILED", "The password is incorrect.", 401)
    _validate_password_pair(new_password, confirm_password)
    stored = hash_password(new_password)
    row.password_hash = stored["password_hash"]
    row.password_algorithm = stored["password_algorithm"]
    row.password_params_json = json.dumps(stored["password_params"])
    row.password_version = int(row.password_version or 1) + 1
    row.protection_updated_at = datetime.utcnow()
    n = grants.revoke_grants(db, project_id)
    _clear_failures(db, project_id, client_key)
    audit.record_audit(
        db, project_id, "project_password_changed", {"grantsRevoked": n, "passwordVersion": row.password_version}
    )
    db.commit()
    return status(db, project_id)


def disable_password(
    db: Session,
    project_id: str,
    *,
    current_password: str,
    confirm: bool,
    client_key: str = "local",
) -> SecurityStatusOut:
    if not confirm:
        raise _err("CONFIRMATION_REQUIRED", "Explicit confirmation is required to remove password protection.")
    row = get_or_create_security(db, project_id)
    if not row.password_protected or not row.password_hash:
        raise _err("NOT_PROTECTED", "Project is not password protected.")
    _check_throttle(db, project_id, client_key)
    params = _loads(row.password_params_json, {})
    if not verify_password(
        current_password,
        password_hash=row.password_hash or "",
        algorithm=row.password_algorithm or "",
        params=params,
    ):
        _record_failure(db, project_id, client_key)
        audit.record_audit(db, project_id, "project_unlock_failed", {"reason": "disable"})
        db.commit()
        raise _err("UNLOCK_FAILED", "The password is incorrect.", 401)
    row.password_protected = 0
    row.password_hash = None
    row.password_algorithm = None
    row.password_params_json = "{}"
    row.password_hint = None
    row.password_version = int(row.password_version or 1) + 1
    row.protection_updated_at = datetime.utcnow()
    n = grants.revoke_grants(db, project_id)
    _clear_failures(db, project_id, client_key)
    audit.record_audit(db, project_id, "project_password_disabled", {"grantsRevoked": n})
    db.commit()
    return status(db, project_id)


def reset_password(
    db: Session,
    project_id: str,
    *,
    account_confirmation: str,
    new_password: str,
    confirm_password: str,
) -> SecurityStatusOut:
    """Local-first owner reset — requires explicit account confirmation string."""
    if account_confirmation.strip().lower() not in ("owner", "confirm", "adept-local-owner"):
        raise _err(
            "OWNER_REAUTH_REQUIRED",
            "Reauthenticate as the Adept UI project owner before resetting protection.",
            401,
        )
    row = get_or_create_security(db, project_id)
    if not row.password_protected:
        raise _err("NOT_PROTECTED", "Project is not password protected.")
    _validate_password_pair(new_password, confirm_password)
    stored = hash_password(new_password)
    row.password_hash = stored["password_hash"]
    row.password_algorithm = stored["password_algorithm"]
    row.password_params_json = json.dumps(stored["password_params"])
    row.password_version = int(row.password_version or 1) + 1
    row.protection_updated_at = datetime.utcnow()
    n = grants.revoke_grants(db, project_id)
    audit.record_audit(db, project_id, "project_password_reset", {"grantsRevoked": n})
    db.commit()
    return status(db, project_id)


def apply_duplicate_protection(
    db: Session,
    *,
    source_project_id: str,
    new_project_id: str,
    mode: str,
    password: str = "",
    confirm_password: str = "",
) -> None:
    """Apply protection to a duplicate — always fresh salt/hash, never copy hash."""
    src = db.get(ProjectSecurityRow, source_project_id)
    if mode == "none" or not src or not src.password_protected:
        return
    if mode in ("same_password", "new_password"):
        _validate_password_pair(password, confirm_password or password)
        stored = hash_password(password)
        row = get_or_create_security(db, new_project_id)
        row.password_protected = 1
        row.password_hash = stored["password_hash"]
        row.password_algorithm = stored["password_algorithm"]
        row.password_params_json = json.dumps(stored["password_params"])
        row.password_version = 1
        row.password_hint = None
        row.protection_updated_at = datetime.utcnow()
        audit.record_audit(db, new_project_id, "project_password_enabled", {"via": "duplicate", "mode": mode})
        db.flush()


def redact_project_dict(db: Session, data: dict[str, Any], project_id: str, request=None) -> dict[str, Any]:
    """Redact sensitive list/card fields when locked. Never include password hash."""
    row = db.get(ProjectSecurityRow, project_id)
    protected = bool(row and row.password_protected and row.password_hash)
    token = extract_unlock_token_for_project(request, project_id) if request else ""
    unlocked = (not protected) or is_unlocked(db, project_id, token)
    out = dict(data)
    out["password_protected"] = protected
    out["password_locked"] = protected and not unlocked
    out.pop("password_hash", None)
    if protected and not unlocked:
        pol = policy_for(row)
        if pol.hideDescriptionWhenLocked:
            out["description"] = ""
            out["global_prompt"] = ""
            out["negative_prompt"] = ""
            out["settings_json"] = ""
            out["defaults_json"] = ""
            out["learning_json"] = ""
        if pol.hideThumbnailWhenLocked:
            out["cover_asset_id"] = None
            out["cover_kind"] = None
        if pol.hideSceneCountsWhenLocked:
            out["scene_count"] = 0
            out["scenes"] = []
        if pol.hideAssetCountsWhenLocked:
            out["asset_count"] = 0
            out["assets"] = []
            out["render_pct"] = 0
    return out
