"""Phase23: generate speech SoT is Master batch.promptSegments only."""
from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline import DirectorTimeline, PromptSegment
from app.director_timeline_w46.generation.speech_compile import apply_compiled_speech


def _batch(prompt_text: str = ""):
    segs = []
    if prompt_text:
        segs = [SimpleNamespace(text=prompt_text, referenceBindingIds=[], reference_binding_ids=[])]
    return SimpleNamespace(
        promptSegments=segs,
        duration=SimpleNamespace(plannedDuration=5.0),
        speechWindows=None,
        references=[],
        sceneId="scene-1",
    )


def test_master_text_is_speech_authority():
    batch = _batch('CHARACTER\n"Hello there."')
    tl = DirectorTimeline(
        duration_sec=5.0,
        prompt_segments=[
            PromptSegment(id="legacy", start=0, length=5, text='CHARACTER\n"LEGACY MUST NOT WIN."'),
        ],
    )
    errs = apply_compiled_speech(batch, tl)
    assert not any(e.get("code") == "MASTER_PROMPT_SEGMENTS_REQUIRED" for e in errs)
    assert batch.speechWindows
    joined = "\n".join(w.get("promptText") or "" for w in batch.speechWindows)
    assert "Hello there" in joined
    assert "LEGACY MUST NOT WIN" not in joined


def test_legacy_speech_without_master_fails_closed():
    batch = _batch("")
    tl = DirectorTimeline(
        duration_sec=5.0,
        prompt_segments=[
            PromptSegment(id="legacy", start=0, length=5, text='CHARACTER\n"Only on legacy."'),
        ],
    )
    errs = apply_compiled_speech(batch, tl)
    assert any(e.get("code") == "MASTER_PROMPT_SEGMENTS_REQUIRED" for e in errs)
    # Must not promote legacy text into speechWindows promptText
    for w in batch.speechWindows or []:
        assert "Only on legacy" not in (w.get("promptText") or "")
