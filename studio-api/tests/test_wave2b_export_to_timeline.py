"""Wave 2B — 1F/3F Export completed VIDEO → Timeline Visual deposit."""
from __future__ import annotations

import uuid

from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.director_timeline import parse_director_timeline
from app.director_timeline_w46.generation.omni_visual_export import (
    OMNI_EXPORT_CLIP_PREFIX,
    export_completed_video_to_timeline,
)


def _db():
    init_db()
    return SessionLocal()


def _seed_scene_with_video(*, kind: str = "video"):
    db = _db()
    project_id = str(uuid.uuid4())
    scene_id = f"scene_{uuid.uuid4().hex[:10]}"
    asset_id = str(uuid.uuid4())
    db.add(Project(id=project_id, name="Wave2B Export"))
    db.add(
        Scene(
            id=scene_id,
            project_id=project_id,
            name="Export Scene",
            duration_sec=8.0,
            prompt="unused",
        )
    )
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="1f-take",
            kind=kind,
            filename="take.mp4" if kind == "video" else "still.png",
            path="take.mp4" if kind == "video" else "still.png",
            production_approval="none",
        )
    )
    db.commit()
    return db, project_id, scene_id, asset_id


def test_wave2b_export_video_to_visual_deposit():
    db, project_id, scene_id, asset_id = _seed_scene_with_video(kind="video")
    try:
        result = export_completed_video_to_timeline(
            db,
            project_id,
            scene_id,
            asset_id,
            label="1F take",
            source_surface="one-frame",
        )
        assert result.get("ok") is True
        assert result.get("mediaType") == "video"
        assert result.get("mediaMode") == "video"
        assert str(result.get("visualClipId") or "").startswith(OMNI_EXPORT_CLIP_PREFIX)
        assert result.get("w46", {}).get("ok") is True

        scene = db.get(Scene, scene_id)
        tl = parse_director_timeline(scene.director_json, fallback_duration=8.0)
        assert tl.media_mode == "video"
        assert any(c.asset_id == asset_id for c in tl.video_clips)
        assert all(getattr(c, "role", None) != "guide" for c in tl.video_clips)
    finally:
        db.close()


def test_wave2b_rejects_image_as_visual_media():
    db, project_id, scene_id, asset_id = _seed_scene_with_video(kind="image")
    try:
        result = export_completed_video_to_timeline(
            db,
            project_id,
            scene_id,
            asset_id,
            source_surface="three-frame",
        )
        assert result.get("ok") is False
        assert result.get("error") == "VIDEO_REQUIRED"
    finally:
        db.close()


def test_wave2b_export_endpoint_via_client(client):
    db, project_id, scene_id, asset_id = _seed_scene_with_video(kind="video")
    db.close()
    res = client.post(
        f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/export-video-to-timeline",
        json={"assetId": asset_id, "label": "3F take", "sourceSurface": "three-frame"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["mediaType"] == "video"
    assert body["visualClipId"].startswith(OMNI_EXPORT_CLIP_PREFIX)
