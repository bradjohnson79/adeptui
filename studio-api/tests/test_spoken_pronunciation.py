from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.character_identity.spoken_pronunciation import (
    apply_spoken_pronunciations,
    entries_from_voice,
    merge_spoken_pronunciations,
)
from app.character_identity.voice_runtime import generate_approved_voice_speech, generate_voice_design_sample
from app.voice_performance.compiler import apply_pronunciations
from app.voice_performance.schemas import PerformanceSegmentOut


def test_adept_left_unrespelled_by_platform():
    spoken, applied = apply_spoken_pronunciations("Where is the Adept?")
    assert spoken == "Where is the Adept?"
    assert applied == []


def test_adept_possessive_and_case_left_unrespelled():
    spoken, applied = apply_spoken_pronunciations("The ADEPT's door opened.")
    assert spoken == "The ADEPT's door opened."
    assert applied == []


def test_does_not_touch_adeptly_or_inadept():
    source = "She is adeptly inadept at this."
    spoken, applied = apply_spoken_pronunciations(source)
    assert spoken == source
    assert applied == []


def test_already_respelt_add_ept_is_stable():
    spoken, applied = apply_spoken_pronunciations("Where is the Add-ept?")
    assert spoken == "Where is the Add-ept?"
    assert applied == []


def test_anadriya_uses_annadreeya():
    spoken, applied = apply_spoken_pronunciations("Stay close, Anadriya.")
    assert spoken == "Stay close, Annadreeya."
    assert applied == [
        {"word": "Anadriya", "phonetic": "Annadreeya", "count": 1, "source": "platform"}
    ]


def test_anadriya_possessive_and_adept_unrespelled():
    spoken, applied = apply_spoken_pronunciations("Anadriya's Adept is missing.")
    assert spoken == "Annadreeya's Adept is missing."
    words = {item["word"] for item in applied}
    assert words == {"Anadriya"}


def test_already_respelt_annadreeya_is_stable():
    spoken, applied = apply_spoken_pronunciations("Stay close, Annadreeya.")
    assert spoken == "Stay close, Annadreeya."
    assert applied == []


def test_voice_override_can_still_respell_adept():
    spoken, applied = apply_spoken_pronunciations(
        "Find the Adept.",
        [{"word": "Adept", "phonetic": "At-Dept"}],
    )
    assert spoken == "Find the At-Dept."
    assert applied[0]["source"] == "voice"


def test_empty_phonetic_does_not_invent_platform_adept():
    spoken, _applied = apply_spoken_pronunciations(
        "Find the Adept.",
        [{"word": "Adept", "phonetic": ""}],
    )
    assert spoken == "Find the Adept."


def test_entries_from_voice_lineage_json():
    voice = SimpleNamespace(
        lineage_json='{"pronunciations":[{"word":"Anadriya","phonetic":"ah-nah-DREE-yah"}]}'
    )
    entries = entries_from_voice(voice)
    assert entries[0]["word"] == "Anadriya"
    merged = merge_spoken_pronunciations(entries)
    words = {str(item["word"]).lower() for item in merged}
    assert "adept" not in words
    assert "anadriya" in words


def test_compiler_does_not_attach_platform_adept_override():
    segs = [
        PerformanceSegmentOut(
            id="s1",
            orderIndex=1,
            segmentType="speech",
            text="Where is the Adept?",
        )
    ]
    out, issues = apply_pronunciations(segs, {"pronunciations": []})
    assert not any(item.get("word") == "Adept" for item in (out[0].pronunciationOverrides or []))


def test_compiler_attaches_platform_anadriya_override():
    segs = [
        PerformanceSegmentOut(
            id="s1",
            orderIndex=1,
            segmentType="speech",
            text="Stay close, Anadriya.",
        )
    ]
    out, issues = apply_pronunciations(segs, {"pronunciations": []})
    assert any(item.get("word") == "Anadriya" for item in out[0].pronunciationOverrides)


def test_generate_voice_design_sample_leaves_adept_unrespelled(tmp_path):
    dest = tmp_path / "design.wav"
    dest.write_bytes(b"RIFF" + b"\x00" * 1200)
    proc = SimpleNamespace(
        stdin=MagicMock(),
        stdout=MagicMock(),
        poll=MagicMock(return_value=None),
    )
    proc.stdout.readline.return_value = (
        '{"type":"done","id":"job1xxxxxx","first_audio_ms":1200,"complete_ms":1800,"device":"cuda:0"}\n'
    )

    with (
        patch(
            "app.character_identity.voice_runtime._project_audio_dir",
            return_value=tmp_path,
        ),
        patch(
            "app.character_identity.voice_runtime._design_serve",
            return_value={"proc": proc, "ready": {"device": "cuda:0"}},
        ),
        patch(
            "app.character_identity.voice_runtime.validate_generated_wav",
            return_value=None,
        ),
        patch("app.character_identity.voice_runtime.uuid.uuid4") as uuid4,
    ):
        uuid4.return_value = SimpleNamespace(hex="job1xxxxxx")
        generate_voice_design_sample(
            project_id="p1",
            text="Where is the Adept?",
            instruct="dry",
            seed=1,
        )

    written = proc.stdin.write.call_args[0][0]
    assert "Add-ept" not in written
    assert "Where is the Adept?" in written


def test_generate_approved_voice_speech_keeps_adept_unrespelled():
    voice = SimpleNamespace(
        source_mode="DESIGN",
        provider="qwen3-tts",
        voice_design_prompt="dry",
        lineage_json="{}",
        consent_record_id=None,
        reference_transcript=None,
    )
    captured: dict[str, str] = {}

    def _fake_design(**kwargs):
        captured["text"] = kwargs["text"]
        return {"path": "out.wav", "complete_ms": 10}

    with (
        patch(
            "app.character_identity.voice_runtime.qwen_speech_compatible",
            return_value=True,
        ),
        patch(
            "app.character_identity.voice_runtime.generate_voice_design_sample",
            side_effect=_fake_design,
        ),
    ):
        produced = generate_approved_voice_speech(
            SimpleNamespace(),
            project_id="p1",
            voice=voice,
            text="Where is the Adept?",
        )

    assert captured["text"] == "Where is the Adept?"
    assert produced["sourceText"] == "Where is the Adept?"
    assert produced["spokenText"] == "Where is the Adept?"
