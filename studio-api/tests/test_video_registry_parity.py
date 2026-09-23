"""Video registry parity — derived views must equal the historical literals.

The canonical video-generator registry (app.hosted_providers.video_registry)
replaced hand-maintained literals in video_readiness / generator_authority /
workflow_capabilities / model_registry with derived views. These tests snapshot
the ORIGINAL literal values as expected constants and assert byte-identical
parity, plus the intended new honesty (hosted Kling/Veo/Runway surface records)
and the provider-catalog merge rules (approved rows are review inventory only,
never creator-surface truth; pending rows never merge).
"""

from __future__ import annotations

import json

import pytest

from app.hosted_providers import video_registry

# ---------------------------------------------------------------------------
# Snapshot constants — copied verbatim from the literals BEFORE the refactor.
# ---------------------------------------------------------------------------

EXPECTED_PRODUCT_ALIASES = {
    "ltx-2.5": "ltx-2.5-distilled",
    "minimax-h3-local": "minimax-h3",
    "minimax-h3-t2v-local": "minimax-h3",
    "minimax-h3-i2v": "minimax-h3-i2v-local",
    "seedance-api": "seedance-2.0",
    "seedance-fal": "seedance-2.0",
    "fal_seedance": "seedance-2.0",
    "fal_seedance_mini": "seedance-2.0-mini",
    "seedance-mini": "seedance-2.0-mini",
    "fal_seedance_25": "seedance-2.5",
}

EXPECTED_PRODUCT_ADAPTER = {
    "ltx-2.5-full": "ltx-2.5-distilled",
    "ltx-2.5-distilled": "ltx-2.5-distilled",
    "ltx-2.5-comfy": "ltx-2.5-distilled",
    "minimax-h3": "minimax-h3-t2v-local",
    "minimax-h3-i2v-local": "minimax-h3-i2v-local",
    "kling-kie": "kling-api",
    "kling-fal": "kling-api",
    "veo-kie": "veo-api",
    "veo-fal": "veo-api",
    "seedance-2.0": "seedance-2.0",
    "seedance-2.0-mini": "seedance-2.0-mini",
    "seedance-2.5": "seedance-2.5",
}

EXPECTED_LIVE_SUBMIT_ADAPTERS = frozenset(
    {
        "ltx-2.5-distilled",
        "minimax-h3-t2v-local",
        "minimax-h3-i2v-local",
        "seedance-2.0",
        "seedance-2.0-mini",
        "seedance-2.5",
    }
)

EXPECTED_HOSTED_LIVE_ONLY = {
    "seedance-2.0": "fal_api_key",
    "seedance-2.0-mini": "fal_api_key",
    "seedance-2.5": "fal_api_key",
    "kling-fal": "fal_api_key",
    "kling-kie": "kie_api_key",
    "seedance-kie": "kie_api_key",
    "veo-fal": "fal_api_key",
    "veo-kie": "kie_api_key",
}

EXPECTED_SETUP_COMPONENTS = {
    "ltx-2.5-full": ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae", "ltx_2_5_audio_vae"),
    "ltx-2.5-distilled": ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae", "ltx_2_5_audio_vae"),
    "ltx-2.5-comfy": ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"),
}

EXPECTED_REQUIRED_NODES = {
    "ltx-2.5-full": ("UNETLoader", "LTXVBaseSampler", "LTXVScheduler", "LTXVImgToVideo", "LoadImage"),
    "ltx-2.5-distilled": ("UNETLoader", "LTXVBaseSampler", "LTXVScheduler", "LTXVImgToVideo", "LoadImage"),
    "ltx-2.5-comfy": ("UNETLoader", "LTXVBaseSampler", "LTXVScheduler", "LTXVImgToVideo", "LoadImage"),
    "minimax-h3": ("MiniMaxH3ReferenceToVideo", "UNETLoader", "CLIPLoader", "VAELoader", "LoadImage"),
    "minimax-h3-i2v-local": ("MiniMaxH3ReferenceToVideo", "UNETLoader", "CLIPLoader", "VAELoader", "LoadImage"),
}

EXPECTED_ADAPTER_ONLY_IDS = frozenset(
    {
        "minimax-h3-t2v-local",
        "kling-api",
        "seedance-api",
        "veo-api",
        "seedance-fal",
        "fal_seedance_mini",
        "seedance-mini",
    }
)

EXPECTED_CREATE_ENGINE_ROWS = (
    ("auto", "Auto Select", "auto"),
    ("minimax-h3", "MiniMax H3", "local"),
    ("ltx-2.5", "LTX 2.5", "local"),
    ("seedance-2.0", "Seedance 2.0", "hosted"),
    ("seedance-2.0-mini", "Seedance 2.0 Mini", "hosted"),
    ("seedance-2.5", "Seedance 2.5", "hosted"),
    ("fal_kling", "Kling", "hosted"),
    ("fal_veo", "Veo", "hosted"),
    ("fal_runway", "Runway", "hosted"),
)

# Today's workflow_capabilities._LOCAL_WORKFLOW entries (pre-refactor literal).
EXPECTED_SURFACE_WORKFLOWS_EXISTING = {
    "ltx-2.5-distilled": {"t2v": "ltx_25.t2v", "i2v": "ltx_25.i2v", "r2v": "ltx_25.i2v"},
    "ltx-2.5-full": {"t2v": "ltx_25.t2v", "i2v": "ltx_25.i2v", "r2v": "ltx_25.i2v"},
    "ltx-2.5-comfy": {"t2v": "ltx_25.t2v", "i2v": "ltx_25.i2v", "r2v": "ltx_25.i2v"},
    "minimax-h3": {"t2v": "route_a.t2va", "i2v": "route_a.i2va", "multiFrame": "route_a.flf2va", "r2v": "h3.ref2v"},
    "minimax-h3-i2v-local": {"i2v": "route_a.i2va"},
    "seedance-2.0": {"t2v": "fal.seedance-2.0.t2v", "i2v": "fal.seedance-2.0.i2v", "r2v": "fal.seedance-2.0.r2v"},
    "seedance-2.0-mini": {"r2v": "fal.seedance-2.0-mini.r2v"},
    "seedance-2.5": {"t2v": "fal.seedance-2.5.t2v", "i2v": "fal.seedance-2.5.i2v", "r2v": "fal.seedance-2.5.r2v"},
}

# Intended new honesty: hosted entries added by the registry.
EXPECTED_SURFACE_WORKFLOWS_HOSTED_NEW = {
    "kling-fal": {"i2v": "fal.kling-v25-turbo-pro.i2v"},
    "veo-fal": {"t2v": "fal.veo31.t2v", "i2v": "fal.veo31.i2v"},
    "runway": {"i2v": "fal.runway-gen3-turbo.i2v"},
}

# Production Dock video _desc kwarg dicts, in catalog order.
EXPECTED_VIDEO_DESCRIPTORS = [
    dict(
        id="ltx-2.5-full", modality="video", label="LTX 2.5 Full", locality="local",
        provider_id="comfy", capability="Testing", lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation", "native_multishot", "audio_generation", "auto_duration", "fast_generation"],
        does_not_support=[], vram=24.0, gpu=True, executable=True,
    ),
    dict(
        id="ltx-2.5-distilled", modality="video", label="LTX 2.5", locality="local",
        provider_id="comfy", capability="Available", lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation", "native_multishot", "audio_generation", "auto_duration", "fast_generation"],
        does_not_support=[], vram=16.0, gpu=True, executable=True,
    ),
    dict(
        id="ltx-2.5-comfy", modality="video", label="LTX 2.5 Comfy INT8", locality="local",
        provider_id="comfy", capability="Testing", lifecycle="Installed",
        supports=["text_to_video", "image_to_video", "continuation", "audio_generation"],
        does_not_support=[], vram=12.0, gpu=True, executable=True,
    ),
    dict(
        id="minimax-h3", modality="video", label="MiniMax H3", locality="local",
        provider_id=None, capability="Requires Setup", lifecycle=None,
        supports=["native_audio", "text_to_video", "image_to_video"],
        does_not_support=["native_three_keyframe", "three_frame_uses_adept_segmented_assembly"],
        vram=None, gpu=True, executable=False,
    ),
    dict(
        id="minimax-h3-i2v-local", modality="video", label="MiniMax H3 Image-to-Video", locality="local",
        provider_id=None, capability="Requires Setup", lifecycle=None,
        supports=["image_to_video", "start_end_frame", "native_audio"],
        does_not_support=["text_to_video", "native_three_keyframe"],
        vram=None, gpu=True, executable=False,
    ),
    dict(
        id="kling-kie", modality="video", label="Kling (Kie)", locality="hosted",
        provider_id="kie", capability="Testing", lifecycle=None,
        supports=["text_to_video", "image_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="kling-fal", modality="video", label="Kling (fal.ai)", locality="hosted",
        provider_id="fal", capability="Unavailable", lifecycle=None,
        supports=["text_to_video", "image_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="seedance-2.0", modality="video", label="Seedance 2.0", locality="hosted",
        provider_id="fal", capability="Unavailable", lifecycle=None,
        supports=["text_to_video", "image_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="seedance-2.0-mini", modality="video", label="Seedance 2.0 Mini", locality="hosted",
        provider_id="fal", capability="Available", lifecycle=None,
        supports=["image_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="seedance-2.5", modality="video", label="Seedance 2.5", locality="hosted",
        provider_id="fal", capability="Unavailable", lifecycle=None,
        supports=["text_to_video", "image_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="seedance-kie", modality="video", label="Seedance (Kie)", locality="hosted",
        provider_id="kie", capability="Testing", lifecycle=None,
        supports=["text_to_video", "image_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="veo-fal", modality="video", label="Veo (fal.ai)", locality="hosted",
        provider_id="fal", capability="Unavailable", lifecycle=None,
        supports=["text_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
    dict(
        id="veo-kie", modality="video", label="Veo (Kie)", locality="hosted",
        provider_id="kie", capability="Testing", lifecycle=None,
        supports=["text_to_video"], does_not_support=[],
        vram=None, gpu=False, executable=False,
    ),
]


# ---------------------------------------------------------------------------
# Parity: registry views == historical literals, and consumers expose them.
# ---------------------------------------------------------------------------


def test_product_aliases_parity() -> None:
    from app.production_control import generator_authority, video_readiness

    assert video_registry.product_aliases() == EXPECTED_PRODUCT_ALIASES
    assert video_readiness.PRODUCT_ALIASES == EXPECTED_PRODUCT_ALIASES
    # generator_authority re-exports video_readiness (no duplicate literal).
    assert generator_authority.PRODUCT_ALIASES == EXPECTED_PRODUCT_ALIASES
    assert generator_authority.PRODUCT_ALIASES is video_readiness.PRODUCT_ALIASES


def test_product_adapter_map_parity() -> None:
    from app.production_control import video_readiness

    assert video_registry.product_adapter_map() == EXPECTED_PRODUCT_ADAPTER
    assert video_readiness.PRODUCT_ADAPTER == EXPECTED_PRODUCT_ADAPTER


def test_live_submit_adapters_parity() -> None:
    from app.production_control import video_readiness

    assert video_registry.live_submit_adapters() == EXPECTED_LIVE_SUBMIT_ADAPTERS
    assert video_readiness.LIVE_SUBMIT_ADAPTERS == EXPECTED_LIVE_SUBMIT_ADAPTERS


def test_hosted_live_only_parity() -> None:
    from app.production_control import video_readiness

    assert video_registry.hosted_live_only() == EXPECTED_HOSTED_LIVE_ONLY
    assert video_readiness.HOSTED_LIVE_ONLY == EXPECTED_HOSTED_LIVE_ONLY
    # runway carries a hosted secret for surface honesty but is NOT an exposed
    # Dock product, so it stays out of HOSTED_LIVE_ONLY (as today).
    assert "runway" not in video_readiness.HOSTED_LIVE_ONLY


def test_setup_components_parity() -> None:
    from app.production_control import video_readiness

    assert video_registry.setup_components() == EXPECTED_SETUP_COMPONENTS
    assert video_readiness.SETUP_COMPONENTS == EXPECTED_SETUP_COMPONENTS


def test_required_nodes_parity() -> None:
    from app.production_control import video_readiness

    assert video_registry.required_nodes() == EXPECTED_REQUIRED_NODES
    assert video_readiness.REQUIRED_NODES == EXPECTED_REQUIRED_NODES


def test_adapter_only_ids_parity() -> None:
    from app.production_control import generator_authority

    assert video_registry.adapter_only_ids() == EXPECTED_ADAPTER_ONLY_IDS
    assert generator_authority._ADAPTER_ONLY_IDS == EXPECTED_ADAPTER_ONLY_IDS
    # seedance-api / seedance-fal are BOTH aliases and adapter-only.
    assert {"seedance-api", "seedance-fal"} <= set(EXPECTED_PRODUCT_ALIASES)
    assert {"seedance-api", "seedance-fal"} <= set(EXPECTED_ADAPTER_ONLY_IDS)


def test_create_engine_rows_parity() -> None:
    from app.production_control import generator_authority

    assert video_registry.create_engine_rows() == EXPECTED_CREATE_ENGINE_ROWS
    assert tuple(generator_authority.CREATE_ENGINE_ROWS) == EXPECTED_CREATE_ENGINE_ROWS


def test_surface_workflow_map_parity() -> None:
    from app.video_runtime import workflow_capabilities

    surface_map = video_registry.surface_workflow_map()
    # Every pre-existing entry is byte-identical to the historical literal.
    for product, surfaces in EXPECTED_SURFACE_WORKFLOWS_EXISTING.items():
        assert surface_map.get(product) == surfaces, product
    # Intended new honesty: hosted Kling/Veo/Runway entries exist.
    for product, surfaces in EXPECTED_SURFACE_WORKFLOWS_HOSTED_NEW.items():
        assert surface_map.get(product) == surfaces, product
    # The refactored _LOCAL_WORKFLOW IS the registry map.
    assert workflow_capabilities._LOCAL_WORKFLOW == surface_map
    assert len(surface_map) == len(EXPECTED_SURFACE_WORKFLOWS_EXISTING) + len(EXPECTED_SURFACE_WORKFLOWS_HOSTED_NEW)


def test_video_model_descriptors_parity() -> None:
    assert video_registry.video_model_descriptors() == EXPECTED_VIDEO_DESCRIPTORS


def test_model_registry_video_rows_byte_identical() -> None:
    """_CATALOG video rows equal the former literals, post-processing included."""
    from app.production_control.model_registry import _CATALOG, _desc

    video = [m for m in _CATALOG if m.modality == "video"]
    expected = []
    for kwargs in EXPECTED_VIDEO_DESCRIPTORS:
        row = _desc(**kwargs)
        if row.locality == "local":
            # model_registry post-processing strips local lifecycle/executable.
            row = row.model_copy(update={"lifecycle": None, "executable": False})
        expected.append(row)
    assert [m.model_dump() for m in video] == [m.model_dump() for m in expected]


# ---------------------------------------------------------------------------
# Surface status: seedance byte-identical; hosted branch is the new honesty.
# ---------------------------------------------------------------------------


def test_seedance_surface_status_byte_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.production_control import video_readiness
    from app.video_runtime import workflow_capabilities

    monkeypatch.setattr(video_readiness, "_secret_configured", lambda name: True)
    assert workflow_capabilities.surface_workflow_status("seedance-2.0", "t2v") == {
        "productId": "seedance-2.0",
        "surface": "t2v",
        "supported": True,
        "installed": True,
        "executable": True,
        "runtime": "fal",
        "workflowKey": "fal.seedance-2.0.t2v",
        "readiness": "Ready",
        "reason": "",
        "locality": "hosted",
    }

    monkeypatch.setattr(video_readiness, "_secret_configured", lambda name: False)
    assert workflow_capabilities.surface_workflow_status("seedance-2.5", "r2v") == {
        "productId": "seedance-2.5",
        "surface": "r2v",
        "supported": True,
        "installed": False,
        "executable": False,
        "runtime": "fal",
        "workflowKey": "fal.seedance-2.5.r2v",
        "readiness": "Requires Setup",
        "reason": "Provider API Key Missing",
        "locality": "hosted",
    }


def test_hosted_surface_status_new_honesty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.production_control import video_readiness
    from app.video_runtime import workflow_capabilities

    monkeypatch.setattr(video_readiness, "_secret_configured", lambda name: True)
    kling = workflow_capabilities.surface_workflow_status("kling-fal", "i2v")
    assert kling == {
        "productId": "kling-fal",
        "surface": "i2v",
        "supported": True,
        "installed": True,
        "executable": True,
        "runtime": "fal",
        "workflowKey": "fal.kling-v25-turbo-pro.i2v",
        "readiness": "Ready",
        "reason": "",
        "locality": "hosted",
    }
    veo = workflow_capabilities.surface_workflow_status("veo-fal", "t2v")
    assert veo["supported"] is True
    assert veo["executable"] is True
    assert veo["readiness"] == "Ready"
    assert veo["runtime"] == "fal"
    assert veo["workflowKey"] == "fal.veo31.t2v"
    assert veo["locality"] == "hosted"

    # Runway: secret configured but the endpoint is dead (create_live=False,
    # live_submit=False) — never a fake Ready.
    runway = workflow_capabilities.surface_workflow_status("runway", "i2v")
    assert runway["supported"] is True
    assert runway["executable"] is False
    assert runway["readiness"] == "Testing — live submit not certified"
    assert runway["workflowKey"] == "fal.runway-gen3-turbo.i2v"
    assert runway["locality"] == "hosted"

    # Missing secret → Provider Not Configured, never "comfy" runtime leakage.
    monkeypatch.setattr(video_readiness, "_secret_configured", lambda name: False)
    kling_off = workflow_capabilities.surface_workflow_status("kling-fal", "i2v")
    assert kling_off["supported"] is True
    assert kling_off["installed"] is False
    assert kling_off["executable"] is False
    assert kling_off["readiness"] == "Provider Not Configured"
    assert kling_off["reason"] == "Provider API Key Missing"
    assert kling_off["runtime"] == "fal"

    # Surfaces without a workflow key keep the existing unsupported record.
    assert workflow_capabilities.surface_workflow_status("kling-fal", "t2v") == {
        "productId": "kling-fal",
        "surface": "t2v",
        "supported": False,
        "installed": False,
        "executable": False,
        "runtime": None,
        "workflowKey": None,
        "readiness": "Unsupported",
        "reason": "No workflow for this surface",
    }


def test_workflow_capabilities_hosted_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    """generator_authority emits 4-surface records for hosted products with
    registry workflow records; products without records still return None."""
    from app.production_control import generator_authority, video_readiness

    monkeypatch.setattr(video_readiness, "_secret_configured", lambda name: True)

    kling = generator_authority._workflow_capabilities("kling-fal")
    assert kling is not None
    assert set(kling) == {"t2v", "i2v", "multiFrame", "r2v"}
    assert kling["i2v"]["supported"] is True
    assert kling["i2v"]["executable"] is True
    assert kling["t2v"]["supported"] is False

    veo = generator_authority._workflow_capabilities("veo-fal")
    assert veo is not None
    assert veo["t2v"]["supported"] is True
    assert veo["i2v"]["supported"] is True
    assert veo["r2v"]["supported"] is False

    runway = generator_authority._workflow_capabilities("runway")
    assert runway is not None
    assert runway["i2v"]["supported"] is True
    assert runway["i2v"]["executable"] is False  # dead endpoint — honest

    # Seedance record shape unchanged (same keys, same branch).
    seedance = generator_authority._workflow_capabilities("seedance-2.0")
    assert seedance is not None
    assert seedance["t2v"]["workflowKey"] == "fal.seedance-2.0.t2v"
    assert seedance["t2v"]["runtime"] == "fal"
    assert seedance["t2v"]["readiness"] == "Ready"

    # Kie-only products have no workflow records → None (hosted capability path).
    assert generator_authority._workflow_capabilities("kling-kie") is None
    assert generator_authority._workflow_capabilities("veo-kie") is None
    assert generator_authority._workflow_capabilities("seedance-kie") is None


# ---------------------------------------------------------------------------
# Provider-catalog merge: approved rows are review inventory ONLY.
# ---------------------------------------------------------------------------

_APPROVED_ROW = {
    "rowId": "fal:acme/wizard-1/text-to-video",
    "provider": "fal",
    "family": "wizard",
    "model": "Wizard 1 Pro",
    "version": "1",
    "tier": "pro",
    "endpoint": "acme/wizard-1/text-to-video",
    "apiPath": None,
    "t2v": True,
    "i2v": False,
    "r2v": False,
    "firstFrame": False,
    "lastFrame": False,
    "references": 0,
    "videoReferences": 0,
    "durationMinSec": 3.0,
    "durationMaxSec": 10.0,
    "durationsSec": [],
    "resolutions": ["480p", "720p"],
    "audio": False,
    "pricing": None,
    "requestSchema": None,
    "liveSubmit": False,
    "status": "verified",
    "reviewStatus": "approved",
    "source": "live_api",
    "notes": "synthetic parity fixture",
    "discoveredAt": "2026-09-10T00:00:00+00:00",
}

_PENDING_ROW = {
    **_APPROVED_ROW,
    "rowId": "kie:acme/mage-2/image-to-video",
    "provider": "kie",
    "family": "mage",
    "model": "Mage 2",
    "endpoint": "acme/mage-2/image-to-video",
    "t2v": False,
    "i2v": True,
    "firstFrame": True,
    "reviewStatus": "pending_review",
}


@pytest.fixture()
def synthetic_catalog(tmp_path, monkeypatch):
    from app.hosted_providers import catalog_sync

    store = tmp_path / "provider_catalog.json"
    monkeypatch.setattr(catalog_sync, "_STORE_PATH", store)
    store.write_text(
        json.dumps({"version": 1, "updatedAt": None, "providers": {}, "rows": [_APPROVED_ROW, _PENDING_ROW]}),
        encoding="utf-8",
    )
    return store


def test_catalog_merge_approved_only(synthetic_catalog) -> None:
    catalog_rows = video_registry.catalog_registrations()
    assert [r.product_id for r in catalog_rows] == ["fal:acme/wizard-1/text-to-video"]

    merged = video_registry.merged_registry()
    merged_ids = [r.product_id for r in merged]
    assert "fal:acme/wizard-1/text-to-video" in merged_ids
    assert "kie:acme/mage-2/image-to-video" not in merged_ids  # pending never merges
    assert len(merged) == len(video_registry.CORE_VIDEO_REGISTRY) + 1

    approved = catalog_rows[0]
    assert approved.exposed is False
    assert approved.live_submit is False
    assert approved.create_live is False
    assert approved.source == "catalog:fal:acme/wizard-1/text-to-video"
    assert approved.locality == "hosted"
    assert approved.provider == "fal"
    assert approved.label == "Wizard 1 Pro"
    assert approved.endpoints == {"t2v": "acme/wizard-1/text-to-video"}
    assert approved.supports == ("text_to_video",)
    assert approved.duration_min_sec == 3.0
    assert approved.duration_max_sec == 10.0
    assert approved.resolutions == ("480p", "720p")


def test_catalog_rows_never_enter_creator_surface_views(synthetic_catalog) -> None:
    row_id = "fal:acme/wizard-1/text-to-video"
    assert row_id not in video_registry.product_aliases()
    assert row_id not in video_registry.product_aliases().values()
    assert row_id not in video_registry.product_adapter_map()
    assert row_id not in video_registry.hosted_live_only()
    assert row_id not in video_registry.setup_components()
    assert row_id not in video_registry.required_nodes()
    assert row_id not in video_registry.surface_workflow_map()
    assert row_id not in {r["id"] for r in video_registry.video_model_descriptors()}
    assert row_id not in {token for token, _label, _group in video_registry.create_engine_rows()}
    # Creator-surface parity holds even with an approved catalog row present.
    assert video_registry.product_aliases() == EXPECTED_PRODUCT_ALIASES
    assert video_registry.product_adapter_map() == EXPECTED_PRODUCT_ADAPTER
    assert video_registry.create_engine_rows() == EXPECTED_CREATE_ENGINE_ROWS
    assert len(video_registry.video_model_descriptors()) == len(EXPECTED_VIDEO_DESCRIPTORS)


def test_catalog_registrations_empty_without_store(tmp_path, monkeypatch) -> None:
    from app.hosted_providers import catalog_sync

    monkeypatch.setattr(catalog_sync, "_STORE_PATH", tmp_path / "missing.json")
    assert video_registry.catalog_registrations() == []
    assert len(video_registry.merged_registry()) == len(video_registry.CORE_VIDEO_REGISTRY)


def test_core_registry_shape() -> None:
    ids = [r.product_id for r in video_registry.CORE_VIDEO_REGISTRY]
    assert len(ids) == len(set(ids))
    assert "runway" in ids
    assert "ltx-local" not in ids
    assert "wan-local" not in ids
    assert "hunyuan-video-1.5-local" not in ids
    assert "hunyuan-video-13b-local" not in ids
    runway = video_registry.core_registration("runway")
    assert runway is not None
    assert runway.adapter_id is None
    assert runway.live_submit is False
    assert runway.create_live is False
    assert runway.exposed is False
    assert "NOT FOUND" in runway.notes
