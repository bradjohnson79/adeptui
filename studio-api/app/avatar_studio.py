"""Avatar Studio sessions — structured talking-avatar packages.

Character/Profile → Appearance → Voice → Performance → Lip Sync → Clip → Director
Voice execute path this pass: uploaded audio (TTS fields stored, not executed).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, Project, engine, get_db

router = APIRouter(tags=["avatar-studio"])


class AvatarSessionRow(Base):
    __tablename__ = "avatar_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200), default="Avatar Session")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


def ensure_avatar_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[AvatarSessionRow.__table__])


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _empty(project_id: str, name: str = "Avatar Session") -> dict[str, Any]:
    now = _now()
    sid = f"avs-{uuid.uuid4().hex[:10]}"
    return {
        "id": sid,
        "project_id": project_id,
        "name": name,
        "mode": "talking_portrait",
        "character_profile_id": None,
        "character_name": "",
        "continuity_lock": True,
        "look": {
            "id": f"look-{uuid.uuid4().hex[:8]}",
            "name": "Default Look",
            "framing": "medium close-up",
            "wardrobe": "",
            "expression": "neutral",
            "pose": "upright",
            "camera_angle": "three-quarter",
            "lens": "50mm",
            "background": "neutral gray",
            "lighting": "soft key, gentle fill",
            "style": "cinematic live-action",
            "aspect": "16:9",
        },
        "voice": {
            "provider": "upload",
            "model": "",
            "speaker_id": "",
            "language": "en",
            "accent": "",
            "tone": "natural",
            "pitch": "medium",
            "pace": "moderate",
            "emotional_range": "restrained",
            "pronunciation_notes": "",
            "stability": "high",
            "usage_rights": "project",
            "audio_asset_id": None,
            "profile_id": None,
        },
        "dialogue_original": "",
        "dialogue_spoken": "",
        "dialogue_adaptation_accepted": None,
        "performance": {
            "tone": "restrained",
            "eye_contact": "slightly off-camera",
            "head_movement": "minimal",
            "blink_frequency": "natural",
            "shoulder_movement": "low",
            "gesture_intensity": "low",
            "breathing": "subtle",
            "facial_expressiveness": "controlled",
            "energy": "moderate",
            "stillness": "high",
        },
        "camera": {
            "shot_size": "medium close-up",
            "lens": "50mm",
            "height": "eye level",
            "angle": "direct-to-camera",
            "movement": "static",
            "aspect": "16:9",
        },
        "background_mode": "solid",
        "background_notes": "Neutral studio background",
        "model_id": "ltx_2_3",
        "prompt": "",
        "negative_prompt": (
            "identity drift, teeth distortion, frozen face, overactive facial motion, "
            "mouth drift, cropped chin, background warping, duplicate characters, blurry"
        ),
        "source_video_asset_id": None,
        "source_still_asset_id": None,
        "mouth_mask": {"placed": False},
        "lip_sync_method": "external",
        "takes": [],
        "links": {},
        "created_at": now,
        "updated_at": now,
    }


def _validate(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    voice = data.get("voice") or {}
    if not data.get("character_profile_id") and not data.get("character_name") and not data.get("source_still_asset_id"):
        issues.append({"level": "warn", "text": "Identity reference missing"})
    if not voice.get("audio_asset_id") and data.get("lip_sync_method") == "external":
        issues.append({"level": "bad", "text": "Audio required for external lip-sync method"})
    if data.get("mode") == "existing_video_lipsync" and not data.get("source_video_asset_id"):
        issues.append({"level": "bad", "text": "Source video required"})
    mouth = data.get("mouth_mask") or {}
    if data.get("lip_sync_method") == "external" and not mouth.get("placed"):
        issues.append({"level": "warn", "text": "Mouth mask requires user confirmation"})
    if not (data.get("dialogue_original") or data.get("dialogue_spoken") or voice.get("audio_asset_id")):
        issues.append({"level": "warn", "text": "Dialogue empty"})
    return issues


def _row_to_data(row: AvatarSessionRow) -> dict[str, Any]:
    try:
        data = json.loads(row.data_json or "{}")
    except Exception:
        data = _empty(row.project_id, row.name)
    data["id"] = row.id
    data["project_id"] = row.project_id
    data["name"] = row.name or data.get("name") or "Avatar Session"
    data["updated_at"] = row.updated_at or data.get("updated_at")
    return data


class CreateSessionBody(BaseModel):
    name: str = "Avatar Session"
    character_profile_id: Optional[str] = None
    character_name: str = ""
    mode: str = "talking_portrait"
    bootstrap: dict[str, Any] = Field(default_factory=dict)


class TakeBody(BaseModel):
    asset_id: Optional[str] = None
    scene_id: Optional[str] = None
    label: str = "Take"
    status: str = "preview"
    performance_note: str = ""
    favorite: bool = False
    approved: bool = False


@router.get("/projects/{project_id}/avatar-sessions")
def list_sessions(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    rows = (
        db.query(AvatarSessionRow)
        .filter(AvatarSessionRow.project_id == project_id)
        .order_by(AvatarSessionRow.updated_at.desc())
        .all()
    )
    return [_row_to_data(r) for r in rows]


@router.post("/projects/{project_id}/avatar-sessions")
def create_session(project_id: str, body: CreateSessionBody, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    data = _empty(project_id, body.name or "Avatar Session")
    data["mode"] = body.mode or "talking_portrait"
    if body.character_profile_id:
        data["character_profile_id"] = body.character_profile_id
    if body.character_name:
        data["character_name"] = body.character_name
    if body.bootstrap:
        data.update({k: v for k, v in body.bootstrap.items() if k not in ("id", "project_id", "created_at")})
        data["id"] = f"avs-{uuid.uuid4().hex[:10]}"
        data["project_id"] = project_id
        data["updated_at"] = _now()
    row = AvatarSessionRow(
        id=data["id"],
        project_id=project_id,
        name=data["name"],
        data_json=json.dumps(data),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    return data


@router.get("/projects/{project_id}/avatar-sessions/{session_id}")
def get_session(project_id: str, session_id: str, db: Session = Depends(get_db)):
    row = db.get(AvatarSessionRow, session_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Avatar session not found")
    return _row_to_data(row)


@router.patch("/projects/{project_id}/avatar-sessions/{session_id}")
def patch_session(project_id: str, session_id: str, body: dict[str, Any], db: Session = Depends(get_db)):
    row = db.get(AvatarSessionRow, session_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Avatar session not found")
    data = _row_to_data(row)
    for k, v in body.items():
        if k in ("id", "project_id", "created_at"):
            continue
        data[k] = v
    data["updated_at"] = _now()
    row.name = data.get("name") or row.name
    row.data_json = json.dumps(data)
    row.updated_at = data["updated_at"]
    db.commit()
    return data


@router.delete("/projects/{project_id}/avatar-sessions/{session_id}")
def delete_session(project_id: str, session_id: str, db: Session = Depends(get_db)):
    row = db.get(AvatarSessionRow, session_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Avatar session not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/avatar-sessions/{session_id}/validate")
def validate_session(project_id: str, session_id: str, db: Session = Depends(get_db)):
    row = db.get(AvatarSessionRow, session_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Avatar session not found")
    data = _row_to_data(row)
    issues = _validate(data)
    return {"ok": not any(i["level"] == "bad" for i in issues), "issues": issues}


@router.post("/projects/{project_id}/avatar-sessions/{session_id}/takes")
def add_take(project_id: str, session_id: str, body: TakeBody, db: Session = Depends(get_db)):
    row = db.get(AvatarSessionRow, session_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Avatar session not found")
    data = _row_to_data(row)
    takes = list(data.get("takes") or [])
    take = {
        "id": f"take-{uuid.uuid4().hex[:8]}",
        "label": body.label or f"Take {len(takes) + 1}",
        "asset_id": body.asset_id,
        "scene_id": body.scene_id,
        "status": body.status or "preview",
        "favorite": body.favorite,
        "approved": body.approved,
        "performance_note": body.performance_note,
        "created_at": _now(),
    }
    takes.append(take)
    data["takes"] = takes
    data["updated_at"] = _now()
    row.data_json = json.dumps(data)
    row.updated_at = data["updated_at"]
    db.commit()
    return take
