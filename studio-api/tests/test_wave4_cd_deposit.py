"""Wave 4 — Co-Director deposit completed 1F/3F video → Timeline Visual."""
from __future__ import annotations

import uuid

from app.codirector.capabilities.handlers import timeline_deposit_video as deposit
from app.codirector.capabilities.registry import get_capability
from app.codirector.routing.unified_intent import classify_intent
from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.director_timeline import parse_director_timeline
from app.director_timeline_w46.generation.omni_visual_export import OMNI_EXPORT_CLIP_PREFIX


def _db():
    init_db()
    return SessionLocal()


def _seed(*, kind: str = "video", tag: str = "one-frame-take"):
    db = _db()
    project_id = str(uuid.uuid4())
    scene_id = f"scene_{uuid.uuid4().hex[:10]}"
    asset_id = str(uuid.uuid4())
    db.add(Project(id=project_id, name="Wave4 CD Deposit"))
    db.add(
        Scene(
            id=scene_id,
            project_id=project_id,
            name="Deposit Scene",
            duration_sec=8.0,
            prompt="unused",
        )
    )
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag=tag,
            kind=kind,
            filename="take.mp4" if kind == "video" else "still.png",
            path="take.mp4" if kind == "video" else "still.png",
            production_approval="none",
        )
    )
    db.commit()
    return db, project_id, scene_id, asset_id


def test_wave4_capability_registered_and_live():
    cap = get_capability("timeline.deposit_video")
    assert cap is not None
    assert cap.handler_kind.value == "capability_handler"
    assert cap.surface_type == "timeline_deposit"
    assert callable(deposit.handle)


def test_wave4_cd_deposit_video_to_visual():
    db, project_id, scene_id, asset_id = _seed(kind="video", tag="three-frame-take")
    try:
        result = deposit.handle(
            db,
            project_id,
            execution_id="exec-wave4",
            prompt="deposit the completed 3 frame video to timeline visual",
            attachment_asset_ids=[asset_id],
            scene_id=scene_id,
            source_surface="three-frame",
        )
        assert result.get("status") == "completed"
        assert not result.get("error")
        plan = result.get("plan_data") or {}
        assert plan.get("mediaType") == "video"
        assert plan.get("mediaMode") == "video"
        assert plan.get("regenerated") is False
        deposit_body = plan.get("deposit") or {}
        assert deposit_body.get("ok") is True
        assert deposit_body.get("mediaType") == "video"
        assert str(deposit_body.get("visualClipId") or "").startswith(OMNI_EXPORT_CLIP_PREFIX)

        scene = db.get(Scene, scene_id)
        tl = parse_director_timeline(scene.director_json, fallback_duration=8.0)
        assert tl.media_mode == "video"
        assert any(c.asset_id == asset_id for c in tl.video_clips)
        clip = next(c for c in tl.video_clips if c.asset_id == asset_id)
        assert (getattr(clip, "media_type", None) or getattr(clip, "mediaType", None)) == "video"
    finally:
        db.close()


def test_wave4_cd_rejects_image_deposit():
    db, project_id, scene_id, asset_id = _seed(kind="image", tag="still")
    try:
        result = deposit.handle(
            db,
            project_id,
            execution_id="exec-wave4-img",
            prompt="send this to timeline visual",
            attachment_asset_ids=[asset_id],
            scene_id=scene_id,
        )
        assert result.get("status") == "failed"
        assert result.get("errorCode") == "VIDEO_REQUIRED" or "video only" in str(result.get("error") or "").lower()
    finally:
        db.close()


def test_wave4_cd_requires_scene():
    db, project_id, _scene_id, asset_id = _seed(kind="video")
    try:
        result = deposit.handle(
            db,
            project_id,
            execution_id="exec-wave4-noscene",
            prompt="deposit completed one frame video",
            attachment_asset_ids=[asset_id],
            scene_id="",
        )
        assert result.get("status") == "failed"
        assert "scene" in str(result.get("error") or "").lower()
    finally:
        db.close()


def test_wave4_unified_intent_routes_deposit():
    intent = classify_intent("deposit the completed 1 frame video to timeline visual")
    assert intent.capability == "timeline.deposit_video"
    intent2 = classify_intent("send the completed three-frame video to Timeline Visual")
    assert intent2.capability == "timeline.deposit_video"


def test_wave4_export_endpoint_still_works(client):
    db, project_id, scene_id, asset_id = _seed(kind="video", tag="one-frame")
    db.close()
    res = client.post(
        f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/export-video-to-timeline",
        json={"assetId": asset_id, "label": "CD Wave4", "sourceSurface": "one-frame"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["mediaType"] == "video"
