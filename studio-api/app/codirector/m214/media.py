"""Media cards, grouping, contextual refs; M2.13 preview when available (no fake 3D)."""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m214_tables
from .store import M214Store, _jid, _now


def create_media_card(
    db: Session,
    *,
    project_id: str,
    kind: str,
    title: str,
    scene_id: str = "",
    group_key: str = "",
    honesty: str = "mocked",
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    if honesty not in {"mocked", "real", "fixture"}:
        honesty = "mocked"
    row_id = str(uuid4())
    media = {
        "id": row_id,
        "projectId": project_id,
        "sceneId": scene_id,
        "kind": kind,
        "title": title,
        "groupKey": group_key or kind,
        "honesty": honesty,
        "status": "draft",
        "payload": payload or {},
        "fake3d": False,
    }
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_media_cards "
            "(id, project_id, scene_id, kind, title, group_key, honesty, status, media_json, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :kind, :title, :gk, :hon, 'draft', :j, :ts, :ts)"
        ),
        {
            "id": row_id,
            "pid": project_id,
            "sid": scene_id,
            "kind": kind,
            "title": title,
            "gk": group_key or kind,
            "hon": honesty,
            "j": _jid(media),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db, capability_id="codirector.media.list", action="create", project_id=project_id, payload={"id": row_id}
    )
    return media


def list_media(db: Session, project_id: str) -> list[dict[str, Any]]:
    ensure_m214_tables()
    rows = db.execute(
        text(
            "SELECT media_json FROM m214_media_cards WHERE project_id = :pid ORDER BY created_at"
        ),
        {"pid": project_id},
    ).fetchall()
    return [json.loads(r[0] or "{}") for r in rows]


def group_media(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = item.get("groupKey") or item.get("kind") or "other"
        groups.setdefault(key, []).append(item)
    return groups


_REF_PATTERNS = [
    (re.compile(r"\bsecond\s+image\b", re.I), "image", 1),
    (re.compile(r"\bfirst\s+image\b", re.I), "image", 0),
    (re.compile(r"\bnewest\s+video\b", re.I), "video", -1),
    (re.compile(r"\blatest\s+audio\b", re.I), "audio", -1),
    (re.compile(r"\benvironment\s+preview\b", re.I), "environment_preview", 0),
]


def resolve_contextual_ref(text_ref: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for pat, kind, idx in _REF_PATTERNS:
        if not pat.search(text_ref or ""):
            continue
        filtered = [i for i in items if i.get("kind") == kind]
        if not filtered:
            return None
        if idx == -1:
            return filtered[-1]
        if 0 <= idx < len(filtered):
            return filtered[idx]
    return None


def hitchhiker_smoke_media(db: Session, project_id: str) -> dict[str, Any]:
    """Create labeled mocked media for hitchhiker smoke test."""
    cards = [
        create_media_card(
            db,
            project_id=project_id,
            kind="image",
            title="Hitchhiker thumb — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="video",
            title="Hitchhiker beat video — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="audio",
            title="Road ambience bed — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="storyboard",
            title="Hitchhiker panels — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="environment_preview",
            title="M2.13 preview slot (no fake 3D)",
            honesty="fixture",
            payload={"m213PreviewIfAvailable": True, "fake3d": False, "label": "FIXTURE"},
        ),
    ]
    return {"projectId": project_id, "cards": cards, "honesty": "mocked", "fake3d": False}
