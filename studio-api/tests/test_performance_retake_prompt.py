"""Performance Retake prompt compiler tests (owner H3 dialect)."""

from __future__ import annotations

import pytest

from app.performance_retake.contracts import (
    CharacterSheetRef,
    PerformanceRetakeSpec,
    RetakeBeat,
    RetakeReferences,
    RetakeWindow,
)
from app.performance_retake.prompt_compile import (
    PromptCompileError,
    compile_performance_prompt,
)

ANADRIYA = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d"
KORRI = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed"


def _spec() -> PerformanceRetakeSpec:
    return PerformanceRetakeSpec(
        projectId="p",
        sceneId="s",
        window=RetakeWindow(startSec=0.0, endSec=10.016),
        masterDurationSec=10.016,
        beats=[
            RetakeBeat(
                kind="dialogue",
                startSec=0.0,
                endSec=3.0,
                characterId=ANADRIYA,
                characterName="Anadriya",
                line="We've neutralized Cade. The threat is over.",
                voiceAssetId="voice-a",
            ),
            RetakeBeat(
                kind="dialogue",
                startSec=4.0,
                endSec=7.0,
                characterId=KORRI,
                characterName="Korri",
                line="We did it, sis!",
                voiceAssetId="voice-k",
            ),
            RetakeBeat(kind="silence", startSec=7.0, endSec=10.016),
        ],
        references=RetakeReferences(
            characterSheets=[
                CharacterSheetRef(characterId=ANADRIYA, assetId="sheet-a"),
                CharacterSheetRef(characterId=KORRI, assetId="sheet-k"),
            ]
        ),
    )


def test_owner_dialect_subject_and_audio_bindings():
    prompt = compile_performance_prompt(_spec())
    assert "<subject 1> is Anadriya." in prompt
    assert "<subject 2> is Korri." in prompt
    assert "<Audio 1> is the voice-timbre reference for <subject 1> (S1)." in prompt
    assert "<Audio 2> is the voice-timbre reference for <subject 2> (S2)." in prompt


def test_source_video_binding_line():
    prompt = compile_performance_prompt(_spec())
    assert "<Video 1> is the source take" in prompt


def test_timecoded_dialogue_beats():
    prompt = compile_performance_prompt(_spec())
    assert '[00:00.0-00:03.0] <subject 1> (S1): "We\'ve neutralized Cade. The threat is over."' in prompt
    assert '[00:04.0-00:07.0] <subject 2> (S2): "We did it, sis!"' in prompt


def test_silence_beats_are_explicit():
    prompt = compile_performance_prompt(_spec())
    assert "[00:07.0-00:10.0] No dialogue. No speech. No singing. Ambient sound only." in prompt


def test_sub_window_timecodes_are_window_relative():
    spec = _spec()
    spec.window = RetakeWindow(startSec=4.0, endSec=10.016, scope="sub_window")
    spec.beats = spec.beats[1:]
    prompt = compile_performance_prompt(spec)
    assert '[00:00.0-00:03.0] <subject 2> (S2): "We did it, sis!"' in prompt
    assert "[00:03.0-00:06.0] No dialogue." in prompt


def test_shot_observation_included():
    prompt = compile_performance_prompt(
        _spec(), shot_observation="Static wide shot. Two women at a console."
    )
    assert "Source take observation: Static wide shot. Two women at a console." in prompt


def test_old_dialogue_leak_fails_compile():
    with pytest.raises(PromptCompileError, match="old dialogue leaked"):
        compile_performance_prompt(
            _spec(), forbidden_dialogue=["We did it, sis!"]
        )


def test_missing_beat_line_fails_honesty_check():
    spec = _spec()
    original = spec.beats[0].line
    prompt = compile_performance_prompt(spec)
    spec.beats[0].line = "A line that is not in the prompt."
    from app.performance_retake.prompt_compile import assert_prompt_honesty

    with pytest.raises(PromptCompileError, match="missing from the prompt"):
        assert_prompt_honesty(prompt, spec)
    spec.beats[0].line = original
