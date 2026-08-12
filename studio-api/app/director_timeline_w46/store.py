"""Persist Timeline Master state inside scenes.director_json.timelineMaster (COW)."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db import Scene
from ..director_timeline import dumps_director_timeline, parse_director_timeline
from .contracts import SceneTimelineMaster, _now
from .migration import embed_master_into_director_dict, load_or_migrate_scene_master

DEFAULT_TIMELINE_SETTINGS: dict[str, Any] = {
    "trackDensity": "comfortable",
    "displayMode": "seconds",
    "showFilenames": True,
    "showThumbnails": True,
    "snapEnabled": True,
}

DEFAULT_GUIDANCE_PRIORITY = "visual_first"

OPTIONAL_REFS_POLICY_NOTE = (
    "Supporting references are optional and never block generation unless the selected "
    "generator technically requires them."
)


def normalize_timeline_workspace(raw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "settings": dict(DEFAULT_TIMELINE_SETTINGS),
        "guidancePriority": DEFAULT_GUIDANCE_PRIORITY,
        "timelineRevision": 1,
        "removedItems": [],
        "layoutIntent": {},
        "inpaintIntent": {},
    }
    if not isinstance(raw, dict):
        return base
    if isinstance(raw.get("settings"), dict):
        base["settings"] = {**base["settings"], **raw["settings"]}
    if raw.get("guidancePriority"):
        base["guidancePriority"] = str(raw["guidancePriority"])
    if raw.get("timelineRevision") is not None:
        try:
            base["timelineRevision"] = max(1, int(raw["timelineRevision"]))
        except (TypeError, ValueError):
            pass
    if isinstance(raw.get("removedItems"), list):
        base["removedItems"] = list(raw["removedItems"])
    if isinstance(raw.get("layoutIntent"), dict):
        base["layoutIntent"] = dict(raw["layoutIntent"])
    if isinstance(raw.get("inpaintIntent"), dict):
        base["inpaintIntent"] = dict(raw["inpaintIntent"])
    return base


def extract_timeline_workspace(director_raw: str | None) -> dict[str, Any]:
    if not director_raw or not str(director_raw).strip():
        return normalize_timeline_workspace(None)
    try:
        data = json.loads(director_raw)
        if isinstance(data, dict):
            return normalize_timeline_workspace(data.get("timelineWorkspace"))
    except Exception:
        pass
    return normalize_timeline_workspace(None)


def get_scene(db: Session, project_id: str, scene_id: str) -> Scene | None:
    return (
        db.query(Scene)
        .filter(Scene.project_id == project_id, Scene.id == scene_id)
        .one_or_none()
    )


def load_master(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}
    master, tl, data = load_or_migrate_scene_master(
        scene.director_json,
        scene_id=scene_id,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )
    # NO_AUTO_PERSIST_ON_READ: only persist when migration actually created
    # new master state that is not already present in the blob. Previously
    # every GET /master re-saved the blob, which (after a legacy PUT had wiped
    # timelineMaster) cemented a collapsed single-Batch-1 migration. Now we
    # only persist if the blob has no embedded timelineMaster at all.
    existing_master = data.get("timelineMaster") if isinstance(data, dict) else None
    if not existing_master:
        save_master(db, project_id, scene_id, master, director_tl=tl)
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "master": master.model_dump(),
        "legacyMediaMode": tl.media_mode,
        "mock": False,
    }


def save_master(
    db: Session,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster,
    *,
    director_tl=None,
    workspace: dict[str, Any] | None = None,
    bump_revision: bool = False,
    touch_batches: bool = True,
) -> SceneTimelineMaster:
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        raise ValueError("SCENE_NOT_FOUND")
    if director_tl is None:
        director_tl = parse_director_timeline(
            scene.director_json,
            fallback_duration=float(scene.duration_sec or 5.0),
            fallback_prompt=scene.prompt or "",
        )
    base = json.loads(dumps_director_timeline(director_tl))
    raw: dict[str, Any] = {}
    try:
        parsed = json.loads(scene.director_json or "{}")
        if isinstance(parsed, dict):
            raw = parsed
            for k, v in raw.items():
                if k not in base and k not in ("timelineMaster", "timelineWorkspace"):
                    base[k] = v
    except Exception:
        pass
    ws = normalize_timeline_workspace(workspace if workspace is not None else raw.get("timelineWorkspace"))
    if bump_revision:
        ws["timelineRevision"] = int(ws.get("timelineRevision") or 0) + 1
    base["timelineWorkspace"] = ws
    if touch_batches:
        for batch in master.batchBlocks:
            batch.updatedAt = _now()
    embedded = embed_master_into_director_dict(base, master)
    scene.director_json = json.dumps(embedded)
    db.add(scene)
    db.commit()
    return master


def stash_removed_item(workspace: dict[str, Any], *, kind: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ws = normalize_timeline_workspace(workspace)
    entry = {
        "id": f"rm_{uuid4().hex[:10]}",
        "kind": kind,
        "itemId": item_id,
        "payload": payload,
        "removedAt": _now(),
    }
    ws["removedItems"] = list(ws.get("removedItems") or []) + [entry]
    return ws


def replace_master(db: Session, project_id: str, scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}
    master = SceneTimelineMaster.model_validate(payload)
    save_master(db, project_id, scene_id, master)
    return {"ok": True, "master": master.model_dump(), "mock": False}
