"""Atlas generate vs assign routing, source resolve, and no T2I-without-source."""

from __future__ import annotations

import uuid

import pytest

from app.codirector.conversation.foundation.speech_act import classify_speech_act
from app.codirector.conversation.foundation.visual_generation import is_visual_image_request
from app.codirector.routing.atlas_intent import (
    atlas_capability_for_message,
    is_atlas_assign_request,
    is_atlas_generate_request,
)
from app.codirector.routing.atlas_source import source_was_requested
from app.codirector.routing.generation_authority import is_action_first_generation_turn
from app.codirector.routing.unified_intent import UnifiedIntentKind, classify_intent


LIVE_PHRASE = (
    "Take codirector_image_generate_d5d616be in library and use that as a "
    "reference to create an atlas (top down shot) for the Spatial map."
)


def test_live_library_phrase_is_generate_never_assign_reference() -> None:
    assert is_atlas_generate_request(LIVE_PHRASE) is True
    assert is_atlas_assign_request(LIVE_PHRASE) is False
    assert atlas_capability_for_message(LIVE_PHRASE) == "atlas.generate"
    unified = classify_intent(LIVE_PHRASE, {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "atlas.generate"
    assert unified.capability != "character.assign_reference"
    assert is_action_first_generation_turn(LIVE_PHRASE) is True
    assert classify_speech_act(LIVE_PHRASE) == "COMMAND"
    assert is_visual_image_request(LIVE_PHRASE) is False


def test_create_and_turn_into_spatial_map_are_generate() -> None:
    for phrase in (
        "Create an Atlas Shot from this.",
        "Turn this corridor into a Spatial Map.",
        "Create a Spatial Map from this",
        "convert this environment into an atlas",
        "create a top-down shot of the corridor",
        "Use this as a reference to create an atlas (top down shot)",
    ):
        assert atlas_capability_for_message(phrase) == "atlas.generate", phrase
        assert classify_intent(phrase, {}).capability == "atlas.generate", phrase


def test_assign_only_phrases() -> None:
    for phrase in (
        "Use this as the Spatial Map reference.",
        "Use this existing Atlas.",
        "Use this as the Spatial Map background.",
        "Upload this as the Spatial Map.",
        "Use this map for the Venture.",
    ):
        assert is_atlas_generate_request(phrase) is False, phrase
        assert atlas_capability_for_message(phrase) == "atlas.assign", phrase
        assert classify_intent(phrase, {}).capability == "atlas.assign", phrase


def test_source_hint_from_library_tag() -> None:
    assert source_was_requested(LIVE_PHRASE) is True
    assert source_was_requested("create an atlas shot", []) is False
    assert source_was_requested("create an atlas", ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]) is True


def test_start_execution_keeps_context_attachments() -> None:
    from app.codirector.execution.api import merge_start_execution_attachments

    source = "1211dd83-e3f6-4d17-bf2b-669ec5961418"
    assert merge_start_execution_attachments([source], []) == [source]
    assert merge_start_execution_attachments([], [source]) == [source]
    assert merge_start_execution_attachments([source], [source]) == [source]


def test_atlas_require_source_refuses_t2i(monkeypatch) -> None:
    from app.codirector.capabilities.handlers import atlas_generate

    captured: list[dict] = []

    class _Job:
        id = "job-atlas-blocked"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)
    with pytest.raises(RuntimeError, match="could not be resolved"):
        atlas_generate.handle(
            db=None,
            project_id=f"proj-{uuid.uuid4()}",
            execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            prompt="Create an atlas from the library image.",
            scene_intent={"sceneTitle": "Corridor", "summary": "A silver metallic corridor."},
            require_source=True,
        )
    assert captured == []
