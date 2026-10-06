from app.codirector.conversation.foundation.speech_act import classify_speech_act, resolve_production_action
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent


def test_give_korri_a_voice_opens_voice_creator():
    text = "Give Korri a voice."
    assert classify_speech_act(text) == "COMMAND"
    assert resolve_production_action(text) == "voice.creator"
    unified = classify_intent(text, {})
    assert unified.capability == "voice.creator"
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.dispatch == DispatchStrategy.CURATED_TOOLS
    assert "character_creator.open_voice_creator" in unified.curated_tool_ids


def test_create_new_voice_is_voice_creator_not_segment_generate():
    text = "Create a new voice for Anadriya."
    assert resolve_production_action(text) == "voice.creator"
    unified = classify_intent(text, {})
    assert unified.capability == "voice.creator"
    assert unified.capability != "voice.generate"


def test_what_voice_does_korri_have_reads_status():
    text = "What voice does Korri have?"
    assert resolve_production_action(text) == "voice.inspect"
    unified = classify_intent(text, {})
    assert unified.capability == "voice.inspect"
    assert "character_creator.get_voice_status" in unified.curated_tool_ids


def test_clone_recording_opens_voice_creator():
    text = "Clone this recording for Korri."
    assert resolve_production_action(text) == "voice.creator"
    assert classify_intent(text, {}).capability == "voice.creator"
