"""Close-up is a portrait crop of the approved Front View.

Standard and Express both call this. It does not generate a new full-body picture.
Qwen Edit runs only when the cropped face is too small to use as a reference.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy.orm import Session

PORTRAIT_W = 768
PORTRAIT_H = 1024
MIN_FACE_PX = 320
QWEN_PROMPT = (
    "Reframe this picture as a portrait of the same person. "
    "Show the head, face, hair, and neck, with a small amount of shoulder. "
    "Do not show the body below the upper chest. "
    "Do not redesign the face, hair, clothing, or identity."
)


def _clamp_box(left: float, top: float, right: float, bottom: float, width: int, height: int) -> tuple[int, int, int, int]:
    l = int(max(0, min(width - 2, left)))
    t = int(max(0, min(height - 2, top)))
    r = int(max(l + 2, min(width, right)))
    b = int(max(t + 2, min(height, bottom)))
    return l, t, r, b


def _portrait_around(left: float, top: float, right: float, bottom: float, width: int, height: int, anchor_x: float) -> tuple[int, int, int, int]:
    """Keep a 3:4 window so the portrait canvas is filled instead of letterboxed."""

    box_h = max(8.0, bottom - top)
    box_w = box_h * (PORTRAIT_W / PORTRAIT_H)
    left = anchor_x - box_w / 2
    right = anchor_x + box_w / 2
    return _clamp_box(left, top, right, top + box_h, width, height)


def _source_window(image: Image.Image, face: dict[str, float] | None) -> tuple[tuple[int, int, int, int], bool]:
    width, height = image.size
    if not face:
        if width > height * 1.15:
            top = height * 0.02
            bottom = height * 0.62
        else:
            top = 0
            bottom = height * 0.46
        return _portrait_around(0, top, width, bottom, width, height, width / 2), False
    x = float(face["x"]) * width
    y = float(face["y"]) * height
    fw = max(8.0, float(face["w"]) * width)
    fh = max(8.0, float(face["h"]) * height)
    center = x + fw / 2
    top = y - fh * 0.85
    bottom = y + fh + fh * 0.7
    box = _portrait_around(center - fw, top, center + fw, bottom, width, height, center)
    return box, fh < MIN_FACE_PX


def render_closeup_png(front_path: Path) -> tuple[bytes, bool]:
    """Return portrait PNG bytes and whether the face needs a sharper reframe."""

    from ..mouth_tracker import detect_face_rois_in_image

    with Image.open(front_path) as source:
        image = source.convert("RGB")
    face = None
    try:
        found = detect_face_rois_in_image(front_path, max_faces=1)
    except Exception:
        found = []
    if found:
        bbox = (found[0].get("bbox") or {}) if isinstance(found[0], dict) else {}
        if {"x", "y", "w", "h"} <= set(bbox):
            face = {key: float(bbox[key]) for key in ("x", "y", "w", "h")}
    box, needs_qwen = _source_window(image, face)
    crop = image.crop(box)
    canvas = Image.new("RGB", (PORTRAIT_W, PORTRAIT_H), crop.getpixel((0, 0)))
    scale = min(PORTRAIT_W / crop.width, PORTRAIT_H / crop.height)
    fitted = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
    canvas.paste(fitted, ((PORTRAIT_W - fitted.width) // 2, (PORTRAIT_H - fitted.height) // 2))
    handle, raw_path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    path = Path(raw_path)
    try:
        canvas.save(path, format="PNG")
        return path.read_bytes(), needs_qwen
    finally:
        path.unlink(missing_ok=True)


def generate_closeup_from_front(db: Session, project_id: str, character_id: str, profile, state: dict[str, Any]) -> dict[str, Any]:
    from ..generation_tools.lineage import register_derived_asset
    from .cc_v2 import VIEW_ROLES, _asset_path, _err, empty_view, get_status, save_state

    front_id = str((state.get("views") or {}).get("front", {}).get("assetId") or "").strip()
    if not front_id:
        raise _err("FRONT_REQUIRED", "Create Close-up from an approved Front View.", 409)
    front_path = _asset_path(db, project_id, front_id)
    png, needs_qwen = render_closeup_png(front_path)
    handle, raw_path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    crop_path = Path(raw_path)
    crop_path.write_bytes(png)
    try:
        crop_asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=crop_path,
            kind="image",
            tag="character_closeup",
            parent_asset_id=front_id,
            op="closeup_crop",
            model="front_view_crop",
            prompt_meta={"characterId": character_id, "view": "closeup", "source": "front"},
            filename=f"closeup_{character_id[:8]}_{os.urandom(4).hex()}.png",
        )
    finally:
        crop_path.unlink(missing_ok=True)

    if not needs_qwen:
        state["views"]["closeup"] = {
            **empty_view(),
            "status": "ready",
            "assetId": crop_asset.id,
            "generator": "front_view_crop",
            "approved": False,
        }
        state["activeJobView"] = None
        save_state(db, profile, state)
        db.commit()
        return get_status(db, project_id, character_id)

    from .visual_sheet import QWEN_EDIT_2509_FAMILY, QWEN_EDIT_2509_WORKFLOW_KEY, _enqueue_txt2img

    job = _enqueue_txt2img(
        db,
        project_id,
        character_id=character_id,
        prompt=QWEN_PROMPT,
        negative_prompt="full body, waist, legs, redesigned face, different person, collage, text",
        tag=f"closeup_{character_id[:8]}",
        role=VIEW_ROLES["closeup"],
        model_family_preference=QWEN_EDIT_2509_FAMILY,
        source_asset_id=crop_asset.id,
        force_workflow_key=QWEN_EDIT_2509_WORKFLOW_KEY,
        provider_kind="local",
        width=PORTRAIT_W,
        height=PORTRAIT_H,
        prompt_metadata={
            "ccV2": True,
            "characterId": character_id,
            "view": "closeup",
            "workflowKey": QWEN_EDIT_2509_WORKFLOW_KEY,
            "referenceAssetId": crop_asset.id,
            "sourceFrontAssetId": front_id,
        },
    )
    state["views"]["closeup"] = {
        **empty_view(),
        "status": "generating" if job.comfy_prompt_id else "queued",
        "jobId": job.id,
        "promptId": job.comfy_prompt_id,
        "workflowKey": QWEN_EDIT_2509_WORKFLOW_KEY,
        "generator": QWEN_EDIT_2509_FAMILY,
        "approved": False,
    }
    state["activeJobView"] = "closeup"
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)
