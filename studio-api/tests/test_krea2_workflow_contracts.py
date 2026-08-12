"""Krea 2 (Turbo / RAW) workflow contract tests — Phase B (no GPU, no queue).

Covers the Draft registry entries, the ComfyUI graph builders, mu plumbing
through build_leaf_graph, fingerprint generation, and dimension normalization.
All model filenames are placeholders — no real Krea 2 weights are required and
nothing is submitted to ComfyUI.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.image_runtime.certified_registry import get_workflow, reload_registry
from app.image_runtime.contract import resolve_image_workflow
from app.image_runtime.fingerprints import compute_fingerprints
from app.image_runtime.workflow_execute import build_leaf_graph
from app.workflows.krea2_image import (
    KREA2_STANDARD_NEGATIVE,
    build_krea2_raw_txt2img_workflow,
    build_krea2_turbo_txt2img_workflow,
    krea2_normalize_dimension,
    krea2_recommended_settings,
    krea2_resolution_shift,
)

# Placeholder filenames — tests never touch real weights (volatile-redacted in
# graph hashes, so any value works).
TEST_UNET = "test_krea2_unet.safetensors"
TEST_CLIP = "test_qwen3vl_encoder.safetensors"
TEST_VAE = "test_qwen_image_vae.safetensors"

EXPECTED_NODE_CLASSES = {
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "ModelSamplingAuraFlow",
    "CLIPTextEncode",
    "KSampler",
    "EmptyLatentImage",
    "VAEDecode",
    "SaveImage",
}

# Canonical fingerprint build inputs (mirror the Phase B registry generation
# script): 1024x1024 with official default sampling settings per variant.
CANONICAL = {
    "krea2.turbo_txt2img": {"width": 1024, "height": 1024, "steps": 8, "cfg": 0.0, "mu": 1.15},
    "krea2.raw_txt2img": {"width": 1024, "height": 1024, "steps": 52, "cfg": 3.5, "mu": None},
}


@pytest.fixture()
def krea2_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "krea2_turbo_checkpoint", TEST_UNET)
    monkeypatch.setattr(settings, "krea2_raw_checkpoint", "test_krea2_raw.safetensors")
    monkeypatch.setattr(settings, "krea2_text_encoder", TEST_CLIP)
    monkeypatch.setattr(settings, "krea2_vae", TEST_VAE)
    return settings


def _class_types(graph: dict) -> set[str]:
    return {node["class_type"] for node in graph.values()}


def _node_by_class(graph: dict, class_type: str) -> dict:
    for node in graph.values():
        if node["class_type"] == class_type:
            return node
    raise AssertionError(f"node class missing: {class_type}")


def _model_sampling_node(graph: dict) -> dict:
    """The shift-carrying node feeding KSampler.model."""
    ksampler = _node_by_class(graph, "KSampler")
    model_ref = ksampler["inputs"]["model"]
    return graph[str(model_ref[0])]


def test_krea2_registry_entries_present():
    reload_registry()
    turbo = get_workflow("krea2.turbo_txt2img")
    raw = get_workflow("krea2.raw_txt2img")
    assert turbo is not None and raw is not None

    assert turbo.status == "Draft" and raw.status == "Draft"
    assert turbo.model_family == "krea2" and raw.model_family == "krea2"
    assert turbo.model_variant == "turbo" and raw.model_variant == "raw"
    assert turbo.builder_path == "app.workflows.krea2_image:build_krea2_turbo_txt2img_workflow"
    assert raw.builder_path == "app.workflows.krea2_image:build_krea2_raw_txt2img_workflow"

    # requiredModels reference the Phase A settings keys (not filenames)
    assert set(turbo.required_models) == {"krea2_turbo_checkpoint", "krea2_text_encoder", "krea2_vae"}
    assert set(raw.required_models) == {"krea2_raw_checkpoint", "krea2_text_encoder", "krea2_vae"}

    for wf in (turbo, raw):
        assert set(wf.required_nodes) == EXPECTED_NODE_CLASSES
        caps = wf.capabilities
        assert caps["supportsTextToImage"] is True
        assert caps["supportsResolutionControl"] is True
        assert caps["supportsSeed"] is True
        assert caps["supportsLoRA"] is True  # LoRA wiring landed in Phase C
        assert caps["supportsReferenceImages"] is True  # Phase C reference wiring
        assert wf.provider_kind == "local" and wf.provider == "comfyui"

    # runtimeParams carry mu contract-governed values into the resolver
    assert turbo.runtime_params["mu"] == 1.15
    assert raw.runtime_params["mu"] is None
    assert raw.runtime_params["muPolicy"] == "resolution-derived"


def test_turbo_graph_structure_and_mu():
    graph = build_krea2_turbo_txt2img_workflow(
        unet_name=TEST_UNET,
        clip_name=TEST_CLIP,
        vae_name=TEST_VAE,
        positive="a lighthouse keeper at dawn",
    )
    assert _class_types(graph) == EXPECTED_NODE_CLASSES

    unet = _node_by_class(graph, "UNETLoader")
    assert unet["inputs"]["unet_name"] == TEST_UNET
    assert unet["inputs"]["weight_dtype"] == "fp8_e4m3fn"

    clip = _node_by_class(graph, "CLIPLoader")
    assert clip["inputs"]["clip_name"] == TEST_CLIP
    assert clip["inputs"]["type"] == "krea2"

    assert _node_by_class(graph, "VAELoader")["inputs"]["vae_name"] == TEST_VAE

    # mu is applied by the model-sampling node upstream of the sampler
    sampling = _model_sampling_node(graph)
    assert sampling["class_type"] == "ModelSamplingAuraFlow"
    assert sampling["inputs"]["shift"] == 1.15

    ksampler = _node_by_class(graph, "KSampler")
    assert ksampler["inputs"]["steps"] == 8
    assert ksampler["inputs"]["cfg"] == 0.0
    assert ksampler["inputs"]["model"] == ["4", 0]

    latent = _node_by_class(graph, "EmptyLatentImage")
    assert latent["inputs"]["width"] == 1024
    assert latent["inputs"]["height"] == 1024

    save = _node_by_class(graph, "SaveImage")
    assert save["inputs"]["filename_prefix"].startswith("studio/")

    # explicit mu override flows into the shift input
    overridden = build_krea2_turbo_txt2img_workflow(
        unet_name=TEST_UNET, clip_name=TEST_CLIP, vae_name=TEST_VAE,
        positive="p", mu=0.9,
    )
    assert _model_sampling_node(overridden)["inputs"]["shift"] == 0.9


def test_raw_graph_settings_and_resolution_mu():
    graph = build_krea2_raw_txt2img_workflow(
        unet_name=TEST_UNET,
        clip_name=TEST_CLIP,
        vae_name=TEST_VAE,
        positive="weathered fisherman portrait",
    )
    assert _class_types(graph) == EXPECTED_NODE_CLASSES

    ksampler = _node_by_class(graph, "KSampler")
    assert ksampler["inputs"]["steps"] == 52
    assert ksampler["inputs"]["cfg"] == 3.5

    # 1024x1024 → 4096 latent tokens → mu = 0.5 + 0.65 * (4096-256)/(6400-256)
    sampling = _model_sampling_node(graph)
    assert sampling["class_type"] == "ModelSamplingAuraFlow"
    assert sampling["inputs"]["shift"] == pytest.approx(0.90625)

    # explicit mu pins a constant instead of the resolution-derived value
    pinned = build_krea2_raw_txt2img_workflow(
        unet_name=TEST_UNET, clip_name=TEST_CLIP, vae_name=TEST_VAE,
        positive="p", mu=1.15,
    )
    assert _model_sampling_node(pinned)["inputs"]["shift"] == 1.15


def test_build_leaf_graph_dispatch_krea2(krea2_settings):
    reload_registry()
    turbo_contract = resolve_image_workflow("txt2img", engine="krea2", allow_draft=True)
    assert turbo_contract.workflow_key == "krea2.turbo_txt2img"
    assert turbo_contract.status == "Draft"
    # mu arrives via registry runtimeParams → contract runtime requirements
    assert turbo_contract.runtime_requirements["mu"] == 1.15

    graph = build_leaf_graph(
        turbo_contract,
        settings=krea2_settings,
        prompt="storm over a neon harbor",
        width=1024,
        height=1024,
        seed=7,
    )
    assert _class_types(graph) == EXPECTED_NODE_CLASSES
    assert _node_by_class(graph, "UNETLoader")["inputs"]["unet_name"] == TEST_UNET
    assert _node_by_class(graph, "CLIPLoader")["inputs"]["type"] == "krea2"
    assert _model_sampling_node(graph)["inputs"]["shift"] == 1.15
    assert _node_by_class(graph, "KSampler")["inputs"]["steps"] == 8

    raw_contract = resolve_image_workflow(
        "txt2img", engine="krea2", allow_draft=True, force_workflow_key="krea2.raw_txt2img"
    )
    raw_graph = build_leaf_graph(
        raw_contract,
        settings=krea2_settings,
        prompt="storm over a neon harbor",
        width=1024,
        height=1024,
        seed=7,
    )
    raw_ksampler = _node_by_class(raw_graph, "KSampler")
    assert raw_ksampler["inputs"]["steps"] == 52
    assert raw_ksampler["inputs"]["cfg"] == 3.5
    assert _model_sampling_node(raw_graph)["inputs"]["shift"] == pytest.approx(0.90625)

    # explicit call-site mu beats the contract value
    mu_graph = build_leaf_graph(
        turbo_contract,
        settings=krea2_settings,
        prompt="p",
        mu=0.7,
    )
    assert _model_sampling_node(mu_graph)["inputs"]["shift"] == 0.7


def test_krea2_family_aliases_and_production_gate(krea2_settings):
    reload_registry()
    # family aliases normalize onto krea2
    for alias in ("krea2", "krea-2", "krea_2"):
        contract = resolve_image_workflow("txt2img", engine=alias, allow_draft=True)
        assert contract.workflow_key == "krea2.turbo_txt2img"

    # Draft entries are refused on the production path (no silent zimage swap)
    with pytest.raises(RuntimeError, match="not Certified"):
        resolve_image_workflow("txt2img", engine="krea2", allow_draft=False)


def test_krea2_fingerprints_match_registry(krea2_settings):
    reload_registry()
    builders = {
        "krea2.turbo_txt2img": build_krea2_turbo_txt2img_workflow,
        "krea2.raw_txt2img": build_krea2_raw_txt2img_workflow,
    }
    for key, build in builders.items():
        wf = get_workflow(key)
        assert wf is not None and wf.status == "Draft"  # Draft fingerprints allowed
        canon = CANONICAL[key]
        graph = build(
            unet_name=TEST_UNET,
            clip_name=TEST_CLIP,
            vae_name=TEST_VAE,
            positive="canonical fingerprint probe",
            width=canon["width"],
            height=canon["height"],
            seed=42,
            steps=canon["steps"],
            cfg=canon["cfg"],
            mu=canon["mu"],
        )
        fps = compute_fingerprints(
            graph=graph,
            builder_path=wf.builder_path,
            required_nodes=wf.required_nodes,
            required_models=wf.required_models,
        )
        assert fps["graphHash"] == wf.fingerprints.get("graphHash"), f"{key} graphHash drift"
        assert fps["builderHash"] == wf.fingerprints.get("builderHash"), (
            f"{key} builderHash changed — refresh Draft fingerprints after builder edits"
        )
        assert fps["nodeInventoryHash"] == wf.fingerprints.get("nodeInventoryHash")
        assert fps["modelInventoryHash"] == wf.fingerprints.get("modelInventoryHash")


def test_krea2_dimension_normalization():
    assert krea2_normalize_dimension(1024) == 1024
    assert krea2_normalize_dimension(1000) == 1008  # padded UP to multiple of 16
    assert krea2_normalize_dimension(17) == 32
    assert krea2_normalize_dimension(16) == 16
    assert krea2_normalize_dimension(1) == 16
    assert krea2_normalize_dimension(0) == 1024  # fallback
    assert krea2_normalize_dimension(-5) == 1024  # fallback
    assert krea2_normalize_dimension(2048) == 2048

    graph = build_krea2_turbo_txt2img_workflow(
        unet_name=TEST_UNET, clip_name=TEST_CLIP, vae_name=TEST_VAE,
        positive="p", width=1000, height=1033,
    )
    latent = _node_by_class(graph, "EmptyLatentImage")["inputs"]
    assert latent["width"] == 1008
    assert latent["height"] == 1040
    assert latent["width"] % 16 == 0 and latent["height"] % 16 == 0


def test_krea2_resolution_shift_bounds():
    assert krea2_resolution_shift(256, 256) == pytest.approx(0.5)  # base seq len
    assert krea2_resolution_shift(1024, 1024) == pytest.approx(0.90625)
    assert krea2_resolution_shift(2048, 2048) == pytest.approx(1.15)  # clamped max
    low = krea2_resolution_shift(1024, 1024)
    high = krea2_resolution_shift(1536, 1536)
    assert 0.5 <= low < high <= 1.15


def test_krea2_recommended_settings():
    turbo = krea2_recommended_settings("turbo")
    assert turbo["steps"] == 8
    assert turbo["cfg"] == 0.0
    assert turbo["mu"] == 1.15
    assert turbo["weight_dtype"] == "fp8_e4m3fn"
    assert turbo["negative"] == KREA2_STANDARD_NEGATIVE

    raw = krea2_recommended_settings("raw")
    assert raw["steps"] == 52
    assert raw["cfg"] == 3.5
    assert raw["mu"] is None  # resolution-derived at build time


def test_registry_sync_leaves_krea2_draft():
    from app.image_runtime.registry_sync import sync_registry_status_from_discovery

    result = sync_registry_status_from_discovery(dry_run=True)
    krea2_changes = [
        c for c in result.get("changes", []) if str(c.get("workflowKey", "")).startswith("krea2.")
    ]
    assert krea2_changes == [], "registry sync must never auto-promote/demote krea2"
    reload_registry()
    assert get_workflow("krea2.turbo_txt2img").status == "Draft"
    assert get_workflow("krea2.raw_txt2img").status == "Draft"


def test_readiness_reports_krea2_honestly():
    from app.image_runtime.readiness import generate_readiness_report

    report = generate_readiness_report()
    rows = {w["workflowKey"]: w for w in report["workflows"]}
    assert "krea2.turbo_txt2img" in rows and "krea2.raw_txt2img" in rows
    fam = (report.get("discovery", {}).get("families") or {}).get("krea2") or {}
    installed = bool(fam.get("installed"))
    for key in ("krea2.turbo_txt2img", "krea2.raw_txt2img"):
        assert rows[key]["status"] == "Draft"
        assert rows[key]["modelFamily"] == "krea2"
        # certifiable only when weights are actually discovered — never invented
        assert rows[key]["availableForCertification"] is installed
