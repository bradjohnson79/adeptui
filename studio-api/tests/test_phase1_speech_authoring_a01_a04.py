"""Phase1 A01-A04 speech/authoring acceptance tests."""
from __future__ import annotations

from app.director_timeline import DirectorTimeline, PromptSegment
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.execution_window_materialize import (
    _build_batch_blocks,
    _preserve_segment_content,
)
from app.director_timeline_w46.generation.speech_compile import (
    apply_compiled_speech,
    extract_dialogue_cues_from_text,
    prompt_text_implies_speech,
)
from app.codirector.production_lifecycle.live_scene_readiness import _voice_required


def test_a01_screenplay_name_quoted_line():
    text = "KORRI\n\"Hello, welcome to Schnick Coffee.\""
    cues = extract_dialogue_cues_from_text(
        text,
        reference_name_bindings=[{"bindingId": "bind-korri", "promptName": "Korri"}],
    )
    assert cues and "welcome to Schnick Coffee" in cues[0]["text"]
    assert cues[0]["speakerName"].lower() == "korri"


def test_a01_screenplay_no_action_line_leak():
    text = (
        "KORRI\n"
        "Hello, welcome to Schnick Coffee.\n"
        "She smiles at the camera.\n"
    )
    cues = extract_dialogue_cues_from_text(
        text,
        reference_name_bindings=[{"bindingId": "bind-korri", "promptName": "Korri"}],
    )
    assert cues
    assert "welcome to Schnick Coffee" in cues[0]["text"]
    assert "smiles" not in cues[0]["text"].lower()


def test_a01_two_speakers_no_cross_block_leak():
    text = "KORRI\nWhat can I get you?\n\nANADRIYA\nAnything but silence.\n"
    cues = extract_dialogue_cues_from_text(
        text,
        reference_name_bindings=[
            {"bindingId": "bind-korri", "promptName": "Korri"},
            {"bindingId": "bind-ana", "promptName": "Anadriya"},
        ],
    )
    by = {c["speakerName"].lower(): c["text"] for c in cues}
    assert "korri" in by and "What can I get you?" in by["korri"]
    assert "anadriya" in by and "silence" in by["anadriya"].lower()
    assert "silence" not in by["korri"].lower()


def test_a01_required_speech_unresolved_not_silent_success():
    batch = BatchBlock(
        sceneId="s1",
        order=0,
        label="Batch 1",
        duration=DurationState(plannedDuration=5),
        promptSegments=[
            TimelinePromptSegment(
                text="KORRI\n\"Hello from Schnick.\"",
                start=0,
                length=5,
            )
        ],
    )
    errors = apply_compiled_speech(batch, DirectorTimeline(duration_sec=5, prompt_segments=[]))
    assert any(e.get("code") == "REQUIRED_SPEECH_UNRESOLVED" for e in errors)
    assert batch.speechWindows
    assert batch.speechWindows[0]["speechKind"] != "none"
    assert prompt_text_implies_speech(batch.promptSegments[0].text)


def test_a02_voice_required_from_prompt_text():
    tl = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(
                id="p1",
                start=0,
                length=5,
                text="KORRI\n\"Hello\"",
            )
        ],
    )
    assert _voice_required(None, tl) is True


def test_a02_voice_not_required_on_empty_visual_prompt():
    tl = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(id="p1", start=0, length=5, text="Wide shot of the cafe exterior.")
        ],
    )
    assert _voice_required(None, tl) is False


def test_a04_rematerialize_preserves_text_on_count_change():
    master = SceneTimelineMaster(
        sceneId="s1",
        batchBlocks=[
            BatchBlock(
                id="bb1",
                sceneId="s1",
                order=0,
                label="Batch 1",
                duration=DurationState(plannedDuration=10),
                promptSegments=[
                    TimelinePromptSegment(text="KORRI\nHello keep me.", start=0, length=10)
                ],
            )
        ],
    )
    windows = [{"start": 0, "end": 5}, {"start": 5, "end": 10}]
    blocks = _build_batch_blocks(master, windows, scene_id="s1", generator_id="minimax-h3-t2v-local")
    assert len(blocks) == 2
    assert "Hello keep me" in (blocks[0].promptSegments[0].text or "")


def test_a04_preserve_segment_keeps_name_bindings():
    src = TimelinePromptSegment(
        text="hi",
        start=0,
        length=5,
        referenceNameBindings=[{"bindingId": "b1", "promptName": "Korri"}],
    )
    out = _preserve_segment_content(src, 8.0)
    assert out.text == "hi"
    assert out.length == 8.0
    assert getattr(out, "referenceNameBindings", None)
