"""Standalone video.generate handler — honest SeeDance block, no silent MiniMax."""

from __future__ import annotations

from app.codirector.capabilities.handlers import video_generate
from app.codirector.preferences.resolver import PreferenceResolution


class _Boom(Exception):
    pass


def test_seedance_unconfigured_does_not_enqueue(monkeypatch) -> None:
    called = {"enqueue": 0}

    def _fake_resolve(*_args, **_kwargs):
        return PreferenceResolution(
            provider="fal_seedance",
            source="explicit",
            modality="video",
            explicit=True,
            job_scoped=True,
            configured=False,
            error="SeeDance is not configured. I will not switch to another generator.",
        )

    def _fake_enqueue(*_args, **_kwargs):
        called["enqueue"] += 1
        raise _Boom("must not enqueue")

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_generator_preference",
        _fake_resolve,
    )
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        _fake_enqueue,
    )

    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        prompt="Use SeeDance for this one.",
        user_instructions="Use SeeDance for this one.",
    )
    assert called["enqueue"] == 0
    assert result.get("child_jobs") == []
    assert result.get("provider") == "fal_seedance"
    assert "not configured" in str(result.get("error") or "").lower()


def test_timeline_owned_message_does_not_enqueue(monkeypatch) -> None:
    called = {"enqueue": 0}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        lambda *_a, **_k: called.__setitem__("enqueue", called["enqueue"] + 1) or {},
    )
    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        prompt="Generate shot 14.",
        user_instructions="Generate shot 14.",
    )
    assert called["enqueue"] == 0
    assert result.get("child_jobs") == []
    assert "Timeline" in str(result.get("error") or "")


def test_force_enqueue_failure_flag_reaches_intent(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_generator_preference",
        lambda *_a, **_k: PreferenceResolution(
            provider="ltx",
            source="explicit",
            modality="video",
            explicit=True,
            job_scoped=True,
            configured=True,
        ),
    )

    def _enqueue(_db, intent):
        captured["force"] = bool((intent.metadata or {}).get("forceEnqueueFailure"))
        return {
            "ok": False,
            "jobId": "job-forced-1",
            "status": "failed",
            "error": "Could not start the video generation job. Please retry.",
        }

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        _enqueue,
    )
    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        prompt="Use LTX for this one.",
        user_instructions="Use LTX for this one.",
        force_enqueue_failure=True,
    )
    assert captured["force"] is True
    assert result["child_jobs"][0]["status"] == "failed"


def test_enqueue_failure_returns_failed_not_queued(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_generator_preference",
        lambda *_a, **_k: PreferenceResolution(
            provider="ltx",
            source="explicit",
            modality="video",
            explicit=True,
            job_scoped=True,
            configured=True,
        ),
    )
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        lambda *_a, **_k: {
            "ok": False,
            "jobId": "job-failed-1",
            "status": "failed",
            "error": "Could not start the video generation job. Please retry.",
        },
    )
    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        prompt="Use LTX for this one.",
        user_instructions="Use LTX for this one.",
    )
    assert result.get("error")
    assert result["child_jobs"][0]["status"] == "failed"
    assert "queued" not in str(result["child_jobs"][0]["status"]).lower()


def test_explicit_ltx_without_frame_is_t2v_not_blocked(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_generator_preference",
        lambda *_a, **_k: PreferenceResolution(
            provider="ltx",
            source="explicit",
            modality="video",
            explicit=True,
            job_scoped=True,
            configured=True,
        ),
    )

    def _enqueue(_db, intent):
        captured["sourceAssets"] = list(intent.sourceAssets or [])
        captured["engine"] = intent.enginePreference
        return {"jobId": "vid-1", "workflowKey": "ltx"}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        _enqueue,
    )
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_animate_source_asset",
        lambda *_a, **_k: None,
    )

    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        prompt="Use LTX for this one.",
        user_instructions="Use LTX for this one.",
    )
    assert captured["engine"] == "ltx"
    assert captured["sourceAssets"] == []
    assert result["child_jobs"][0]["job_id"] == "vid-1"
    assert result["child_jobs"][0]["metadata"]["videoMode"] == "t2v"


def test_video_version_of_that_shot_is_i2v_with_last_still(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_generator_preference",
        lambda *_a, **_k: PreferenceResolution(
            provider="ltx",
            source="explicit",
            modality="video",
            explicit=True,
            job_scoped=True,
            configured=True,
        ),
    )
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_animate_source_asset",
        lambda *_a, **_k: "still-asset-1",
    )

    def _enqueue(_db, intent):
        captured["sourceAssets"] = list(intent.sourceAssets or [])
        captured["sceneId"] = intent.sceneId
        captured["standalone"] = bool((intent.metadata or {}).get("standalone"))
        captured["videoMode"] = (intent.metadata or {}).get("videoMode")
        return {"jobId": "vid-i2v-1", "workflowKey": "ltx"}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        _enqueue,
    )
    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        scene_id="scene-venture",
        prompt="Create a short video version of that corridor shot.",
        user_instructions="Create a short video version of that corridor shot.",
    )
    assert captured["videoMode"] == "i2v"
    assert captured["sourceAssets"] == ["still-asset-1"]
    assert captured["sceneId"] == "scene-venture"
    assert captured["standalone"] is True
    assert result["child_jobs"][0]["job_id"] == "vid-i2v-1"


def test_retry_utterance_keeps_original_i2v_brief(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_generator_preference",
        lambda *_a, **_k: PreferenceResolution(
            provider="ltx",
            source="explicit",
            modality="video",
            explicit=True,
            job_scoped=True,
            configured=True,
        ),
    )
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.resolve_animate_source_asset",
        lambda *_a, **_k: "still-asset-2",
    )

    def _enqueue(_db, intent):
        captured["prompt"] = intent.prompt
        captured["videoMode"] = (intent.metadata or {}).get("videoMode")
        captured["sourceAssets"] = list(intent.sourceAssets or [])
        return {"jobId": "vid-retry-1", "workflowKey": "ltx"}

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.video_generate.enqueue_intent",
        _enqueue,
    )
    result = video_generate.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec",
        prompt="Create a short video version of that corridor shot.",
        user_instructions="Retry the last video",
        original_user_instructions="Create a short video version of that corridor shot.",
    )
    assert captured["prompt"].startswith("Create a short video version")
    assert captured["videoMode"] == "i2v"
    assert captured["sourceAssets"] == ["still-asset-2"]
    assert result["child_jobs"][0]["job_id"] == "vid-retry-1"


def test_timeline_generate_shot_is_handoff_not_video_job() -> None:
    from app.codirector.capabilities.handlers import timeline_generate_shot

    result = timeline_generate_shot.handle(
        db=None,  # type: ignore[arg-type]
        project_id="proj",
        execution_id="exec-9",
        prompt="Generate shot 14.",
    )
    assert result["status"] == "failed"
    assert result["plan_data"]["sceneProduction"] is True
    assert result["child_jobs"][0]["status"] == "failed"
    assert "Shot 14" in (result["child_jobs"][0].get("error") or "")
