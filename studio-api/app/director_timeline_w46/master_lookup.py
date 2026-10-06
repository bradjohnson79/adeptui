"""Master-owned clip lookup. Product runtime must not parse leftover DirectorTimeline."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .contracts import BatchClip, SceneTimelineMaster
from .store import load_master


def load_scene_master(db: Session, project_id: str, scene_id: str) -> Optional[SceneTimelineMaster]:
    payload = load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return None
    raw = payload.get("master")
    if isinstance(raw, SceneTimelineMaster):
        return raw
    if isinstance(raw, dict):
        return SceneTimelineMaster.model_validate(raw)
    return None


def iter_master_visual_clips(master: Any) -> list[tuple[Any, BatchClip]]:
    out: list[tuple[Any, BatchClip]] = []
    for batch in getattr(master, "batchBlocks", None) or []:
        for clip in getattr(batch, "visualClips", None) or []:
            out.append((batch, clip))
    return out


def find_master_visual_clip(master: Any, item_id: str) -> Optional[BatchClip]:
    token = str(item_id or "").strip()
    if not token:
        return None
    for _batch, clip in iter_master_visual_clips(master):
        if str(clip.id) == token or str(getattr(clip, "legacyClipId", "") or "") == token:
            return clip
    return None


def find_master_visual_by_tag(master: Any, tag: str) -> Optional[BatchClip]:
    needle = str(tag or "").strip().lstrip("@").lower()
    if not needle:
        return None
    for _batch, clip in iter_master_visual_clips(master):
        label = str(getattr(clip, "label", "") or "").strip().lstrip("@").lower()
        cid = str(clip.id).strip().lstrip("@").lower()
        if needle in {label, cid}:
            return clip
    return None


def visual_clip_public(clip: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(clip, "id", "") or ""),
        "displayTag": str(getattr(clip, "label", "") or getattr(clip, "id", "") or ""),
        "assetId": getattr(clip, "assetId", None),
        "start": float(getattr(clip, "start", 0.0) or 0.0),
        "length": float(getattr(clip, "length", 0.0) or 0.0),
    }
