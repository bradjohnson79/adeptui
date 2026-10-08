"""SenseNova U1.5 registry, builders, fingerprints, Setup catalog."""

import pytest

from app.image_runtime.fingerprints import canonicalize_graph, graph_hash
from app.image_studio.providers import family_catalog
from app.imagegen_workflows import _FAMILY_INSTALL_COMPONENTS, _FAMILY_LABELS, build_local_generator_models
from app.setup.catalog import get_component
from app.workflows.sensenova_u15 import (
    REQUIRED_NODES,
    build_sensenova_crs_workflow,
    build_sensenova_ers_workflow,
    build_sensenova_txt2img_workflow,
    is_sensenova_family,
)


def test_family_helpers() -> None:
    assert is_sensenova_family("sensenova")
    assert is_sensenova_family("sensenova-u15-local")
    assert not is_sensenova_family("qwen2512")


def test_builders_emit_official_nodes_not_ksampler() -> None:
    t2i = build_sensenova_txt2img_workflow(prompt="a lamp", width=2720, height=1536, seed=7)
    types = {node["class_type"] for node in t2i.values()}
    assert "SenseNovaU1LocalLoader" in types
    assert "SenseNovaU1LocalTextToImage" in types
    assert "KSampler" not in types
    assert t2i["2"]["inputs"]["resolution"] == "2720x1536|16:9"
    assert t2i["1"]["inputs"]["device"] == "cuda"
    assert t2i["1"]["inputs"]["vram_mode"] == "fast"

    crs = build_sensenova_crs_workflow(prompt="sheet", image_name="ref.png")
    assert any(n["class_type"] == "SenseNovaU1LocalImageEdit" for n in crs.values())

    ers = build_sensenova_ers_workflow(prompt="ers", image_name="atlas.png")
    assert any(n["class_type"] == "LoadImage" for n in ers.values())


def test_fingerprint_redacts_volatile_inputs() -> None:
    a = build_sensenova_txt2img_workflow(prompt="one", seed=1, width=2720, height=1536)
    b = build_sensenova_txt2img_workflow(prompt="two", seed=99, width=2048, height=2048)
    assert graph_hash(a, workflow_key="sensenova.txt2img") == graph_hash(b, workflow_key="sensenova.txt2img")
    canon = canonicalize_graph(a, extra_volatile=None)
    assert "one" not in canon or "<redacted>" in canon


def test_setup_catalog_and_roster() -> None:
    with pytest.raises(KeyError):
        get_component("sensenova_u15_models")
    assert "sensenova" not in _FAMILY_INSTALL_COMPONENTS
    assert "sensenova" not in _FAMILY_LABELS
    roster = build_local_generator_models()
    assert all(row["id"] != "sensenova" for row in roster)
    fams = {row["family"] for row in family_catalog()}
    assert "sensenova" not in fams


def test_required_nodes_match_official_pack() -> None:
    assert "SenseNovaU1LocalLoader" in REQUIRED_NODES
    assert "SenseNovaU1LocalTextToImage" in REQUIRED_NODES
    assert "SenseNovaU1LocalImageEdit" in REQUIRED_NODES
