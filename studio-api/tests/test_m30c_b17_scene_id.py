"""M3.0c B17 regression: video sceneId survives job enqueue."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_video_scene_id_is_present_in_provider_payload(monkeypatch):
    from app.codirector.m29.video.service import VideoService

    captured: dict = {}

    def fake_enqueue(db_sess, *, project_id, job_type, payload, scene_id=None, owner="user"):
        captured["payload"] = dict(payload)
        captured["scene_id"] = scene_id
        job = MagicMock()
        job.id = "exec-job-b17-separate"
        return job

    monkeypatch.setattr("app.codirector.m29.video.service.enqueue_executive_job", fake_enqueue)
    monkeypatch.setattr(
        "app.codirector.m29.video.service.video_provider_available",
        lambda _db: False,
    )
    monkeypatch.setattr(
        "app.codirector.m29.video.service.fixture_mode_enabled",
        lambda: False,
    )

    result = VideoService.generate(
        MagicMock(),
        project_id="proj-b17-separate",
        prompt="motion",
        mode="image_to_video",
        scene_id="scene-b17-separate",
    )

    assert result["jobId"] == "exec-job-b17-separate"
    assert captured["scene_id"] == "scene-b17-separate"
    assert captured["payload"]["sceneId"] == "scene-b17-separate"
