"""Tests for the analyze.video capability handler.

The handler resolves a scene's playable video, runs Media Intelligence, and
returns a creator-facing summary with counts of contact/cue/music opportunities.
GPU / perception is monkeypatched so these tests do not touch ComfyUI or Qwen.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.codirector.capabilities.handlers import analyze_video
from app.codirector.capabilities.registry import get_capability
from app.codirector.video_intelligence import media_analyze, media_persist
from app.db import Asset, Project, Scene, SessionLocal, init_db


def _fake_qwen_payload() -> dict:
    return {
        "parseOk": True,
        "summary": "A tester walks left to right across a steel corridor while a door slams shut.",
        "visualEvents": [{"startTime": 0.0, "endTime": 2.0, "label": "person walks", "phase": "early"}],
        "audioEvents": [{"startTime": 1.8, "endTime": 2.1, "eventType": "door slam", "presentInAudio": True}],
        "speechSegments": [],
        "motionEvents": [{"startTime": 0.0, "endTime": 2.0, "subject": "character", "motionType": "walk"}],
        "contactEvents": [
            {"startTime": 0.12, "endTime": 0.12, "characterLabel": "Korri", "foot": "right", "surface": "steel"},
            {"startTime": 0.65, "endTime": 0.65, "characterLabel": "Korri", "foot": "left", "surface": "steel"},
            {"startTime": 1.18, "endTime": 1.18, "characterLabel": "Korri", "foot": "right", "surface": "steel"},
        ],
        "cueOpportunities": [
            {"startTime": 1.7, "endTime": 2.2, "kind": "door", "label": "door slam", "presentInAudio": True}
        ],
        "musicOpportunities": [{"startTime": 0.0, "endTime": 5.0, "role": "bed", "duckUnderDialogue": True}],
        "confidence": 0.92,
    }


def test_analyze_video_capability_is_registered() -> None:
    cap = get_capability("analyze.video")
    assert cap is not None
    assert cap.handler_kind.value == "capability_handler"
    assert cap.surface_type == "media_intelligence"


def test_handler_returns_creator_ack_with_counts(tmp_path, monkeypatch) -> None:
    init_db()
    monkeypatch.setattr(media_analyze, "perception_mode", lambda: "stub")
    monkeypatch.setattr(media_analyze, "comfy_generation_active", lambda: {"active": False, "running": 0, "pending": 0})
    monkeypatch.setattr(media_analyze, "best_effort_free_generator", lambda: {"comfyFreeRequested": True})
    monkeypatch.setattr(media_analyze, "preflight_for_review", lambda *, min_gb: {"ok": True, "freeVramGb": 31.0, "reason": None})
    monkeypatch.setattr(media_analyze, "run_av_perception", lambda *a, **k: _fake_qwen_payload())

    project_id = f"proj-{uuid.uuid4().hex[:10]}"
    scene_id = f"scene-{uuid.uuid4().hex[:10]}"
    video_id = str(uuid.uuid4())
    video_path = tmp_path / "scene.mp4"
    video_path.write_bytes(b"not-a-real-mp4")

    session = SessionLocal()
    try:
        session.merge(Project(id=project_id, name="Analyze Video Test"))
        session.merge(
            Scene(
                id=scene_id,
                project_id=project_id,
                index=0,
                name="Corridor Walk",
                prompt="Korri walks the corridor",
                duration_sec=5.0,
                director_json='{"timelineMaster": {"sceneStitch": {"assetId": "' + video_id + '"}}}',
            )
        )
        session.merge(
            Asset(
                id=video_id,
                project_id=project_id,
                tag="scene_stitch",
                kind="video",
                filename="scene.mp4",
                path=str(video_path),
            )
        )
        session.commit()

        result = analyze_video.handle(
            session,
            project_id,
            "exec-analyze-video",
            prompt="Watch this clip and tell me what you see.",
            scene_id=scene_id,
            playhead_sec=0.0,
        )
        assert result.get("error") in (None, "")
        assert result["status"] == "completed"
        assert result["surface_type"] == "media_intelligence"
        assert result["result_asset_ids"] == [video_id]

        ack = result["creatorAck"]
        assert "3 contact event(s)" in ack
        assert "1 cue opportunity(s)" in ack
        assert "1 music opportunity(s)" in ack
        assert "A tester walks left to right" in ack

        # Packet is persisted with Timeline context.
        packet = media_persist.load_packet(session, project_id, video_id)
        assert packet is not None
        assert packet.timelineContext is not None
        assert packet.timelineContext.sceneId == scene_id
        assert packet.timelineContext.projectId == project_id
        assert packet.timelineContext.clipAssetId == video_id
    finally:
        session.close()


def test_handler_fails_closed_without_playable_video(tmp_path) -> None:
    init_db()
    project_id = f"proj-{uuid.uuid4().hex[:10]}"
    scene_id = f"scene-{uuid.uuid4().hex[:10]}"

    session = SessionLocal()
    try:
        session.merge(Project(id=project_id, name="Analyze Video No Video"))
        session.merge(
            Scene(
                id=scene_id,
                project_id=project_id,
                index=0,
                name="Empty Scene",
                prompt="Nothing rendered yet",
                duration_sec=5.0,
            )
        )
        session.commit()

        result = analyze_video.handle(
            session,
            project_id,
            "exec-analyze-video",
            prompt="Review this scene.",
            scene_id=scene_id,
        )
        assert result["status"] == "failed"
        assert "No playable video clip" in result["error"]
    finally:
        session.close()
