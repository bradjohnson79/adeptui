"""Timeline spoken language is stored on the shot and written into the prompt.

An earlier batch that spoke another language does not become the next language.
"""

from app.film_timeline.h3_fast_renderer import compile_provider_prompt
from app.film_timeline.spoken_language import apply_to_prompt, clause, normalize


def test_english_is_the_default():
    spoken = normalize("")
    assert spoken.code == "en"
    assert spoken.label == "English"
    text = clause(spoken)
    assert "All spoken dialogue in this scene is in English." in text
    assert "If nobody speaks, keep the scene silent." in text
    assert "does not change this language" in text


def test_a_named_language_replaces_english():
    spoken = normalize("fr")
    assert spoken.label == "French"
    assert "in French." in apply_to_prompt("She answers.", spoken)


def test_custom_language_uses_the_creator_name():
    spoken = normalize("custom", "Welsh")
    assert spoken.label == "Welsh"
    assert "in Welsh." in clause(spoken)


def test_shot_document_keeps_the_selected_language():
    from app.film_timeline.contracts import Shot

    shot = Shot()
    assert shot.state.spokenLanguage == "en"
    shot.state.spokenLanguage = "ja"
    restored = Shot.model_validate(shot.model_dump())
    assert restored.state.spokenLanguage == "ja"
    assert restored.state.spokenLanguageCustom == ""


def test_earlier_speech_does_not_outrank_the_stored_language():
    prompt = apply_to_prompt("She glances toward the window.", normalize("en"))
    text = compile_provider_prompt(
        prompt,
        [{"label": "Renkoka"}],
        [{"label": "Ending"}],
        [],
        continuation=True,
        pair_video_audio=True,
        boundary="The person is speaking Japanese.",
        spoken_language="English",
    )
    assert "The person is speaking Japanese." in text
    assert "Any words in this new shot are spoken in English only." in text
    assert "Do not copy its language." in text
    assert "All spoken dialogue in this scene is in English." in text
    assert text.rfind("English") > text.rfind("Japanese")
    assert text.rfind("She glances toward the window.") < text.rfind("in English")
