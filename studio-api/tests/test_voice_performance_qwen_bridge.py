from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.character_identity.models import VoiceProfileRow
from app.character_identity.schemas import DialogueGenerateRequest
from app.character_identity.voice_runtime import (
    dialogue_style_text,
    qwen_speech_compatible,
    reject_clone_performance_style,
)


def test_qwen_speech_compatible_only_for_qwen_clone_or_design():
    qwen = VoiceProfileRow(
        id="v1",
        project_id="p",
        character_profile_id="c",
        provider="qwen3-tts",
        source_mode="CLONE",
    )
    design = VoiceProfileRow(
        id="v2",
        project_id="p",
        character_profile_id="c",
        provider="qwen3-tts-voice-design",
        source_mode="DESIGN",
    )
    index = VoiceProfileRow(
        id="v3",
        project_id="p",
        character_profile_id="c",
        provider="index-tts2-local",
        source_mode="DESIGN",
    )
    assert qwen_speech_compatible(qwen) is True
    assert qwen_speech_compatible(design) is True
    assert qwen_speech_compatible(index) is False
    assert qwen_speech_compatible(None) is False


def test_clone_rejects_emotional_direction_instead_of_ignoring_it():
    clone = VoiceProfileRow(
        id="v-clone",
        project_id="p",
        character_profile_id="c",
        provider="qwen3-tts",
        source_mode="CLONE",
    )
    design = VoiceProfileRow(
        id="v-design",
        project_id="p",
        character_profile_id="c",
        provider="qwen3-tts",
        source_mode="DESIGN",
    )
    styled = DialogueGenerateRequest(text="Stay close.", emotional_direction="whisper", performance_instruction="soft")
    plain = DialogueGenerateRequest(text="Stay close.")
    assert dialogue_style_text(styled)
    reject_clone_performance_style(clone, plain)
    reject_clone_performance_style(design, styled)
    with pytest.raises(HTTPException) as exc:
        reject_clone_performance_style(clone, styled)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "STYLE_UNSUPPORTED"
