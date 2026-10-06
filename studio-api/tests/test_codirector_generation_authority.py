"""Co-Director generation authority: first-frame, animate-it, Timeline ownership."""

from __future__ import annotations

from app.codirector.conversation.foundation.visual_generation import (
    is_executable_image_turn,
    is_first_frame_image_request,
)
from app.codirector.preferences.resolver import (
    extract_explicit_provider,
    is_provider_configured,
    resolve_generator_preference,
    wants_persist_default,
)
from app.codirector.routing.generation_authority import (
    classify_generation_authority,
    is_action_first_generation_turn,
    normalize_job_output_asset_id,
)
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent
from app.codirector.service import _contradictory_creator_intent


DREAMWEAVER = "Create a first frame of a silver metallic Dreamweaver corridor."


def test_dreamweaver_first_frame_is_image_generate() -> None:
    assert is_first_frame_image_request(DREAMWEAVER) is True
    assert is_executable_image_turn(DREAMWEAVER) is True
    unified = classify_intent(DREAMWEAVER, {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "image.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    authority = classify_generation_authority(DREAMWEAVER)
    assert authority is not None
    assert authority.production_role == "video_first_frame"
    assert authority.owner == "codirector"


def test_animate_it_is_standalone_video() -> None:
    unified = classify_intent("Animate it.", {})
    assert unified.capability == "video.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    authority = classify_generation_authority("Animate it.")
    assert authority is not None
    assert authority.kind == "animate_it"
    assert authority.owner == "codirector"


def test_standalone_t2v_i2v_and_three_frame() -> None:
    assert classify_intent("Create a text-to-video clip.", {}).capability == "video.generate"
    assert classify_intent("Generate a video of this frame.", {}).capability == "video.generate"
    assert classify_intent("Generate a 3-frame video from these references.", {}).capability == "video.generate"
    assert classify_generation_authority("Generate a video of this frame.").video_mode == "i2v"
    assert classify_generation_authority("Create a short video version of that corridor shot.").video_mode == "i2v"
    assert classify_generation_authority("Create a text-to-video clip.").video_mode == "t2v"
    assert classify_generation_authority("Generate a 3-frame video from these references.").video_mode == "multi_frame"


def test_timeline_prepare_vs_timeline_owned_generation() -> None:
    prepare = classify_generation_authority("Put this into shot 14 on Timeline.")
    assert prepare is not None
    assert prepare.capability == "timeline.add_asset"
    assert prepare.owner == "timeline"
    owned = classify_generation_authority("Generate shot 14.")
    assert owned is not None
    assert owned.capability == "timeline.generate_shot"
    assert owned.owner == "timeline"
    assert owned.shot_index == 14
    assert classify_intent("Generate shot 14.", {}).capability == "timeline.generate_shot"


def test_action_first_covers_generate_not_timeline_prepare() -> None:
    assert is_action_first_generation_turn(DREAMWEAVER) is True
    assert is_action_first_generation_turn("Animate it.") is True
    assert is_action_first_generation_turn("Generate shot 14.") is True
    assert is_action_first_generation_turn("Put this into shot 14 on Timeline.") is False


H3_DURATION_SHOT = (
    "Create this now: a 5-second MiniMax H3 shot of Korri and Anadriya walking "
    "the Venture corridor. Use both characters and this corridor."
)


def test_minimax_h3_duration_shot_is_not_still_image() -> None:
    assert is_executable_image_turn(H3_DURATION_SHOT) is False
    authority = classify_generation_authority(H3_DURATION_SHOT)
    assert authority is not None
    assert authority.capability == "video.generate"
    assert authority.owner == "codirector"
    unified = classify_intent(H3_DURATION_SHOT, {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "video.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC


def test_minimax_h3_duration_shot_on_timeline_is_handoff_not_t2v() -> None:
    authority = classify_generation_authority(H3_DURATION_SHOT, workspace="timeline")
    assert authority is not None
    assert authority.capability == "timeline.prepare_scene"
    assert authority.owner == "timeline"
    unified = classify_intent(H3_DURATION_SHOT, {"active_workspace": "timeline"})
    assert unified.capability == "timeline.prepare_scene"
    assert unified.capability != "image.generate"


def test_timeline_t2v_is_handoff_not_proceed() -> None:
    text = "Make a text-to-video Timeline shot with no references at all."
    authority = classify_generation_authority(text, workspace="timeline")
    assert authority is not None
    assert authority.capability == "timeline.prepare_scene"
    assert authority.owner == "timeline"
    unified = classify_intent(text, {"active_workspace": "timeline"})
    assert unified.capability == "timeline.prepare_scene"
    assert unified.capability != "video.generate"


def test_timeline_scene_prepare_phrasing_families_are_universal() -> None:
    """The front door must recognize varied natural phrasings of the same
    scene-preparation intent — not just "Build a scene in Timeline …".

    Regression: "Create/Make/Prepare a Timeline scene …" (Timeline-first
    order) previously fell through to image.generate or an empty-capability
    LLM path, so the most natural creator phrasing produced a still image
    instead of a prepared scene.
    """
    phrasings = [
        "Create a Timeline scene using the Salt Flats environment reference sheet as the setting. Slow aerial drift. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        "Build a Timeline scene with the Character reference of Mara Voss inside the Neon Harbor environment reference sheet. Fog drifts. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        "Make a Timeline scene with the Character reference of Iris Kane in the Rust Market environment reference sheet. Iris waits. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        "Prepare a Timeline scene in the Obsidian Gate environment reference sheet with the Character reference of Echo Nine. Do not show Echo Nine before the energy ring flares. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        "Build a scene in Timeline in the Canyon Crossing environment reference sheet. Wide shot. 20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
        "Write a Timeline prompt for the Character reference of Cade O'Connor using the Venture Corridor Scene environment reference sheet as the setting. A door buckles. 30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
        "Generate a Timeline scene in the Rust Market environment reference sheet. Dawn breaks. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
    ]
    for text in phrasings:
        authority = classify_generation_authority(text, workspace="timeline")
        assert authority is not None, text
        assert authority.capability == "timeline.prepare_scene", text
        assert authority.owner == "timeline", text
        unified = classify_intent(text, {"active_workspace": "timeline"})
        assert unified.capability == "timeline.prepare_scene", text
        # Never silently collapse a scene request into a still image.
        assert unified.capability != "image.generate", text


def test_confirm_job_question_is_not_video_execution() -> None:
    text = "You just generated the MiniMax H3 shot, right? Confirm the job id."
    assert classify_generation_authority(text, workspace="timeline") is None
    unified = classify_intent(text, {"active_workspace": "timeline"})
    assert unified.capability != "video.generate"
    assert unified.capability != "timeline.generate_shot"


def test_use_minimax_h3_alone_is_not_video_execution() -> None:
    assert classify_generation_authority("Use MiniMax H3.") is None
    unified = classify_intent("Use MiniMax H3.", {})
    assert unified.capability != "image.generate"


def test_contradictory_h3_only_and_fallback_is_disclosed() -> None:
    msg = _contradictory_creator_intent("Use MiniMax H3 only, but fall back if unavailable.")
    assert msg is not None
    assert "contradict" in msg.lower()
    assert "will not silently fall back" in msg.lower()


def test_use_ltx_for_this_one_is_job_scoped_video() -> None:
    unified = classify_intent("Use LTX for this one.", {})
    assert unified.capability == "video.generate"
    authority = classify_generation_authority("Use LTX for this one.")
    assert authority is not None
    assert authority.owner == "codirector"
    assert authority.video_mode == "t2v"


def test_explicit_provider_is_job_scoped_unless_default_requested() -> None:
    assert extract_explicit_provider("Use LTX for this one.") == "ltx"
    assert wants_persist_default("Use LTX for this one.") is False
    assert wants_persist_default("Always use LTX for video.") is True
    resolution = resolve_generator_preference(
        None,
        "proj",
        modality="video",
        message="Use LTX for this one.",
    )
    assert resolution.provider == "ltx"
    assert resolution.explicit is True
    assert resolution.job_scoped is True
    assert resolution.persist_default is False


def test_crs_question_is_not_execution() -> None:
    unified = classify_intent("Should we create Korri's CRS?", {})
    assert unified.intent != UnifiedIntentKind.EXECUTION
    assert unified.dispatch == DispatchStrategy.LLM_ONLY


def test_speech_act_imperative_and_pragmatic_request_execute() -> None:
    for text in (
        "Create Korri's CRS.",
        "Please create Korri's CRS.",
        "Can you create Korri's CRS?",
        "Yes, create it now.",
        "Generate an image of a silver corridor.",
        "Animate this.",
    ):
        unified = classify_intent(text, {})
        assert unified.intent == UnifiedIntentKind.EXECUTION, text
        assert unified.dispatch != DispatchStrategy.LLM_ONLY, text


def test_speech_act_recommendation_and_hypothetical_discuss() -> None:
    for text in (
        "Should we create Korri's CRS?",
        "Should we create it?",
        "Would creating Korri's CRS help?",
        "Would creating this help?",
        "Do you think we should create Korri's CRS?",
        "What if we created Korri's CRS?",
    ):
        unified = classify_intent(text, {})
        assert unified.intent != UnifiedIntentKind.EXECUTION, text
        assert unified.dispatch == DispatchStrategy.LLM_ONLY, text


def test_seedance_unconfigured_fails_honestly(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.preferences.resolver.is_provider_configured",
        lambda provider: False if "seedance" in provider else True,
    )
    resolution = resolve_generator_preference(
        None,
        "proj",
        modality="video",
        message="Use SeeDance for this one.",
    )
    assert resolution.ok is False
    assert resolution.provider == "seedance-2.0"
    assert resolution.configured is False
    assert not resolution.error
    strict = resolve_generator_preference(
        None,
        "proj",
        modality="video",
        message="Use SeeDance only.",
    )
    assert strict.ok is False
    assert strict.error
    assert "not configured" in strict.error.lower()
    assert "Seedance 2.0" in strict.error or "SeeDance" in strict.error
    assert "will not switch" in strict.error.lower()
    assert "fal_seedance" not in strict.error
    assert "fal seedance" not in strict.error.lower()
    assert "minimax" not in strict.error.lower()


def test_seedance_unconfigured_does_not_resolve_to_minimax(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.codirector.preferences.resolver.is_provider_configured",
        lambda provider: "seedance" not in str(provider),
    )
    resolution = resolve_generator_preference(
        None,
        "proj",
        modality="video",
        message="Animate it with SeeDance.",
    )
    assert resolution.provider == "seedance-2.0"
    assert resolution.configured is False


def test_live_seedance_config_check_is_boolean() -> None:
    assert isinstance(is_provider_configured("fal_seedance"), bool)


def test_normalize_job_output_asset_id_canonical() -> None:
    assert normalize_job_output_asset_id({"output_asset_id": "a1"}) == "a1"
    assert normalize_job_output_asset_id({"outputAssetIds": ["b2"]}) == "b2"
    assert normalize_job_output_asset_id({"outputAssetId": "c3"}) == "c3"


def test_remember_first_frame_survives_new_session() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.codirector.routing.generation_authority import (
        remember_first_frame,
        resolve_animate_source_asset,
    )
    from app.db import Asset, Base, Project

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Project(id="proj-a", name="A"))
    db.add(Project(id="proj-b", name="B"))
    db.add(Asset(id="frame-a", project_id="proj-a", kind="image", filename="a.png", path="a.png", tag="still"))
    db.commit()
    remember_first_frame(db, "proj-a", execution_id="e1", job_id="j1", asset_id="frame-a")
    db.close()

    db2 = Session()
    assert resolve_animate_source_asset(db2, "proj-a") == "frame-a"
    assert resolve_animate_source_asset(db2, "proj-b") is None
    db2.close()
