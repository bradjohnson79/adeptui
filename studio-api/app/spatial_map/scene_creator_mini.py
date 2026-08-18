"""Scene Creator Mini — camera-true stills from a saved Spatial Map.

Thin layer over Spatial Map cameras, ERS I2I adapters, and Library ingest.
Does not fork Scene Creator or add a Mini Library.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Job
from ..spatial_map.ers_projection import (
    compile_camera_viewpoint_facts,
    compile_structured_blocking,
    compile_structured_cameras,
)
from ..spatial_map.limits import CAMERA_LIMIT
from ..spatial_map.service import get_document
from ..storyboard_jobs import enqueue_imagegen_job

MINI_ASPECTS = ("1:1", "4:5", "3:2", "16:9", "9:16", "21:9")
MINI_PIXELS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "4:5": (1024, 1280),
    "3:2": (1536, 1024),
    "16:9": (1280, 720),
    "9:16": (1080, 1920),
    "21:9": (1344, 576),
}
VARIATIONS = ("A", "B")
SOURCE_FEATURE = "scene_creator_mini"
MINI_HERO_TAG = "scene_creator_mini_hero_inset"
# production_ers 3×3 panel 0 — Hero Environment (top-left).
MINI_HERO_PANEL = {"left": 0.0, "top": 0.0, "width": 1.0 / 3.0, "height": 1.0 / 3.0}
# Inset inside that panel so titles, gold headers, borders, and legends are excluded.
MINI_HERO_CONTENT = {"left": 0.08, "top": 0.22, "width": 0.84, "height": 0.70}


class MiniTakeCreateBody(BaseModel):
    generator: Literal["qwen2512", "gpt-image-2"] = "qwen2512"
    aspectRatio: str = "16:9"
    cameraIds: list[str] | None = None


class MiniSendBody(BaseModel):
    resultIds: list[str] = Field(default_factory=list)


class MiniRegenerateBody(BaseModel):
    cameraId: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mini_dir(project_id: str) -> Path:
    path = Path(settings.data_dir) / "projects" / project_id / "scene_creator_mini"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _take_path(project_id: str, take_id: str) -> Path:
    return _mini_dir(project_id) / f"{take_id}.json"


def _index_path(project_id: str, map_id: str) -> Path:
    return _mini_dir(project_id) / f"index-{map_id}.json"


def load_take(project_id: str, take_id: str) -> dict[str, Any]:
    path = _take_path(project_id, take_id)
    if not path.is_file():
        raise HTTPException(404, "Mini Take not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_take(project_id: str, take: dict[str, Any]) -> dict[str, Any]:
    take["updatedAt"] = _now()
    path = _take_path(project_id, str(take["id"]))
    path.write_text(json.dumps(take, indent=2), encoding="utf-8")
    return take


def require_saved_document(document: Any) -> None:
    saved = getattr(document, "savedVersion", None)
    version = getattr(document, "version", None)
    if not saved or saved != version:
        raise HTTPException(409, "Save Spatial Map to generate a Mini Take.")


def active_cameras_for_document(document: Any) -> dict[str, Any]:
    return compile_structured_cameras(getattr(document, "cameras", None) or [])


def mini_output_count(camera_count: int) -> int:
    n = max(0, min(int(camera_count), CAMERA_LIMIT))
    return n * 2


def mini_pixels(aspect: str) -> tuple[int, int]:
    key = (aspect or "16:9").strip()
    if key not in MINI_ASPECTS:
        raise HTTPException(400, f"Frame size {aspect} is not supported for Scene Creator Mini.")
    try:
        from ..aspect_fps import PRODUCTION_ASPECTS, production_pixels

        if key in PRODUCTION_ASPECTS:
            return production_pixels(key, "final")
    except Exception:
        pass
    return MINI_PIXELS[key]


def _next_take_number(project_id: str, map_id: str) -> int:
    path = _index_path(project_id, map_id)
    n = 0
    if path.is_file():
        try:
            n = int(json.loads(path.read_text(encoding="utf-8")).get("lastTakeNumber") or 0)
        except Exception:
            n = 0
    n += 1
    path.write_text(json.dumps({"lastTakeNumber": n, "mapId": map_id}), encoding="utf-8")
    return n


def _latest_ers_composite(project_id: str, map_id: str) -> str:
    return _latest_ers_reference(project_id, map_id)[1]


def _latest_ers_reference(project_id: str, map_id: str) -> tuple[str, str]:
    """Current authoritative ERS (sheet_id, composite_asset_id) for a map."""
    try:
        from ..environment_reference_sheet.store import list_sheets

        sheets = [
            s
            for s in list_sheets(project_id)
            if getattr(s, "spatialMap", None) is not None
            and str(s.spatialMap.mapId or "") == str(map_id)
        ]
        sheets.sort(key=lambda s: str(getattr(s, "updatedAt", "") or getattr(s, "updated_at", "") or ""), reverse=True)
        for sheet in sheets:
            composite = str(getattr(sheet, "ers_composite_asset_id", None) or "").strip()
            if composite:
                return str(getattr(sheet, "sheetId", "") or ""), composite
    except Exception:
        pass
    return "", ""


def crop_ers_hero(image_path: str | Path, panel: dict[str, float] | None = None):
    """Crop the Hero Environment panel from a production_ers 3×3 sheet."""
    from PIL import Image

    spec = panel or MINI_HERO_PANEL
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    left = int(round(float(spec["left"]) * width))
    top = int(round(float(spec["top"]) * height))
    right = int(round((float(spec["left"]) + float(spec["width"])) * width))
    bottom = int(round((float(spec["top"]) + float(spec["height"])) * height))
    if right <= left or bottom <= top:
        raise RuntimeError("ERS hero crop is empty.")
    return image.crop((left, top, right, bottom))


def crop_mini_environment_plate(
    image_path: str | Path,
    panel: dict[str, float] | None = None,
    content: dict[str, float] | None = None,
):
    """Hero panel inset: environment pixels only, no sheet titles or legends."""
    hero = crop_ers_hero(image_path, panel)
    spec = content or MINI_HERO_CONTENT
    width, height = hero.size
    left = int(round(float(spec["left"]) * width))
    top = int(round(float(spec["top"]) * height))
    right = int(round((float(spec["left"]) + float(spec["width"])) * width))
    bottom = int(round((float(spec["top"]) + float(spec["height"])) * height))
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))
    return hero.crop((left, top, right, bottom))


def _ensure_hero_plate_asset(db: Session, project_id: str, composite_id: str) -> str:
    from ..db import Asset

    existing = (
        db.query(Asset)
        .filter(
            Asset.project_id == project_id,
            Asset.parent_asset_id == composite_id,
            Asset.tag == MINI_HERO_TAG,
        )
        .first()
    )
    if existing and Path(str(existing.path)).is_file():
        return str(existing.id)
    parent = db.get(Asset, composite_id)
    if not parent or not Path(str(parent.path)).is_file():
        return composite_id
    crop = crop_mini_environment_plate(parent.path)
    dest = _mini_dir(project_id) / f"hero-inset-{composite_id}.png"
    crop.save(dest, "PNG")
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=MINI_HERO_TAG,
        kind="image",
        filename=dest.name,
        path=str(dest),
        comfy_name="",
        parent_asset_id=composite_id,
        prompt_meta_json=json.dumps(
            {
                "libraryVisible": False,
                "sourceFeature": SOURCE_FEATURE,
                "role": "mini_hero_plate_inset",
                "crop": {"panel": MINI_HERO_PANEL, "content": MINI_HERO_CONTENT},
            }
        ),
    )
    db.add(asset)
    db.flush()
    return str(asset.id)


def _mini_source_asset(db: Session, project_id: str, document: Any) -> str:
    """Pixel plate for Mini I2I: clean environment pixels ONLY.

    Priority: ERS hero-inset plate (chrome-free), then the Atlas Shot. The
    full ERS composite (titles/legends/3x3 panels) is NEVER fed to a Mini
    generator (Part 22 law) — blocking is honest when no clean plate exists.
    """
    composite = _latest_ers_composite(project_id, str(getattr(document, "id", "") or ""))
    if composite and db is not None:
        try:
            plate = _ensure_hero_plate_asset(db, project_id, composite)
            if plate and plate != composite:
                return plate
        except Exception:
            pass  # fall through to atlas; never the chrome composite
    atlas = str(getattr(document, "backgroundAssetId", None) or "").strip()
    if atlas:
        return atlas
    raise RuntimeError(
        "Scene Creator Mini requires clean environment pixels. "
        "Attach an Atlas Shot or generate an Environment Reference Sheet first."
    )


def _compile_mini_prompt(
    db: Session,
    project_id: str,
    document: Any,
    camera: dict[str, Any],
    *,
    variation: str,
    aspect: str,
) -> str:
    """Legacy wrapper: compile the production prompt from a fresh shot packet.

    The deterministic compiler is compile_production_prompt over a
    CameraShotPacket. This wrapper keeps the old signature for tests and
    call sites that have no ERS reference ids.
    """
    from .camera_shot_packet import compile_camera_shot_packet
    from .mini_production_compiler import compile_production_prompt

    packet = compile_camera_shot_packet(db, project_id, document, camera)
    return compile_production_prompt(
        packet.model_dump(mode="json"),
        generator="gpt-image-2",
        aspect=aspect,
        variation=variation,
    )


def _pin_generator(
    body: dict[str, Any],
    generator: str,
    source_asset_id: str,
    extra_reference_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Pin the generator and reference conditioning for one Mini variation.

    Reference hierarchy (Part 19):
      GPT Image 2 : environment plate + character reference + camera reference
                    (separate responsibilities, distinct images).
      Qwen        : single reference only (qwen2512.ref graph has one
                    LoadImage) — environment plate; identity is text + MUST
                    BE PRESENT + validation. Never pretend multi-reference.
    """
    from ..codirector.capabilities.handlers.ers_generate import (
        _ers_i2i_workflow_key,
        _gpt_i2i_official_id,
        _public_asset_url,
    )

    extras = [str(rid) for rid in (extra_reference_ids or []) if str(rid or "").strip()]
    ctx = body.setdefault("creativeContext", {})
    # Live Kie gpt-image-2 image-to-image rejects multi-image requests
    # (verified: 5/7 jobs failed with image-fetch/type errors). The strongest
    # SUPPORTED hierarchy is ONE authoritative reference (clean environment
    # plate) + text identity; extra references are recorded as lineage only
    # and never pretend to be consumed (Parts 19/22 honesty law).
    if generator == "qwen2512":
        key = _ers_i2i_workflow_key()
        if not key:
            raise HTTPException(
                409,
                "Qwen Image image-to-image is not ready. Choose GPT Image 2 or repair the local installation.",
            )
        body["forceWorkflowKey"] = key
        body["allow_force_workflow_key"] = True
        body["lockModelFamily"] = True
        body["modelFamilyPreference"] = "qwen2512"
        body["source"] = "local"
        ctx["operationIntent"] = "image_to_image_reference"
        ctx["referenceGrounding"] = {
            "mode": "pixel",
            "workflow": key,
            "authoritativeSourceAssetId": source_asset_id,
            # qwen2512.ref consumes exactly ONE reference image (LoadImage).
            # Character/camera references cannot be consumed by this graph and
            # are intentionally NOT attached — identity rides the prompt text.
        }
    else:
        body["hostedModelId"] = "gpt-image-2-kie"
        body["kieImageModelId"] = _gpt_i2i_official_id()
        body["lockModelFamily"] = True
        # Single authoritative reference only (see honesty note above).
        url_ids = list(dict.fromkeys([source_asset_id]))
        urls = [u for u in (_public_asset_url(aid) for aid in url_ids) if u]
        if urls:
            body["input_urls"] = urls
        ctx["operationIntent"] = "image.generate"
        ctx["referenceGrounding"] = {
            "mode": "pixel",
            "assetIds": url_ids,
            "authoritativeSourceAssetId": source_asset_id,
            "consideredReferenceAssetIds": extras,
            "referenceConsumption": "single_authoritative_only",
            "workflow": _gpt_i2i_official_id(),
        }
    if source_asset_id:
        body["sourceAssetId"] = source_asset_id
        body["source_asset_id"] = source_asset_id
        body["referenceImage"] = source_asset_id
    return body


def _enqueue_variation(
    db: Session,
    *,
    project_id: str,
    document: Any,
    take: dict[str, Any],
    camera: dict[str, Any],
    variation: str,
    generator: str,
    aspect: str,
    source_asset_id: str,
    packet: dict[str, Any] | None = None,
    camera_reference_asset_id: str | None = None,
) -> dict[str, Any]:
    from .mini_production_compiler import compile_production_prompt

    width, height = mini_pixels(aspect)
    packet_dict = dict(packet or {})
    if not packet_dict:
        from .camera_shot_packet import compile_camera_shot_packet

        packet_dict = compile_camera_shot_packet(db, project_id, document, camera).model_dump(
            mode="json"
        )
    prompt = compile_production_prompt(
        packet_dict,
        generator=generator,
        aspect=aspect,
        variation=variation,
    )
    # Reference conditioning hierarchy (Part 19): character identity refs from
    # the packet (approved assets of required characters) + the camera
    # viewpoint reference when available and not stale. GPT consumes them;
    # Qwen records but does not consume (single LoadImage graph).
    required_ids = set(str(rid) for rid in (packet_dict.get("requiredCharacterIds") or []))
    char_refs: list[str] = []
    for char in packet_dict.get("characters") or []:
        if not isinstance(char, dict):
            continue
        if str(char.get("characterId") or "") in required_ids:
            approved = str(char.get("approvedAssetId") or "").strip()
            if approved:
                char_refs.append(approved)
    camera_ref = str(camera_reference_asset_id or "").strip()
    extras_raw: list[str] = [*char_refs]
    if camera_ref:
        extras_raw.append(camera_ref)
    extras = list(dict.fromkeys(extras_raw))
    result_id = str(uuid.uuid4())
    body: dict[str, Any] = {
        "prompt": prompt,
        "purpose": "scene_shot",
        "operation": "image.generate",
        "aspectRatio": aspect,
        "width": width,
        "height": height,
        "batchCount": 1,
        "commitToLibrary": False,
        "sourceFeature": SOURCE_FEATURE,
        "miniTakeId": take["id"],
        "miniVariation": variation,
        "spatialCameraId": camera.get("id"),
        "spatialMapId": document.id,
        "spatialMapVersion": str(getattr(document, "version", "") or ""),
        "tag": f"scene_creator_mini_{take['takeNumber']}_{camera.get('label')}_{variation}",
        "creativeContext": {
            "objective": SOURCE_FEATURE,
            "sourceFeature": SOURCE_FEATURE,
            "miniTakeId": take["id"],
            "miniVariation": variation,
            "spatialMapId": document.id,
            "spatialCameraId": camera.get("id"),
            "commitToLibrary": False,
            "camera": camera,
            "cameraShotPacket": packet_dict,
            "frameSize": aspect,
        },
    }
    body = _pin_generator(body, generator, source_asset_id, extra_reference_ids=extras)
    job = enqueue_imagegen_job(db, project_id, body, scene_id=getattr(document, "sceneId", None))
    return {
        "id": result_id,
        "cameraId": camera.get("id"),
        "cameraLabel": camera.get("label"),
        "variation": variation,
        "jobId": job.id,
        "assetId": None,
        "status": "queued",
        "libraryVisible": False,
        "inLibrary": False,
        "error": None,
        "generator": generator,
        "frameSize": aspect,
        "shotSize": (packet_dict.get("camera") or {}).get("shotSize") if isinstance(packet_dict.get("camera"), dict) else None,
        "requiredCharacters": list(packet_dict.get("requiredCharacterIds") or []),
    }


def _hydrate_results(db: Session, take: dict[str, Any]) -> dict[str, Any]:
    for result in take.get("results") or []:
        job_id = str(result.get("jobId") or "")
        if not job_id:
            continue
        job = db.get(Job, job_id)
        if job is None:
            continue
        status = str(job.status or "").lower()
        if status in {"completed", "complete", "success", "done"}:
            result["status"] = "complete"
            params = {}
            try:
                params = json.loads(job.params_json or "{}")
            except Exception:
                params = {}
            asset_id = str(params.get("output_asset_id") or "").strip()
            if asset_id:
                result["assetId"] = asset_id
                asset = db.get(Asset, asset_id)
                if asset is not None:
                    try:
                        meta = json.loads(asset.prompt_meta_json or "{}")
                    except Exception:
                        meta = {}
                    result["inLibrary"] = bool(meta.get("libraryVisible") is True)
                    result["libraryVisible"] = result["inLibrary"]
        elif status in {"failed", "error", "cancelled", "canceled"}:
            result["status"] = "failed"
            result["error"] = job.message or "Generation failed."
        elif status in {"queued"}:
            result["status"] = "queued"
        else:
            result["status"] = "generating"
    _schedule_missing_validations(db, take)
    return take


def _schedule_missing_validations(db: Session, take: dict[str, Any]) -> None:
    """Hydrate fallback: completed results without a verdict get validated.

    The queue worker normally stamps the verdict at completion; this covers
    worker restarts / missed hooks. In-flight markers prevent duplicate
    VLM calls while a validation is running.
    """
    from .mini_validation import _INFLIGHT_TTL_SECONDS, schedule_validation

    project_id = str(take.get("projectId") or "")
    take_id = str(take.get("id") or "")
    if not project_id or not take_id:
        return
    for result in take.get("results") or []:
        if str(result.get("status") or "") != "complete":
            continue
        if not result.get("assetId"):
            continue
        validation = result.get("validation")
        if isinstance(validation, dict) and validation.get("verdict"):
            continue
        # A FRESH pendingSince means a validation call is in flight — do not
        # stack a duplicate. An EXPIRED marker (stuck thread / crashed worker)
        # must be retried, otherwise the candidate is stuck forever.
        if isinstance(validation, dict) and validation.get("pendingSince"):
            try:
                started = datetime.fromisoformat(str(validation["pendingSince"]))
                age = (datetime.now(timezone.utc) - started).total_seconds()
            except Exception:
                age = 0.0
            if age < _INFLIGHT_TTL_SECONDS:
                continue
        result["validation"] = {"state": "validating", "scheduledAt": _now()}
        schedule_validation(project_id, take_id, str(result.get("id") or ""))


def create_mini_take(
    db: Session,
    project_id: str,
    map_id: str,
    body: MiniTakeCreateBody,
) -> dict[str, Any]:
    document = get_document(db, project_id, map_id)
    require_saved_document(document)
    compiled = active_cameras_for_document(document)
    cameras = list(compiled.get("cameras") or [])
    if body.cameraIds:
        wanted = {str(cid) for cid in body.cameraIds}
        cameras = [c for c in cameras if str(c.get("id")) in wanted]
    if not cameras:
        raise HTTPException(400, "Add and save at least one camera to generate a Mini Take.")
    if len(cameras) > CAMERA_LIMIT:
        raise HTTPException(409, "Scene Creator Mini supports at most four cameras. Select which cameras to use.")
    try:
        source = _mini_source_asset(db, project_id, document)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)[:400]) from exc
    if not source:
        raise HTTPException(409, "Attach an Atlas Shot or generate an Environment Reference Sheet first.")
    aspect = (body.aspectRatio or "16:9").strip()
    mini_pixels(aspect)
    ers_sheet_id, ers_composite_id = _latest_ers_reference(project_id, map_id)
    ers_revision = str(getattr(document, "groundingFingerprint", "") or "")
    take_number = _next_take_number(project_id, map_id)
    take = {
        "id": str(uuid.uuid4()),
        "takeNumber": take_number,
        "projectId": project_id,
        "mapId": map_id,
        "savedVersion": document.savedVersion,
        "mapVersion": document.version,
        "ersSheetId": ers_sheet_id,
        "ersCompositeAssetId": ers_composite_id,
        "ersRevision": ers_revision,
        "generator": body.generator,
        "aspectRatio": aspect,
        "cameras": cameras,
        "cameraPackets": {},
        "results": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    from .camera_reference import current_reference_asset
    from .camera_shot_packet import compile_camera_shot_packet

    results = []
    try:
        for camera in cameras:
            packet = compile_camera_shot_packet(
                db,
                project_id,
                document,
                camera,
                ers_sheet_id=ers_sheet_id,
                ers_composite_asset_id=ers_composite_id,
                ers_revision=ers_revision,
            )
            take["cameraPackets"][str(camera.get("id"))] = packet.model_dump(mode="json")
            camera_ref_asset = current_reference_asset(db, project_id, document, camera)
            for variation in VARIATIONS:
                results.append(
                    _enqueue_variation(
                        db,
                        project_id=project_id,
                        document=document,
                        take=take,
                        camera=camera,
                        variation=variation,
                        generator=body.generator,
                        aspect=aspect,
                        source_asset_id=source,
                        packet=packet.model_dump(mode="json"),
                        camera_reference_asset_id=camera_ref_asset,
                    )
                )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)[:400]) from exc
    take["results"] = results
    return save_take(project_id, take)


def get_mini_take(db: Session, project_id: str, take_id: str) -> dict[str, Any]:
    take = load_take(project_id, take_id)
    take = _hydrate_results(db, take)
    save_take(project_id, take)
    return take


def latest_mini_take(project_id: str, map_id: str) -> dict[str, Any] | None:
    files = sorted(_mini_dir(project_id).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        if path.name.startswith("index-"):
            continue
        try:
            take = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(take.get("mapId") or "") == str(map_id):
            return take
    return None


def regenerate_mini(
    db: Session,
    project_id: str,
    map_id: str,
    take_id: str,
    body: MiniRegenerateBody,
) -> dict[str, Any]:
    document = get_document(db, project_id, map_id)
    require_saved_document(document)
    take = load_take(project_id, take_id)
    compiled = active_cameras_for_document(document)
    cameras = {str(c.get("id")): c for c in compiled.get("cameras") or []}
    target_ids = [body.cameraId] if body.cameraId else [str(c.get("id")) for c in take.get("cameras") or []]
    try:
        source = _mini_source_asset(db, project_id, document)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)[:400]) from exc
    generator = str(take.get("generator") or "qwen2512")
    aspect = str(take.get("aspectRatio") or "16:9")
    ers_sheet_id, ers_composite_id = _latest_ers_reference(project_id, map_id)
    ers_revision = str(getattr(document, "groundingFingerprint", "") or "")
    from .camera_reference import current_reference_asset
    from .camera_shot_packet import compile_camera_shot_packet

    kept = []
    for result in take.get("results") or []:
        if str(result.get("cameraId")) in {str(tid) for tid in target_ids if tid}:
            continue
        kept.append(result)
    for cam_id in target_ids:
        camera = cameras.get(str(cam_id or ""))
        if camera is None:
            continue
        packet = compile_camera_shot_packet(
            db,
            project_id,
            document,
            camera,
            ers_sheet_id=ers_sheet_id,
            ers_composite_asset_id=ers_composite_id,
            ers_revision=ers_revision,
        )
        take.setdefault("cameraPackets", {})[str(camera.get("id"))] = packet.model_dump(mode="json")
        camera_ref_asset = current_reference_asset(db, project_id, document, camera)
        for variation in VARIATIONS:
            kept.append(
                _enqueue_variation(
                    db,
                    project_id=project_id,
                    document=document,
                    take=take,
                    camera=camera,
                    variation=variation,
                    generator=generator,
                    aspect=aspect,
                    source_asset_id=source,
                    packet=packet.model_dump(mode="json"),
                    camera_reference_asset_id=camera_ref_asset,
                )
            )
    take["results"] = kept
    take["savedVersion"] = document.savedVersion
    take["ersSheetId"] = ers_sheet_id
    take["ersCompositeAssetId"] = ers_composite_id
    take["ersRevision"] = ers_revision
    return save_take(project_id, take)


def send_selected_to_library(db: Session, project_id: str, take_id: str, body: MiniSendBody) -> dict[str, Any]:
    from .mini_validation import validation_state_for_result

    take = load_take(project_id, take_id)
    wanted = {str(rid) for rid in body.resultIds or []}
    sent = 0
    skipped = []
    for result in take.get("results") or []:
        if str(result.get("id")) not in wanted:
            continue
        # Continuity gate (Part 27): only PASS-validated candidates are
        # Library-ingestable. Failed/unvalidated results are never sent.
        if validation_state_for_result(result) != "pass":
            skipped.append(str(result.get("id")))
            continue
        asset_id = str(result.get("assetId") or "").strip()
        if not asset_id:
            take = _hydrate_results(db, take)
            asset_id = str(result.get("assetId") or "").strip()
        if not asset_id:
            continue
        asset = db.get(Asset, asset_id)
        if asset is None:
            continue
        try:
            meta = json.loads(asset.prompt_meta_json or "{}")
        except Exception:
            meta = {}
        if meta.get("libraryVisible") is True:
            result["inLibrary"] = True
            result["libraryVisible"] = True
            continue
        meta["libraryVisible"] = True
        meta["sourceFeature"] = SOURCE_FEATURE
        meta["miniTakeId"] = take_id
        meta["spatialCameraId"] = result.get("cameraId")
        meta["cameraLabel"] = result.get("cameraLabel")
        meta["miniVariation"] = result.get("variation")
        asset.prompt_meta_json = json.dumps(meta)
        result["inLibrary"] = True
        result["libraryVisible"] = True
        sent += 1
    db.commit()
    take["lastLibrarySendCount"] = sent
    take["lastLibrarySkippedIds"] = skipped
    return save_take(project_id, take)
