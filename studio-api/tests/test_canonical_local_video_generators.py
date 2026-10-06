"""Canonical Adept UI local video architecture invariant.

LOCAL VIDEO SUPPORTED: MiniMax H3, MiniMax H3 Base Optimized, LTX 2.5,
and HunyuanVideo 1.5 Distilled.
RETIRED LOCAL: WAN, the old Hunyuan Video ids, LTX 2.3.
API VIDEO: separately supported and must remain present.
"""

from __future__ import annotations

from app.director_timeline_w46.generation.registry import get_registry
from app.hosted_providers import video_registry


def test_supported_local_video_generators_are_minimax_h3_and_ltx_25() -> None:
    assert video_registry.SUPPORTED_LOCAL_VIDEO_GENERATOR_IDS == {
        "minimax-h3",
        "minimax-h3-i2v-local",
        "minimax-h3-base-optimized",
        "ltx-2.5-full",
        "ltx-2.5-distilled",
        "ltx-2.5-comfy",
        "hunyuan-video-1.5-distilled",
    }
    assert video_registry.supported_local_video_ids() == video_registry.SUPPORTED_LOCAL_VIDEO_GENERATOR_IDS
    families = {
        row.family
        for row in video_registry.CORE_VIDEO_REGISTRY
        if row.locality == "local"
    }
    assert families == {"minimax", "ltx", "hunyuan"}
    versions = {
        row.version
        for row in video_registry.CORE_VIDEO_REGISTRY
        if row.locality == "local" and row.family == "ltx"
    }
    assert versions == {"2.5"}


def test_retired_local_video_generators_are_not_active() -> None:
    active_ids = {row.product_id for row in video_registry.CORE_VIDEO_REGISTRY}
    aliases = set(video_registry.product_aliases())
    descriptors = {row["id"] for row in video_registry.video_model_descriptors()}
    adapters = set(get_registry().known_ids())
    for retired in video_registry.RETIRED_LOCAL_VIDEO_GENERATOR_IDS:
        assert retired not in active_ids
        assert retired not in descriptors
        assert retired not in adapters
        assert video_registry.is_retired_local_video(retired)
    for alias in ("wan", "ltx", "hunyuan", "hunyuan15", "hunyuan13b"):
        assert alias not in aliases
        assert video_registry.is_retired_local_video(alias)


def test_api_video_generators_remain_separately_supported() -> None:
    hosted = video_registry.supported_hosted_video_ids()
    assert {
        "kling-kie",
        "kling-fal",
        "seedance-2.0",
        "seedance-2.0-mini",
        "seedance-2.5",
        "seedance-kie",
        "veo-fal",
        "veo-kie",
        "runway",
    } <= hosted
    local = video_registry.supported_local_video_ids()
    assert hosted.isdisjoint(local)


def test_timeline_adapters_keep_h3_r2v_and_ltx25() -> None:
    registry = get_registry()
    h3 = registry.capabilities("minimax-h3")
    assert h3.supportsReferenceToVideo is True
    assert h3.supportsTextToVideo is False
    assert h3.supportsImageToVideo is False
    ltx = registry.capabilities("ltx-2.5")
    assert ltx.id == "ltx-2.5-distilled"
    assert ltx.supportsTextToVideo is True
    assert ltx.supportsReferenceToVideo is False
    assert ltx.supportsThreeFrame is False
    assert ltx.continuationMode == "hard"
    for retired in ("wan-local", "ltx-local", "hunyuan-video-1.5-local", "hunyuan-video-13b-local"):
        try:
            registry.resolve_id(retired)
        except Exception:
            continue
        raise AssertionError(f"retired generator {retired} remains resolvable")
