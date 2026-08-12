"""Topology fingerprint drift regressions (Timeline Full Audit, t3/t6).

Mandatory contract (plan Phase 11): the certified topologyHash must be
INVARIANT under legitimate per-job dynamic substitution (prompt, seed, image
filename, duration/resolution/fps/steps) and must BLOCK on any true topology
change (node class changed, link rewired, model node missing, I2V→T2V
downgrade). Legacy graphHash conflated the two classes and produced the
release-blocking WORKFLOW_GRAPH_DRIFT false positives on ordinary Timeline
batches; these tests pin the split so it cannot regress.
"""

from __future__ import annotations

import pytest

from app.video_runtime.fingerprints import (
    WorkflowGraphDriftError,
    assert_no_topology_drift,
    topology_hash,
    validate_dynamic_bindings,
)

WORKFLOW_KEY = "ltx.simple_i2v"
WORKFLOW_VERSION = "1.0.0"


def _ltx_i2v_graph() -> dict:
    """Minimal but structurally faithful LTX image-to-video graph."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltxv-2.3.safetensors"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "korri_start.png"}},
        "3": {
            "class_type": "LTXVImgToVideo",
            "inputs": {"pixels": ["2", 0], "vae": ["1", 2], "width": 768, "height": 512, "length": 121},
        },
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cinematic reveal", "clip": ["1", 1]}},
        "5": {"class_type": "LTXVConditioning", "inputs": {"positive": ["4", 0], "frame_rate": 24}},
        "6": {
            "class_type": "KSampler",
            "inputs": {"model": ["1", 0], "positive": ["5", 0], "latent_image": ["3", 0], "noise_seed": 42},
        },
        "7": {"class_type": "BasicScheduler", "inputs": {"model": ["1", 0], "steps": 30}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "9": {
            "class_type": "VHS_VideoCombine",
            "inputs": {"images": ["8", 0], "frame_rate": 24, "filename_prefix": "timeline/ltx_out"},
        },
    }


def _assert_matches_reference(graph: dict, reference_hash: str) -> None:
    # Must NOT raise — legitimate dynamic substitution never drifts.
    assert_no_topology_drift(
        built_graph=graph,
        expected_topology_hash=reference_hash,
        workflow_key=WORKFLOW_KEY,
        workflow_version=WORKFLOW_VERSION,
    )


def _assert_blocked(graph: dict, reference_hash: str) -> None:
    with pytest.raises(WorkflowGraphDriftError):
        assert_no_topology_drift(
            built_graph=graph,
            expected_topology_hash=reference_hash,
            workflow_key=WORKFLOW_KEY,
            workflow_version=WORKFLOW_VERSION,
        )


# ---------------------------------------------------------------------------
# NO-DRIFT cases — legitimate per-job dynamic substitution
# ---------------------------------------------------------------------------


def test_prompt_variation_does_not_drift():
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    variant["4"]["inputs"]["text"] = "Korri turns toward camera, sarcastic smirk, neon rim light"
    _assert_matches_reference(variant, ref_hash)


def test_seed_variation_does_not_drift():
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    variant["6"]["inputs"]["noise_seed"] = 987654321
    _assert_matches_reference(variant, ref_hash)


def test_image_filename_variation_does_not_drift():
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    variant["2"]["inputs"]["image"] = "batch_17_start_frame.png"
    variant["9"]["inputs"]["filename_prefix"] = "timeline/scene2_batch17"
    _assert_matches_reference(variant, ref_hash)


def test_duration_geometry_fps_steps_variation_does_not_drift():
    """The exact six drifting inputs from the release-blocking incident:
    LTXVImgToVideo.width/.height/.length, LTXVConditioning.frame_rate,
    VHS_VideoCombine.frame_rate, BasicScheduler.steps — all per-batch values."""
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    variant["3"]["inputs"].update({"width": 1024, "height": 576, "length": 49})
    variant["5"]["inputs"]["frame_rate"] = 30
    variant["9"]["inputs"]["frame_rate"] = 30
    variant["7"]["inputs"]["steps"] = 20
    _assert_matches_reference(variant, ref_hash)


def test_node_id_relabeling_does_not_drift():
    """WL canonicalization: builders that randomize node IDs per build (e.g.
    hunyuan) must produce identical topology hashes."""
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    relabeled = {}
    id_map = {nid: f"n{1000 + int(nid)}" for nid in reference}
    for nid, node in reference.items():
        new_inputs = {}
        for key, value in node["inputs"].items():
            if isinstance(value, list) and len(value) >= 1 and not isinstance(value[0], (dict, list)):
                new_inputs[key] = [id_map[str(value[0])], value[1]]
            else:
                new_inputs[key] = value
        relabeled[id_map[nid]] = {"class_type": node["class_type"], "inputs": new_inputs}
    _assert_matches_reference(relabeled, ref_hash)


# ---------------------------------------------------------------------------
# DRIFT-BLOCKED cases — true topology changes must fail closed
# ---------------------------------------------------------------------------


def test_node_class_changed_blocks():
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    variant["9"]["class_type"] = "LTXVVideoCombine"  # different saver node
    _assert_blocked(variant, ref_hash)


def test_link_changed_blocks():
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    # Rewire the sampler's positive conditioning past LTXVConditioning,
    # straight to the raw CLIPTextEncode output.
    variant["6"]["inputs"]["positive"] = ["4", 0]
    _assert_blocked(variant, ref_hash)


def test_model_node_missing_blocks():
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    del variant["1"]  # CheckpointLoaderSimple removed — downstream links dangle
    _assert_blocked(variant, ref_hash)


def test_i2v_to_t2v_downgrade_blocks():
    """Removing the image-conditioning path (LoadImage + LTXVImgToVideo) is a
    modality downgrade, not a dynamic substitution — it must block."""
    reference = _ltx_i2v_graph()
    ref_hash = topology_hash(reference)
    variant = _ltx_i2v_graph()
    del variant["2"]
    del variant["3"]
    variant["6"]["inputs"]["latent_image"] = ["10", 0]
    variant["10"] = {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 768, "height": 512, "length": 121}}
    _assert_blocked(variant, ref_hash)


# ---------------------------------------------------------------------------
# Dynamic bindings validation — per-build values checked OUTSIDE the hash
# ---------------------------------------------------------------------------


def test_bindings_report_extracts_notable_values_and_passes_valid_graph():
    report = validate_dynamic_bindings(_ltx_i2v_graph())
    assert report["ok"] is True
    assert report["errors"] == []
    assert report["bindings"]["3.width"] == 768
    assert report["bindings"]["3.length"] == 121
    assert report["bindings"]["5.frame_rate"] == 24
    assert report["bindings"]["7.steps"] == 30
    assert report["bindings"]["2.image"] == "korri_start.png"


def test_bindings_reject_non_positive_geometry_and_dangling_links():
    variant = _ltx_i2v_graph()
    variant["3"]["inputs"]["width"] = 0
    variant["6"]["inputs"]["noise_seed"] = -5
    variant["8"]["inputs"]["vae"] = ["99", 0]  # dangling
    variant["2"]["inputs"]["image"] = "   "  # empty file reference
    report = validate_dynamic_bindings(variant)
    assert report["ok"] is False
    joined = "\n".join(report["errors"])
    assert "width" in joined
    assert "noise_seed" in joined
    assert "not in graph" in joined
    assert "empty file/model reference" in joined
