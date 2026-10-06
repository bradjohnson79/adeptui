"""Character Creator V3 multi-view state and endpoints.

Front stays on the selected image generator. Side / 3/4 / Back use the named
Character Angles engine (Qwen Image Edit 2509). This module never silently
routes those angles through FLUX / Krea / Qwen-as-Front or generate_view("back").
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from ..workflows.qwen_image_edit_2509 import (
    QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE,
    QWEN_EDIT_2509_DEFAULT_CFG,
    QWEN_EDIT_2509_DEFAULT_STEPS,
)
from .multiview_engine import (
    ANGLE_NEGATIVE,
    ANGLE_PROMPTS,
    ENGINE_QWEN_EDIT_2509,
    PRODUCTION_ENGINE,
    QWEN_EDIT_FAMILY,
    QWEN_EDIT_WEIGHTS,
    QWEN_EDIT_WORKFLOW_KEY,
    assert_can_generate,
    production_engine_status,
)

MULTIVIEW_ANGLES = ("side", "three_quarter", "back")
CAMERA_ROLES = {
    "side": "SIDE",
    "three_quarter": "THREE_QUARTER",
    "back": "BACK",
}
SOURCE_GENERATED = "generated"
SOURCE_UPLOADED = "uploaded"
ANGLE_ROLE = "character_angle"
ANGLE_LIBRARY_LABELS = {
    "side": "Side",
    "three_quarter": "3/4",
    "back": "Back",
}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
_MIN_DIM = 32
_MAX_DIM = 16384

MULTIVIEW_VISION_INSTRUCTIONS = """You are Co-Director inspecting approved FRONT, SIDE, 3/4, and BACK character photographs.
Return JSON only with keys: side_silhouette, rear_hairstyle, rear_wardrobe, three_quarter_facial_depth, visible_accessories, confirmed_body_proportions, multi_view_continuity, notes.
Use only facts visible across the images. Empty string if unknown.
Do not invent personality, biography, age, or height. Do not overwrite the creator's written name or description.
No markdown."""


def empty_angle() -> dict[str, Any]:
    return {
        "status": "idle",
        "assetId": None,
        "assetUrl": None,
        "approved": False,
        "approvedAt": None,
        "rejected": False,
        "sourceFrontAssetId": None,
        "wonder3dModelVersion": None,
        "modelVersion": QWEN_EDIT_WEIGHTS,
        "runtime": None,
        "engine": PRODUCTION_ENGINE,
        "cameraRole": None,
        "generatedAt": None,
        "jobId": None,
        "promptId": None,
        "seed": None,
        "workflowKey": None,
        "canonAssetId": None,
        "upscaledAssetId": None,
        "upscaleStatus": "idle",
        "error": None,
        "progress": {"percent": 0, "stage": "idle", "label": "", "source": PRODUCTION_ENGINE},
        "provenance": None,
        "source": None,
    }


def empty_multiview() -> dict[str, Any]:
    return {
        "status": "idle",
        "engine": PRODUCTION_ENGINE,
        "progress": {"percent": 0, "stage": "idle", "label": "", "source": PRODUCTION_ENGINE},
        "error": None,
        "pendingReplacement": False,
        "angles": {name: empty_angle() for name in MULTIVIEW_ANGLES},
    }


def empty_enrichment() -> dict[str, Any]:
    return {
        "status": "none",
        "facts": {},
        "provenance": None,
        "error": None,
        "at": None,
    }


def merge_multiview(raw: Any) -> dict[str, Any]:
    base = empty_multiview()
    if not isinstance(raw, dict):
        return base
    base.update({k: v for k, v in raw.items() if k != "angles"})
    base["engine"] = PRODUCTION_ENGINE
    angles = dict(raw.get("angles") or {})
    merged = {}
    for name in MULTIVIEW_ANGLES:
        slot = empty_angle()
        slot.update(angles.get(name) or {})
        slot["cameraRole"] = CAMERA_ROLES[name]
        if _slot_source(slot) != SOURCE_UPLOADED:
            slot["engine"] = PRODUCTION_ENGINE
        merged[name] = slot
    base["angles"] = merged
    return base


def angles_approved(state: dict[str, Any]) -> bool:
    mv = merge_multiview(state.get("multiView"))
    return all(bool(mv["angles"][name].get("approved")) for name in MULTIVIEW_ANGLES)


ANGLE_DISPLAY = ANGLE_LIBRARY_LABELS
_LIVE_STATUSES = frozenset({"generating", "queued", "running", "starting"})


def _approved_asset_id(slot: Any) -> str:
    if not isinstance(slot, dict) or not slot.get("approved"):
        return ""
    return str(slot.get("assetId") or "").strip()


def _asset_bound_character_id(db, asset_id: str) -> str:
    if db is None or not asset_id:
        return ""
    from ..db import Asset

    asset = db.get(Asset, asset_id)
    if asset is None:
        return ""
    return str(_asset_prompt_meta(asset).get("characterId") or "").strip()


def sheet_gate(state: dict[str, Any], db=None, character_id: str | None = None) -> dict[str, Any]:
    """Sheet compose is ready when four approved canonical views exist.

    Source (uploaded / generated) and Co-Director vision lock are not a gate.
    """
    missing: list[str] = []
    cid = str(character_id or (state.get("characterId") if isinstance(state, dict) else "") or "").strip()
    views = state.get("views") if isinstance(state.get("views"), dict) else {}
    front = views.get("front") if isinstance(views.get("front"), dict) else {}
    approved = {
        "front": _approved_asset_id(front),
        "side": "",
        "three_quarter": "",
        "back": "",
    }
    if not approved["front"]:
        missing.append("Approve Front")

    mv = merge_multiview(state.get("multiView"))
    for name in MULTIVIEW_ANGLES:
        approved[name] = _approved_asset_id(mv["angles"][name])
        if not approved[name]:
            missing.append(f"Approve {ANGLE_DISPLAY[name]}")

    if cid and db is not None:
        for name, aid in approved.items():
            bound = _asset_bound_character_id(db, aid)
            if bound and bound != cid:
                label = "Front" if name == "front" else ANGLE_DISPLAY[name]
                missing.append(f"{label} belongs to a different character")

    ready = not missing
    return {
        "ready": ready,
        "missing": missing,
        "approvedFrontAssetId": approved["front"] or None,
        "approvedSideAssetId": approved["side"] or None,
        "approvedThreeQuarterAssetId": approved["three_quarter"] or None,
        "approvedBackAssetId": approved["back"] or None,
        "nextAction": "Character Sheet ready to create." if ready else (missing[0] if missing else ""),
    }


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _front_lock_ok(state: dict[str, Any]) -> tuple[bool, str]:
    lock_ok = str((state.get("visualLock") or {}).get("status") or "") == "ok"
    front_approved = bool(state["views"]["front"].get("approved"))
    front_id = str(state["views"]["front"].get("assetId") or "").strip()
    if not front_approved or not lock_ok or not front_id:
        return False, ""
    return True, front_id


def _forget_asset(db, project_id: str, asset_id: Optional[str], *, protect: set[str]) -> None:
    aid = str(asset_id or "").strip()
    if not aid or aid in protect:
        return
    from ..db import Asset

    asset = db.get(Asset, aid)
    if not asset or asset.project_id != project_id:
        return
    path = Path(asset.path) if asset.path else None
    if path and path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    try:
        db.delete(asset)
        db.flush()
    except Exception:
        pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_json(raw: Any, fallback: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw or "").strip()
    if not text:
        return fallback
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _asset_prompt_meta(asset) -> dict[str, Any]:
    meta = _parse_json(getattr(asset, "prompt_meta_json", None), {})
    return dict(meta) if isinstance(meta, dict) else {}


def _asset_source(db, asset_id: Optional[str]) -> str:
    aid = str(asset_id or "").strip()
    if not aid:
        return ""
    from ..db import Asset

    asset = db.get(Asset, aid)
    if asset is None:
        return ""
    return str(_asset_prompt_meta(asset).get("source") or "").strip().lower()


def _slot_source(slot: dict[str, Any] | None) -> str:
    return str((slot or {}).get("source") or "").strip().lower()


def _keep_uploaded_history(db, asset_id: Optional[str], slot: dict[str, Any] | None = None) -> bool:
    if _slot_source(slot) == SOURCE_UPLOADED:
        return True
    return _asset_source(db, asset_id) == SOURCE_UPLOADED


def _forget_replaced_candidate(
    db,
    project_id: str,
    slot: dict[str, Any],
    *,
    protect: set[str],
    field: str = "assetId",
) -> None:
    aid = str(slot.get(field) or "").strip() or None
    if _keep_uploaded_history(db, aid, slot if field == "assetId" else None):
        return
    _forget_asset(db, project_id, aid, protect=protect)


def angle_library_title(character_name: str, angle: str) -> str:
    name = str(character_name or "").strip() or "Character"
    return f"{name} — {ANGLE_DISPLAY.get(angle, angle)}"


def validate_angle_image_bytes(data: bytes, *, filename: str = "", content_type: str = "") -> dict[str, Any]:
    raw = data or b""
    name = str(filename or "").strip()
    ctype = str(content_type or "").split(";")[0].strip().lower()
    ext = Path(name).suffix.lower()
    head = raw[:16]
    if not raw:
        raise _err("IMAGE_DECODE_FAILED", "Could not decode image.")
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        raise _err("NOT_AN_IMAGE", "That file is audio, not a picture.")
    if head.startswith(b"ID3") or head.startswith(b"\xff\xfb") or head.startswith(b"\xff\xf3"):
        raise _err("NOT_AN_IMAGE", "That file is audio, not a picture.")
    if head[4:8] == b"ftyp" or b"ftyp" in head or head.startswith(b"\x00\x00\x00\x01"):
        raise _err("NOT_AN_IMAGE", "That file is a video, not a picture.")
    if ctype.startswith("video/") or ctype.startswith("audio/"):
        raise _err("NOT_AN_IMAGE", "Upload a picture, not a video or audio file.")
    if ext and ext not in _IMAGE_EXTS and not ctype.startswith("image/"):
        raise _err("UNSUPPORTED_IMAGE_FORMAT", "Unsupported image format.")
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            width, height = im.size
            fmt = str(im.format or "").upper()
    except HTTPException:
        raise
    except Exception:
        raise _err("IMAGE_DECODE_FAILED", "Could not decode image.") from None
    if width < _MIN_DIM or height < _MIN_DIM:
        raise _err("IMAGE_TOO_SMALL", "That picture is too small to use as a character angle.")
    if width > _MAX_DIM or height > _MAX_DIM:
        raise _err("IMAGE_TOO_LARGE", "That picture is too large to use as a character angle.")
    return {"width": width, "height": height, "format": fmt or ext.lstrip(".").upper()}


def stamp_angle_library_asset(
    db,
    asset,
    *,
    project_id: str,
    character_id: str,
    character_name: str,
    angle: str,
    source: str,
) -> None:
    now = _iso_now()
    meta = _asset_prompt_meta(asset)
    created = str(meta.get("createdAt") or getattr(asset, "created_at", "") or now)
    if hasattr(created, "strftime"):
        created = created.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta.update(
        {
            "assetId": asset.id,
            "projectId": project_id,
            "characterId": character_id,
            "characterName": character_name,
            "assetType": "image",
            "role": ANGLE_ROLE,
            "angle": angle,
            "source": source,
            "createdAt": str(created or now),
            "updatedAt": now,
            "cameraRole": CAMERA_ROLES[angle],
        }
    )
    labels = _parse_json(getattr(asset, "labels_json", None), [])
    if not isinstance(labels, list):
        labels = []
    for item in (ANGLE_ROLE, angle, source):
        if item not in labels:
            labels.append(item)
    asset.kind = "image"
    asset.labels_json = json.dumps(labels)
    asset.prompt_meta_json = json.dumps(meta, ensure_ascii=False)
    title = angle_library_title(character_name, angle)
    if not str(asset.tag or "").strip() or str(asset.tag).startswith(f"{character_id[:8]}") or "_v3_" in str(asset.tag or ""):
        asset.tag = title[:64]
    try:
        from ..project_library.service import assign_asset

        assign_asset(
            db,
            asset,
            entity_type="character",
            entity_name=character_name,
            entity_id=character_id,
            classified_by="character_angle",
            hints={"systemKey": "characters.references", "role": ANGLE_ROLE, "angle": angle},
        )
    except Exception:
        pass


def adopt_angle_from_asset(
    db,
    project_id: str,
    character_id: str,
    angle: str,
    asset_id: str,
    *,
    source_type: str = SOURCE_UPLOADED,
) -> dict[str, Any]:
    """Library / uploaded picture becomes an angle candidate. Creator still Approves."""
    from .cc_v2 import _now, _profile, get_status, save_state
    from .cc_v2_media import resolve_character_asset

    if angle not in MULTIVIEW_ANGLES:
        raise _err("INVALID_VIEW", f"Unknown multi-view angle: {angle}")
    profile = _profile(db, project_id, character_id)
    resolved = resolve_character_asset(db, project_id, asset_id)
    if not resolved:
        raise _err("ASSET_NOT_FOUND", "That picture is not in this project's Library.", 404)
    from ..db import Asset

    asset = db.get(Asset, resolved["assetId"])
    if asset is None:
        raise _err("ASSET_NOT_FOUND", "That picture is not in this project's Library.", 404)
    source = SOURCE_UPLOADED if str(source_type or "").strip().lower() in {"upload", "uploaded", SOURCE_UPLOADED} else SOURCE_UPLOADED
    stamp_angle_library_asset(
        db,
        asset,
        project_id=str(asset.project_id or project_id),
        character_id=character_id,
        character_name=profile.name,
        angle=angle,
        source=source,
    )
    state = get_status(db, project_id, character_id)
    mv = merge_multiview(state.get("multiView"))
    prior = mv["angles"][angle]
    canon = str(prior.get("assetId") or "").strip() or None
    keep_canon = bool(prior.get("approved") and canon and canon != resolved["assetId"])
    slot = empty_angle()
    slot.update(
        {
            "status": "ready",
            "assetId": resolved["assetId"],
            "assetUrl": resolved.get("assetUrl"),
            "approved": False,
            "approvedAt": None,
            "rejected": False,
            "source": source,
            "cameraRole": CAMERA_ROLES[angle],
            "engine": None,
            "runtime": None,
            "workflowKey": None,
            "jobId": None,
            "promptId": None,
            "seed": None,
            "generatedAt": _now(),
            "canonAssetId": canon if keep_canon else None,
            "error": None,
            "provenance": {
                "source": source,
                "cameraRole": CAMERA_ROLES[angle],
                "assetId": resolved["assetId"],
            },
        }
    )
    mv["angles"][angle] = slot
    if any(
        str(item.get("status") or "") in _LIVE_STATUSES
        for item in mv["angles"].values()
    ):
        mv["status"] = "generating"
    elif any(item.get("assetId") for item in mv["angles"].values()):
        mv["status"] = "review"
        mv["error"] = None
    else:
        mv["status"] = "idle"
    state["multiView"] = mv
    state["multiviewEnrichment"] = empty_enrichment()
    _stale_sheet(state)
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def upload_angle_from_bytes(
    db,
    project_id: str,
    character_id: str,
    angle: str,
    *,
    data: bytes,
    filename: str = "",
    content_type: str = "",
) -> dict[str, Any]:
    from .cc_v2 import _profile
    from ..config import settings
    from ..db import Asset

    if angle not in MULTIVIEW_ANGLES:
        raise _err("INVALID_VIEW", f"Unknown multi-view angle: {angle}")
    profile = _profile(db, project_id, character_id)
    info = validate_angle_image_bytes(data, filename=filename, content_type=content_type)
    ext = Path(filename or "").suffix.lower()
    if ext not in _IMAGE_EXTS:
        fmt = str(info.get("format") or "PNG").lower()
        ext = ".jpg" if fmt in {"jpeg", "jpg"} else f".{fmt}" if fmt else ".png"
        if ext not in _IMAGE_EXTS:
            ext = ".png"
    asset_id = str(uuid.uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}{ext}"
    dest.write_bytes(data)
    title = angle_library_title(profile.name, angle)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=title[:64],
        kind="image",
        filename=filename or f"{title}{ext}",
        path=str(dest),
        comfy_name="",
    )
    db.add(asset)
    db.flush()
    stamp_angle_library_asset(
        db,
        asset,
        project_id=project_id,
        character_id=character_id,
        character_name=profile.name,
        angle=angle,
        source=SOURCE_UPLOADED,
    )
    try:
        content_hash = hashlib.sha256(data).hexdigest()
        from ..project_library.service import find_duplicates_by_hash, mark_duplicate

        duplicates = [a for a in find_duplicates_by_hash(db, project_id, content_hash) if a.id != asset.id]
        if duplicates:
            mark_duplicate(db, asset, duplicates[0].id)
    except Exception:
        pass
    return adopt_angle_from_asset(
        db,
        project_id,
        character_id,
        angle,
        asset.id,
        source_type=SOURCE_UPLOADED,
    )


def _stale_sheet(state: dict[str, Any]) -> None:
    state["sheet"] = state.get("sheet") or {}
    if str((state.get("sheet") or {}).get("status") or "") == "ready":
        state["sheet"]["status"] = "stale"
        state["sheetAssetId"] = None


def _angle_prompt(state: dict[str, Any], angle: str) -> str:
    lock_facts = (state.get("visualLock") or {}).get("facts") or {}
    prompt = ANGLE_PROMPTS[angle]
    if isinstance(lock_facts, dict) and lock_facts:
        brief = ", ".join(f"{k}: {v}" for k, v in lock_facts.items() if str(v).strip())
        if brief:
            prompt = f"{prompt}\nIdentity lock from approved front: {brief}"
    return prompt


def _enqueue_angle_job(
    db,
    project_id: str,
    character_id: str,
    state: dict[str, Any],
    angle: str,
    *,
    front_asset_id: str,
):
    from . import service
    from .visual_sheet import _enqueue_txt2img

    profile_dump = service.get_profile(db, project_id, character_id).model_dump()
    name = profile_dump.get("name") or "Character"
    char_slug = (profile_dump.get("slug") or name).replace(" ", "_").lower()
    seed = uuid.uuid4().int % 2_147_483_647
    job = _enqueue_txt2img(
        db,
        project_id,
        character_id=character_id,
        prompt=_angle_prompt(state, angle),
        negative_prompt=ANGLE_NEGATIVE,
        tag=f"{char_slug}_v3_{angle}",
        role=CAMERA_ROLES[angle],
        model_family_preference=QWEN_EDIT_FAMILY,
        source_asset_id=front_asset_id,
        denoise=0.72,
        seed=seed,
        steps=QWEN_EDIT_2509_DEFAULT_STEPS,
        cfg=QWEN_EDIT_2509_DEFAULT_CFG,
        width=QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE,
        height=QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE,
        force_workflow_key=QWEN_EDIT_WORKFLOW_KEY,
        provider_kind="local",
        hosted_model_id=None,
        sheet_layout="cc_v2",
        prompt_metadata={
            "ccV3": True,
            "ccV2": False,
            "view": angle,
            "angle": angle,
            "role": ANGLE_ROLE,
            "source": SOURCE_GENERATED,
            "characterId": character_id,
            "assetType": "image",
            "cameraRole": CAMERA_ROLES[angle],
            "workflowKey": QWEN_EDIT_WORKFLOW_KEY,
            "modelFamily": QWEN_EDIT_FAMILY,
            "runtime": ENGINE_QWEN_EDIT_2509,
            "engine": ENGINE_QWEN_EDIT_2509,
            "referenceAssetId": front_asset_id,
            "sourceFrontAssetId": front_asset_id,
            "approvedFrontAssetId": front_asset_id,
            "referenceKind": "IDENTITY_REFERENCE",
            "taskType": "CC_V3_MULTIVIEW",
            "fourViewSingleOutput": False,
            "seed": seed,
            "acceleration": {
                "profile": "qwen_edit_2509_native",
                "steps": QWEN_EDIT_2509_DEFAULT_STEPS,
                "cfg": QWEN_EDIT_2509_DEFAULT_CFG,
                "size": QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE,
            },
        },
    )
    return job, seed


def _slot_from_job(
    slot: dict[str, Any],
    *,
    job,
    angle: str,
    front_asset_id: str,
    seed: int,
    canon_asset_id: Optional[str],
) -> dict[str, Any]:
    from .cc_v2 import _now

    next_slot = empty_angle()
    next_slot.update(
        {
            "status": "generating" if job.comfy_prompt_id else "queued",
            "jobId": job.id,
            "promptId": job.comfy_prompt_id,
            "workflowKey": QWEN_EDIT_WORKFLOW_KEY,
            "runtime": ENGINE_QWEN_EDIT_2509,
            "engine": ENGINE_QWEN_EDIT_2509,
            "cameraRole": CAMERA_ROLES[angle],
            "sourceFrontAssetId": front_asset_id,
            "modelVersion": QWEN_EDIT_WEIGHTS,
            "seed": seed,
            "generatedAt": _now(),
            "canonAssetId": canon_asset_id,
            "assetId": canon_asset_id,
            "approved": False,
            "rejected": False,
            "source": SOURCE_GENERATED,
            "provenance": {
                "runtime": ENGINE_QWEN_EDIT_2509,
                "cameraRole": CAMERA_ROLES[angle],
                "sourceFrontAssetId": front_asset_id,
                "source": SOURCE_GENERATED,
                "workflowKey": QWEN_EDIT_WORKFLOW_KEY,
                "seed": seed,
                "jobId": job.id,
                "prompt_id": job.comfy_prompt_id,
            },
        }
    )
    return next_slot


def generate_multiview(db, project_id: str, character_id: str) -> dict[str, Any]:
    from .cc_v2 import _active_job_busy, _profile, get_status, save_state

    profile = _profile(db, project_id, character_id)
    state = get_status(db, project_id, character_id)
    busy = _active_job_busy(state)
    if busy:
        raise _err("JOB_ACTIVE", f"Another GPU job is active ({busy}). One heavyweight task at a time.", 409)
    ok, front_id = _front_lock_ok(state)
    if not ok:
        raise _err(
            "FRONT_LOCK_REQUIRED",
            "Generate Character Angles only after Front is approved and Co-Director vision lock is ready.",
            409,
        )
    engine = assert_can_generate()
    mv = merge_multiview(state.get("multiView"))
    pending = []
    for name in MULTIVIEW_ANGLES:
        slot = mv["angles"][name]
        if slot.get("approved") and slot.get("assetId"):
            continue
        if _slot_source(slot) == SOURCE_UPLOADED and slot.get("assetId"):
            continue
        pending.append(name)
    if not pending:
        raise _err(
            "ANGLES_APPROVED",
            "These angles already have pictures. Use Regenerate on an angle to make a new generated version.",
            409,
        )
    protect = {front_id}
    started: list[str] = []
    try:
        for name in pending:
            prior = mv["angles"][name]
            _forget_replaced_candidate(db, project_id, prior, protect=protect)
            job, seed = _enqueue_angle_job(db, project_id, character_id, state, name, front_asset_id=front_id)
            mv["angles"][name] = _slot_from_job(
                prior,
                job=job,
                angle=name,
                front_asset_id=front_id,
                seed=seed,
                canon_asset_id=None,
            )
            started.append(name)
    except Exception:
        if not started:
            raise
        mv["status"] = "failed"
        mv["error"] = "Some Character Angles could not start. The ones that did start are still running."
        mv["engine"] = engine.get("engine") or PRODUCTION_ENGINE
        state["multiView"] = mv
        save_state(db, profile, state)
        db.commit()
        raise
    mv["status"] = "generating"
    mv["engine"] = engine.get("engine") or PRODUCTION_ENGINE
    mv["error"] = None
    mv["pendingReplacement"] = False
    state["multiView"] = mv
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def regenerate_angle(db, project_id: str, character_id: str, angle: str) -> dict[str, Any]:
    from .cc_v2 import _active_job_busy, _profile, get_status, save_state

    if angle not in MULTIVIEW_ANGLES:
        raise _err("INVALID_VIEW", f"Unknown multi-view angle: {angle}")
    profile = _profile(db, project_id, character_id)
    state = get_status(db, project_id, character_id)
    busy = _active_job_busy(state)
    if busy:
        raise _err("JOB_ACTIVE", f"Another GPU job is active ({busy}). One heavyweight task at a time.", 409)
    ok, front_id = _front_lock_ok(state)
    if not ok:
        raise _err(
            "FRONT_LOCK_REQUIRED",
            "Regenerate this angle only after Front is approved and Co-Director vision lock is ready.",
            409,
        )
    assert_can_generate()
    mv = merge_multiview(state.get("multiView"))
    prior = mv["angles"][angle]
    canon = str(prior.get("assetId") or "").strip() or None
    keep_canon = bool(prior.get("approved") and canon)
    if not keep_canon:
        _forget_replaced_candidate(db, project_id, prior, protect={front_id})
        canon = None
    job, seed = _enqueue_angle_job(db, project_id, character_id, state, angle, front_asset_id=front_id)
    mv["angles"][angle] = _slot_from_job(
        prior,
        job=job,
        angle=angle,
        front_asset_id=front_id,
        seed=seed,
        canon_asset_id=canon if keep_canon else None,
    )
    mv["status"] = "generating"
    mv["error"] = None
    state["multiView"] = mv
    state["multiviewEnrichment"] = empty_enrichment()
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def regenerate_multiview(db, project_id: str, character_id: str) -> dict[str, Any]:
    """Start a replacement set without deleting approved canon until replace-approve."""
    from .cc_v2 import _active_job_busy, _profile, get_status, save_state

    profile = _profile(db, project_id, character_id)
    state = get_status(db, project_id, character_id)
    busy = _active_job_busy(state)
    if busy:
        raise _err("JOB_ACTIVE", f"Another GPU job is active ({busy}). One heavyweight task at a time.", 409)
    ok, front_id = _front_lock_ok(state)
    if not ok:
        raise _err(
            "FRONT_LOCK_REQUIRED",
            "Regenerate Character Angles only after Front is approved and Co-Director vision lock is ready.",
            409,
        )
    assert_can_generate()
    mv = merge_multiview(state.get("multiView"))
    mv["pendingReplacement"] = True
    for name in MULTIVIEW_ANGLES:
        prior = mv["angles"][name]
        canon = str(prior.get("assetId") or "").strip() or None
        keep_canon = bool(prior.get("approved") and canon)
        if not keep_canon:
            _forget_replaced_candidate(db, project_id, prior, protect={front_id})
            canon = None
        job, seed = _enqueue_angle_job(db, project_id, character_id, state, name, front_asset_id=front_id)
        mv["angles"][name] = _slot_from_job(
            prior,
            job=job,
            angle=name,
            front_asset_id=front_id,
            seed=seed,
            canon_asset_id=canon if keep_canon else None,
        )
    mv["status"] = "generating"
    mv["error"] = None
    state["multiView"] = mv
    state["multiviewEnrichment"] = empty_enrichment()
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def set_angle_approval(
    db,
    project_id: str,
    character_id: str,
    angle: str,
    *,
    approved: bool,
) -> dict[str, Any]:
    from .cc_v2 import _now, _profile, get_status, save_state

    if angle not in MULTIVIEW_ANGLES:
        raise _err("INVALID_VIEW", f"Unknown multi-view angle: {angle}")
    profile = _profile(db, project_id, character_id)
    state = get_status(db, project_id, character_id)
    mv = merge_multiview(state.get("multiView"))
    slot = mv["angles"][angle]
    front_id = str(state["views"]["front"].get("assetId") or "").strip()
    protect = {front_id} if front_id else set()
    if approved:
        if not slot.get("assetId"):
            raise _err("VIEW_NOT_READY", f"{angle} image is not ready to approve.", 409)
        old_canon = str(slot.get("canonAssetId") or "").strip()
        if old_canon and old_canon != slot.get("assetId"):
            if not _keep_uploaded_history(db, old_canon):
                _forget_asset(db, project_id, old_canon, protect=protect | {str(slot.get("assetId"))})
        slot["approved"] = True
        slot["rejected"] = False
        slot["approvedAt"] = _now()
        slot["canonAssetId"] = None
        slot["status"] = "approved"
        _stale_sheet(state)
    else:
        candidate = str(slot.get("assetId") or "").strip() or None
        canon = str(slot.get("canonAssetId") or "").strip() or None
        if candidate and candidate != canon:
            if not _keep_uploaded_history(db, candidate, slot):
                _forget_asset(db, project_id, candidate, protect=protect | ({canon} if canon else set()))
        if canon:
            slot["assetId"] = canon
            slot["approved"] = True
            slot["rejected"] = False
            slot["approvedAt"] = slot.get("approvedAt") or _now()
            slot["status"] = "approved"
            slot["canonAssetId"] = None
            slot["jobId"] = None
            slot["error"] = None
        else:
            if not _keep_uploaded_history(db, candidate, slot):
                _forget_asset(db, project_id, candidate, protect=protect)
            cleared = empty_angle()
            cleared["cameraRole"] = CAMERA_ROLES[angle]
            cleared["rejected"] = True
            slot = cleared
        _stale_sheet(state)
        state["multiviewEnrichment"] = empty_enrichment()
    mv["angles"][angle] = slot
    if not any(
        str(item.get("status") or "") in {"generating", "queued", "running", "starting"}
        for item in mv["angles"].values()
    ):
        if angles_approved({**state, "multiView": mv}):
            mv["status"] = "ready"
        elif any(item.get("assetId") for item in mv["angles"].values()):
            mv["status"] = "review"
        else:
            mv["status"] = "idle"
    state["multiView"] = mv
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def upscale_angle(db, project_id: str, character_id: str, angle: str) -> dict[str, Any]:
    from .cc_v2 import _active_job_busy, get_status

    if angle not in MULTIVIEW_ANGLES:
        raise _err("INVALID_VIEW", f"Unknown multi-view angle: {angle}")
    state = get_status(db, project_id, character_id)
    busy = _active_job_busy(state)
    if busy:
        raise _err("JOB_ACTIVE", f"Another GPU job is active ({busy}). One heavyweight task at a time.", 409)
    mv = merge_multiview(state.get("multiView"))
    slot = mv["angles"][angle]
    if not slot.get("assetId"):
        raise _err("VIEW_NOT_READY", f"{angle} must exist before upscale.", 409)
    raise _err(
        "UPSCALE_NOT_WIRED",
        "Angle upscale is not wired for the Character Angles engine yet.",
        409,
    )


def hydrate_multiview(db, project_id: str, state: dict[str, Any]) -> dict[str, Any]:
    from .cc_v2 import _hydrate_view

    mv = merge_multiview(state.get("multiView"))
    live = False
    failed = False
    ready_count = 0
    for name, slot in mv["angles"].items():
        hydrated = _hydrate_view(db, project_id, dict(slot), name)
        job_status = str(hydrated.get("status") or "")
        if job_status in {"generating", "queued", "running", "starting"}:
            live = True
            if hydrated.get("canonAssetId") and not hydrated.get("assetUrl"):
                from .cc_v2_media import resolve_character_asset

                canon = resolve_character_asset(db, project_id, hydrated.get("canonAssetId"))
                if canon:
                    hydrated["assetId"] = canon["assetId"]
                    hydrated["assetUrl"] = canon["assetUrl"]
        elif job_status == "failed":
            failed = True
            if hydrated.get("canonAssetId"):
                from .cc_v2_media import resolve_character_asset

                canon = resolve_character_asset(db, project_id, hydrated.get("canonAssetId"))
                if canon:
                    hydrated["assetId"] = canon["assetId"]
                    hydrated["assetUrl"] = canon["assetUrl"]
        elif hydrated.get("assetId"):
            ready_count += 1
            if hydrated.get("approved"):
                hydrated["status"] = "approved"
            if not _slot_source(hydrated):
                inferred = _asset_source(db, hydrated.get("assetId")) or (
                    SOURCE_GENERATED if hydrated.get("jobId") or hydrated.get("workflowKey") else ""
                )
                if inferred:
                    hydrated["source"] = inferred
        mv["angles"][name] = hydrated
    if live:
        mv["status"] = "generating"
        mv["error"] = None
    elif failed and ready_count < 3:
        mv["status"] = "failed"
        mv["error"] = next(
            (str(item.get("error") or "") for item in mv["angles"].values() if item.get("error")),
            "Character Angles failed.",
        )
    elif ready_count == 3:
        mv["status"] = "ready" if angles_approved({**state, "multiView": mv}) else "review"
        mv["error"] = None
    elif ready_count:
        mv["status"] = "review"
    else:
        mv["status"] = "idle" if not mv.get("error") else mv.get("status") or "idle"
    mv["engine"] = PRODUCTION_ENGINE
    state["multiView"] = mv
    return state


async def enrich_multiview_canon(db, project_id: str, character_id: str) -> dict[str, Any]:
    from .cc_v2 import (
        USER_PROTECTED_FIELDS,
        _asset_path,
        _merge_evidenced,
        _now,
        _profile,
        _run_vision,
        get_status,
        save_state,
    )

    profile = _profile(db, project_id, character_id)
    state = get_status(db, project_id, character_id)
    if not angles_approved(state):
        raise _err("VIEWS_REQUIRED", "Side, 3/4, and Back must be approved before multi-view details.", 409)
    front_id = str(state["views"]["front"].get("assetId") or "")
    mv = merge_multiview(state.get("multiView"))
    paths = [_asset_path(db, project_id, front_id)]
    for name in MULTIVIEW_ANGLES:
        paths.append(_asset_path(db, project_id, str(mv["angles"][name]["assetId"])))
    result = await _run_vision(paths, MULTIVIEW_VISION_INSTRUCTIONS)
    if not result.get("ok"):
        state["multiviewEnrichment"] = {
            "status": "failed",
            "facts": {},
            "provenance": None,
            "error": result.get("error") or "vision_failed",
            "at": _now(),
        }
        save_state(db, profile, state)
        db.commit()
        raise _err(
            "VISION_UNAVAILABLE",
            str(result.get("error") or "Co-Director could not read the multi-view set."),
            409,
        )
    cleaned = {
        k: v
        for k, v in (result.get("facts") or {}).items()
        if k not in USER_PROTECTED_FIELDS
    }
    _merge_evidenced(profile, cleaned)
    state["multiviewEnrichment"] = {
        "status": "ok",
        "facts": cleaned,
        "provenance": "CONFIRMED_BY_MULTIVIEW",
        "error": None,
        "at": _now(),
    }
    state["revision2"] = {
        "status": "ok",
        "facts": cleaned,
        "error": None,
        "at": _now(),
        "stage": "ready",
        "provenance": "CONFIRMED_BY_MULTIVIEW",
    }
    state["jsonRevision"] = max(int(state.get("jsonRevision") or 1), 2)
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def engine_payload() -> dict[str, Any]:
    return production_engine_status()
