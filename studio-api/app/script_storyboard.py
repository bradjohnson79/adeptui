from __future__ import annotations

"""Script documents, segments, and storyboard panels."""

import json
import re
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, engine


SegmentType = Literal[
    "scene_heading",
    "action",
    "dialogue",
    "dialogue_exchange",
    "reaction",
    "insert",
    "transition",
    "camera_beat",
    "story_beat",
    "vfx",
    "sound_cue",
]
SyncStatus = Literal["ok", "script_changed", "needs_regen", "non_visual"]
ApprovalState = Literal["draft", "complete", "approved", "rejected"]
PanelStatus = Literal[
    "missing",
    "draft",
    "generating",
    "complete",
    "approved",
    "script_changed",
    "needs_regen",
    "in_director",
]


class ScriptDocRow(Base):
    __tablename__ = "script_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled Script")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    source_attachment_path: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScriptSegmentRow(Base):
    __tablename__ = "script_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    doc_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    index: Mapped[int] = mapped_column(Integer, default=0)
    segment_number: Mapped[int] = mapped_column(Integer, default=1)
    segment_type: Mapped[str] = mapped_column(String(32), default="action")
    speaker: Mapped[str] = mapped_column(String(120), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    dialogue: Mapped[str] = mapped_column(Text, default="")
    emotion: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    time_of_day: Mapped[str] = mapped_column(String(64), default="")
    characters_json: Mapped[str] = mapped_column(Text, default="[]")
    duration_est: Mapped[float] = mapped_column(Float, default=3.0)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    spatial_scene_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    continuity_json: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StoryboardPanelRow(Base):
    __tablename__ = "storyboard_panels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    doc_id: Mapped[str] = mapped_column(String(36), index=True)
    segment_id: Mapped[str] = mapped_column(String(36), index=True)
    panel_index: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(160), default="")
    asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    spatial_state_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    camera_avatar_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    style: Mapped[str] = mapped_column(String(64), default="Pencil storyboard")
    shot_size: Mapped[str] = mapped_column(String(64), default="")
    lens: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    approval: Mapped[str] = mapped_column(String(32), default="draft")
    script_sync_status: Mapped[str] = mapped_column(String(32), default="ok")
    status: Mapped[str] = mapped_column(String(32), default="missing")
    duration_est: Mapped[float] = mapped_column(Float, default=3.0)
    script_revision: Mapped[int] = mapped_column(Integer, default=1)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def ensure_script_tables() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[ScriptDocRow.__table__, ScriptSegmentRow.__table__, StoryboardPanelRow.__table__],
    )


class SegmentOut(BaseModel):
    id: str
    project_id: str
    doc_id: str
    scene_id: Optional[str] = None
    index: int = 0
    segment_number: int = 1
    segment_type: str = "action"
    speaker: str = ""
    text: str = ""
    action: str = ""
    dialogue: str = ""
    emotion: str = ""
    location: str = ""
    time_of_day: str = ""
    characters: list[str] = Field(default_factory=list)
    duration_est: float = 3.0
    status: str = "draft"
    spatial_scene_id: Optional[str] = None
    continuity_json: str = ""
    revision: int = 1
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_row(cls, row: ScriptSegmentRow) -> "SegmentOut":
        try:
            chars = json.loads(row.characters_json or "[]")
        except Exception:
            chars = []
        try:
            meta = json.loads(row.meta_json or "{}")
        except Exception:
            meta = {}
        return cls(
            id=row.id,
            project_id=row.project_id,
            doc_id=row.doc_id,
            scene_id=row.scene_id,
            index=row.index,
            segment_number=row.segment_number,
            segment_type=row.segment_type,
            speaker=row.speaker or "",
            text=row.text or "",
            action=row.action or "",
            dialogue=row.dialogue or "",
            emotion=row.emotion or "",
            location=row.location or "",
            time_of_day=row.time_of_day or "",
            characters=chars if isinstance(chars, list) else [],
            duration_est=row.duration_est or 3.0,
            status=row.status,
            spatial_scene_id=row.spatial_scene_id,
            continuity_json=row.continuity_json or "",
            revision=row.revision or 1,
            meta=meta if isinstance(meta, dict) else {},
        )


class PanelOut(BaseModel):
    id: str
    project_id: str
    doc_id: str
    segment_id: str
    panel_index: int = 0
    label: str = ""
    asset_id: Optional[str] = None
    spatial_state_id: Optional[str] = None
    camera_avatar_id: Optional[str] = None
    style: str = "Pencil storyboard"
    shot_size: str = ""
    lens: str = ""
    notes: str = ""
    prompt: str = ""
    approval: str = "draft"
    script_sync_status: str = "ok"
    status: str = "missing"
    duration_est: float = 3.0
    script_revision: int = 1
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_row(cls, row: StoryboardPanelRow) -> "PanelOut":
        try:
            meta = json.loads(row.meta_json or "{}")
        except Exception:
            meta = {}
        return cls(
            id=row.id,
            project_id=row.project_id,
            doc_id=row.doc_id,
            segment_id=row.segment_id,
            panel_index=row.panel_index,
            label=row.label or "",
            asset_id=row.asset_id,
            spatial_state_id=row.spatial_state_id,
            camera_avatar_id=row.camera_avatar_id,
            style=row.style or "Pencil storyboard",
            shot_size=row.shot_size or "",
            lens=row.lens or "",
            notes=row.notes or "",
            prompt=row.prompt or "",
            approval=row.approval or "draft",
            script_sync_status=row.script_sync_status or "ok",
            status=row.status or "missing",
            duration_est=row.duration_est or 3.0,
            script_revision=row.script_revision or 1,
            meta=meta if isinstance(meta, dict) else {},
        )


def get_or_create_script_doc(db: Session, project_id: str, title: str = "Main Script") -> ScriptDocRow:
    row = (
        db.query(ScriptDocRow)
        .filter(ScriptDocRow.project_id == project_id)
        .order_by(ScriptDocRow.created_at.asc())
        .first()
    )
    if row:
        return row
    row = ScriptDocRow(id=str(uuid.uuid4()), project_id=project_id, title=title)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


_HEADING_RE = re.compile(r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s+", re.I)
_SPEAKER_RE = re.compile(r"^[A-Z][A-Z0-9 .'\-]{1,40}$")


def import_plain_text(db: Session, project_id: str, text: str, *, doc_id: str | None = None) -> list[ScriptSegmentRow]:
    doc = db.get(ScriptDocRow, doc_id) if doc_id else get_or_create_script_doc(db, project_id)
    if not doc:
        doc = get_or_create_script_doc(db, project_id)
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    segments: list[ScriptSegmentRow] = []
    buf: list[str] = []
    speaker = ""
    seg_type: SegmentType = "action"
    idx = db.query(ScriptSegmentRow).filter(ScriptSegmentRow.doc_id == doc.id).count()

    def flush():
        nonlocal idx, buf, speaker, seg_type
        body = "\n".join(buf).strip()
        if not body and not speaker:
            buf = []
            return
        dialogue = body if seg_type == "dialogue" else ""
        action = body if seg_type != "dialogue" else ""
        row = ScriptSegmentRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=doc.id,
            index=idx,
            segment_number=idx + 1,
            segment_type=seg_type,
            speaker=speaker,
            text=body,
            action=action,
            dialogue=dialogue,
            characters_json=json.dumps([speaker] if speaker else []),
        )
        db.add(row)
        segments.append(row)
        idx += 1
        buf = []
        speaker = ""
        seg_type = "action"

    for ln in lines:
        raw = ln.strip()
        if not raw:
            flush()
            continue
        if _HEADING_RE.match(raw):
            flush()
            seg_type = "scene_heading"
            buf = [raw]
            flush()
            continue
        if _SPEAKER_RE.match(raw) and len(raw) < 40 and not raw.endswith("."):
            flush()
            speaker = raw.title() if raw.isupper() else raw
            seg_type = "dialogue"
            continue
        buf.append(raw)
    flush()
    doc.updated_at = datetime.utcnow()
    db.commit()
    return segments


def visual_change_heuristic(old: ScriptSegmentRow, new_text: str, new_action: str, new_dialogue: str) -> bool:
    """True if edit likely affects visuals (staging), not dialogue-only wording."""
    old_vis = f"{old.action} {old.text} {old.location} {old.segment_type}".lower()
    new_vis = f"{new_action} {new_text} {old.location}".lower()
    # Dialogue-only change
    if (new_action or "").strip() == (old.action or "").strip() and (new_dialogue or "") != (old.dialogue or ""):
        # still check if action-ish words moved into dialogue block oddly
        return False
    staging_tokens = (
        "stand",
        "walk",
        "enter",
        "exit",
        "beside",
        "behind",
        "camera",
        "door",
        "elevator",
        "close-up",
        "wide",
        "sits",
        "runs",
        "approaches",
    )
    old_hits = {t for t in staging_tokens if t in old_vis}
    new_hits = {t for t in staging_tokens if t in new_vis}
    if old_hits != new_hits:
        return True
    # Character name set change in action
    if (new_action or "").strip() != (old.action or "").strip():
        return True
    return False


def mark_panels_script_changed(db: Session, segment_id: str, visual: bool) -> int:
    panels = db.query(StoryboardPanelRow).filter(StoryboardPanelRow.segment_id == segment_id).all()
    n = 0
    for p in panels:
        if p.approval == "approved" and not visual:
            # dialogue-only: keep sync ok but note dialogue meta
            p.meta_json = json.dumps({**(json.loads(p.meta_json or "{}") or {}), "dialogue_updated": True})
        else:
            p.script_sync_status = "script_changed" if visual else "ok"
            if visual:
                p.status = "script_changed"
            n += 1
        p.updated_at = datetime.utcnow()
    db.commit()
    return n


def storyboard_style_prompt(style: str, body: str) -> str:
    style_map = {
        "Pencil storyboard": "pencil sketch storyboard panel, clean line art, production storyboard",
        "Ink storyboard": "inked storyboard panel, bold contours",
        "Grayscale cinematic": "grayscale cinematic storyboard frame, dramatic lighting",
        "Color concept frame": "color concept frame, cinematic previsualization",
        "Anime storyboard": "anime storyboard panel, clear staging",
        "Photoreal previs": "photoreal previs still, cinematic",
        "Production still": "production still, on-set cinematic photograph",
    }
    prefix = style_map.get(style, f"{style} storyboard")
    return f"{prefix}. {body}".strip()
