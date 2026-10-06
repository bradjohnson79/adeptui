"""Addendum: H3 Video/Audio natural tags, duration guards, solo-audio refuse, mixed + counts."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter, _capabilities
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.direct_reference import (
    DirectReferenceItem,
    DirectReferencePayload,
    _map_sockets,
    payload_to_r2v_slots,
)
from app.director_timeline_w46.generation.r2v import CanonicalR2VRequest, R2VSlot
from app.director_timeline_w46.generation.runtime_dependency_preflight import (
    H3_REF_DURATION_MAX_SEC,
    H3_REF_DURATION_MIN_SEC,
    _validate_h3_av_duration_guards,
)
from app.director_timeline_w46.generation.semantic_contract import (
    apply_bound_reference_tokens,
    compile_h3_av_natural_tags,
)
from app.workflows.h3_ref2v_builder import (
    assert_h3_ref2v_graph,
    build_h3_ref2v,
    h3_ref_audio_links,
    h3_ref_image_links,
    h3_ref_video_links,
)


def _slot(role: str, asset_id: str, *, picture=None, video=None, audio=None, label=""):
    return R2VSlot(
        role=role,  # type: ignore[arg-type]
        assetId=asset_id,
        label=label or asset_id,
        pictureIndex=picture,
        videoIndex=video,
        audioIndex=audio,
    )


def test_compile_natural_av_tags_only_when_assets_wired():
    slots = [
        _slot("character", "img1", picture=1, label="@Hero"),
        _slot("video", "vid1", video=1, label="*Walk"),
        _slot("audio", "aud1", audio=1, label="&Voice"),
        _slot("video", "vid2", video=2, label="*Run"),
    ]
    prompt = "Action with @Video1 and @Audio1 then @Video2. Keep @Hero."
    out = compile_h3_av_natural_tags(prompt, slots)
    assert "<Video 1>" in out
    assert "<Audio 1>" in out
    assert "<Video 2>" in out
    assert "@Hero" in out  # character sheet tag untouched
    # Unwired index stays natural (no invent)
    lonely = compile_h3_av_natural_tags("See @Video3 alone", slots)
    assert "@Video3" in lonely
    assert "<Video 3>" not in lonely


def test_apply_bound_reference_tokens_compiles_av_and_keeps_tp_action():
    slots = [
        _slot("character", "img1", picture=1, label="@Addex"),
        _slot("video", "vid1", video=1, label="*Walk"),
        _slot("audio", "aud1", audio=1, label="&Voice"),
    ]
    authored = "Addex walks. Use @Video1 with @Audio1."
    out = apply_bound_reference_tokens(authored, slots)
    assert "Addex walks" in out
    assert "<Video 1>" in out
    assert "<Audio 1>" in out
    assert "@Video1" not in out
    assert "@Audio1" not in out


@pytest.mark.parametrize("n", [1, 2, 3])
def test_h3_graph_simultaneous_video_counts(n):
    videos = [f"studio/v{i}.mp4" for i in range(n)]
    graph = build_h3_ref2v(
        prompt="TP with " + " ".join(f"@Video{i+1}" for i in range(n)),
        ref_comfy_names=["studio/hero.png"],
        filename_prefix="t/h3",
        ref_video_comfy_names=videos,
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=["studio/hero.png"],
        expected_video_names=videos,
    )
    assert len(h3_ref_video_links(graph)) == n


@pytest.mark.parametrize("n", [1, 2, 3])
def test_h3_graph_simultaneous_audio_counts(n):
    audios = [f"studio/a{i}.wav" for i in range(n)]
    graph = build_h3_ref2v(
        prompt="TP with " + " ".join(f"@Audio{i+1}" for i in range(n)),
        ref_comfy_names=["studio/hero.png"],
        filename_prefix="t/h3",
        ref_audio_comfy_names=audios,
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=["studio/hero.png"],
        expected_audio_names=audios,
    )
    assert len(h3_ref_audio_links(graph)) == n


def test_mixed_character_video_audio_ordering_and_assets():
    payload = DirectReferencePayload(
        projectId="p", sceneId="s", batchId="b", generatorId="minimax-h3-t2v-local"
    )
    payload.characters.append(
        DirectReferenceItem(kind="character", canonicalTag="@Hero", bindingId="c1", assetId="img_hero", sourcePath="/hero.png")
    )
    payload.motion.append(
        DirectReferenceItem(kind="motion", canonicalTag="*Walk", bindingId="v1", assetId="vid_walk", assetType="video", sourcePath="/w.mp4")
    )
    payload.audio.append(
        DirectReferenceItem(kind="audio", canonicalTag="&Voice", bindingId="a1", assetId="aud_voice", assetType="audio", sourcePath="/v.wav")
    )
    _map_sockets(payload)
    slots = payload_to_r2v_slots(payload)
    assert [s.role for s in slots] == ["character", "video", "audio"]
    assert slots[0].assetId == "img_hero" and slots[0].pictureIndex == 1
    assert slots[1].assetId == "vid_walk" and slots[1].videoIndex == 1
    assert slots[2].assetId == "aud_voice" and slots[2].audioIndex == 1
    compiled = apply_bound_reference_tokens("Hero uses @Video1 and @Audio1.", slots)
    assert "<Video 1>" in compiled and "<Audio 1>" in compiled
    graph = build_h3_ref2v(
        prompt=compiled,
        ref_comfy_names=["studio/hero.png"],
        filename_prefix="t/h3",
        ref_video_comfy_names=["studio/walk.mp4"],
        ref_audio_comfy_names=["studio/voice.wav"],
    )
    assert list(h3_ref_image_links(graph).keys()) == ["ref_image_0"]
    assert list(h3_ref_video_links(graph).keys()) == ["ref_video_0"]
    assert list(h3_ref_audio_links(graph).keys()) == ["ref_audio_0"]


def test_duration_guard_each_and_totals():
    class _DB:
        def __init__(self, assets):
            self._assets = assets

        def get(self, _cls, asset_id):
            return self._assets.get(asset_id)

    assets = {
        "ok": SimpleNamespace(duration_sec=5.0, prompt_meta_json=""),
        "short": SimpleNamespace(duration_sec=1.0, prompt_meta_json=""),
        "long": SimpleNamespace(duration_sec=16.0, prompt_meta_json=""),
        "a": SimpleNamespace(duration_sec=6.0, prompt_meta_json=""),
        "b": SimpleNamespace(duration_sec=6.0, prompt_meta_json=""),
        "c": SimpleNamespace(duration_sec=6.0, prompt_meta_json=""),
    }
    db = _DB(assets)
    assert _validate_h3_av_duration_guards(
        db,
        [{"role": "video", "assetId": "ok", "videoIndex": 1, "label": "*Ok"}],
    ) is None
    bad_short = _validate_h3_av_duration_guards(
        db,
        [{"role": "video", "assetId": "short", "videoIndex": 1, "label": "*Short"}],
    )
    assert bad_short and bad_short["error"] == "H3_REF_DURATION_OUT_OF_RANGE"
    assert str(int(H3_REF_DURATION_MIN_SEC)) in bad_short["message"]
    bad_long = _validate_h3_av_duration_guards(
        db,
        [{"role": "audio", "assetId": "long", "audioIndex": 1, "label": "&Long"}],
    )
    assert bad_long and bad_long["error"] == "H3_REF_DURATION_OUT_OF_RANGE"
    assert str(int(H3_REF_DURATION_MAX_SEC)) in bad_long["message"]
    bad_total = _validate_h3_av_duration_guards(
        db,
        [
            {"role": "video", "assetId": "a", "videoIndex": 1, "label": "*A"},
            {"role": "video", "assetId": "b", "videoIndex": 2, "label": "*B"},
            {"role": "video", "assetId": "c", "videoIndex": 3, "label": "*C"},
        ],
    )
    assert bad_total and bad_total["error"] == "H3_REF_VIDEO_DURATION_TOTAL"


def test_adapter_refuses_audio_without_visual():
    slots = [_slot("audio", "aud1", audio=1, label="&Only")]
    canon = CanonicalR2VRequest(slots=slots, mechanism="h3_ref2va", promptPrefix="TP", tensorSlotCount=0)
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt="TP @Audio1",
        duration=5.0,
        fallbackAllowed=False,
        providerOptions={"r2v": canon.to_job_dict()},
    )
    result = MiniMaxH3LocalAdapter().validate(req)
    assert result.ok is False
    assert any("sole" in e.lower() or "accompany" in e.lower() for e in result.errors)


def test_caps_still_three():
    caps = _capabilities()
    assert caps.maximumReferenceVideos == 3
    assert caps.maximumReferenceAudio == 3
