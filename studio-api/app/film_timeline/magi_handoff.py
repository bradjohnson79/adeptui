"""Send to MAGI is allowed only for the current published stitch."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .publish_media import ready_stitch_id
from .store import require_film

UNPUBLISHED_MESSAGE = "Your scene must be published before it can be sent to MAGI."
STALE_MESSAGE = "Update Published before this scene can be sent to MAGI."


def film_magi_handoff(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    shot_id: str | None = None,
) -> dict[str, Any]:
    film = require_film(db, project_id, scene_id)
    stitch_id = ready_stitch_id(film, shot_id)
    published = str(film.publishedAssetId or "").strip()
    source = str(film.publishedSourceAssetId or "").strip()
    if not published:
        return {
            "ok": False,
            "state": "unpublished",
            "message": UNPUBLISHED_MESSAGE,
            "canSend": False,
            "canPublish": bool(stitch_id),
            "canUpdate": False,
        }
    if not stitch_id or stitch_id != source:
        return {
            "ok": False,
            "state": "stale",
            "message": STALE_MESSAGE,
            "canSend": False,
            "canPublish": False,
            "canUpdate": True,
            "publishedAssetId": published,
        }
    return {
        "ok": True,
        "state": "current",
        "message": "",
        "canSend": True,
        "canPublish": False,
        "canUpdate": False,
        "publishedAssetId": published,
        "publishedSourceAssetId": source,
        "uiAction": "open_magi",
        "workspaceUrl": f"/project/{project_id}?workspace=magi&sceneId={scene_id}",
        "sceneId": scene_id,
        "projectId": project_id,
    }
