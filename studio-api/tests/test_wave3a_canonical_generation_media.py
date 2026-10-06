#"""Wave 3A - CanonicalGenerationMedia + bleed fence + deposit compatibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.director_timeline_w46.generation.canonical_generation_media import (
    CanonicalGenerationMedia,
    classify_visual_placement,
    map_cgm_images_to_h3_ref_sockets,
    persist_media_type_on_clip,
    visual_image_clips_to_cgm,
)


def test_classify_image_is_reference_not_visual_take():
    m = classify_visual_placement(asset_id="a1", kind="image", source_surface="library")
    assert m.mediaType == "image"
    assert m.role == "reference"
    assert m.assetId == "a1"


def test_classify_video_is_visual_take():
    m = classify_visual_placement(asset_id="v1", kind="video", source_surface="export")
    assert m.mediaType == "video"
    assert m.role == "visual_take"


def test_classify_rejects_empty_asset():
    with pytest.raises(ValueError, match="ASSET_ID_REQUIRED"):
        classify_visual_placement(asset_id="  ", kind="image")


def test_h3_socket_map_native_ref_image_N():
    items = [
        CanonicalGenerationMedia(assetId="i0", mediaType="image", role="reference"),
        CanonicalGenerationMedia(assetId="v0", mediaType="video", role="visual_take"),
        CanonicalGenerationMedia(assetId="i1", mediaType="image", role="reference"),
    ]
    sockets = map_cgm_images_to_h3_ref_sockets(items, maximum=9)
    assert [s["socket"] for s in sockets] == ["ref_image_0", "ref_image_1"]
    assert sockets[0]["assetId"] == "i0"
    assert sockets[1]["assetId"] == "i1"


def test_visual_image_clips_to_cgm_reference_role():
    clips = [
        {"id": "c1", "asset_id": "img1", "mediaType": "image", "label": "Guide"},
        {"id": "c2", "asset_id": "vid1", "mediaType": "video"},
        {"id": "c3", "asset_id": None, "mediaType": "image"},
    ]
    out = visual_image_clips_to_cgm(clips)
    assert len(out) == 1
    assert out[0].role == "reference"
    assert out[0].assetId == "img1"


def test_persist_media_type_stamps_both_keys():
    stamped = persist_media_type_on_clip({"id": "x", "asset_id": "v"}, "video")
    assert stamped["mediaType"] == "video"
    assert stamped["media_type"] == "video"


def test_reconcile_legacy_image_anchors_does_not_inject():
    from app.director_timeline_w46.contracts import (
        BatchBlock,
        DurationState,
        SceneTimelineMaster,
        TimelineVisualAnchor,
    )
    from app.director_timeline_w46.reconcile import reconcile_legacy_image_anchors

    class Clip:
        def __init__(self, cid, start=0.0, length=2.0):
            self.id = cid
            self.start = start
            self.length = length

    master = SceneTimelineMaster(
        batchBlocks=[
            BatchBlock(
                id="b1",
                sceneId="s1",
                order=0,
                duration=DurationState(plannedDuration=5.0),
                sourceAnchors=[
                    TimelineVisualAnchor(kind="image", assetId="keep-user", label="Start"),
                    TimelineVisualAnchor(kind="image", assetId="stale", label="legacy:gone"),
                ],
            )
        ]
    )
    changed = reconcile_legacy_image_anchors(master, [Clip("alive")])
    assert changed is True
    labels = [a.label for a in master.batchBlocks[0].sourceAnchors]
    assert "Start" in labels
    assert "legacy:gone" not in labels
    assert not any(str(a.label or "").startswith("legacy:alive") for a in master.batchBlocks[0].sourceAnchors)


def test_omni_visual_export_deposit_path_unchanged_video_clips():
    from app.director_timeline_w46.generation import omni_visual_export as ove

    src = Path(ove.__file__).read_text(encoding="utf-8")
    assert "video_clips" in src
    assert "media_mode" in src
