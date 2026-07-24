from __future__ import annotations

"""Per-scene Spatial Scene Engine document (v2) + persistence helpers."""

import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, Project, Scene, engine
from .schemas import SpatialMap


EntityType = Literal[
    "character",
    "prop",
    "architecture",
    "vehicle",
    "camera",
    "light",
    "audio",
    "zone",
    "marker",
]
ShapeType = Literal["circle", "square", "diamond", "hex", "camera", "light", "speaker", "zone"]
GuidanceLevel = Literal["loose", "balanced", "strict"]
FacingMode = Literal[
    "compass",
    "face_avatar",
    "face_camera",
    "face_object",
    "look_left",
    "look_right",
    "over_shoulder",
    "back_to_camera",
    "three_quarter_camera",
]
RelationType = Literal[
    "faces",
    "looks_at",
    "speaks_to",
    "holds",
    "touches",
    "approaches",
    "follows",
    "guards",
    "attacks",
    "avoids",
    "blocks",
    "stands_beside",
    "sits_on",
    "leans_against",
    "walks_toward",
    "moves_away_from",
]


SHAPE_FOR_ENTITY: dict[str, ShapeType] = {
    "character": "circle",
    "prop": "square",
    "architecture": "diamond",
    "vehicle": "hex",
    "camera": "camera",
    "light": "light",
    "audio": "speaker",
    "zone": "zone",
    "marker": "circle",
}

DEFAULT_COLORS = ["#0f766e", "#c45c26", "#1d4ed8", "#7c3aed", "#b91c1c", "#047857", "#a16207"]


class FacingSpec(BaseModel):
    mode: FacingMode = "compass"
    target_avatar_id: Optional[str] = None
    compass: Optional[str] = "south"


class AvatarRelation(BaseModel):
    type: RelationType = "looks_at"
    to_id: str = ""


class MovementPath(BaseModel):
    points: list[dict[str, float]] = Field(default_factory=list)
    speed: float = 1.0
    pauses: list[dict[str, Any]] = Field(default_factory=list)


class CameraSpec(BaseModel):
    lens_mm: float = 35
    height_m: float = 1.6
    shot_size: str = "medium"
    focus_targets: list[str] = Field(default_factory=list)
    fov_deg: float = 50
    aspect: str = "16:9"
    rig: str = "tripod"
    movement: str = "static"
    depth_of_field: str = "medium"
    sensor_preset: str = ""


class SceneAvatar(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    initials: str = ""
    color: str = "#0f766e"
    shape: ShapeType = "circle"
    entity_type: EntityType = "character"
    x: float = 0
    y: float = 0
    rotation: float = 0
    scale: float = 1.0
    height: float = 1.7
    parent_id: Optional[str] = None
    profile_id: Optional[str] = None
    asset_id: Optional[str] = None
    spatial_prompt: str = ""
    continuity: str = "unlocked"  # locked | unlocked
    visible: bool = True
    locked: bool = False
    facing: FacingSpec = Field(default_factory=FacingSpec)
    relationships: list[AvatarRelation] = Field(default_factory=list)
    path: Optional[MovementPath] = None
    camera: Optional[CameraSpec] = None
    prop_state: str = ""
    door_state: str = ""
    expression: str = ""
    pose: str = ""
    wardrobe: str = ""


class SceneState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "State A"
    avatar_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    camera_id: Optional[str] = None
    lighting: str = ""
    spatial_prompt_snapshot: str = ""


class PromptLayers(BaseModel):
    scene: str = ""
    identity: str = ""
    performance: str = ""
    spatial: str = ""
    camera: str = ""
    environment: str = ""
    props: str = ""
    lighting: str = ""
    style: str = ""
    negative_identity: str = ""
    negative_spatial: str = ""


class SpatialSceneDoc(BaseModel):
    version: int = 2
    width: float = 1000
    height: float = 700
    background_asset_id: Optional[str] = None
    notes: str = ""
    guidance: GuidanceLevel = "balanced"
    calibration: dict[str, Any] = Field(default_factory=dict)
    avatars: list[SceneAvatar] = Field(default_factory=list)
    states: list[SceneState] = Field(default_factory=list)
    active_state_id: Optional[str] = None
    prompt_layers: PromptLayers = Field(default_factory=PromptLayers)
    # legacy compatibility
    points: list[dict[str, Any]] = Field(default_factory=list)


class SpatialSceneRow(Base):
    __tablename__ = "spatial_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[str] = mapped_column(String(36), index=True)
    map_json: Mapped[str] = mapped_column(Text, default="{}")
    calibration_json: Mapped[str] = mapped_column(Text, default="{}")
    guidance: Mapped[str] = mapped_column(String(16), default="balanced")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def ensure_spatial_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[SpatialSceneRow.__table__])


def _initials(label: str) -> str:
    parts = [p for p in (label or "").replace("_", " ").split() if p]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def migrate_legacy_map(raw: str | None) -> SpatialSceneDoc:
    """Upgrade v1 SpatialMap / empty → v2 SpatialSceneDoc."""
    if not raw or not str(raw).strip():
        doc = SpatialSceneDoc()
        st = SceneState(name="State A")
        doc.states = [st]
        doc.active_state_id = st.id
        return doc
    try:
        data = json.loads(raw)
    except Exception:
        doc = SpatialSceneDoc()
        st = SceneState(name="State A")
        doc.states = [st]
        doc.active_state_id = st.id
        return doc

    if isinstance(data, dict) and int(data.get("version") or 0) >= 2 and "avatars" in data:
        try:
            return SpatialSceneDoc.model_validate(data)
        except Exception:
            pass

    # v1 SpatialMap
    try:
        legacy = SpatialMap.model_validate(data)
    except Exception:
        legacy = SpatialMap()

    avatars: list[SceneAvatar] = []
    for i, p in enumerate(legacy.points):
        kind = p.kind if p.kind in ("camera", "prop") else ("architecture" if p.kind == "wall" else "marker")
        entity: EntityType = kind  # type: ignore[assignment]
        if p.kind == "wall":
            entity = "architecture"
        elif p.kind == "marker":
            entity = "marker"
        avatars.append(
            SceneAvatar(
                id=p.id or str(uuid.uuid4()),
                label=p.label or f"{entity} {i + 1}",
                initials=_initials(p.label or entity),
                color=DEFAULT_COLORS[i % len(DEFAULT_COLORS)],
                shape=SHAPE_FOR_ENTITY.get(entity, "circle"),
                entity_type=entity,
                x=p.x,
                y=p.y,
                rotation=p.rotation or 0,
                asset_id=p.asset_id,
                camera=CameraSpec() if entity == "camera" else None,
            )
        )
    st = SceneState(name="State A")
    return SpatialSceneDoc(
        version=2,
        width=legacy.width,
        height=legacy.height,
        background_asset_id=legacy.background_asset_id,
        notes=legacy.notes or "",
        avatars=avatars,
        states=[st],
        active_state_id=st.id,
        points=[],
    )


def get_or_create_spatial(db: Session, project_id: str, scene_id: str) -> SpatialSceneRow:
    row = (
        db.query(SpatialSceneRow)
        .filter(SpatialSceneRow.project_id == project_id, SpatialSceneRow.scene_id == scene_id)
        .first()
    )
    if row:
        return row
    project = db.get(Project, project_id)
    doc = migrate_legacy_map(getattr(project, "spatial_map_json", None) if project else None)
    row = SpatialSceneRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        map_json=doc.model_dump_json(),
        calibration_json=json.dumps(doc.calibration),
        guidance=doc.guidance,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def parse_spatial_doc(row: SpatialSceneRow | None, fallback_project_json: str | None = None) -> SpatialSceneDoc:
    if row and row.map_json:
        return migrate_legacy_map(row.map_json)
    return migrate_legacy_map(fallback_project_json)


def save_spatial_doc(db: Session, row: SpatialSceneRow, doc: SpatialSceneDoc) -> SpatialSceneDoc:
    doc.version = 2
    row.map_json = doc.model_dump_json()
    row.calibration_json = json.dumps(doc.calibration or {})
    row.guidance = doc.guidance
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return doc


def resolve_avatars_for_state(doc: SpatialSceneDoc, state_id: str | None = None) -> list[SceneAvatar]:
    sid = state_id or doc.active_state_id
    state = next((s for s in doc.states if s.id == sid), None)
    out: list[SceneAvatar] = []
    for a in doc.avatars:
        if not a.visible:
            continue
        data = a.model_dump()
        if state and a.id in (state.avatar_overrides or {}):
            data.update(state.avatar_overrides[a.id] or {})
        out.append(SceneAvatar.model_validate(data))
    return out


def apply_avatar_mutations(doc: SpatialSceneDoc, mutations: list[dict[str, Any]]) -> SpatialSceneDoc:
    """Apply proposed Co-Director mutations (non-destructive caller must confirm first)."""
    by_id = {a.id: a for a in doc.avatars}
    for m in mutations:
        op = (m.get("op") or "").lower()
        if op == "add":
            et: EntityType = m.get("entity_type") or "character"
            label = m.get("label") or et.title()
            avatar = SceneAvatar(
                label=label,
                initials=m.get("initials") or _initials(label),
                color=m.get("color") or DEFAULT_COLORS[len(doc.avatars) % len(DEFAULT_COLORS)],
                shape=SHAPE_FOR_ENTITY.get(et, "circle"),
                entity_type=et,
                x=float(m.get("x") or doc.width / 2),
                y=float(m.get("y") or doc.height / 2),
                profile_id=m.get("profile_id"),
                camera=CameraSpec() if et == "camera" else None,
            )
            doc.avatars.append(avatar)
            by_id[avatar.id] = avatar
        elif op == "update":
            aid = m.get("id")
            if aid and aid in by_id:
                cur = by_id[aid].model_dump()
                for k, v in (m.get("patch") or {}).items():
                    if k in cur:
                        cur[k] = v
                updated = SceneAvatar.model_validate(cur)
                by_id[aid] = updated
                doc.avatars = [by_id[a.id] if a.id in by_id else a for a in doc.avatars]
        elif op == "remove":
            aid = m.get("id")
            doc.avatars = [a for a in doc.avatars if a.id != aid]
    return doc


def spatial_doc_summary(doc: SpatialSceneDoc) -> str:
    parts = []
    for a in doc.avatars:
        if not a.visible:
            continue
        bits = [f"{a.initials or a.label} ({a.entity_type})"]
        if a.facing.mode == "face_avatar" and a.facing.target_avatar_id:
            bits.append(f"faces {a.facing.target_avatar_id[:6]}")
        parts.append(" ".join(bits))
    return "; ".join(parts)[:800]
