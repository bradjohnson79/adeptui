"""Prop view upload — Library ingest for Basic identity + Advanced primary/angles.

Uploaded and generated views share one PropEntity. Upload creates a candidate
(source=uploaded). Approve moves the canonical pointer. Does not mint a new %tag.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..db import Asset

SOURCE_GENERATED = "generated"
SOURCE_UPLOADED = "uploaded"
PROP_VIEW_ROLE = "prop_view"

VIEW_LABELS = {
    "primary": "Primary",
    "front": "Front",
    "back": "Back",
    "left": "Left",
    "right": "Right",
    "top": "Top",
    "bottom": "Bottom",
    "hero": "Hero",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
_MIN_DIM = 32
_MAX_DIM = 16384


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def view_library_title(prop_name: str, view: str) -> str:
    name = str(prop_name or "").strip() or "Prop"
    return f"{name} — {VIEW_LABELS.get(view, view.title())}"


def validate_prop_image_bytes(data: bytes, *, filename: str = "", content_type: str = "") -> dict[str, Any]:
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
        raise _err("IMAGE_TOO_SMALL", "That picture is too small to use as a prop view.")
    if width > _MAX_DIM or height > _MAX_DIM:
        raise _err("IMAGE_TOO_LARGE", "That picture is too large to use as a prop view.")
    return {"width": width, "height": height, "format": fmt or ext.lstrip(".").upper()}


def _parse_json(raw: Any, fallback: Any) -> Any:
    if raw is None or raw == "":
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _asset_prompt_meta(asset: Asset) -> dict[str, Any]:
    meta = _parse_json(getattr(asset, "prompt_meta_json", None), {})
    return meta if isinstance(meta, dict) else {}


def write_prop_image_asset(
    db,
    *,
    project_id: str,
    prop_id: str,
    prop_name: str,
    view: str,
    data: bytes,
    filename: str = "",
    content_type: str = "",
    source: str = SOURCE_UPLOADED,
) -> Asset:
    info = validate_prop_image_bytes(data, filename=filename, content_type=content_type)
    ext = Path(filename or "").suffix.lower()
    if ext not in _IMAGE_EXTS:
        fmt = str(info.get("format") or "PNG").lower()
        ext = ".jpg" if fmt in {"jpeg", "jpg"} else f".{fmt}" if fmt else ".png"
        if ext not in _IMAGE_EXTS:
            ext = ".png"
    from ..config import settings

    asset_id = str(uuid.uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}{ext}"
    dest.write_bytes(data)
    title = view_library_title(prop_name, view)
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
    stamp_prop_view_asset(
        db,
        asset,
        project_id=project_id,
        prop_id=prop_id,
        prop_name=prop_name,
        view=view,
        source=source,
    )
    try:
        content_hash = hashlib.sha256(data).hexdigest()
        from ..project_library.service import find_duplicates_by_hash, mark_duplicate

        duplicates = [a for a in find_duplicates_by_hash(db, project_id, content_hash) if a.id != asset.id]
        if duplicates:
            mark_duplicate(db, asset, duplicates[0].id)
    except Exception:
        pass
    return asset


def stamp_prop_view_asset(
    db,
    asset: Asset,
    *,
    project_id: str,
    prop_id: str,
    prop_name: str,
    view: str,
    source: str,
) -> None:
    now = _now()
    meta = _asset_prompt_meta(asset)
    created = str(meta.get("createdAt") or getattr(asset, "created_at", "") or now)
    if hasattr(created, "strftime"):
        created = created.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta.update(
        {
            "assetId": asset.id,
            "projectId": project_id,
            "propId": prop_id,
            "propName": prop_name,
            "assetType": "image",
            "role": PROP_VIEW_ROLE,
            "view": view,
            "source": source,
            "createdAt": str(created or now),
            "updatedAt": now,
        }
    )
    labels = _parse_json(getattr(asset, "labels_json", None), [])
    if not isinstance(labels, list):
        labels = []
    for item in (PROP_VIEW_ROLE, view, source):
        if item and item not in labels:
            labels.append(item)
    asset.kind = "image"
    asset.labels_json = json.dumps(labels)
    asset.prompt_meta_json = json.dumps(meta, ensure_ascii=False)
    title = view_library_title(prop_name, view)
    current = str(asset.tag or "").strip()
    if not current or current.startswith(str(prop_id)[:8]) or current.lower() in {"prop", "image", "upload"}:
        asset.tag = title[:64]
    try:
        from ..project_library.service import assign_asset

        folder = "props.generated" if source == SOURCE_GENERATED else "props.references"
        assign_asset(
            db,
            asset,
            entity_type="prop",
            entity_name=prop_name,
            entity_id=prop_id,
            classified_by="prop_view",
            hints={"systemKey": folder, "role": PROP_VIEW_ROLE, "view": view, "source": source},
        )
    except Exception:
        pass
