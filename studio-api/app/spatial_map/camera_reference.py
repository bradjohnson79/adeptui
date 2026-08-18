"""Camera Shot References — per-camera viewpoint/framing canon for Mini.

Role (Part 17): viewpoint reference + framing reference + spatial
conditioning. NOT final scene art; never auto-approved scene imagery.

Each camera reference is independently replaceable (Part 15/18): changing one
camera's shot size regenerates only that camera's reference — the ERS core
and other cameras are untouched.

Staleness (Part 40): a reference is stale when the authoritative camera data
(camera moved / yaw / shot size / primary subject / FOV) or the ERS revision
changes after the reference was created. Stale references are excluded from
Mini conditioning and flagged in the UI.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..config import settings
from .camera_shot_packet import compile_camera_shot_packet
from .mini_production_compiler import compile_production_prompt

REF_TAG = "scene_creator_mini_camera_ref"
REF_SOURCE_FEATURE = "scene_creator_mini"
REF_ASPECT = "16:9"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refs_root(project_id: str) -> Path:
    path = Path(settings.data_dir) / "projects" / project_id / "scene_creator_mini" / "camera_refs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ref_dir(project_id: str, map_id: str) -> Path:
    path = _refs_root(project_id) / str(map_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ref_path(project_id: str, map_id: str, camera_id: str) -> Path:
    return _ref_dir(project_id, map_id) / f"{camera_id}.json"


def load_ref(project_id: str, map_id: str, camera_id: str) -> dict[str, Any] | None:
    path = _ref_path(project_id, map_id, camera_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_ref(project_id: str, map_id: str, record: dict[str, Any]) -> dict[str, Any]:
    record["updatedAt"] = _now()
    path = _ref_path(project_id, map_id, str(record.get("cameraId") or ""))
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_float(a: Any, b: Any, epsilon: float = 1e-6) -> bool:
    af = _finite(a)
    bf = _finite(b)
    if af is None and bf is None:
        return True
    if af is None or bf is None:
        return False
    return abs(af - bf) < epsilon


def compute_staleness(
    record: dict[str, Any],
    document: Any,
    camera: dict[str, Any],
    ers_revision: str,
) -> tuple[bool, list[str]]:
    """Compare the reference snapshot against current authoritative data."""
    reasons: list[str] = []
    if str(record.get("savedVersion") or "") != str(getattr(document, "savedVersion", "") or ""):
        reasons.append("Spatial Map was re-saved after this reference")
    if str(record.get("mapVersion") or "") != str(getattr(document, "version", "") or ""):
        reasons.append("Spatial Map version changed")
    if str(record.get("ersRevision") or "") != str(ers_revision or ""):
        reasons.append("ERS revision changed")
    current_shot_size = str(camera.get("shotSize") or "auto").strip().lower() or "auto"
    if str(record.get("shotSize") or "auto").strip().lower() != current_shot_size:
        reasons.append(f"Shot size changed to {current_shot_size}")
    current_primary = str(camera.get("primarySubject") or "auto").strip().lower() or "auto"
    if str(record.get("primarySubject") or "auto").strip().lower() != current_primary:
        reasons.append("Primary subject changed")
    current_orientation = str(camera.get("orientation") or "N").strip().upper() or "N"
    if str(record.get("orientation") or "").strip().upper() != current_orientation:
        reasons.append("Camera orientation changed")
    if not _same_float(record.get("yawDegrees"), camera.get("yawDegrees"), epsilon=0.5):
        reasons.append("Camera yaw changed")
    if str(record.get("fovPreset") or "") != str(camera.get("fovPreset") or ""):
        reasons.append("Camera FOV changed")
    position = record.get("position") if isinstance(record.get("position"), dict) else record
    if not _same_float(position.get("normalizedX"), camera.get("normalizedX")):
        reasons.append("Camera moved (position)")
    if not _same_float(position.get("normalizedY"), camera.get("normalizedY")):
        reasons.append("Camera moved (position)")
    return bool(reasons), reasons


def _hydrate(db: Any, record: dict[str, Any]) -> dict[str, Any]:
    job_id = str(record.get("jobId") or "")
    if not job_id or record.get("assetId"):
        return record
    try:
        from ..db import Job

        job = db.get(Job, job_id)
        if job is None:
            return record
        status = str(job.status or "").lower()
        if status in {"completed", "complete", "success", "done"}:
            params = {}
            try:
                params = json.loads(job.params_json or "{}")
            except Exception:
                params = {}
            asset_id = str(params.get("output_asset_id") or "").strip()
            if asset_id:
                record["assetId"] = asset_id
                record["status"] = "complete"
        elif status in {"failed", "error", "cancelled", "canceled"}:
            record["status"] = "failed"
            record["error"] = job.message or "Generation failed."
        elif status in {"queued"}:
            record["status"] = "queued"
        else:
            record["status"] = "generating"
    except Exception:
        pass
    return record


def list_refs(db: Any, project_id: str, document: Any) -> dict[str, Any]:
    """All camera references for a map, hydrated + staleness-stamped."""
    from .ers_projection import compile_structured_cameras

    compiled = compile_structured_cameras(getattr(document, "cameras", None) or [])
    cameras = list(compiled.get("cameras") or [])
    map_id = str(getattr(document, "id", "") or "")
    ers_revision = str(getattr(document, "groundingFingerprint", "") or "")
    out: list[dict[str, Any]] = []
    for camera in cameras:
        camera_id = str(camera.get("id") or "")
        record = load_ref(project_id, map_id, camera_id)
        if record is None:
            out.append(
                {
                    "cameraId": camera_id,
                    "label": camera.get("label"),
                    "assetId": None,
                    "status": "missing",
                    "stale": False,
                    "staleReasons": [],
                    "shotSize": camera.get("shotSize") or "auto",
                    "primarySubject": camera.get("primarySubject") or "auto",
                }
            )
            continue
        record = _hydrate(db, record)
        stale, reasons = compute_staleness(record, document, camera, ers_revision)
        record["stale"] = stale
        record["staleReasons"] = reasons
        out.append(record)
    return {"references": out, "count": len(out), "staleCount": sum(1 for r in out if r.get("stale"))}


def _prompt_for_reference(packet: Any, generator: str) -> str:
    """Camera reference prompt: viewpoint/framing canon, not final scene art."""
    packet_dict = packet.model_dump(mode="json") if hasattr(packet, "model_dump") else packet
    cam = packet_dict.get("camera") or {}
    label = str(cam.get("label") or "Camera")
    base = compile_production_prompt(
        packet_dict,
        generator=generator,
        aspect=REF_ASPECT,
        variation="A",
    )
    return (
        base
        + "\n"
        + f"This image is a CAMERA SHOT REFERENCE for {label}: it documents the "
        "canonical viewpoint, framing and shot scale for this camera. "
        "It is a clean photographic still — no labels, arrows, UI, or annotations. "
        "Do not add camera glyphs, grids, or text of any kind."
    )


def enqueue_camera_ref(
    db: Any,
    project_id: str,
    document: Any,
    camera: dict[str, Any],
    generator: str,
) -> dict[str, Any]:
    """Generate (or regenerate) ONE camera reference. Low-overhead rule:
    only this camera's reference is touched."""
    from ..storyboard_jobs import enqueue_imagegen_job
    from .scene_creator_mini import (
        _latest_ers_reference,
        _mini_source_asset,
        _pin_generator,
        mini_pixels,
    )

    from .ers_projection import _as_dict

    camera = _as_dict(camera)  # tolerate pydantic SpatialCamera or plain dict
    map_id = str(getattr(document, "id", "") or "")
    ers_sheet_id, ers_composite_id = _latest_ers_reference(project_id, map_id)
    ers_revision = str(getattr(document, "groundingFingerprint", "") or "")
    packet = compile_camera_shot_packet(
        db,
        project_id,
        document,
        camera,
        ers_sheet_id=ers_sheet_id,
        ers_composite_asset_id=ers_composite_id,
        ers_revision=ers_revision,
    )
    try:
        source = _mini_source_asset(db, project_id, document)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)[:400]) from exc
    if not source:
        raise HTTPException(409, "Attach an Atlas Shot or generate an Environment Reference Sheet first.")
    prompt = _prompt_for_reference(packet, generator)
    width, height = mini_pixels(REF_ASPECT)
    camera_id = str(camera.get("id") or "")
    record: dict[str, Any] = {
        "mapId": map_id,
        "cameraId": camera_id,
        "label": str(camera.get("label") or "Camera"),
        "assetId": None,
        "jobId": "",
        "status": "queued",
        "savedVersion": getattr(document, "savedVersion", None),
        "mapVersion": str(getattr(document, "version", "") or ""),
        "ersSheetId": ers_sheet_id,
        "ersRevision": ers_revision,
        "shotSize": str(camera.get("shotSize") or "auto"),
        "primarySubject": str(camera.get("primarySubject") or "auto"),
        "position": {
            "cell": str(camera.get("cell") or ""),
            "normalizedX": camera.get("normalizedX"),
            "normalizedY": camera.get("normalizedY"),
        },
        "orientation": str(camera.get("orientation") or "N"),
        "yawDegrees": camera.get("yawDegrees"),
        "fovPreset": str(camera.get("fovPreset") or "medium"),
        "generator": generator,
        "model": generator,
        "sourceAssetIds": [source],
        "stale": False,
        "staleReasons": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    body: dict[str, Any] = {
        "prompt": prompt,
        "purpose": "scene_shot",
        "operation": "image.generate",
        "aspectRatio": REF_ASPECT,
        "width": width,
        "height": height,
        "batchCount": 1,
        "commitToLibrary": False,
        "sourceFeature": REF_SOURCE_FEATURE,
        "tag": f"scene_creator_mini_camera_ref_{camera_id[:8]}_{uuid.uuid4().hex[:6]}",
        "spatialCameraId": camera_id,
        "spatialMapId": map_id,
        "creativeContext": {
            "objective": REF_SOURCE_FEATURE,
            "sourceFeature": REF_SOURCE_FEATURE,
            "referenceRole": "camera_shot_reference",
            "spatialMapId": map_id,
            "spatialCameraId": camera_id,
            "commitToLibrary": False,
            "camera": camera,
            "cameraShotPacket": packet.model_dump(mode="json"),
            "frameSize": REF_ASPECT,
        },
    }
    body = _pin_generator(body, generator, source)
    job = enqueue_imagegen_job(db, project_id, body, scene_id=getattr(document, "sceneId", None))
    record["jobId"] = str(job.id)
    return save_ref(project_id, map_id, record)


def current_reference_asset(
    db: Any,
    project_id: str,
    document: Any,
    camera: dict[str, Any],
) -> str:
    """Best non-stale camera reference asset for Mini conditioning, if any."""
    map_id = str(getattr(document, "id", "") or "")
    camera_id = str(camera.get("id") or "")
    record = load_ref(project_id, map_id, camera_id)
    if record is None:
        return ""
    record = _hydrate(db, record)
    if not record.get("assetId") or record.get("status") != "complete":
        return ""
    stale, _reasons = compute_staleness(
        record,
        document,
        camera,
        str(getattr(document, "groundingFingerprint", "") or ""),
    )
    if stale:
        return ""
    return str(record.get("assetId") or "")
