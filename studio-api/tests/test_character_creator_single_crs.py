"""Character Creator single canonical CRS routing contract."""

from __future__ import annotations

from app.character_identity.visual_sheet import (
    _build_candidate_routing_plan,
    _coerce_single_crs_sources,
)


def test_qwen_is_default_crs_source() -> None:
    sources = _coerce_single_crs_sources(None)
    assert sources["local"][0]["family"] == "qwen2512"
    assert sources["api"] is None


def test_gpt_image_2_selection_is_honored() -> None:
    sources = _coerce_single_crs_sources(
        {
            "local": [{"family": "qwen2512", "enabled": False, "batchCount": 3}],
            "api": [
                {
                    "model": "gpt-image-2-kie",
                    "providerId": "kie",
                    "modelId": "gpt-image-2",
                    "enabled": True,
                    "batchCount": 4,
                }
            ],
        }
    )
    assert sources["api"][0]["modelId"] == "gpt-image-2"
    assert sources["api"][0]["batchCount"] == 1
    assert sources["local"] is None


def test_parallel_generators_collapse_to_one_slot() -> None:
    plan = _build_candidate_routing_plan(
        candidate_count=4,
        reference_asset_id=None,
        visual_style="cinematic_anime",
        generator_sources={
            "local": [
                {"family": "qwen2512", "enabled": True, "batchCount": 2},
                {"family": "illustrious", "enabled": True, "batchCount": 2},
            ],
            "api": [
                {
                    "model": "nano-banana-kie",
                    "providerId": "kie",
                    "modelId": "nano-banana-pro",
                    "enabled": True,
                    "batchCount": 2,
                }
            ],
        },
    )
    assert len(plan) == 1
    assert plan[0]["batchOf"] == 1


def test_illustrious_or_nano_banana_cannot_stay_as_crs_source() -> None:
    sources = _coerce_single_crs_sources(
        {
            "local": [{"family": "illustrious", "enabled": True, "batchCount": 2}],
            "api": [
                {
                    "model": "nano-banana-kie",
                    "providerId": "kie",
                    "modelId": "nano-banana-pro",
                    "enabled": True,
                    "batchCount": 2,
                }
            ],
        }
    )
    assert sources["local"][0]["family"] == "qwen2512"
    assert sources["api"] is None
