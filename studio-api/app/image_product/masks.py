"""Mask asset persistence (M42 W4)."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .store import project_dir, read_json, write_json

_MASKS_INDEX = "masks_index.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _masks_dir(project_id: str) -> Path:
    d = project_dir(project_id) / "masks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _checksum(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _load_index(project_id: str) -> dict[str, Any]:
    return read_json(project_id, _MASKS_INDEX, {"masks": []})


def _save_index(project_id: str, data: dict[str, Any]) -> None:
    write_json(project_id, _MASKS_INDEX, data)


def save_mask(
    project_id: str,
    *,
    source_asset_id: str,
    png_bytes: bytes | None = None,
    png_base64: str | None = None,
    path: str | None = None,
    role: str = "include",
    dimensions: dict[str, int] | None = None,
    creator: str = "user",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save mask PNG under data/image_product/{projectId}/masks/."""
    mask_id = f"mask-{uuid4().hex[:12]}"
    raw: bytes
    if png_bytes is not None:
        raw = png_bytes
    elif png_base64:
        b64 = png_base64.split(",", 1)[-1] if "," in png_base64 else png_base64
        raw = base64.b64decode(b64)
    elif path:
        raw = Path(path).read_bytes()
    else:
        raise ValueError("png_bytes, png_base64, or path required")

    checksum = _checksum(raw)
    filename = f"{mask_id}.png"
    out_path = _masks_dir(project_id) / filename
    out_path.write_bytes(raw)

    meta_path = _masks_dir(project_id) / f"{mask_id}.json"
    record = {
        "maskId": mask_id,
        "projectId": project_id,
        "sourceAssetId": source_asset_id,
        "filename": filename,
        "path": str(out_path),
        "checksum": checksum,
        "dimensions": dimensions or {},
        "role": role,
        "creator": creator,
        "createdAt": _now(),
        "modifiedAt": _now(),
        "metadata": dict(metadata or {}),
    }
    meta_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    idx = _load_index(project_id)
    idx.setdefault("masks", []).append(
        {k: record[k] for k in record if k != "path" or True}
    )
    _save_index(project_id, idx)
    return record


def list_masks(project_id: str, *, source_asset_id: str | None = None) -> list[dict[str, Any]]:
    idx = _load_index(project_id)
    masks = list(idx.get("masks") or [])
    if source_asset_id:
        masks = [m for m in masks if m.get("sourceAssetId") == source_asset_id]
    return masks


def get_mask(project_id: str, mask_id: str) -> dict[str, Any] | None:
    for m in list_masks(project_id):
        if m.get("maskId") == mask_id:
            meta_path = _masks_dir(project_id) / f"{mask_id}.json"
            if meta_path.is_file():
                try:
                    return json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    return m
            return m
    return None


def get_mask_path(project_id: str, mask_id: str) -> str | None:
    """Return filesystem path to mask PNG if present."""
    rec = get_mask(project_id, mask_id)
    if rec and rec.get("path") and Path(rec["path"]).is_file():
        return str(rec["path"])
    png = _masks_dir(project_id) / f"{mask_id}.png"
    return str(png) if png.is_file() else None


def delete_mask(project_id: str, mask_id: str) -> bool:
    idx = _load_index(project_id)
    before = len(idx.get("masks") or [])
    idx["masks"] = [m for m in (idx.get("masks") or []) if m.get("maskId") != mask_id]
    _save_index(project_id, idx)

    png = _masks_dir(project_id) / f"{mask_id}.png"
    meta = _masks_dir(project_id) / f"{mask_id}.json"
    if png.is_file():
        png.unlink()
    if meta.is_file():
        meta.unlink()
    return len(idx["masks"]) < before


def verify_mask_checksum(project_id: str, mask_id: str) -> bool:
    rec = get_mask(project_id, mask_id)
    if not rec:
        return False
    png = _masks_dir(project_id) / f"{mask_id}.png"
    if not png.is_file():
        return False
    return _checksum(png.read_bytes()) == rec.get("checksum")
