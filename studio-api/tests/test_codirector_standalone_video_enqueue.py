"""Standalone Co-Director video must not enqueue Timeline render_scene."""

from __future__ import annotations

from app.codirector.capabilities.registry import get_capability
from app.codirector.execution.dispatcher import _tool_params
from app.codirector.production_intent.execute import (
    IntentExecutionError,
    _enqueue_standalone_video,
    _is_h3_engine,
    enqueue_intent,
)
from app.codirector.production_intent.schemas import ProductionIntent
from app.codirector.tools import registry as tool_registry


class _FakeStore:
    def save(self, intent) -> None:
        return None

    def update_state(self, *args, **kwargs):
        return None


class _FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = 0

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed += 1


def test_h3_engine_tokens() -> None:
    assert _is_h3_engine("minimax-h3")
    assert _is_h3_engine("minimax-h3-i2v-local")
    assert not _is_h3_engine("ltx")


def test_standalone_ltx_enqueues_txt2vid_not_scene_row(monkeypatch) -> None:
    db = _FakeDb()
    monkeypatch.setattr(
        "app.codirector.production_intent.execute.get_intent_store",
        lambda: _FakeStore(),
    )
    monkeypatch.setattr(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        lambda *_a, **_k: None,
    )

    intent = ProductionIntent(
        projectId="proj",
        sceneId="wiki-scene-1",
        sourceSurface="codirector",
        operation="video.generate",
        modality="video",
        prompt="Create a short video version of that corridor shot.",
        sourceAssets=["still-1"],
        enginePreference="ltx",
        metadata={"standalone": True, "executionId": "exec-1", "videoMode": "i2v"},
    )
    result = _enqueue_standalone_video(db, intent)
    assert result["ok"] is True
    assert result["jobKind"] == "txt2vid"
    assert db.added
    job = db.added[0]
    assert job.kind == "txt2vid"
    assert job.scene_id is None
    assert job.project_id == "proj"


def test_standalone_h3_offline_is_honest(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.production_intent.execute.get_intent_store",
        lambda: _FakeStore(),
    )

    def _boom(*_a, **_k):
        raise AssertionError("must not prepare an H3 plan when Route A is offline")

    monkeypatch.setattr(
        "app.minimax_h3.service.readiness",
        lambda: {"ready": False, "creatorStatus": "MiniMax H3 is offline."},
    )
    monkeypatch.setattr("app.minimax_h3.service.prepare_plan", _boom)

    intent = ProductionIntent(
        projectId="proj",
        sourceSurface="codirector",
        operation="video.generate",
        modality="video",
        prompt="Create a short video version of that corridor shot.",
        enginePreference="minimax-h3",
        metadata={"standalone": True, "executionId": "exec-1"},
    )
    try:
        _enqueue_standalone_video(_FakeDb(), intent)
        raise AssertionError("expected honest H3 failure")
    except IntentExecutionError as exc:
        assert "offline" in str(exc).lower() or "not ready" in str(exc).lower()


def test_audio_generate_capabilities_act_not_navigate() -> None:
    sfx = get_capability("audio.sfx")
    assert sfx is not None
    assert sfx.tool_ids[0] == "audio.generate_sfx"
    definition = tool_registry.find("audio.generate_sfx")
    assert definition is not None
    assert definition.requires_approval is False


def test_tool_params_inherit_prompt_and_scene() -> None:
    params = _tool_params(
        {
            "user_instructions": "Generate footsteps on the metal grating for this scene.",
            "scene_id": "scene-1",
        }
    )
    assert params["prompt"].startswith("Generate footsteps")
    assert params["sceneId"] == "scene-1"


def test_image_enqueue_surfaces_the_image_product_job_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.production_intent.execute.get_intent_store",
        lambda: _FakeStore(),
    )

    def _fake_image(_db, _intent):
        return {
            "ok": True,
            "queued": True,
            "jobId": "job-ref-1",
            "jobs": [{"jobId": "job-ref-1", "workflowKey": "qwen2512.ref"}],
        }

    monkeypatch.setattr(
        "app.codirector.production_intent.execute._image_generate",
        _fake_image,
    )
    intent = ProductionIntent(
        projectId="proj",
        sourceSurface="codirector",
        operation="image.generate",
        modality="image",
        prompt="cinematic still of the ship",
        sourceAssets=["asset-1"],
    )
    result = enqueue_intent(_FakeDb(), intent)
    assert result["jobId"] == "job-ref-1"
    assert result["workflowKey"] == "qwen2512.ref"
    assert result["status"] == "queued"
    assert result["result"]["jobId"] == "job-ref-1"


def test_tool_params_canonical_retry_does_not_use_retry_utterance() -> None:
    params = _tool_params(
        {
            "canonical_resolved": True,
            "canonical_original_instructions": "Generate footsteps on the metal grating for this scene.",
            "prompt": "Generate footsteps on the metal grating for this scene.",
            "user_instructions": "Retry the last audio.",
            "scene_id": "scene-1",
        }
    )
    assert params["prompt"].startswith("Generate footsteps")
    assert "Retry" not in params["prompt"]
