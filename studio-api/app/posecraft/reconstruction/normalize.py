"""Normalize official Fire3D outputs into Fire3DReconstructionPackage.

Reads the real release layout when present:
  oriented_bboxes.json
  reconstruction/<scene_id>/ world object meshes
  composed scene GLB
  background instance
Never invents Fire3D fields. Missing native files stay absent.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .contracts import DetectedHuman, Fire3DReconstructionObject, Fire3DReconstructionPackage, Vec3

_HUMAN_LABELS = {
    "person",
    "human",
    "man",
    "woman",
    "child",
    "people",
    "character",
    "body",
}


def _label_is_human(label: str) -> bool:
    token = (label or "").strip().lower()
    return any(part in token for part in _HUMAN_LABELS)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_bbox_entries(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("objects", "instances", "oriented_bboxes", "bboxes", "items", "obj_dict"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if any(k in payload for k in ("id", "instance_id", "label", "center", "pose", "bbox3d_world_center")):
            return [payload]
    return []


def _vec_from(value: Any, default: Vec3 | None = None) -> Vec3:
    fallback = default or Vec3()
    if isinstance(value, dict):
        return Vec3(
            x=float(value.get("x") or value.get("0") or 0.0),
            y=float(value.get("y") or value.get("1") or 0.0),
            z=float(value.get("z") or value.get("2") or 0.0),
        )
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return Vec3(x=float(value[0]), y=float(value[1]), z=float(value[2]))
    return fallback


def normalize_fire3d_output(
    output_root: str | Path,
    *,
    reconstruction_id: str | None = None,
    source_asset_id: str = "",
    source_type: str = "image",
    provider: str = "LOCAL_FIRE3D",
    scene_glb_asset_id: str | None = None,
    background_asset_id: str | None = None,
    mesh_asset_ids: dict[str, str] | None = None,
) -> Fire3DReconstructionPackage:
    """Parse a Fire3D result directory into an Adept package."""
    root = Path(output_root)
    reconstruction_id = reconstruction_id or str(uuid.uuid4())
    mesh_asset_ids = mesh_asset_ids or {}

    bbox_payload = _read_json(root / "oriented_bboxes.json")
    if bbox_payload is None:
        bbox_payload = _read_json(root / "raw_oriented_bboxes.json")
    entries = _iter_bbox_entries(bbox_payload)

    objects: list[Fire3DReconstructionObject] = []
    humans: list[DetectedHuman] = []
    failed = 0
    for index, entry in enumerate(entries):
        source_id = str(
            entry.get("instance_id")
            or entry.get("id")
            or entry.get("object_id")
            or entry.get("obj_id")
            or f"instance_{index:03d}"
        )
        label = str(entry.get("label") or entry.get("class") or entry.get("name") or entry.get("cls") or source_id)
        status = "failed" if entry.get("failed") or entry.get("error") else "ok"
        if status == "failed":
            failed += 1
        human = bool(entry.get("is_human") or _label_is_human(label))
        position = _vec_from(
            entry.get("center")
            or entry.get("position")
            or entry.get("translation")
            or entry.get("obj_tran")
            or entry.get("bbox3d_world_center")
        )
        rotation = _vec_from(entry.get("rotation") or entry.get("rpy") or entry.get("euler") or entry.get("obj_rot"))
        scale = _vec_from(
            entry.get("scale") or entry.get("size") or entry.get("obj_scale") or entry.get("half_length"),
            default=Vec3(x=1.0, y=1.0, z=1.0),
        )
        obj = Fire3DReconstructionObject(
            objectId=f"obj_{index:03d}",
            name=label,
            detectedLabel=label,
            meshAssetId=mesh_asset_ids.get(source_id) or mesh_asset_ids.get(str(index)),
            position=position,
            rotation=rotation,
            scale=scale,
            boundingBox={
                k: entry[k]
                for k in ("obb", "bbox", "extent", "corners", "half_length")
                if k in entry
            },
            sourceInstanceId=source_id,
            status=status,  # type: ignore[arg-type]
            detectedHuman=human,
            categoryHint="human" if human else "object",
            failureReason=str(entry.get("error") or entry.get("failure") or ""),
        )
        objects.append(obj)
        if human:
            humans.append(
                DetectedHuman(
                    objectId=obj.objectId,
                    sourceInstanceId=source_id,
                    position=position,
                    rotation=rotation,
                    suggestedReplace=True,
                )
            )

    metadata: dict[str, Any] = {}
    for name in ("protocol.json", "scene_audit.json", "run_manifest.json"):
        payload = _read_json(root / name)
        if payload is not None:
            metadata[name] = payload

    if scene_glb_asset_id is None:
        for candidate in root.rglob("*.glb"):
            if "scene" in candidate.name.lower() or candidate.name.lower() == "composed.glb":
                metadata.setdefault("localSceneGlb", str(candidate))
                break
    if background_asset_id is None:
        for candidate in root.rglob("*background*"):
            if candidate.suffix.lower() in {".glb", ".ply", ".obj"}:
                metadata.setdefault("localBackground", str(candidate))
                break

    return Fire3DReconstructionPackage(
        reconstructionId=reconstruction_id,
        sourceAssetId=source_asset_id,
        sourceType=source_type,  # type: ignore[arg-type]
        provider=provider,  # type: ignore[arg-type]
        sceneGlbAssetId=scene_glb_asset_id,
        backgroundAssetId=background_asset_id,
        objects=objects,
        detectedHumans=humans,
        cameraData=metadata.get("protocol.json", {}).get("views") if isinstance(metadata.get("protocol.json"), dict) else None,
        metadata=metadata,
        partialSuccess=failed > 0 and failed < max(len(objects), 1),
    )
