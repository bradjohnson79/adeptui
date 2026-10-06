"""Performance Retake H3 graph wiring tests (ref_videos by composition)."""

from __future__ import annotations

import pytest

from app.performance_retake.h3_retake_graph import (
    RetakeGraphError,
    assert_h3_retake_graph,
    build_h3_retake_graph,
)
from app.workflows.h3_ref2v_builder import find_h3_conditioner

PROMPT = "<subject 1> is Anadriya.\n[00:00.0-00:03.0] <subject 1> (S1): \"Line.\""
SHEETS = ["studio/sheet-anadriya.png", "studio/sheet-korri.png"]
VOICES = ["studio/voice-anadriya.wav"]
WINDOW = "studio/scene8-window.mp4"


def _graph(**overrides):
    kwargs = dict(
        prompt=PROMPT,
        ref_comfy_names=SHEETS,
        ref_video_comfy_name=WINDOW,
        filename_prefix="retake/scene8",
        length=243,
        width=1152,
        height=640,
        ref_audio_comfy_names=VOICES,
    )
    kwargs.update(overrides)
    return build_h3_retake_graph(**kwargs)


def test_ref_videos_wired_via_load_video_components():
    graph = _graph()
    _, cond = find_h3_conditioner(graph)
    cond_in = cond["inputs"]
    link = cond_in.get("ref_videos.ref_video_0")
    assert isinstance(link, list) and len(link) == 2
    components = graph[str(link[0])]
    assert components["class_type"] == "GetVideoComponents"
    assert link[1] == 0  # images output
    load_id = components["inputs"]["video"][0]
    assert graph[str(load_id)]["class_type"] == "LoadVideo"
    assert graph[str(load_id)]["inputs"]["file"] == WINDOW


def test_ref_video_audios_unwired_by_default():
    graph = _graph()
    _, cond = find_h3_conditioner(graph)
    leaked = [k for k in cond["inputs"] if str(k).startswith("ref_video_audios.")]
    assert leaked == []


def test_ref_video_audios_opt_in():
    graph = _graph(include_source_audio=True)
    _, cond = find_h3_conditioner(graph)
    link = cond["inputs"].get("ref_video_audios.ref_video_audio_0")
    assert isinstance(link, list)
    assert graph[str(link[0])]["class_type"] == "GetVideoComponents"
    assert link[1] == 1  # audio output


def test_missing_video_ref_rejected():
    with pytest.raises(RetakeGraphError, match="source window video"):
        _graph(ref_video_comfy_name="")


def test_assert_passes_and_preserves_fm4_invariants():
    graph = _graph()
    assert_h3_retake_graph(
        graph,
        expected_names=SHEETS,
        expected_video_name=WINDOW,
        expected_audio_names=VOICES,
        expected_prompt=PROMPT,
        expected_width=1152,
        expected_height=640,
        expect_fast=False,
    )


def test_assert_catches_missing_video_link():
    graph = _graph()
    _, cond = find_h3_conditioner(graph)
    del cond["inputs"]["ref_videos.ref_video_0"]
    with pytest.raises(RetakeGraphError, match="ref_videos.ref_video_0"):
        assert_h3_retake_graph(
            graph, expected_names=SHEETS, expected_video_name=WINDOW
        )


def test_assert_catches_source_audio_leak():
    graph = _graph(include_source_audio=True)
    with pytest.raises(RetakeGraphError, match="old-dialogue leak guard"):
        assert_h3_retake_graph(
            graph,
            expected_names=SHEETS,
            expected_video_name=WINDOW,
            expect_source_audio=False,
        )


def test_length_snaps_to_legal_grid():
    graph = _graph(length=241)
    _, cond = find_h3_conditioner(graph)
    assert cond["inputs"]["length"] == 243  # 17*14+5
