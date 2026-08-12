"""PoseCraft persistence service — project-scoped save/load/revision/export preview."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import Project
from .schemas import (
    JOINT_NAMES,
    POSECRAFT_SCHEMA_VERSION,
    PoseCraftDocument,
    PoseCraftExportPreview,
    PoseCraftProvenance,
    PoseCraftRevision,
    PoseCraftScene,
    PoseCraftSnapshot,
)


class PoseCraftError(Exception):
    """Raised for PoseCraft persistence failures (not found, schema, etc.)."""


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


_KNOWN_JOINTS = set(JOINT_NAMES)

# Legacy staging color IDs (schemaVersion 1) → current canonical IDs.
# Visual hex is preserved (teal/seaglass share #0f766e, coral/orange share
# #ea580c, etc.); sky→blue and rose→red are the closest current matches.
_LEGACY_COLOR_REMAP = {
    "teal": "seaglass",
    "coral": "orange",
    "violet": "purple",
    "sky": "blue",
    "gold": "yellow",
    "rose": "red",
}


def _remap_color_id(color_id):
    if not color_id:
        return color_id
    return _LEGACY_COLOR_REMAP.get(color_id, color_id)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _migrate_figure(figure: dict) -> dict:
    """Migrate one figure dict to the current schema.

    Preserves id/name/archetypeId/colorId/position/rotationY/scale/characterId/
    identityId verbatim. Known joints are kept (clamped); missing known joints
    are filled with neutral (0,0,0); unsupported legacy joints are moved to
    legacyJointData (provenance) rather than discarded.
    """
    pose_in = figure.get("pose") or {}
    next_pose = {joint: {"x": 0.0, "y": 0.0, "z": 0.0} for joint in _KNOWN_JOINTS}
    legacy = dict(figure.get("legacyJointData") or {})
    for joint, rotation in pose_in.items():
        rot = rotation or {}
        x = float(rot.get("x", 0.0))
        y = float(rot.get("y", 0.0))
        z = float(rot.get("z", 0.0))
        if joint in _KNOWN_JOINTS:
            next_pose[joint] = {"x": x, "y": y, "z": z}
        else:
            legacy[joint] = {"x": x, "y": y, "z": z}
    out = {k: v for k, v in figure.items() if k not in ("pose", "legacyJointData")}
    out["pose"] = next_pose
    if "colorId" in out:
        out["colorId"] = _remap_color_id(out["colorId"])
    if legacy:
        out["legacyJointData"] = legacy
    return out


def migrate_scene_to_current(data: dict) -> dict:
    """Migrate a raw PoseCraft scene dict to the current schemaVersion (2).

    Idempotent. Preserves all protected fields; never corrupts an existing
    project merely because the figure mesh / joint system improved.
    """
    scene = dict(data)
    migrated_from = int(scene.get("schemaVersion") or 1)
    needs_migration = migrated_from < POSECRAFT_SCHEMA_VERSION
    scene["schemaVersion"] = POSECRAFT_SCHEMA_VERSION
    figures = scene.get("figures")
    if isinstance(figures, list):
        scene["figures"] = [_migrate_figure(f) for f in figures if isinstance(f, dict)]
    if needs_migration:
        notes = (
            "Migrated from schemaVersion 1 (block-figure) to 2 (humanoid rig). "
            "Unsupported legacy joints retained in figure.legacyJointData."
            if migrated_from < 2
            else "Schema normalized to current version."
        )
        scene["provenance"] = {
            "migratedFrom": migrated_from,
            "migratedAt": _now_iso(),
            "notes": notes,
        }
    return scene


def _coerce_iso(value: Any) -> str:
    """Coerce a datetime-or-string from SQLite into an ISO-8601 string."""
    if value is None:
        return _now_iso()
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    text = str(value).strip()
    if not text:
        return _now_iso()
    if text.endswith("Z"):
        return text
    return text + "Z"


def _empty_document() -> PoseCraftDocument:
    return PoseCraftDocument()


def load_scene(project_id: str, db: Session) -> PoseCraftDocument:
    """Load the live PoseCraft document for a project. Empty doc if unset.

    Runs the backward-compat migration gate so GREEN-baseline saved scenes
    remain loadable after the rig/joint upgrade: protected fields preserved,
    unsupported legacy joints retained in figure.legacyJointData.
    """
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    raw = (project.posecraft_document_json or "").strip()
    if not raw:
        return _empty_document()
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        # Corrupt document — fall back to empty rather than crash the UI.
        return _empty_document()
    try:
        # Migrate the current scene to the current schema (idempotent).
        if isinstance(data, dict) and isinstance(data.get("currentScene"), dict):
            data["currentScene"] = migrate_scene_to_current(data["currentScene"])
        if isinstance(data, dict) and isinstance(data.get("savedVersions"), list):
            for v in data["savedVersions"]:
                if isinstance(v, dict) and isinstance(v.get("scene"), dict):
                    v["scene"] = migrate_scene_to_current(v["scene"])
        # Snapshot contract migration: missing snapshots → [], missing
        # selectedSnapshotId → None. Snapshots are frozen at capture time;
        # we do not mutate their frozen camera/figures/primitives here.
        if isinstance(data, dict):
            if not isinstance(data.get("snapshots"), list):
                data["snapshots"] = []
            if data.get("selectedSnapshotId") is not None and not isinstance(data.get("selectedSnapshotId"), str):
                data["selectedSnapshotId"] = None
        return PoseCraftDocument.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        # Schema mismatch that migration could not fix — fall back to empty.
        return _empty_document()


def save_scene(project_id: str, document: PoseCraftDocument, db: Session, *, saved_by: str = "creator") -> PoseCraftDocument:
    """Persist the live PoseCraft document for a project.

    Marks the scene creatorModified=True so Co-Director mutations cannot
    silently overwrite a creator's work without approval. Runs the
    backward-compat migration gate on the incoming currentScene (and any
    savedVersions) so a PUT of a legacy schemaVersion-1 document is migrated
    to the current schema before persistence — the returned document always
    reports the current schemaVersion for both the document and its scene.
    """
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    # Bump schema/revision metadata defensively.
    document.schemaVersion = POSECRAFT_SCHEMA_VERSION
    # Migrate the incoming currentScene to the current schema (idempotent):
    # remaps legacy color IDs, retains unsupported legacy joints in
    # figure.legacyJointData, and records provenance when a legacy scene is
    # upgraded. Without this, a PUT of a schemaVersion-1 document is stored
    # and returned unchanged (currentScene.schemaVersion stays 1).
    document.currentScene = PoseCraftScene.model_validate(
        migrate_scene_to_current(document.currentScene.model_dump())
    )
    for rev in document.savedVersions:
        rev.scene = PoseCraftScene.model_validate(
            migrate_scene_to_current(rev.scene.model_dump())
        )
    if document.currentScene.updatedAt == "":
        document.currentScene.updatedAt = _now_iso()
    document.currentScene.creatorModified = True
    project.posecraft_document_json = document.model_dump_json()
    project.updated_at = datetime.utcnow()
    db.commit()
    return document


def list_revisions(project_id: str, db: Session) -> list[PoseCraftRevision]:
    """List saved milestone revisions for a project (newest first)."""
    rows = db.execute(
        text(
            "SELECT id, revision, label, scene_json, created_at FROM posecraft_revisions "
            "WHERE project_id = :pid ORDER BY revision DESC"
        ),
        {"pid": project_id},
    ).fetchall()
    revisions: list[PoseCraftRevision] = []
    for row in rows:
        try:
            scene = PoseCraftScene.model_validate(json.loads(row.scene_json or "{}"))
        except Exception:  # noqa: BLE001
            continue
        saved_at = _coerce_iso(row.created_at)
        revisions.append(
            PoseCraftRevision(
                id=row.id,
                label=row.label or "",
                savedAt=saved_at,
                revision=row.revision,
                scene=scene,
            )
        )
    return revisions


def save_revision(project_id: str, label: str, scene: PoseCraftScene, db: Session, *, saved_by: str = "creator") -> PoseCraftRevision:
    """Record a milestone revision of the current scene."""
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    revision_id = str(uuid.uuid4())
    created_at = datetime.utcnow()
    db.execute(
        text(
            "INSERT INTO posecraft_revisions (id, project_id, revision, label, scene_json, "
            "creator_modified, saved_by, created_at) VALUES (:id, :pid, :rev, :label, :scene, 1, :by, :ts)"
        ),
        {
            "id": revision_id,
            "pid": project_id,
            "rev": int(scene.revision),
            "label": (label or f"Revision {scene.revision}")[:200],
            "scene": scene.model_dump_json(),
            "by": saved_by,
            "ts": created_at,
        },
    )
    db.commit()
    return PoseCraftRevision(
        id=revision_id,
        label=label or f"Revision {scene.revision}",
        savedAt=created_at.isoformat() + "Z",
        revision=int(scene.revision),
        scene=scene,
    )


def restore_revision(project_id: str, revision_id: str, db: Session) -> PoseCraftDocument:
    """Restore a saved milestone as the live document (new revision number)."""
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    row = db.execute(
        text(
            "SELECT scene_json FROM posecraft_revisions WHERE id = :rid AND project_id = :pid"
        ),
        {"rid": revision_id, "pid": project_id},
    ).fetchone()
    if not row:
        raise PoseCraftError("Revision not found", 404)
    scene = PoseCraftScene.model_validate(json.loads(row.scene_json or "{}"))
    scene.revision = int(scene.revision) + 1
    scene.updatedAt = _now_iso()
    scene.creatorModified = True
    doc = PoseCraftDocument(currentScene=scene, savedVersions=[])
    project.posecraft_document_json = doc.model_dump_json()
    project.updated_at = datetime.utcnow()
    db.commit()
    return doc


def _semantic_figure(f) -> dict:
    """Co-Director scene label package: id permanent, label = creator name."""
    return {
        "id": f.id,
        "label": f.name,
        "name": f.name,
        "role": getattr(f, "role", None) or "unspecified",
        "type": getattr(f, "kind", None) == "custom" and "custom-figure" or f.archetypeId,
        "archetypeId": f.archetypeId,
        "colorId": f.colorId,
        "characterId": f.characterId,
        "identityId": f.identityId,
        "poseId": getattr(f, "poseId", None),
        "poseLabel": getattr(f, "poseLabel", None),
        "eyelineTargetId": getattr(f, "eyelineTargetId", None),
        "customAssetId": getattr(f, "customAssetId", None),
        "position": f.position,
        "rotationY": f.rotationY,
        "scale": f.scale,
    }


def _semantic_primitive(p) -> dict:
    return {
        "id": p.id,
        "label": p.name,
        "name": p.name,
        "type": p.kind,
        "furnitureKind": p.kind,
        "position": p.position,
        "size": p.size,
        "color": p.color,
    }


def _semantic_summary(scene: PoseCraftScene) -> str:
    lines = [f"Scene: {scene.name}"]
    for f in scene.figures:
        role = getattr(f, "role", None) or "unspecified"
        role_s = f" ({role})" if role != "unspecified" else ""
        pose = getattr(f, "poseLabel", None) or getattr(f, "poseId", None) or "Neutral"
        lines.append(f"{f.name}{role_s} — {f.archetypeId} — {pose}")
    for p in scene.primitives:
        lines.append(f"{p.name} — {p.kind}")
    return "\n".join(lines)


def build_export_preview(project_id: str, db: Session, *, snapshot_id: str | None = None) -> PoseCraftExportPreview:
    """Build an honesty-labelled staging reference preview for the Image Pipeline.

    When ``snapshot_id`` is supplied, the preview is built from the frozen
    Snapshot composition (camera/figures/primitives/semanticSummary captured
    at freeze time) rather than the live scene. This is the production
    handoff path: the Snapshot freezes one exact camera composition.
    """
    doc = load_scene(project_id, db)
    if snapshot_id:
        snapshot = _find_snapshot(doc, snapshot_id)
        if not snapshot:
            raise PoseCraftError("Snapshot not found", 404)
        return PoseCraftExportPreview(
            sceneName=snapshot.name,
            revision=int(snapshot.sceneRevision),
            figureCount=len(snapshot.figures),
            primitiveCount=len(snapshot.primitives),
            lensMm=float(snapshot.camera.lensMm),
            aspect=snapshot.camera.aspect,
            honestyLabel="PoseCraft Snapshot — Visual Staging Reference",
            notes=snapshot.semanticSummary,
            figures=[_semantic_figure(f) for f in snapshot.figures],
            objects=[_semantic_primitive(p) for p in snapshot.primitives],
            semanticSummary=snapshot.semanticSummary,
            camera=snapshot.camera,
        )
    scene = doc.currentScene
    return PoseCraftExportPreview(
        sceneName=scene.name,
        revision=int(scene.revision),
        figureCount=len(scene.figures),
        primitiveCount=len(scene.primitives),
        lensMm=float(scene.camera.lensMm),
        aspect=scene.camera.aspect,
        notes=scene.notes,
        figures=[_semantic_figure(f) for f in scene.figures],
        objects=[_semantic_primitive(p) for p in scene.primitives],
        semanticSummary=_semantic_summary(scene),
        camera=scene.camera,
    )


# --------------------------------------------------------------------------
# Snapshot CRUD — frozen camera-composition handoff artifacts.
# --------------------------------------------------------------------------

POSECRAFT_SNAPSHOT_CAP = 48


def _find_snapshot(doc: PoseCraftDocument, snapshot_id: str) -> PoseCraftSnapshot | None:
    for s in doc.snapshots or []:
        if s.snapshotId == snapshot_id:
            return s
    return None


def list_snapshots(project_id: str, db: Session) -> list[PoseCraftSnapshot]:
    """List frozen Snapshots for a project (newest first)."""
    doc = load_scene(project_id, db)
    snaps = list(doc.snapshots or [])
    snaps.sort(key=lambda s: s.createdAt or s.updatedAt or "", reverse=True)
    return snaps


def get_snapshot(project_id: str, snapshot_id: str, db: Session) -> PoseCraftSnapshot:
    doc = load_scene(project_id, db)
    snap = _find_snapshot(doc, snapshot_id)
    if not snap:
        raise PoseCraftError("Snapshot not found", 404)
    return snap


def rename_snapshot(project_id: str, snapshot_id: str, name: str, db: Session) -> PoseCraftDocument:
    """Rename a Snapshot. Only `name` changes — frozen camera/figures/etc. are immutable."""
    doc = load_scene(project_id, db)
    snap = _find_snapshot(doc, snapshot_id)
    if not snap:
        raise PoseCraftError("Snapshot not found", 404)
    next_name = (name or "").strip()[:200] or snap.name
    snap.name = next_name
    snap.updatedAt = _now_iso()
    return save_scene(project_id, doc, db, saved_by="creator")


def duplicate_snapshot(project_id: str, snapshot_id: str, db: Session) -> PoseCraftDocument:
    """Duplicate a Snapshot's frozen composition under a new snapshotId."""
    doc = load_scene(project_id, db)
    snap = _find_snapshot(doc, snapshot_id)
    if not snap:
        raise PoseCraftError("Snapshot not found", 404)
    if len(doc.snapshots or []) >= POSECRAFT_SNAPSHOT_CAP:
        raise PoseCraftError(
            f"Snapshot cap reached ({POSECRAFT_SNAPSHOT_CAP}). Delete one before duplicating.",
            400,
        )
    copy = snap.model_copy(deep=True)
    copy.snapshotId = str(uuid.uuid4())
    copy.name = f"{snap.name} Copy"
    copy.createdAt = _now_iso()
    copy.updatedAt = _now_iso()
    snaps = list(doc.snapshots or [])
    idx = next((i for i, s in enumerate(snaps) if s.snapshotId == snapshot_id), len(snaps) - 1)
    snaps.insert(idx + 1, copy)
    doc.snapshots = snaps
    doc.selectedSnapshotId = copy.snapshotId
    return save_scene(project_id, doc, db, saved_by="creator")


def delete_snapshot(project_id: str, snapshot_id: str, db: Session) -> PoseCraftDocument:
    """Delete a Snapshot. Clears selection if the deleted snap was selected."""
    doc = load_scene(project_id, db)
    snaps = [s for s in (doc.snapshots or []) if s.snapshotId != snapshot_id]
    if len(snaps) == len(doc.snapshots or []):
        raise PoseCraftError("Snapshot not found", 404)
    doc.snapshots = snaps
    if doc.selectedSnapshotId == snapshot_id:
        doc.selectedSnapshotId = None
    return save_scene(project_id, doc, db, saved_by="creator")


def select_snapshot(project_id: str, snapshot_id: str | None, db: Session) -> PoseCraftDocument:
    """Select a Snapshot for handoff (null clears selection). Does NOT restore the scene."""
    doc = load_scene(project_id, db)
    if snapshot_id is not None and not _find_snapshot(doc, snapshot_id):
        raise PoseCraftError("Snapshot not found", 404)
    doc.selectedSnapshotId = snapshot_id
    return save_scene(project_id, doc, db, saved_by="creator")


def apply_tool_mutation(project_id: str, mutation: dict[str, Any], db: Session, *, actor: str) -> PoseCraftDocument:
    """Apply a Co-Director posecraft.* tool mutation.

    Approval-gated by the caller (Co-Director tool execution layer). This
    function refuses to silently overwrite a creatorModified scene unless the
    mutation carries an explicit ``force`` flag (which the approval layer only
    sets after creator consent). Returns the updated document.
    """
    doc = load_scene(project_id, db)
    if doc.currentScene.creatorModified and not mutation.get("force", False):
        raise PoseCraftError(
            "PoseCraft scene is creator-modified; Co-Director mutation requires approval",
            409,
        )
    new_scene = mutation.get("scene")
    if isinstance(new_scene, PoseCraftScene):
        doc.currentScene = new_scene
    elif isinstance(new_scene, dict):
        doc.currentScene = PoseCraftScene.model_validate(new_scene)
    return save_scene(project_id, doc, db, saved_by=actor)


# --------------------------------------------------------------------------
# Master Program Phase 15–20: custom pose CRUD (project-scoped persistence).
# --------------------------------------------------------------------------


def list_custom_poses(project_id: str, db: Session) -> list[dict[str, Any]]:
    """List creator-defined poses for a project (newest first)."""
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    rows = db.execute(
        text(
            "SELECT id, pose_id, label, description, category, archetypes_json, "
            "joints_json, thumbnail, creator_modified, saved_by, created_at, updated_at "
            "FROM posecraft_custom_poses WHERE project_id = :pid ORDER BY updated_at DESC"
        ),
        {"pid": project_id},
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            archetypes = json.loads(row.archetypes_json or "[]")
            joints = json.loads(row.joints_json or "{}")
        except Exception:  # noqa: BLE001
            archetypes, joints = [], {}
        out.append(
            {
                "id": row.id,
                "projectId": project_id,
                "poseId": row.pose_id,
                "label": row.label or "",
                "description": row.description or "",
                "category": row.category or "custom",
                "archetypes": archetypes,
                "joints": joints,
                "thumbnail": row.thumbnail or "",
                "creatorModified": bool(row.creator_modified),
                "savedBy": row.saved_by or "creator",
                "createdAt": _coerce_iso(row.created_at),
                "updatedAt": _coerce_iso(row.updated_at),
            }
        )
    return out


def create_custom_pose(project_id: str, pose: dict[str, Any], db: Session, *, saved_by: str = "creator") -> dict[str, Any]:
    """Create a creator-defined pose for a project."""
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    pose_id = str(pose.get("poseId") or "").strip()[:120]
    if not pose_id:
        raise PoseCraftError("poseId is required", 400)
    label = str(pose.get("label") or pose_id)[:200]
    description = str(pose.get("description") or "")[:2000]
    category = str(pose.get("category") or "custom")[:48]
    archetypes = pose.get("archetypes") if isinstance(pose.get("archetypes"), list) else []
    joints = pose.get("joints") if isinstance(pose.get("joints"), dict) else {}
    thumbnail = str(pose.get("thumbnail") or "")[:20000]
    row_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db.execute(
        text(
            "INSERT INTO posecraft_custom_poses (id, project_id, pose_id, label, description, "
            "category, archetypes_json, joints_json, thumbnail, creator_modified, saved_by, "
            "created_at, updated_at) VALUES (:id, :pid, :pose_id, :label, :description, :category, "
            ":archetypes, :joints, :thumbnail, 1, :by, :ts, :ts)"
        ),
        {
            "id": row_id,
            "pid": project_id,
            "pose_id": pose_id,
            "label": label,
            "description": description,
            "category": category,
            "archetypes": json.dumps(archetypes),
            "joints": json.dumps(joints),
            "thumbnail": thumbnail,
            "by": saved_by,
            "ts": now,
        },
    )
    db.commit()
    return {
        "id": row_id,
        "projectId": project_id,
        "poseId": pose_id,
        "label": label,
        "description": description,
        "category": category,
        "archetypes": archetypes,
        "joints": joints,
        "thumbnail": thumbnail,
        "creatorModified": True,
        "savedBy": saved_by,
        "createdAt": now.isoformat() + "Z",
        "updatedAt": now.isoformat() + "Z",
    }


def update_custom_pose(
    project_id: str, pose_id: str, patch: dict[str, Any], db: Session, *, saved_by: str = "creator"
) -> dict[str, Any]:
    """Update a creator-defined pose (label/description/category/archetypes/joints/thumbnail)."""
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    row = db.execute(
        text(
            "SELECT id, label, description, category, archetypes_json, joints_json, thumbnail "
            "FROM posecraft_custom_poses WHERE project_id = :pid AND pose_id = :pose_id"
        ),
        {"pid": project_id, "pose_id": pose_id},
    ).fetchone()
    if not row:
        raise PoseCraftError("Custom pose not found", 404)
    label = str(patch.get("label", row.label) or row.label)[:200]
    description = str(patch.get("description", row.description) or row.description)[:2000]
    category = str(patch.get("category", row.category) or row.category)[:48]
    archetypes = patch["archetypes"] if isinstance(patch.get("archetypes"), list) else json.loads(row.archetypes_json or "[]")
    joints = patch["joints"] if isinstance(patch.get("joints"), dict) else json.loads(row.joints_json or "{}")
    thumbnail = str(patch.get("thumbnail", row.thumbnail) or row.thumbnail)[:20000]
    now = datetime.utcnow()
    db.execute(
        text(
            "UPDATE posecraft_custom_poses SET label = :label, description = :description, "
            "category = :category, archetypes_json = :archetypes, joints_json = :joints, "
            "thumbnail = :thumbnail, saved_by = :by, updated_at = :ts "
            "WHERE project_id = :pid AND pose_id = :pose_id"
        ),
        {
            "label": label,
            "description": description,
            "category": category,
            "archetypes": json.dumps(archetypes),
            "joints": json.dumps(joints),
            "thumbnail": thumbnail,
            "by": saved_by,
            "ts": now,
            "pid": project_id,
            "pose_id": pose_id,
        },
    )
    db.commit()
    return {
        "id": row.id,
        "projectId": project_id,
        "poseId": pose_id,
        "label": label,
        "description": description,
        "category": category,
        "archetypes": archetypes,
        "joints": joints,
        "thumbnail": thumbnail,
        "creatorModified": True,
        "savedBy": saved_by,
        "updatedAt": now.isoformat() + "Z",
    }


def delete_custom_pose(project_id: str, pose_id: str, db: Session) -> None:
    """Delete a creator-defined pose."""
    project = db.get(Project, project_id)
    if not project:
        raise PoseCraftError("Project not found", 404)
    result = db.execute(
        text("DELETE FROM posecraft_custom_poses WHERE project_id = :pid AND pose_id = :pose_id"),
        {"pid": project_id, "pose_id": pose_id},
    )
    db.commit()
    if result.rowcount == 0:
        raise PoseCraftError("Custom pose not found", 404)
