"""Director Sequences + Editor Project packages.

Director creates the shots (Prompt Timeline). Editor assembles approved outputs into film.
Non-destructive: regenerated Director output never auto-overwrites Editor clips.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, Project, Scene, Asset, engine, get_db

router = APIRouter(tags=["editor-sequences"])

DirectorSeqStatus = Literal["draft", "generating", "variations", "approved", "used_in_editor"]
EditorStatus = Literal["animatic", "rough_cut", "scene_cut", "alternate", "approved", "master"]


class DirectorSequenceRow(Base):
    __tablename__ = "director_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="Director Sequence")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class EditorProjectRow(Base):
    __tablename__ = "editor_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True, unique=True)
    name: Mapped[str] = mapped_column(String(200), default="Editor")
    status: Mapped[str] = mapped_column(String(32), default="rough_cut")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


def ensure_editor_tables() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[DirectorSequenceRow.__table__, EditorProjectRow.__table__],
    )


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _nid(prefix: str = "seq") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _parse_director(scene: Scene) -> dict[str, Any]:
    try:
        return json.loads(scene.director_json or "{}") if scene.director_json else {}
    except Exception:
        return {}


def _collect_audio_intent(director: dict[str, Any]) -> list[str]:
    intents: list[str] = []
    for seg in director.get("prompt_segments") or []:
        for item in seg.get("audio_intent") or []:
            if item and item not in intents:
                intents.append(str(item))
    return intents


def _resolve_video_asset(scene: Scene, db: Session, project_id: str) -> Optional[str]:
    """Best-effort: match scene output_path to an asset, else use video clip asset_id."""
    director = _parse_director(scene)
    for clip in director.get("video_clips") or []:
        aid = clip.get("asset_id")
        if aid:
            return str(aid)
    if scene.output_path:
        asset = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.path == scene.output_path)
            .first()
        )
        if asset:
            return asset.id
    return None


def _empty_sequence(
    project_id: str,
    scene: Scene | None = None,
    name: str = "Director Sequence",
    status: str = "draft",
) -> dict[str, Any]:
    now = _now()
    scene_id = scene.id if scene else None
    director = _parse_director(scene) if scene else {}
    return {
        "id": _nid("dseq"),
        "project_id": project_id,
        "scene_id": scene_id,
        "name": name or (f"{scene.name} Sequence" if scene else "Director Sequence"),
        "status": status,
        "version": 1,
        "asset_id": None,
        "output_path": scene.output_path if scene else None,
        "lipsync_output_path": scene.lipsync_output_path if scene else None,
        "director_snapshot": director,
        "prompt_segments": director.get("prompt_segments") or [],
        "links": {
            "script_segment_ids": [],
            "storyboard_panel_ids": [],
            "spatial_map_id": f"spatial-{scene_id}" if scene_id else None,
            "master_sheet_id": f"ms-{scene_id}" if scene_id else None,
        },
        "profiles": {},
        "camera_metadata": {
            "camera_clips": director.get("camera_clips") or [],
            "camera_note": scene.camera_note if scene else "",
        },
        "model": scene.engine if scene else "ltx",
        "seed": scene.seed if scene else -1,
        "settings": {
            "duration_sec": scene.duration_sec if scene else director.get("duration_sec", 5),
            "aspect_ratio": scene.aspect_ratio if scene else "16:9",
            "width": scene.width if scene else 0,
            "height": scene.height if scene else 0,
            "fps": scene.fps if scene else 0,
        },
        "audio_intent": _collect_audio_intent(director),
        "approval": {"approved": status == "approved", "at": now if status == "approved" else None},
        "editor_usage": [],
        "created_at": now,
        "updated_at": now,
    }


def _empty_editor(project_id: str) -> dict[str, Any]:
    now = _now()
    tracks = {
        "video": [],
        "video_b": [],
        "placeholder": [],
        "titles": [],
        "dialogue": [],
        "sfx": [],
        "ambience": [],
        "music": [],
    }
    return {
        "id": _nid("ed"),
        "project_id": project_id,
        "name": "Editor",
        "status": "rough_cut",
        "tracks": tracks,
        "playhead": 0,
        "created_at": now,
        "updated_at": now,
    }


def _row_to_seq(row: DirectorSequenceRow) -> dict[str, Any]:
    try:
        data = json.loads(row.data_json or "{}")
    except Exception:
        data = {}
    data["id"] = row.id
    data["project_id"] = row.project_id
    data["scene_id"] = row.scene_id
    data["name"] = row.name or data.get("name") or "Director Sequence"
    data["status"] = row.status or data.get("status") or "draft"
    data["version"] = row.version if row.version is not None else data.get("version", 1)
    data["asset_id"] = row.asset_id or data.get("asset_id")
    data["updated_at"] = row.updated_at or data.get("updated_at")
    return data


def _row_to_editor(row: EditorProjectRow) -> dict[str, Any]:
    try:
        data = json.loads(row.data_json or "{}")
    except Exception:
        data = _empty_editor(row.project_id)
    data["id"] = row.id
    data["project_id"] = row.project_id
    data["name"] = row.name or data.get("name") or "Editor"
    data["status"] = row.status or data.get("status") or "rough_cut"
    data["updated_at"] = row.updated_at or data.get("updated_at")
    if "tracks" not in data:
        data["tracks"] = _empty_editor(row.project_id)["tracks"]
    return data


def _get_or_create_editor(project_id: str, db: Session) -> EditorProjectRow:
    row = db.query(EditorProjectRow).filter(EditorProjectRow.project_id == project_id).first()
    if row:
        return row
    data = _empty_editor(project_id)
    row = EditorProjectRow(
        id=data["id"],
        project_id=project_id,
        name=data["name"],
        status=data["status"],
        data_json=json.dumps(data),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mark_pending_newer(editor: dict[str, Any], seq_id: str, version: int) -> None:
    tracks = editor.get("tracks") or {}
    for key, clips in list(tracks.items()):
        next_clips = []
        for clip in clips or []:
            c = dict(clip)
            if c.get("source_director_sequence_id") == seq_id:
                src_ver = int(c.get("source_version") or 0)
                if version > src_ver:
                    c["pending_newer_version"] = version
            next_clips.append(c)
        tracks[key] = next_clips
    editor["tracks"] = tracks


class CreateSequenceBody(BaseModel):
    name: str = "Director Sequence"
    scene_id: Optional[str] = None
    status: str = "draft"
    asset_id: Optional[str] = None
    bootstrap: dict[str, Any] = Field(default_factory=dict)


class FromSceneBody(BaseModel):
    scene_id: str
    name: Optional[str] = None
    status: str = "draft"
    include_audio: bool = True
    proxy: bool = False
    segment_ids: Optional[list[str]] = None


class SendToEditorBody(BaseModel):
    track: str = "video"
    label: Optional[str] = None
    include_audio: bool = True
    proxy: bool = False
    start: Optional[float] = None
    length: Optional[float] = None


class PatchSequenceBody(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    approve: Optional[bool] = None
    bump_version: bool = False
    asset_id: Optional[str] = None
    patch: dict[str, Any] = Field(default_factory=dict)


# ── Director Sequences ──────────────────────────────────────────────


@router.get("/projects/{project_id}/director-sequences")
def list_sequences(project_id: str, status: Optional[str] = None, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    q = db.query(DirectorSequenceRow).filter(DirectorSequenceRow.project_id == project_id)
    if status:
        q = q.filter(DirectorSequenceRow.status == status)
    rows = q.order_by(DirectorSequenceRow.updated_at.desc()).all()
    return [_row_to_seq(r) for r in rows]


@router.post("/projects/{project_id}/director-sequences")
def create_sequence(project_id: str, body: CreateSequenceBody, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = db.get(Scene, body.scene_id) if body.scene_id else None
    if body.scene_id and (not scene or scene.project_id != project_id):
        raise HTTPException(404, "Scene not found")
    data = _empty_sequence(project_id, scene, body.name, body.status)
    if body.asset_id:
        data["asset_id"] = body.asset_id
    elif scene:
        data["asset_id"] = _resolve_video_asset(scene, db, project_id)
    if body.bootstrap:
        data.update({k: v for k, v in body.bootstrap.items() if k not in ("id", "project_id", "created_at")})
        data["id"] = _nid("dseq")
        data["project_id"] = project_id
        data["updated_at"] = _now()
    row = DirectorSequenceRow(
        id=data["id"],
        project_id=project_id,
        scene_id=data.get("scene_id"),
        name=data["name"],
        status=data["status"],
        version=int(data.get("version") or 1),
        data_json=json.dumps(data),
        asset_id=data.get("asset_id"),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    return data


@router.post("/projects/{project_id}/director-sequences/from-scene")
def sequence_from_scene(project_id: str, body: FromSceneBody, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = db.get(Scene, body.scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")

    name = body.name or f"{scene.name} Sequence"
    # If approved output exists, default toward variations/approved when output present
    status = body.status
    if status == "draft" and (scene.output_path or scene.lipsync_output_path):
        status = "generating"

    data = _empty_sequence(project_id, scene, name, status)
    data["asset_id"] = _resolve_video_asset(scene, db, project_id)
    data["include_audio"] = body.include_audio
    data["proxy"] = body.proxy
    if body.segment_ids:
        segs = data.get("prompt_segments") or []
        data["prompt_segments"] = [s for s in segs if s.get("id") in body.segment_ids]
        data["audio_intent"] = _collect_audio_intent({"prompt_segments": data["prompt_segments"]})

    row = DirectorSequenceRow(
        id=data["id"],
        project_id=project_id,
        scene_id=scene.id,
        name=data["name"],
        status=data["status"],
        version=1,
        data_json=json.dumps(data),
        asset_id=data.get("asset_id"),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    return data


@router.get("/projects/{project_id}/director-sequences/{seq_id}")
def get_sequence(project_id: str, seq_id: str, db: Session = Depends(get_db)):
    row = db.get(DirectorSequenceRow, seq_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Director sequence not found")
    return _row_to_seq(row)


@router.patch("/projects/{project_id}/director-sequences/{seq_id}")
def patch_sequence(project_id: str, seq_id: str, body: PatchSequenceBody, db: Session = Depends(get_db)):
    row = db.get(DirectorSequenceRow, seq_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Director sequence not found")
    data = _row_to_seq(row)

    if body.name is not None:
        data["name"] = body.name
        row.name = body.name
    if body.asset_id is not None:
        data["asset_id"] = body.asset_id
        row.asset_id = body.asset_id
    if body.patch:
        for k, v in body.patch.items():
            if k in ("id", "project_id", "created_at"):
                continue
            data[k] = v

    bumped = False
    if body.bump_version:
        data["version"] = int(data.get("version") or 1) + 1
        row.version = data["version"]
        bumped = True

    if body.approve is True:
        data["status"] = "approved"
        data["approval"] = {"approved": True, "at": _now()}
        row.status = "approved"
    elif body.status:
        data["status"] = body.status
        row.status = body.status
        if body.status == "approved":
            data["approval"] = {"approved": True, "at": _now()}

    data["updated_at"] = _now()
    row.data_json = json.dumps(data)
    row.updated_at = data["updated_at"]
    row.version = int(data.get("version") or 1)
    db.commit()

    # Non-destructive: flag Editor clips when sequence version advances
    if bumped or body.approve is True:
        ed_row = db.query(EditorProjectRow).filter(EditorProjectRow.project_id == project_id).first()
        if ed_row:
            editor = _row_to_editor(ed_row)
            _mark_pending_newer(editor, seq_id, int(data.get("version") or 1))
            editor["updated_at"] = _now()
            ed_row.data_json = json.dumps(editor)
            ed_row.updated_at = editor["updated_at"]
            db.commit()

    return data


@router.post("/projects/{project_id}/director-sequences/{seq_id}/send-to-editor")
def send_to_editor(project_id: str, seq_id: str, body: SendToEditorBody, db: Session = Depends(get_db)):
    row = db.get(DirectorSequenceRow, seq_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Director sequence not found")
    seq = _row_to_seq(row)
    ed_row = _get_or_create_editor(project_id, db)
    editor = _row_to_editor(ed_row)

    track = body.track if body.track in editor.get("tracks", {}) else "video"
    clips = list((editor.get("tracks") or {}).get(track) or [])
    start = body.start
    if start is None:
        start = max((float(c.get("start", 0)) + float(c.get("length", 0)) for c in clips), default=0.0)
    settings = seq.get("settings") or {}
    length = body.length if body.length is not None else float(settings.get("duration_sec") or 5)

    clip = {
        "id": _nid("clip"),
        "asset_id": seq.get("asset_id"),
        "output_path": seq.get("output_path") or seq.get("lipsync_output_path"),
        "start": float(start),
        "length": float(length),
        "trim_start": 0.0,
        "label": body.label or seq.get("name") or "Director shot",
        "source_director_sequence_id": seq_id,
        "source_version": int(seq.get("version") or 1),
        "source_scene_id": seq.get("scene_id"),
        "include_audio": body.include_audio,
        "proxy": body.proxy,
        "pending_newer_version": None,
    }
    clips.append(clip)
    editor.setdefault("tracks", {})[track] = clips

    # Optional audio placeholders from audio_intent when include_audio
    if body.include_audio:
        for intent in seq.get("audio_intent") or []:
            kind = "ambience" if "ambi" in str(intent).lower() else "sfx"
            audio_clips = list((editor.get("tracks") or {}).get(kind) or [])
            audio_clips.append(
                {
                    "id": _nid("clip"),
                    "asset_id": None,
                    "start": float(start),
                    "length": float(length),
                    "trim_start": 0.0,
                    "label": f"[intent] {intent}",
                    "source_director_sequence_id": seq_id,
                    "source_version": int(seq.get("version") or 1),
                    "placeholder": True,
                }
            )
            editor["tracks"][kind] = audio_clips

    usage = list(seq.get("editor_usage") or [])
    usage.append(
        {
            "clip_id": clip["id"],
            "track": track,
            "at": _now(),
            "editor_project_id": editor.get("id"),
        }
    )
    seq["editor_usage"] = usage
    if seq.get("status") == "approved":
        seq["status"] = "used_in_editor"
        row.status = "used_in_editor"
    seq["updated_at"] = _now()
    row.data_json = json.dumps(seq)
    row.updated_at = seq["updated_at"]

    editor["updated_at"] = _now()
    ed_row.data_json = json.dumps(editor)
    ed_row.updated_at = editor["updated_at"]
    db.commit()
    return {"sequence": seq, "editor": editor, "clip": clip}


# ── Editor Project ──────────────────────────────────────────────────


@router.get("/projects/{project_id}/editor")
def get_editor(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    row = _get_or_create_editor(project_id, db)
    return _row_to_editor(row)


@router.put("/projects/{project_id}/editor")
def put_editor(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    row = _get_or_create_editor(project_id, db)
    data = _row_to_editor(row)
    for k, v in body.items():
        if k in ("id", "project_id", "created_at"):
            continue
        data[k] = v
    data["updated_at"] = _now()
    row.name = data.get("name") or row.name
    row.status = data.get("status") or row.status
    row.data_json = json.dumps(data)
    row.updated_at = data["updated_at"]
    db.commit()
    return data
