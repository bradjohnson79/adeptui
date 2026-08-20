"""M42 Wave 2 — certified image runtime tests."""

from __future__ import annotations

from pathlib import Path

from app.image_runtime.certified_registry import (
    family_keys,
    get_workflow,
    production_ready_keys,
    reload_registry,
)
from app.image_runtime.contract import resolve_image_workflow
from app.image_runtime.fingerprints import compute_fingerprints, graph_hash
from app.image_runtime.legacy_adapter import normalize_legacy_image_params
from app.image_runtime.output_gate import validate_image_output
from app.image_runtime.production_gate import (
    evaluate_image_wave2_gate,
    evaluate_modern_model_foundation,
    load_production_gate,
)
from app.image_runtime.workflow_execute import build_leaf_graph, legacy_comfy_workflow_key
from app.workflow_runtime import resolve_workflow


def test_required_local_keys_stable():
    gate = load_production_gate()
    assert gate["requiredLocalProductionWorkflowKeys"] == ["zimage.txt2img", "zimage.ref_edit"]
    assert gate.get("enabledCloudProductionWorkflowKeys") == []


def test_modern_families_registered():
    families = family_keys()
    for fam in ("zimage", "flux", "qwen", "imagen"):
        assert fam in families
        assert families[fam]


def test_certified_required_keys():
    reload_registry()
    ready = production_ready_keys()
    assert "zimage.txt2img" in ready
    assert "zimage.ref_edit" in ready
    assert get_workflow("zimage.txt2img").status == "Certified"
    # FLUX is now live-certified locally.
    assert get_workflow("flux.txt2img").status == "Certified"
    assert get_workflow("flux.img2img").status == "Certified"


def test_resolve_production_mode_certified():
    c = resolve_image_workflow("txt2img", engine="zimage", allow_draft=False)
    assert c.workflow_key == "zimage.txt2img"
    assert c.status == "Certified"
    assert c.model_family == "zimage"
    d = c.to_dict()
    assert "supportsReferences" in d
    pinned = c.to_pinned_snapshot()
    assert pinned["workflowKey"] == "zimage.txt2img"
    assert pinned.get("fingerprint") or pinned.get("fingerprints")


def test_resolve_flux_production_mode_certified():
    c = resolve_image_workflow("txt2img", engine="flux", allow_draft=False)
    assert c.workflow_key == "flux.txt2img"
    assert c.status == "Certified"
    assert c.model_family == "flux"


def test_multi_family_unified_resolver():
    c = resolve_workflow("txt2img", modality="image", engine="zimage")
    assert c.workflow_key == "zimage.txt2img"


def test_legacy_normalize_once():
    intent, compat = normalize_legacy_image_params(
        {"prompt": "hello", "model": "zimage", "width": 1024},
        project_id="p1",
        job_kind="imagegen",
    )
    assert intent.prompt == "hello"
    assert compat["legacyInputUsed"] is True
    assert compat["normalizedBy"] == "m42-wave2-adapter"


def test_output_gate_checksum(tmp_path: Path):
    from PIL import Image

    p = tmp_path / "out.png"
    Image.new("RGB", (128, 128), (10, 20, 30)).save(p)
    result = validate_image_output(p, generate_previews=True, preview_dir=tmp_path / "prev")
    assert result.ok
    assert result.checksum and result.checksum.startswith("sha256:")


def test_build_leaf_graph_no_worker_import():
    from app.config import settings

    c = resolve_image_workflow("txt2img", engine="zimage", allow_draft=True)
    g = build_leaf_graph(
        c,
        settings=settings,
        prompt="test",
        width=1024,
        height=1024,
        seed=1,
        steps=4,
        cfg=1.0,
    )
    assert "1" in g
    assert g["1"]["class_type"] == "UNETLoader"
    fps = compute_fingerprints(graph=g, builder_path=c.builder_path)
    assert fps["graphHash"] == graph_hash(g)
    assert legacy_comfy_workflow_key("zimage.txt2img") == "image.txt2img"


def test_zimage_inpaint_denoise_and_grow_are_not_graph_drift():
    from app.config import settings

    c = resolve_image_workflow("inpaint", engine="zimage", allow_draft=True)
    kwargs = dict(
        settings=settings,
        prompt="test",
        source_image="src.png",
        mask_image="mask.png",
        width=1024,
        height=1024,
        seed=1,
        steps=8,
        cfg=1.0,
    )
    remove = build_leaf_graph(c, denoise=0.85, grow_mask_by=6, **kwargs)
    add = build_leaf_graph(c, denoise=0.94, grow_mask_by=12, **kwargs)
    assert graph_hash(remove) == graph_hash(add)
    certified = get_workflow("zimage.inpaint").fingerprints.get("graphHash")
    assert certified
    assert graph_hash(remove) == certified


def test_zimage_ref_edit_matches_certified_graph_after_latent_path():
    from app.config import settings

    c = resolve_image_workflow(
        "image.edit",
        engine="zimage",
        force_workflow_key="zimage.ref_edit",
        allow_draft=True,
    )
    g = build_leaf_graph(
        c,
        settings=settings,
        prompt="test",
        reference_image="ref.png",
        source_image="ref.png",
        width=1024,
        height=1024,
        seed=1,
        steps=8,
        cfg=1.0,
    )
    types = {node["class_type"] for node in g.values()}
    assert "VAEEncode" in types
    assert "ImageScale" in types
    assert "EmptyLatentImage" not in types
    certified = get_workflow("zimage.ref_edit").fingerprints.get("graphHash")
    assert certified
    assert graph_hash(g, workflow_key="zimage.ref_edit") == certified


def test_modern_foundation_ready():
    foundation = evaluate_modern_model_foundation()
    assert foundation["ModernModelFoundationReady"] is True


def test_wave2_gate_go():
    gate = evaluate_image_wave2_gate()
    assert gate["wave2Go"] is True
    assert set(gate["requiredLocalProductionWorkflowKeys"]).issubset(
        set(gate["certifiedProductionPathWorkflowKeys"])
    )
    # Exact inclusion — never count heuristic
    assert len(gate["requiredLocalProductionWorkflowKeys"]) == 2
