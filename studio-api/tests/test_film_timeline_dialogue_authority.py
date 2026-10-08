"""Film Timeline Dialogue is stored on the shot and reaches the H3 prompt.

Character Voice keeps ambience language and does not store a voice id.
"""

from types import SimpleNamespace

from app.film_timeline.contracts import Shot
from app.film_timeline.dialogue_authority import (
    availability_message,
    execution_options,
    continue_dialogue_instruction,
    lock_prompt,
    prompt_asks_to_speak,
    mode_from_instruction,
    normalize_mode,
)
from app.film_timeline.h3_fast_renderer import compile_provider_prompt
from app.film_timeline.spoken_language import apply_to_prompt, normalize


def test_dialogue_defaults_to_native_model_and_persists():
    shot = Shot()
    assert shot.state.dialogueAuthority == "native_model"
    shot.state.dialogueAuthority = "character_voice"
    restored = Shot.model_validate(shot.model_dump())
    assert restored.state.dialogueAuthority == "character_voice"
    assert normalize_mode("nope") == "native_model"


def test_character_voice_lock_keeps_english_and_drops_silence():
    spoken = apply_to_prompt("Renkoka looks up.", normalize("en"))
    locked = lock_prompt(spoken)
    assert "in English." in locked
    assert "This shot has no written dialogue, so nobody speaks." not in locked
    assert "Keep environmental ambience, room tone, and other non-dialogue scene sound." in locked
    assert "Do not speak any character lines." in locked
    compiled = compile_provider_prompt(locked, [{"label": "Renkoka"}], [], [], spoken_language="English")
    assert "Do not speak any character lines." in compiled
    assert "providerVoiceId" not in compiled


def test_execution_options_are_ambience_on_and_carry_no_voice_id():
    options = execution_options(
        [{"characterId": "char-1", "name": "Renkoka", "provider": "elevenlabs", "voiceName": "Renkoka Final", "usable": True}]
    )
    assert options["generate_audio"] is True
    assert options["audioAuthority"]["authority"] == "ambience_speech_off"
    assert options["audioAuthority"]["dialogue"] == "speech_locked_empty"
    assert options["dialogueAuthority"]["mode"] == "character_voice"
    assert options["characterVoices"]["characters"][0]["voiceName"] == "Renkoka Final"
    assert "providerVoiceId" not in str(options)


def test_missing_voice_is_a_creator_message():
    assert availability_message([], has_character=False) == "Choose the character who speaks in this shot."
    assert (
        availability_message([{"usable": False, "name": "Renkoka"}], has_character=True)
        == "Renkoka has no Character Voice currently approved."
    )
    assert availability_message([{"usable": True}], has_character=True) == ""


def test_continue_keeps_the_new_spoken_line():
    line = 'Renkoka continues and says "What you see before you is a reflection of the person I once was."'
    assert prompt_asks_to_speak(line) is True
    assert prompt_asks_to_speak("The aurora moves behind her.") is False
    clause = continue_dialogue_instruction(line)
    assert "Speak the dialogue written in this prompt" in clause
    assert "Do not repeat the previous shot's spoken line." in clause
    assert "Greetings" not in clause


def test_codirector_instruction_uses_the_same_modes():
    assert mode_from_instruction("Use Renkoka's character voice for this scene.") == "character_voice"
    assert mode_from_instruction("Switch this shot back to native model dialogue.") == "native_model"
    assert mode_from_instruction("She walks to the window.") is None
    shot = SimpleNamespace(state=SimpleNamespace(dialogueAuthority="character_voice"))
    assert shot.state.dialogueAuthority == "character_voice"
