"""Seedance 2.0 and 2.5 are distinct hosted identities — no collapse, no remap."""

from __future__ import annotations

import pytest


def test_create_engines_exposes_versioned_seedance_not_generic() -> None:
    from app.production_control.generator_authority import list_create_engines

    rows = list_create_engines()
    ids = [row["id"] for row in rows]
    labels = [row["label"] for row in rows]
    assert "seedance-2.0" in ids
    assert "seedance-2.5" in ids
    assert "seedance-fal" not in ids
    assert "fal_seedance" not in ids
    assert "auto" in ids
    assert "minimax-h3" in ids
    assert "ltx-2.5" in ids
    assert "ltx" not in ids
    assert "wan" not in ids
    assert any("Seedance 2.0" == label for label in labels)
    assert any("Seedance 2.5" == label for label in labels)
    assert not any(label.strip() == "Seedance" for label in labels)


def test_seedance_versions_route_to_distinct_fal_model_ids() -> None:
    from app.fal_catalog import build_fal_arguments, build_seedance_r2v_arguments

    t2v_20, _ = build_fal_arguments(
        engine="seedance-2.0",
        prompt="a quiet porch",
        negative="",
        image_url=None,
        end_image_url=None,
        duration_sec=5,
        width=1280,
        height=720,
        seed=-1,
    )
    t2v_25, _ = build_fal_arguments(
        engine="seedance-2.5",
        prompt="a quiet porch",
        negative="",
        image_url=None,
        end_image_url=None,
        duration_sec=5,
        width=1280,
        height=720,
        seed=-1,
    )
    assert t2v_20 == "bytedance/seedance-2.0/text-to-video"
    assert t2v_25 == "bytedance/seedance-2.5/text-to-video"

    r2v_20, _ = build_seedance_r2v_arguments(
        prompt="walk",
        image_urls=["https://example.test/a.png"],
        video_urls=["https://example.test/a.mp4"],
        duration_sec=5,
        aspect_ratio="16:9",
        resolution="720p",
        seed=-1,
        engine="seedance-2.0",
    )
    r2v_25, _ = build_seedance_r2v_arguments(
        prompt="walk",
        image_urls=["https://example.test/a.png"],
        video_urls=["https://example.test/a.mp4"],
        duration_sec=5,
        aspect_ratio="16:9",
        resolution="720p",
        seed=-1,
        engine="seedance-2.5",
    )
    assert r2v_20 == "bytedance/seedance-2.0/reference-to-video"
    assert r2v_25 == "bytedance/seedance-2.5/reference-to-video"


def test_legacy_seedance_aliases_are_2_0_only() -> None:
    from app.fal_catalog import build_fal_arguments, seedance_product_id
    from app.production_control.video_readiness import adapter_for_product, canonical_product_id

    for token in ("seedance-fal", "seedance-api", "fal_seedance"):
        assert canonical_product_id(token) == "seedance-2.0"
        assert seedance_product_id(token) == "seedance-2.0"
        assert adapter_for_product(token) == "seedance-2.0"
        model_id, _ = build_fal_arguments(
            engine=token,
            prompt="legacy",
            negative="",
            image_url=None,
            end_image_url=None,
            duration_sec=4,
            width=1280,
            height=720,
            seed=-1,
        )
        assert model_id.startswith("bytedance/seedance-2.0/")
    assert canonical_product_id("seedance-2.5") == "seedance-2.5"
    assert adapter_for_product("seedance-2.5") == "seedance-2.5"
    assert adapter_for_product("seedance-2.5") != adapter_for_product("seedance-2.0")


def test_ltx_25_does_not_bind_ltx_local() -> None:
    from app.director_timeline_w46.generation.registry import GeneratorNotFoundError, get_registry
    from app.production_control.video_readiness import adapter_for_product

    assert adapter_for_product("ltx-2.5-distilled") == "ltx-2.5-distilled"
    assert adapter_for_product("ltx-2.5") == "ltx-2.5-distilled"
    # ltx-local is retired and is no longer advertised or resolvable.
    assert adapter_for_product("ltx-local") is None
    registry = get_registry()
    assert registry.resolve_id("ltx-2.5-distilled") == "ltx-2.5-distilled"
    assert registry.resolve_id("ltx-2.5") == "ltx-2.5-distilled"
    with pytest.raises(GeneratorNotFoundError):
        registry.resolve_id("ltx-local")
    assert registry.resolve_id("seedance-2.5") == "seedance-2.5"
    assert registry.resolve_id("seedance-fal") == "seedance-2.0"


def test_auto_select_never_picks_hosted_seedance() -> None:
    from types import SimpleNamespace

    from app.engine_recommend import recommend_engine

    rec = recommend_engine(
        project=SimpleNamespace(vram_gb=32, global_prompt=""),
        scene=SimpleNamespace(duration_sec=5, lipsync_enabled=0, start_asset_id=None, prompt="cinematic porch"),
        prompt="cinematic porch",
    )
    assert rec["engineId"] == "minimax-h3"
    assert rec["local"] is True
    assert rec["engineId"] not in {"seedance-2.0", "seedance-2.5", "fal_seedance"}


def test_seedance_lineage_fields_on_submit() -> None:
    from app.director_timeline_w46.generation.adapters.seedance_api import (
        Seedance25ApiAdapter,
        SeedanceApiAdapter,
    )
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    req = TimelineGenerationRequest(
        projectId="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        sceneId="scene-1",
        batchBlockId="batch-1",
        executionSnapshotId="snap-1",
        generatorId="seedance-2.5",
        prompt="lineage check",
        duration=5,
        providerOptions={"testInjectResult": {"status": "completed", "outputAssetIds": ["a1"]}},
    )
    sub = Seedance25ApiAdapter().submit(req)
    assert sub.generatorId == "seedance-2.5"
    assert sub.providerMetadata["resolvedEngineId"] == "seedance-2.5"
    assert sub.providerMetadata["modelVersion"] == "2.5"
    assert sub.providerMetadata["requestedEngineId"] == "seedance-2.5"

    req20 = req.model_copy(update={"generatorId": "seedance-2.0"})
    sub20 = SeedanceApiAdapter().submit(req20)
    assert sub20.generatorId == "seedance-2.0"
    assert sub20.providerMetadata["modelVersion"] == "2.0"


def test_seedance_readiness_is_independent() -> None:
    from app.production_control.video_readiness import VideoFacts, derive_video_readiness

    ready_20, _, exec_20 = derive_video_readiness(
        VideoFacts(
            product_id="seedance-2.0",
            locality="hosted",
            adapter_id="seedance-2.0",
            adapter_registered=True,
            live_submit=True,
            credentials_ok=True,
        )
    )
    blocked_25, _, exec_25 = derive_video_readiness(
        VideoFacts(
            product_id="seedance-2.5",
            locality="hosted",
            adapter_id="seedance-2.5",
            adapter_registered=True,
            live_submit=True,
            credentials_ok=False,
            credentials_reason="Provider API Key Missing",
        )
    )
    assert ready_20 in {"Ready", "Testing"}
    assert exec_25 is False
    assert blocked_25 == "Requires Setup"
    assert exec_20 is True or ready_20 == "Testing"


def test_knowledge_files_are_versioned() -> None:
    from app.codirector.knowledgebase.video_generators import load_video_generator_knowledge

    v20 = load_video_generator_knowledge("seedance-2.0")
    v25 = load_video_generator_knowledge("seedance-2.5")
    assert v20.loaded and v20.spec_path.name == "seedance-2.0.md"
    assert v25.loaded and v25.spec_path.name == "seedance-2.5.md"
    assert "does **not** expose Seedance 2.5" not in v20.spec_path.read_text(encoding="utf-8")
