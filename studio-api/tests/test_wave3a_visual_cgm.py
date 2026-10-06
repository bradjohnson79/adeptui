"""Wave 3A — Visual image=reference + CanonicalGenerationMedia + bleed-control."""
from __future__ import annotations

from app.director_timeline import DirectorTimeline, ImageClip, TimelineClip
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.generation.adapters.minimax_h3_local import (
    map_canonical_generation_media_to_ref_sockets,
)
from app.director_timeline_w46.generation.canonical_generation_media import (
    CanonicalGenerationMedia,
    classify_visual_placement,
    map_cgm_images_to_h3_ref_sockets,
    persist_media_type_on_clip,
    visual_image_clips_to_cgm,
)
from app.director_timeline_w46.migration_reconcile import reconcile_legacy_to_master
from app.director_timeline_w46.reconcile import reconcile_legacy_image_anchors


def test_wave3a_classify_image_is_reference_video_is_take():
    img = classify_visual_placement(asset_id="a1", kind="image", clip_id="c1")
    assert img.mediaType == "image"
    assert img.role == "reference"
    vid = classify_visual_placement(asset_id="a2", kind="video", clip_id="c2")
    assert vid.mediaType == "video"
    assert vid.role == "visual_take"


def test_wave3a_persist_media_type_on_clip():
    stamped = persist_media_type_on_clip({"id": "x", "asset_id": "a"}, "image")
    assert stamped["mediaType"] == "image"
    assert stamped["media_type"] == "image"


def test_wave3a_cgm_maps_to_h3_ref_image_sockets():
    items = [
        CanonicalGenerationMedia(assetId="img0", mediaType="image", role="reference"),
        CanonicalGenerationMedia(assetId="img1", mediaType="image", role="reference"),
        CanonicalGenerationMedia(assetId="take", mediaType="video", role="visual_take"),
    ]
    sockets = map_cgm_images_to_h3_ref_sockets(items)
    assert [s["socket"] for s in sockets] == ["ref_image_0", "ref_image_1"]
    assert all(s["mediaType"] == "image" for s in sockets)
    # Adapter-owned mapper
    assert map_canonical_generation_media_to_ref_sockets(items) == sockets


def test_wave3a_visual_image_clips_to_cgm_reference_bearing():
    clips = [
        ImageClip(id="i1", asset_id="asset_A", start=0.0, length=2.0, role="guide", media_type="image"),
        TimelineClip(id="v1", asset_id="asset_V", start=0.0, length=5.0, media_type="video"),
    ]
    cgm = visual_image_clips_to_cgm(clips)
    assert len(cgm) == 1
    assert cgm[0].assetId == "asset_A"
    assert cgm[0].role == "reference"
    assert cgm[0].mediaType == "image"


def test_wave3a_reconcile_does_not_inject_visual_images_as_source_anchors():
    master = SceneTimelineMaster()
    master.batchBlocks.append(
        BatchBlock(
            id="bb1",
            sceneId="sc",
            order=0,
            label="B1",
            duration=DurationState(plannedDuration=5.0),
        )
    )
    tl = DirectorTimeline(
        image_clips=[
            ImageClip(
                id="img_guide",
                asset_id="asset_VIS",
                start=0.0,
                length=2.0,
                role="guide",
                media_type="image",
            )
        ]
    )
    assert reconcile_legacy_to_master(master, tl) is False
    assert master.batchBlocks[0].sourceAnchors == []


def test_wave3a_reconcile_cleans_stale_managed_keeps_explicit_start():
    master = SceneTimelineMaster()
    master.batchBlocks.append(
        BatchBlock(
            id="bb1",
            sceneId="sc",
            order=0,
            label="B1",
            duration=DurationState(plannedDuration=5.0),
            sourceAnchors=[
                TimelineVisualAnchor(kind="image", assetId="U", label="Start", atTime=0.0),
                TimelineVisualAnchor(kind="image", assetId="X", label="legacy:old", atTime=0.0),
            ],
        )
    )
    clips = [ImageClip(id="keep", asset_id="K", start=0.0, length=5.0, role="guide", media_type="image")]
    assert reconcile_legacy_image_anchors(master, clips) is True
    labels = {a.label for a in master.batchBlocks[0].sourceAnchors}
    assert "Start" in labels
    assert "legacy:old" not in labels
    # Still no inject of keep
    assert "legacy:keep" not in labels
