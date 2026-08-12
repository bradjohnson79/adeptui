"""FLUX Kontext conversational edit interface stub (M42 W4).

Always Blocked until flux.kontext_edit is live dual-stage Certified.
Never fake execute or pixel manipulation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .store import read_json, write_json

_SESSIONS_FILE = "kontext_sessions.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _kontext_status() -> str:
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow("flux.kontext_edit")
        if wf and wf.status == "Certified":
            return "CertifiedReady"
        if wf and wf.status == "Draft":
            return "Draft"
    except Exception:
        pass
    return "Blocked"


def _load_sessions(project_id: str) -> dict[str, Any]:
    return read_json(project_id, _SESSIONS_FILE, {"sessions": []})


def _save_sessions(project_id: str, data: dict[str, Any]) -> None:
    write_json(project_id, _SESSIONS_FILE, data)


def create_session(
    project_id: str,
    *,
    source_asset_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = _kontext_status()
    session_id = f"kontext-{uuid4().hex[:12]}"
    session = {
        "sessionId": session_id,
        "projectId": project_id,
        "sourceAssetId": source_asset_id,
        "turns": [],
        "editMemory": {"summary": "", "retainedReferenceIds": [], "lastPinnedContract": None},
        "status": status,
        "createdAt": _now(),
        "metadata": dict(metadata or {}),
        "blockedReason": (
            None
            if status == "CertifiedReady"
            else "flux.kontext_edit is not live dual-stage Certified — conversational edit unavailable"
        ),
    }
    data = _load_sessions(project_id)
    data.setdefault("sessions", []).append(session)
    _save_sessions(project_id, data)
    return session


def add_turn(
    project_id: str,
    session_id: str,
    *,
    role: str,
    text: str,
    edit_intent_id: str | None = None,
    output_asset_id: str | None = None,
) -> dict[str, Any]:
    status = _kontext_status()
    data = _load_sessions(project_id)
    session = None
    for s in data.get("sessions") or []:
        if s.get("sessionId") == session_id:
            session = s
            break
    if not session:
        raise ValueError(f"Kontext session not found: {session_id}")

    turn = {
        "turnId": f"turn-{uuid4().hex[:10]}",
        "role": role,
        "text": text,
        "editIntentId": edit_intent_id,
        "outputAssetId": output_asset_id,
        "createdAt": _now(),
        "executed": False,
        "blocked": status != "CertifiedReady",
    }
    session.setdefault("turns", []).append(turn)
    session["status"] = status
    session["modifiedAt"] = _now()
    if status != "CertifiedReady":
        session["blockedReason"] = (
            "flux.kontext_edit is not Certified — turn recorded but not executed"
        )
    _save_sessions(project_id, data)
    return {
        "session": session,
        "turn": turn,
        "status": status,
        "executable": status == "CertifiedReady",
        "disclosure": "Kontext stub — no pixel manipulation until flux.kontext_edit Certified.",
    }


def get_session(project_id: str, session_id: str) -> dict[str, Any] | None:
    for s in _load_sessions(project_id).get("sessions") or []:
        if s.get("sessionId") == session_id:
            s["status"] = _kontext_status()
            return s
    return None
