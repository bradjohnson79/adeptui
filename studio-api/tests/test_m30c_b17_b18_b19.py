"""M3.0c regression: B17 sceneId, B18 export director_json, B19 vision override."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_b17_video_generate_puts_scene_id_in_payload(monkeypatch):
    from app.codirector.m29.video.service import VideoService

    captured: dict = {}

    def fake_enqueue(db_sess, *, project_id, job_type, payload, scene_id=None, owner="user"):
        captured["payload"] = dict(payload)
        captured["scene_id"] = scene_id
        job = MagicMock()
        job.id = "exec-job-b17"
        return job

    monkeypatch.setattr(
        "app.codirector.m29.video.service.enqueue_executive_job",
        fake_enqueue,
    )
    monkeypatch.setattr(
        "app.codirector.m29.video.service.video_provider_available",
        lambda _db: False,
    )
    monkeypatch.setattr(
        "app.codirector.m29.video.service.fixture_mode_enabled",
        lambda: False,
    )

    out = VideoService.generate(
        MagicMock(),
        project_id="proj-b17",
        prompt="motion",
        mode="image_to_video",
        scene_id="scene-b17",
    )
    assert out["jobId"] == "exec-job-b17"
    assert captured["scene_id"] == "scene-b17"
    assert captured["payload"].get("sceneId") == "scene-b17"


def test_b18_export_source_includes_director_json_field():
    """Static guard: _export scene dict must include director_json (B18)."""
    from app import queue_worker

    src = inspect.getsource(queue_worker.JobQueue._export)
    assert "director_json" in src


def test_b18_export_payload_includes_director_json(monkeypatch, tmp_path):
    from app.queue_worker import JobQueue

    scene = MagicMock()
    scene.id = "sc1"
    scene.index = 0
    scene.name = "Scene"
    scene.engine = "fal_seedance"
    scene.prompt = "p"
    scene.duration_sec = 4
    scene.output_path = None
    scene.lipsync_output_path = None
    scene.director_json = json.dumps({"version": 1, "clips": [{"id": "c1"}]})

    project = MagicMock()
    project.id = "proj-b18"
    project.name = "ExportB18"
    project.global_prompt = ""
    project.engine_default = "fal_seedance"
    project.width = 1280
    project.height = 720
    project.fps = 24
    project.preset = ""
    project.spatial_map_json = "{}"

    job = MagicMock()
    job.id = "job-b18"
    job.output_path = None

    class _Q:
        def __init__(self):
            self._n = 0

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def all(self):
            self._n += 1
            return [scene] if self._n == 1 else []

    db = MagicMock()
    db.query.return_value = _Q()

    captured: dict = {}

    def fake_export_pack(payload, asset_paths, videos, out_dir):
        captured["payload"] = payload
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return Path(out_dir)

    monkeypatch.setattr("app.queue_worker.export_pack", fake_export_pack)
    monkeypatch.setattr("app.queue_worker.settings.data_dir", tmp_path)

    q = JobQueue()
    monkeypatch.setattr(q, "_set_status", lambda *a, **k: None)
    asyncio.run(q._export(db, job, project))

    assert "c1" in captured["payload"]["scenes"][0]["director_json"]


def test_b19_reject_band_requires_override(monkeypatch):
    from app.codirector.vision import approval as approval_mod

    session = MagicMock()
    session.reportId = "rep-b19"
    session.assetId = None

    report = MagicMock()
    report.band = "reject"

    monkeypatch.setattr(
        approval_mod.VisionStore,
        "get_session",
        lambda db, sid, project_id=None: session,
    )
    monkeypatch.setattr(
        approval_mod.VisionStore,
        "get_report",
        lambda db, rid, project_id=None: report,
    )

    with pytest.raises(ValueError, match="override"):
        approval_mod.record_decision(
            MagicMock(),
            project_id="proj",
            session_id="sess",
            decision="approved",
            override=False,
        )
