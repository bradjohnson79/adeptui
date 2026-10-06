"""Unit proof: MiniMax H3 video+audio reference wiring."""
from __future__ import annotations

from app.workflows.h3_ref2v_builder import build_h3_ref2v, assert_h3_ref2v_graph, h3_ref_video_links, h3_ref_audio_links
from app.director_timeline_w46.generation.adapters.minimax_h3_local import _capabilities, MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.direct_reference import (
    DirectReferencePayload,
    DirectReferenceItem,
    _map_sockets,
    payload_to_r2v_slots,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.r2v import R2VSlot, CanonicalR2VRequest
from app.scene_references.sheet_tags import PREFIX_AUDIO, classify_asset
from types import SimpleNamespace


def test_h3_caps_match_live_comfy_av_limits():
    caps = _capabilities()
    assert caps.supportsVideoReferences is True
    assert caps.maximumReferenceVideos == 3
    assert caps.supportsAudioReferences is True
    assert caps.maximumReferenceAudio == 3
    assert caps.supportsImageAndVideoTogether is True


def test_h3_builder_wires_loadvideo_and_ref_videos():
    graph = build_h3_ref2v(
        prompt="TP authority",
        ref_comfy_names=["studio/hero.png"],
        filename_prefix="t/h3",
        ref_video_comfy_names=["studio/a.mp4", "studio/b.mp4"],
        ref_audio_comfy_names=["studio/v.wav"],
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=["studio/hero.png"],
        expected_video_names=["studio/a.mp4", "studio/b.mp4"],
        expected_audio_names=["studio/v.wav"],
    )
    vids = h3_ref_video_links(graph)
    auds = h3_ref_audio_links(graph)
    assert list(vids.keys()) == ["ref_video_0", "ref_video_1"]
    assert list(auds.keys()) == ["ref_audio_0"]
    loads = [n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "LoadVideo"]
    assert {n["inputs"]["file"] for n in loads} == {"studio/a.mp4", "studio/b.mp4"}
    # Timed Prompt bytes land on PrimitiveStringMultiline
    prims = [
        n["inputs"]["value"]
        for n in graph.values()
        if isinstance(n, dict) and n.get("class_type") == "PrimitiveStringMultiline"
    ]
    assert "TP authority" in prims


def test_h3_builder_refuses_fourth_video_and_audio():
    try:
        build_h3_ref2v(
            prompt="x",
            ref_comfy_names=["studio/hero.png"],
            filename_prefix="t/h3",
            ref_video_comfy_names=["a.mp4", "b.mp4", "c.mp4", "d.mp4"],
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "at most 3 reference videos" in str(e)
    try:
        build_h3_ref2v(
            prompt="x",
            ref_comfy_names=["studio/hero.png"],
            filename_prefix="t/h3",
            ref_audio_comfy_names=["a.wav", "b.wav", "c.wav", "d.wav"],
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "at most 3 reference audios" in str(e)


def test_h3_direct_reference_maps_video_audio_and_blocks_fourth():
    payload = DirectReferencePayload(
        projectId="p", sceneId="s", batchId="b", generatorId="minimax-h3"
    )
    payload.characters.append(
        DirectReferenceItem(kind="character", canonicalTag="@Hero", bindingId="c1", assetId="img1", sourcePath="/i.png")
    )
    for i in range(4):
        payload.motion.append(
            DirectReferenceItem(
                kind="motion",
                canonicalTag=f"*V{i}",
                bindingId=f"v{i}",
                assetId=f"vid{i}",
                assetType="video",
                sourcePath=f"/v{i}.mp4",
            )
        )
        payload.audio.append(
            DirectReferenceItem(
                kind="audio",
                canonicalTag=f"{PREFIX_AUDIO}A{i}",
                bindingId=f"a{i}",
                assetId=f"aud{i}",
                assetType="audio",
                sourcePath=f"/a{i}.wav",
            )
        )
    _map_sockets(payload)
    assert [s.socket for s in payload.sockets if s.socket.startswith("ref_video_")] == [
        "ref_video_0",
        "ref_video_1",
        "ref_video_2",
    ]
    assert [s.socket for s in payload.sockets if s.socket.startswith("ref_audio_")] == [
        "ref_audio_0",
        "ref_audio_1",
        "ref_audio_2",
    ]
    assert any(b.canonicalTag == "*V3" and b.reason == "over_limit" for b in payload.blocked)
    assert any(b.canonicalTag.endswith("A3") and b.reason == "over_limit" for b in payload.blocked)
    slots = payload_to_r2v_slots(payload)
    videos = [s for s in slots if s.role == "video"]
    audios = [s for s in slots if s.role == "audio"]
    assert [s.videoIndex for s in videos] == [1, 2, 3]
    assert [s.audioIndex for s in audios] == [1, 2, 3]


def test_h3_adapter_refuses_four_r2v_video_slots():
    slots = [
        R2VSlot(role="character", assetId="img0", label="@Hero", pictureIndex=1),
        R2VSlot(role="video", assetId="v0", label="*A", videoIndex=1),
        R2VSlot(role="video", assetId="v1", label="*B", videoIndex=2),
        R2VSlot(role="video", assetId="v2", label="*C", videoIndex=3),
        R2VSlot(role="video", assetId="v3", label="*D", videoIndex=4),
    ]
    canon = CanonicalR2VRequest(slots=slots, mechanism="h3_ref2va", promptPrefix="TP", tensorSlotCount=5)
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt="TP",
        duration=5.0,
        fallbackAllowed=False,
        providerOptions={"r2v": canon.to_job_dict()},
    )
    result = MiniMaxH3LocalAdapter().validate(req)
    assert result.ok is False
    assert any("video" in e.lower() and "3" in e for e in result.errors)


def test_classify_library_audio_asset():
    asset = SimpleNamespace(kind="audio", tag="VoiceClip", filename="voice.wav", labels_json=[], prompt_meta_json="")
    classified = classify_asset(asset)
    assert classified.media_kind == "audio"
    assert classified.reference_type == "audio"
    assert classified.prefix == PREFIX_AUDIO
