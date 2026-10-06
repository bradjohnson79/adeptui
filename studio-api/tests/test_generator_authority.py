"""One product-level generator join — not a fourth catalog."""

from __future__ import annotations

import pytest

from app.production_control.video_readiness import VideoFacts, derive_video_readiness


def test_canonical_aliases_keep_distinct_products() -> None:
    from app.production_control.generator_authority import canonical_product_id

    assert canonical_product_id("kling-kie") == "kling-kie"
    assert canonical_product_id("kling-fal") == "kling-fal"
    assert canonical_product_id("seedance-kie") == "seedance-kie"
    assert canonical_product_id("seedance-fal") == "seedance-2.0"
    assert canonical_product_id("fal_seedance") == "seedance-2.0"
    assert canonical_product_id("seedance-2.5") == "seedance-2.5"
    assert canonical_product_id("fal_seedance_25") == "seedance-2.5"
    assert canonical_product_id("minimax-h3") == "minimax-h3"
    assert canonical_product_id("minimax-h3-t2v-local") == "minimax-h3"
    assert canonical_product_id("minimax-h3-i2v") == "minimax-h3-i2v-local"
    assert canonical_product_id("ltx-2.5") == "ltx-2.5-distilled"
    assert canonical_product_id("ltx-2.5-distilled") == "ltx-2.5-distilled"
    assert canonical_product_id("ltx-2.5-full") == "ltx-2.5-full"


def test_mocks_are_dropped_from_production() -> None:
    from app.production_control.generator_authority import apply_authority_to_model

    assert (
        apply_authority_to_model(
            {
                "id": "openai-compat:demo:mock-chat-1",
                "modality": "llm",
                "label": "Mock",
                "locality": "hosted",
                "capabilityLabel": "Available",
                "executable": True,
            }
        )
        is None
    )


def test_derived_readiness_states() -> None:
    ready, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="ltx-2.5-distilled",
            locality="local",
            adapter_id="ltx-2.5-distilled",
            adapter_registered=True,
            live_submit=True,
            checkpoint_ok=True,
            runtime_ok=True,
            nodes_ok=True,
            vram_ok=True,
        )
    )
    assert ready == "Ready"
    assert executable is True
    assert reason == ""

    offline, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="ltx-2.5-distilled",
            locality="local",
            adapter_id="ltx-2.5-distilled",
            adapter_registered=True,
            live_submit=True,
            checkpoint_ok=True,
            runtime_ok=False,
            runtime_reason="Comfy Runtime Offline",
            nodes_ok=True,
        )
    )
    assert offline == "Runtime Offline"
    assert executable is False
    assert "Comfy Runtime Offline" in reason

    offline_h3, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="minimax-h3",
            locality="local",
            adapter_id="minimax-h3-t2v-local",
            adapter_registered=True,
            live_submit=True,
            checkpoint_ok=True,
            runtime_ok=False,
            runtime_reason="Comfy Runtime Offline — MiniMax Route A is not ready",
        )
    )
    assert offline_h3 == "Runtime Offline"
    assert executable is False
    assert "Route A" in reason

    blocked_h3, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="minimax-h3",
            locality="local",
            adapter_id="minimax-h3-t2v-local",
            adapter_registered=True,
            live_submit=True,
            checkpoint_ok=True,
            runtime_ok=True,
            nodes_ok=True,
            admission_ok=False,
            admission_reason="GPU admission — Desktop Comfy holds the GPU; MiniMax Route A requires handoff",
        )
    )
    assert blocked_h3 == "Testing"
    assert executable is False
    assert "GPU admission" in reason

    missing, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="ltx-2.5-distilled",
            locality="local",
            adapter_id="ltx-2.5-distilled",
            adapter_registered=True,
            live_submit=True,
            checkpoint_ok=False,
            checkpoint_reason="Checkpoint Missing — ltx_2_5_checkpoint",
        )
    )
    assert missing == "Requires Setup"
    assert executable is False


def test_ltx_25_distilled_is_ready_when_live_facts_pass() -> None:
    readiness, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="ltx-2.5-distilled",
            locality="local",
            adapter_id="ltx-2.5-distilled",
            adapter_registered=True,
            live_submit=True,
            checkpoint_ok=True,
            runtime_ok=True,
            nodes_ok=True,
            vram_ok=True,
        )
    )
    assert readiness == "Ready"
    assert executable is True
    assert reason == ""


def test_ltx_25_full_stays_testing_when_installed() -> None:
    for product in ("ltx-2.5-full", "ltx-2.5-comfy"):
        readiness, _reason, executable = derive_video_readiness(
            VideoFacts(
                product_id=product,
                locality="local",
                adapter_id="ltx-2.5-distilled",
                adapter_registered=True,
                live_submit=True,
                checkpoint_ok=True,
                runtime_ok=True,
                nodes_ok=True,
                vram_ok=True,
            )
        )
        assert readiness == "Testing"
        assert executable is False


def test_hosted_missing_credentials_is_requires_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.production_control import generator_authority as authority

    readiness, reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="seedance-fal",
            locality="hosted",
            adapter_id="seedance-api",
            adapter_registered=True,
            live_submit=True,
            credentials_ok=False,
            credentials_reason="Provider API Key Missing",
        )
    )
    assert readiness == "Requires Setup"
    assert executable is False
    assert "API Key" in reason

    monkeypatch.setattr(
        authority,
        "collect_video_facts",
        lambda *_a, **_k: VideoFacts(
            product_id="seedance-fal",
            locality="hosted",
            adapter_id="seedance-api",
            adapter_registered=True,
            live_submit=True,
            credentials_ok=False,
            credentials_reason="Provider API Key Missing",
        ),
    )
    row = authority.apply_authority_to_model(
        {
            "id": "seedance-fal",
            "modality": "video",
            "label": "Seedance (fal.ai)",
            "locality": "hosted",
            "providerId": "fal",
            "capabilityLabel": "Available",
            "executable": True,
        }
    )
    assert row is not None
    assert row["readiness"] == "Requires Setup"
    assert row["capabilityLabel"] == "Requires Setup"
    assert row["executable"] is False


def test_seedance_kie_never_binds_fal() -> None:
    from app.production_control.generator_authority import apply_authority_to_model, timeline_adapter_for
    from app.production_control.video_readiness import adapter_for_product

    assert adapter_for_product("seedance-kie") is None
    assert timeline_adapter_for("seedance-kie") is None
    row = apply_authority_to_model(
        {
            "id": "seedance-kie",
            "modality": "video",
            "label": "Seedance (Kie)",
            "locality": "hosted",
            "providerId": "kie",
            "capabilityLabel": "Available",
            "executable": True,
        }
    )
    assert row is not None
    assert row["id"] == "seedance-kie"
    assert row["canonicalId"] == "seedance-kie"
    assert row["executable"] is False
    assert row["readiness"] == "Unsupported"
    assert "fal" not in (row["disabledReason"] or "").lower() or "will not use fal" in (row["disabledReason"] or "").lower()


def test_fal_timeline_engines_are_selectable() -> None:
    from app.fal_catalog import timeline_fal_engine
    from app.production_control import video_readiness

    assert timeline_fal_engine("kling-fal") == "fal_kling"
    assert timeline_fal_engine("veo-fal") == "fal_veo"
    assert timeline_fal_engine("kling-kie") is None
    assert timeline_fal_engine("veo-kie") is None
    assert timeline_fal_engine("seedance-kie") is None
    live = video_readiness._fal_live_product_ids()
    for product in (
        "seedance-2.0",
        "seedance-2.0-mini",
        "seedance-2.0-fast",
        "seedance-2.5",
        "kling-fal",
        "veo-fal",
    ):
        assert product in live
    for product in ("kling-kie", "veo-kie", "seedance-kie"):
        assert product not in live


def test_adapter_declared_executable_is_not_proof() -> None:
    readiness, _reason, executable = derive_video_readiness(
        VideoFacts(
            product_id="kling-fal",
            locality="hosted",
            adapter_id="kling-api",
            adapter_registered=True,
            live_submit=False,
            credentials_ok=True,
        )
    )
    assert readiness == "Testing"
    assert executable is False


def test_audio_certified_without_exec_is_requires_setup() -> None:
    from app.production_control.generator_authority import apply_authority_to_model

    row = apply_authority_to_model(
        {
            "id": "ace-step-local",
            "modality": "audio",
            "label": "ACE-Step",
            "locality": "local",
            "capabilityLabel": "Certified",
            "executable": False,
        }
    )
    assert row is not None
    assert row["capabilityLabel"] == "Requires Setup"
    assert row["readiness"] == "Requires Setup"


def test_list_models_and_list_generators_share_honesty() -> None:
    from app.director_timeline_w46.capabilities import get_generator, list_generators
    from app.production_control.model_registry import list_models

    video = {m.id: m for m in list_models("video")}
    gens = {g.id: g for g in list_generators()}
    assert "ltx-2.5-full" in video
    assert "ltx-2.5-full" in gens
    assert video["ltx-2.5-full"].executable is False
    assert gens["ltx-2.5-full"].executable is False
    assert video["ltx-2.5-full"].readiness != "Ready"
    assert "mock-chat" not in {m.id for m in list_models("llm")}
    assert "minimax-h3" in video
    assert "minimax-h3-i2v-local" in video
    assert "minimax-h3-t2v-local" not in video
    assert get_generator("minimax-h3-local") is not None
    assert get_generator("kling-kie") is not None
    if "kling-kie" in video and "kling-fal" in video:
        assert video["kling-kie"].id != video["kling-fal"].id
    for mid, model in video.items():
        if model.executable:
            assert model.readiness == "Ready"
        if mid in gens:
            assert bool(model.executable) == bool(gens[mid].executable)


def test_timeline_snapshot_keeps_adapter_generation_flag() -> None:
    """Ready LTX 2.5 must stay Timeline-executable. Adapter id must not drop the flag."""
    from app.director_timeline_w46.capabilities import list_generators
    from app.production_control.generator_authority import _capability_from_row

    restored = _capability_from_row(
        {
            "id": "ltx-2.5-distilled",
            "label": "LTX 2.5 Distilled",
            "locality": "local",
            "capabilityLabel": "Available",
            "executable": True,
            "timelineAdapterId": "ltx-2.5-distilled",
            "readiness": "Ready",
            "disabledReason": "",
        },
        None,
    )
    assert restored.supportsTimelineGeneration is True

    gens = {g.id: g for g in list_generators()}
    ltx = gens.get("ltx-2.5-distilled")
    assert ltx is not None
    assert ltx.timelineAdapterId == "ltx-2.5-distilled"
    assert ltx.supportsTimelineGeneration is True


def test_timeline_adapters_are_execution_bindings() -> None:
    from app.director_timeline_w46.generation.registry import get_registry

    ids = {c.id for c in get_registry().list_capabilities()}
    assert "ltx-2.5-distilled" in ids
    assert "minimax-h3-t2v-local" in ids
    assert "minimax-h3-i2v-local" in ids
    assert "kling-api" in ids
    assert "veo-api" in ids
    try:
        get_registry().resolve_id("seedance-kie")
        raise AssertionError("seedance-kie must not resolve to the fal adapter")
    except Exception as exc:
        assert "seedance-kie" in str(exc) or "Unknown" in str(exc)
