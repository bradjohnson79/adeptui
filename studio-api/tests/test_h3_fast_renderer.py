"""Attached Ref2Video contract for the Timeline V2 H3 fast renderer."""

from __future__ import annotations

import pytest

from app.film_timeline.h3_fast_renderer import (
    EASYCACHE_END,
    EASYCACHE_REUSE,
    EASYCACHE_START,
    MECHANISM,
    STEPS,
    build_h3_fast_workflow,
    compile_provider_prompt,
    legal_frames,
    legal_tail_frame_count,
    plan_references,
)


def _graph():
    return build_h3_fast_workflow(
        prompt="Korri turns toward the door.",
        filename_prefix="h3_fast_test",
        seed=140011,
        width=1376,
        height=768,
        duration_sec=15,
        image_names=["korri.png", "room.png"],
        image_labels=["Korri", "Mess hall"],
        video_names=["prior.mp4"],
        video_labels=["Previous segment"],
        audio_names=["line.wav"],
        audio_labels=["Korri"],
    )


def test_legal_frames_match_attached_expression():
    assert legal_frames(15) == 362
    assert legal_frames(10) == 243
    assert legal_frames(7) == 175
    assert legal_frames(12) == 294
    assert legal_frames(5) == 124
    assert legal_frames(3) == 73


def test_image_only_keeps_sage_attention():
    graph = build_h3_fast_workflow(
        prompt="Korri turns toward the door.",
        filename_prefix="h3_fast_test",
        seed=140011,
        width=1376,
        height=768,
        duration_sec=15,
        image_names=["korri.png"],
        image_labels=["Korri"],
    )
    assert graph["6"]["inputs"]["sage_attention"] == "auto"


def test_acceleration_matches_attached_wiring():
    graph = _graph()
    assert graph["5"]["class_type"] == "EasyCache"
    assert graph["5"]["inputs"]["model"] == ["1", 0]
    assert graph["5"]["inputs"]["reuse_threshold"] == EASYCACHE_REUSE
    assert graph["5"]["inputs"]["start_percent"] == EASYCACHE_START
    assert graph["5"]["inputs"]["end_percent"] == EASYCACHE_END
    assert graph["5"]["inputs"]["verbose"] is False
    assert graph["6"]["class_type"] == "PathchSageAttentionKJ"
    assert graph["6"]["inputs"]["model"] == ["5", 0]
    assert graph["6"]["inputs"]["sage_attention"] == "auto"
    assert graph["6"]["inputs"]["allow_compile"] is False
    # Scheduler stays on the raw UNET. Sage feeds the guider only.
    assert graph["7"]["inputs"]["model"] == ["1", 0]
    assert graph["7"]["inputs"]["scheduler"] == "simple"
    assert graph["7"]["inputs"]["steps"] == STEPS
    assert graph["12"]["inputs"]["model"] == ["6", 0]
    assert graph["8"]["inputs"]["sampler_name"] == "res_multistep"
    assert "MiniMaxH3Director" not in {node["class_type"] for node in graph.values()}
    assert "MiniMaxH3SpeedCache" not in {node["class_type"] for node in graph.values()}
    assert MECHANISM == "h3_fast_renderer"


def test_native_audio_and_provider_tags():
    graph = _graph()
    assert graph["11"]["inputs"]["length"] == 362
    assert graph["11"]["inputs"]["width"] == 1376
    assert graph["11"]["inputs"]["height"] == 768
    assert graph["11"]["inputs"]["ref_image_size"] == "match"
    text = graph["10"]["inputs"]["value"]
    assert "<Picture 1> is Korri." in text
    assert "<Picture 2> is Mess hall." in text
    assert "<Video 1> is Previous segment." in text
    assert "<Audio 1> is the sound with that video." in text
    # The video soundtrack consumes Audio 1. The standalone clip is Audio 2.
    assert "<Audio 2> is Korri." in text
    assert text.endswith("Korri turns toward the door.")
    assert graph["15"]["class_type"] == "VAEDecodeAudio"
    assert graph["16"]["inputs"]["audio"] == ["15", 0]
    assert graph["11"]["inputs"]["ref_videos.ref_video_0"] == ["41", 0]
    assert graph["11"]["inputs"]["ref_video_audios.ref_video_audio_0"] == ["41", 1]


def test_identity_refs_outrank_the_last_frame():
    slots = [
        {"role": "character", "assetId": f"c{i}", "label": f"C{i}", "pictureIndex": i}
        for i in range(1, 10)
    ]
    planned = plan_references(
        slots,
        {"enabled": True, "priorAssetId": "vid", "lastFrameAssetId": "frame"},
    )
    assert len(planned["images"]) == 9
    assert all(item["assetId"] != "frame" for item in planned["images"])
    assert planned["videos"][0]["assetId"] == "vid"

    room = plan_references(
        [{"role": "character", "assetId": "c1", "label": "Korri", "pictureIndex": 1}],
        {"enabled": True, "priorAssetId": "vid", "lastFrameAssetId": "frame"},
    )
    assert [item["assetId"] for item in room["images"]] == ["c1", "frame"]
    assert room["images"][1]["label"] == "Last frame"


def test_continue_does_not_replace_identity_with_prior_video():
    planned = plan_references(
        [
            {"role": "character", "assetId": "korri", "label": "Korri", "pictureIndex": 1},
            {"role": "video", "assetId": "other", "label": "Clip", "pictureIndex": None, "videoIndex": 1},
        ],
        {"enabled": True, "priorAssetId": "prior"},
    )
    assert planned["images"][0]["assetId"] == "korri"
    assert [item["assetId"] for item in planned["videos"]] == ["prior", "other"]


def test_tail_frame_count_keeps_the_ending_grid():
    assert legal_tail_frame_count(2) == 39
    assert legal_tail_frame_count(3, at_least=True) == 73
    assert legal_frames(5) == 124
    assert legal_tail_frame_count(2) < legal_frames(5)
    assert legal_tail_frame_count(3, at_least=True) < legal_frames(5)


def test_tail_replaces_the_full_prior_video():
    planned = plan_references(
        [{"role": "character", "assetId": "korri", "label": "Korri", "pictureIndex": 1}],
        {
            "enabled": True,
            "priorAssetId": "full-clip",
            "tailAssetId": "tail-clip",
            "lastFrameAssetId": "frame",
            "h3Continuity": {"includeLastFrame": True},
        },
    )
    assert planned["videos"] == [{"assetId": "tail-clip", "label": "Ending"}]
    assert [item["assetId"] for item in planned["images"]] == ["korri", "frame"]


def test_last_frame_can_be_left_out_without_dropping_identity():
    planned = plan_references(
        [{"role": "character", "assetId": "korri", "label": "Korri", "pictureIndex": 1}],
        {
            "enabled": True,
            "priorAssetId": "full-clip",
            "lastFrameAssetId": "frame",
            "h3Continuity": {"includeLastFrame": False},
        },
    )
    assert [item["assetId"] for item in planned["images"]] == ["korri"]
    assert planned["videos"][0]["assetId"] == "full-clip"


def test_continuation_prompt_names_the_ending_and_its_sound():
    text = compile_provider_prompt(
        "She looks toward the camera.",
        [{"label": "Renkoka"}, {"label": "Mess hall"}, {"label": "Last frame"}],
        [{"label": "Ending"}],
        [],
        continuation=True,
        pair_video_audio=True,
        boundary="Renkoka is present, seated at the table.",
    )
    assert "Continue directly from the ending shown in <Video 1>." in text
    assert "Begin in that same framing, with the same positions and orientation." in text
    assert "<Audio 1> is the sound at that ending." in text
    assert "<Picture 3> is the visual state this shot begins from." in text
    assert "Motion starts there." in text
    assert "Renkoka is present, seated at the table." in text
    assert text.endswith("She looks toward the camera.")
    silent = build_h3_fast_workflow(
        prompt="She looks toward the camera.",
        filename_prefix="h3_fast_tail",
        seed=140011,
        width=1376,
        height=768,
        duration_sec=5,
        image_names=["renkoka.png"],
        image_labels=["Renkoka"],
        video_names=["tail.mp4"],
        video_labels=["Ending"],
        continuation=True,
        pair_video_audio=False,
    )
    assert "ref_video_audios.ref_video_audio_0" not in silent["11"]["inputs"]
    assert "Continue directly from the ending shown in <Video 1>." in silent["10"]["inputs"]["value"]
    assert "Begin in that same framing, with the same positions and orientation." in silent["10"]["inputs"]["value"]
    assert "<Audio 1>" not in silent["10"]["inputs"]["value"]


def test_prepend_prompt_names_the_opening_as_the_arrival():
    text = compile_provider_prompt(
        "Renkoka walks into the chamber.",
        [{"label": "Renkoka"}, {"label": "Arrival"}],
        [{"label": "Opening"}],
        [],
        continuation=False,
        pair_video_audio=True,
        boundary="At the end of this new shot, arrive at this opening: Renkoka stands facing the camera.",
        prepend=True,
    )
    assert "Continue directly from the ending shown in <Video 1>." not in text
    assert "Begin in that same framing" not in text
    assert "Do not begin in that opening." in text
    assert "End this shot there" in text
    assert "<Audio 1> is the sound at that opening." in text
    assert "<Picture 2> is the opening frame this shot must reach at the end." in text
    assert "The exact last picture" not in text
    assert text.endswith("Renkoka walks into the chamber.")
    english = compile_provider_prompt(
        "Renkoka walks into the chamber.",
        [{"label": "Renkoka"}],
        [{"label": "Opening"}],
        [],
        continuation=False,
        pair_video_audio=True,
        prepend=True,
        spoken_language="English",
    )
    assert "Any words in this new shot are spoken in English only." in english
    assert "Do not copy its language." in english


def test_refuses_empty_generation():
    with pytest.raises(ValueError, match="needs a character"):
        build_h3_fast_workflow(
            prompt="hello",
            filename_prefix="x",
            seed=1,
            width=1152,
            height=640,
            duration_sec=5,
            image_names=[],
        )
