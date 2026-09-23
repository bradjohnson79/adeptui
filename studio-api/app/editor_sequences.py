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
from .magi.authority import (
    MAGI_SEQUENCE_AUTHORITY,
    MAGI_SEQUENCE_STORE,
    editorial_deprecation_detail,
    magi_sequence_path,
)
from .magi.sequence.store import get_sequence as get_magi_sequence, save_sequence as save_magi_sequence

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


def _master_prompt_segments(db: Session, project_id: str, scene_id: str) -> list[dict[str, Any]]:
    """Flatten Master batch.promptSegments (single store)."""
    try:
        from .director_timeline_w46.service import load_timeline_bundle

        bundle = load_timeline_bundle(db, project_id, scene_id)
        if not bundle.get("ok"):
            return []
        master = bundle.get("master")
        if hasattr(master, "model_dump"):
            master = master.model_dump()
        segs: list[dict[str, Any]] = []
        for batch in (master or {}).get("batchBlocks") or []:
            for seg in batch.get("promptSegments") or []:
                segs.append(seg)
        return segs
    except Exception:
        return []


def _empty_sequence(
    project_id: str,
    scene: Scene | None = None,
    name: str = "Director Sequence",
    status: str = "draft",
    db: Session | None = None,
) -> dict[str, Any]:
    now = _now()
    scene_id = scene.id if scene else None
    director = _parse_director(scene) if scene else {}
    master_segments = _master_prompt_segments(db, project_id, scene_id) if (db and scene_id) else []
    return {
        "id": _nid("dseq"),
        "project_id": project_id,
        "scene_id": scene_id,
        "name": name or (f"{scene.name} Sequence" if scene else "Director Sequence"),
        "status": status,
        "version": 1,
        "asset_id": None,
        "output_path": scene.output_path if scene else None,
        "lipsync_output_path": scene.lipsync_output_path if scene else None,  # MAGI/legacy only; not Preview Visual authority
        "director_snapshot": director,
        "prompt_segments": master_segments,
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
        "audio_intent": _collect_audio_intent({"prompt_segments": master_segments}),
        "approval": {"approved": status == "approved", "at": now if status == "approved" else None},
        "editor_usage": [],
        "created_at": now,
        "updated_at": now,
    }



def _editor_compat_from_sequence(project_id: str, sequence: dict[str, Any]) -> dict[str, Any]:
    """Project MAGI sequence.json into legacy editor-shaped read-compat.

    Sole authority remains sequence.json. This is not a second store.
    """
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
    track_meta = {t.get("id"): t for t in (sequence.get("tracks") or [])}
    fps = max(int(sequence.get("frameRate") or 24), 1)
    for clip in sequence.get("clips") or []:
        tmeta = track_meta.get(clip.get("trackId")) or {}
        kind = str(tmeta.get("kind") or "")
        label = str(tmeta.get("label") or "")
        bucket = "video"
        if kind == "audio":
            low = label.lower()
            if label == "A2" or "music" in low:
                bucket = "music"
            elif label == "A3" or "sfx" in low:
                bucket = "sfx"
            elif "ambi" in low:
                bucket = "ambience"
            else:
                bucket = "dialogue"
        elif kind == "text":
            bucket = "titles"
        elif kind not in {"video", "image"}:
            bucket = "placeholder"
        start_frame = int(clip.get("startFrame") or 0)
        dur_frames = int(clip.get("durationFrames") or max(fps, 1))
        in_point = int(clip.get("inPoint") or 0)
        tracks[bucket].append(
            {
                "id": clip.get("id"),
                "asset_id": clip.get("assetId"),
                "start": float(start_frame) / fps,
                "length": float(dur_frames) / fps,
                "trim_start": float(in_point) / fps,
                "label": clip.get("name") or "MAGI clip",
                "source": "magi-sequence",
                "placeholder": False,
            }
        )
    return {
        "id": sequence.get("id") or f"magi-{project_id[:8]}",
        "project_id": project_id,
        "name": "MAGI Sequence",
        "status": "magi_sequence",
        "tracks": tracks,
        "playhead": float(sequence.get("playheadFrame") or 0) / fps,
        "authority": MAGI_SEQUENCE_AUTHORITY,
        "authorityStore": MAGI_SEQUENCE_STORE,
        "deprecatedEndpoint": True,
        "magiSequencePath": magi_sequence_path(project_id),
        "message": (
            "Legacy /editor is read-compat only. "
            "MAGI sequence.json is sole editorial authority."
        ),
        "sequenceRevision": sequence.get("revision"),
        "clipCount": len(sequence.get("clips") or []),
        "updated_at": sequence.get("updatedAt") or _now(),
        "created_at": sequence.get("updatedAt") or _now(),
    }


def _legacy_editor_snapshot(project_id: str, db: Session) -> dict[str, Any] | None:
    """Non-authoritative forensic snapshot of the old editor_projects row."""
    row = db.query(EditorProjectRow).filter(EditorProjectRow.project_id == project_id).first()
    if not row:
        return None
    snap = _row_to_editor(row)
    snap["authority"] = "legacy-editor-forensic"
    snap["notMagiAuthority"] = True
    return snap


def _place_director_shot_on_magi(
    project_id: str,
    *,
    asset_id: str | None,
    name: str,
    length_sec: float,
    scene_id: str | None,
    source_seq_id: str,
    source_version: int,
    track_hint: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Sync-through: Director send-to-editor places onto MAGI sequence.json."""
    if not asset_id:
        raise HTTPException(
            400,
            detail={
                "ok": False,
                "code": "DIRECTOR_ASSET_REQUIRED",
                "message": (
                    "Director sequence has no asset_id to place on MAGI. "
                    "Generate/approve a shot asset first, then send to MAGI."
                ),
                "magiSequencePath": magi_sequence_path(project_id),
            },
        )
    sequence = get_magi_sequence(project_id)
    tracks = list(sequence.get("tracks") or [])
    wanted_label = "V1"
    wanted_kind = "video"
    hint = (track_hint or "video").lower()
    if hint in {"music", "a2"}:
        wanted_label, wanted_kind = "A2", "audio"
    elif hint in {"sfx", "a3"}:
        wanted_label, wanted_kind = "A3", "audio"
    elif hint in {"dialogue", "a1", "ambience"}:
        wanted_label, wanted_kind = "A1", "audio"
    track = next((t for t in tracks if t.get("label") == wanted_label), None)
    if track is None:
        track = {
            "id": f"trk_{wanted_label.lower()}_{uuid.uuid4().hex[:6]}",
            "kind": wanted_kind,
            "label": wanted_label,
            "order": len(tracks),
        }
        tracks.append(track)
        sequence["tracks"] = tracks
    fps = max(int(sequence.get("frameRate") or 24), 1)
    duration_frames = max(int(round(float(length_sec) * fps)), 1)
    clips = list(sequence.get("clips") or [])
    start = 0
    same_track = [c for c in clips if c.get("trackId") == track["id"]]
    if same_track:
        last = max(same_track, key=lambda c: int(c.get("startFrame") or 0) + int(c.get("durationFrames") or 0))
        start = int(last.get("startFrame") or 0) + int(last.get("durationFrames") or 0)
    clip = {
        "id": f"clip_{uuid.uuid4().hex[:10]}",
        "trackId": track["id"],
        "assetId": asset_id,
        "name": name or "Director shot",
        "startFrame": start,
        "durationFrames": duration_frames,
        "inPoint": 0,
        "outPoint": duration_frames,
        "sceneId": scene_id,
        "sourceClipId": source_seq_id,
        "generationId": f"director-seq:{source_seq_id}:v{source_version}",
    }
    clips.append(clip)
    sequence["clips"] = clips
    saved = save_magi_sequence(project_id, sequence)
    return saved, clip


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

    data = _empty_sequence(project_id, scene, name, status, db=db)
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

    # Legacy editor_projects dual-write removed (P0). MAGI sequence.json is sole
    # editorial authority; Director version bumps no longer mutate editor_projects.
    if bumped or body.approve is True:
        pass

    return data


@router.post("/projects/{project_id}/director-sequences/{seq_id}/send-to-editor")
def send_to_editor(project_id: str, seq_id: str, body: SendToEditorBody, db: Session = Depends(get_db)):
    """Sync-through: place Director shot onto MAGI sequence.json (sole editorial authority).

    Legacy editor_projects is no longer written. Response `editor` is read-compat
    projection of sequence.json.
    """
    row = db.get(DirectorSequenceRow, seq_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Director sequence not found")
    seq = _row_to_seq(row)
    settings = seq.get("settings") or {}
    length = body.length if body.length is not None else float(settings.get("duration_sec") or 5)
    saved, clip = _place_director_shot_on_magi(
        project_id,
        asset_id=seq.get("asset_id"),
        name=body.label or seq.get("name") or "Director shot",
        length_sec=float(length),
        scene_id=seq.get("scene_id"),
        source_seq_id=seq_id,
        source_version=int(seq.get("version") or 1),
        track_hint=body.track or "video",
    )
    usage = list(seq.get("editor_usage") or [])
    usage.append(
        {
            "clip_id": clip["id"],
            "track": body.track or "video",
            "at": _now(),
            "authority": MAGI_SEQUENCE_AUTHORITY,
            "magi_sequence_id": saved.get("id"),
        }
    )
    seq["editor_usage"] = usage
    if seq.get("status") == "approved":
        seq["status"] = "used_in_editor"
        row.status = "used_in_editor"
    seq["updated_at"] = _now()
    row.data_json = json.dumps(seq)
    row.updated_at = seq["updated_at"]
    db.commit()
    editor = _editor_compat_from_sequence(project_id, saved)
    # Compat shape expected by older clients/tests
    compat_clip = {
        "id": clip["id"],
        "asset_id": clip.get("assetId"),
        "start": float(clip.get("startFrame") or 0) / max(int(saved.get("frameRate") or 24), 1),
        "length": float(clip.get("durationFrames") or 1) / max(int(saved.get("frameRate") or 24), 1),
        "trim_start": 0.0,
        "label": clip.get("name"),
        "source_director_sequence_id": seq_id,
        "source_version": int(seq.get("version") or 1),
        "source_scene_id": seq.get("scene_id"),
        "include_audio": body.include_audio,
        "proxy": body.proxy,
        "pending_newer_version": None,
        "authority": MAGI_SEQUENCE_AUTHORITY,
    }
    return {"sequence": seq, "editor": editor, "clip": compat_clip, "magiSequence": saved}


# ── Editor Project ──────────────────────────────────────────────────


@router.get("/projects/{project_id}/editor")
def get_editor(project_id: str, db: Session = Depends(get_db)):
    """Read-compat proxy of MAGI sequence.json (sole editorial authority).

    Does not create or mutate legacy editor_projects. Optional legacySnapshot is
    forensic-only and never authoritative.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sequence = get_magi_sequence(project_id)
    payload = _editor_compat_from_sequence(project_id, sequence)
    legacy = _legacy_editor_snapshot(project_id, db)
    if legacy is not None:
        payload["legacySnapshot"] = legacy
    return payload


@router.put("/projects/{project_id}/editor")
def put_editor(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)):
    """Writes deprecated — MAGI sequence.json is sole editorial authority."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    detail = editorial_deprecation_detail(project_id)
    detail["hint"] = "Send mutations via PUT /api/magi/projects/{id}/sequence (expectedRevision)."
    raise HTTPException(status_code=409, detail=detail)
