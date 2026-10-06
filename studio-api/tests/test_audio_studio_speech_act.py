from app.codirector.conversation.foundation.speech_act import (
    classify_speech_act,
    resolve_production_action,
)
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent


def test_audio_studio_phrases_route_to_the_right_surface() -> None:
    cases = {
        "Give me a tense orchestral cue for this scene.": "audio.music",
        "Make a metallic door slam.": "audio.sfx",
        "Generate footsteps on the metal grating for this scene.": "audio.sfx",
        "Add footsteps on the metal corridor floor for them.": "audio.sfx",
        "Add the approved footsteps to this scene.": "timeline.add_audio",
        "I need quiet spaceship corridor ambience.": "audio.ambience",
        "Use the approved corridor ambience on Scene 2.": "audio.open",
        "Open Audio Studio": "audio.open",
    }
    for text, expected in cases.items():
        assert resolve_production_action(text) == expected, text
        unified = classify_intent(text, {})
        assert unified.intent == UnifiedIntentKind.EXECUTION, text
        assert unified.capability == expected, text
        assert unified.dispatch == DispatchStrategy.DETERMINISTIC, text


def test_add_footsteps_places_on_timeline_not_open_studio() -> None:
    text = (
        "Add footsteps for Korri and Anadriya and time them to their walking. "
        "Use the approved metal grate footstep SFX already in Audio Studio"
    )
    assert classify_speech_act(text) == "COMMAND"
    assert resolve_production_action(text) == "timeline.add_audio"
    unified = classify_intent(text, {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "timeline.add_audio"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    assert "audio.place" in unified.curated_tool_ids
    assert resolve_production_action("Use the approved corridor ambience on Scene 2.") == "audio.open"


def test_approved_footsteps_are_in_the_live_dispatch_allowlist() -> None:
    from app.codirector.service import _UI_HANDOFF_CAPABILITIES

    text = "Add the approved footsteps to this scene."
    unified = classify_intent(text, {})
    assert unified.capability == "timeline.add_audio"
    assert unified.capability in _UI_HANDOFF_CAPABILITIES
    assert unified.is_high_confidence_execution is True


def test_visual_corridor_still_is_image_not_ambience() -> None:
    corridor = (
        "Create a Silver metallic corridor scene where we see an elevator door at the end "
        "of the corridor, and then about 10 meters ahead, there is a door that leads to a "
        "Combat Chamber room."
    )
    assert resolve_production_action(corridor) == "image.generate"
