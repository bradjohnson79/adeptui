"""H3 Director cutover — Bot A fail-closed + useDirector propagation pins."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.director_timeline_w46.generation.adapters import comfy_render_scene as crs
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.film_timeline.orchestrator import _is_local_h3


def test_is_local_h3_tokens():
    assert _is_local_h3("minimax-h3-i2v-local")
    assert _is_local_h3("minimax-h3-local")
    assert not _is_local_h3("minimax-h3")
    assert not _is_local_h3("ltx-2.5")


def test_comfy_render_scene_forces_use_director_for_local_h3(monkeypatch):
    """Local H3 Timeline jobs must land useDirector=True in params_json."""
    captured: dict = {}

    class _FakeJob:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.id = kwargs.get("id")
            self.params_json = kwargs.get("params_json")
            self.status = "queued"
            self.stage = "queued"
            self.message = kwargs.get("message")
            self.history_json = None

    class _FakeDB:
        def add(self, row):
            self.row = row

        def commit(self):
            pass

        def close(self):
            pass

        def get(self, *a, **k):
            return None

    monkeypatch.setattr(crs, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(crs, "Job", _FakeJob)
    monkeypatch.setattr(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        lambda job_id: None,
    )

    req = TimelineGenerationRequest(
        projectId="p1",
        sceneId="s1",
        batchBlockId="b1",
        executionSnapshotId="e1",
        generatorId="minimax-h3-i2v-local",
        generationMode="reference",
        prompt="a quiet walk",
        duration=5,
        resolution="1152x640",
        providerOptions={
            "originalGeneratorId": "minimax-h3-i2v-local",
            "filmTimeline": True,
            "requestedDurationSec": 5,
            # deliberately omit useDirector — adapter must force it
        },
    )
    sub = crs.submit_render_scene(
        req,
        engine="minimax-h3",
        generator_id="minimax-h3-i2v-local",
        queue_message="test",
    )
    assert sub.internalJobId or sub.queueJobId
    import json

    params = json.loads(captured["params_json"])
    assert params.get("useDirector") is True
    assert int(params.get("requestedDurationSec")) == 5
    assert params.get("timelineGeneration") is True


def test_comfy_render_scene_honors_explicit_use_director(monkeypatch):
    captured: dict = {}

    class _FakeJob:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.id = kwargs.get("id")
            self.params_json = kwargs.get("params_json")
            self.status = "queued"
            self.stage = "queued"
            self.message = kwargs.get("message")
            self.history_json = None

    class _FakeDB:
        def add(self, row):
            pass

        def commit(self):
            pass

        def close(self):
            pass

        def get(self, *a, **k):
            return None

    monkeypatch.setattr(crs, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(crs, "Job", _FakeJob)
    monkeypatch.setattr(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        lambda job_id: None,
    )
    req = TimelineGenerationRequest(
        projectId="p1",
        sceneId="s1",
        batchBlockId="b1",
        executionSnapshotId="e1",
        generatorId="some-adapter",
        generationMode="reference",
        prompt="x",
        duration=8,
        providerOptions={
            "originalGeneratorId": "minimax-h3-i2v-local",
            "useDirector": True,
            "requestedDurationSec": 8,
        },
    )
    crs.submit_render_scene(req, engine="minimax-h3", generator_id="x", queue_message="t")
    import json

    params = json.loads(captured["params_json"])
    assert params["useDirector"] is True


def test_queue_worker_ft_h3_has_no_silent_ref2v_fallback():
    """Static pin: timeline H3 branch must not call _build_and_run_h3_ref2v."""
    src_path = Path(__file__).resolve().parents[1] / "app" / "queue_worker.py"
    src = src_path.read_text(encoding="utf-8")
    # Find the timeline H3 Director cutover block and ensure ref2v is not in the else.
    marker = "Director cutover (fail-closed)"
    assert marker in src, "fail-closed Director cutover marker missing"
    idx = src.index(marker)
    window = src[idx : idx + 1200]
    assert "_build_and_run_h3_director" in window
    assert "_build_and_run_h3_ref2v" not in window
    assert "H3_DIRECTOR_REQUIRED" in window


def test_queue_worker_director_skips_frames_for_duration_authority():
    src_path = Path(__file__).resolve().parents[1] / "app" / "queue_worker.py"
    src = src_path.read_text(encoding="utf-8")
    assert "frames_for_duration is\n                    # NOT duration authority" in src or (
        "NOT duration authority" in src and "useDirector" in src
    )
    # Director method uses requestedDurationSec, not frames_for_duration
    dir_idx = src.index("async def _build_and_run_h3_director")
    dir_body = src[dir_idx : dir_idx + 8000]
    assert "requestedDurationSec" in dir_body
    assert "frames_for_duration" not in dir_body


def test_orchestrator_provider_options_include_use_director_for_local_h3():
    src_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "film_timeline"
        / "orchestrator.py"
    )
    src = src_path.read_text(encoding="utf-8")
    assert '**({"useDirector": True} if _is_local_h3(generator_id) else {})' in src
    assert 'request.providerOptions["useDirector"] = True' in src


def test_queue_worker_missing_use_director_raises_human_error():
    """FT H3 without useDirector must raise H3_DIRECTOR_REQUIRED (no silent ref2v)."""
    src = (Path(__file__).resolve().parents[1] / "app" / "queue_worker.py").read_text(encoding="utf-8")
    idx = src.index("Director cutover (fail-closed)")
    window = src[idx : idx + 900]
    assert "H3_DIRECTOR_REQUIRED" in window
    assert "_build_and_run_h3_ref2v" not in window
    assert "forcing Director" not in window
