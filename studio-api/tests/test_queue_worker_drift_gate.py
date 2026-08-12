"""Production-path drift gate regression (Live Drift False-Positive Closure).

Exercises the SAME call sequence the QueueWorker uses for Timeline LTX batches
(queue_worker.py: resolve_from_scene_params → build_leaf_graph →
prepare_executable_graph(enforce_certified_fingerprint=True)) — not the isolated
fingerprint helpers (those are pinned in test_video_runtime_topology_drift.py).

Contract:
- Two legitimate LTX batch configs that differ only in dynamic values
  (duration→frames, fps, steps, seed, prompt, start-image filename, prefix)
  must BOTH pass the gate via the topology path (legacyGraphHashCheck=false).
- A true topology mutation of the built graph must BLOCK with
  WORKFLOW_GRAPH_DRIFT / topologyHash mismatch.
- If the legacy graphHash fallback is ever selected, the raised error must
  explain WHY (self-explaining drift message).

No GPU: prepare_executable_graph runs before any ComfyUI queue_prompt.
"""

from __future__ import annotations

import logging

import pytest

from app.config import settings
from app.video_runtime import workflow_execute
from app.video_runtime.certified_registry import get_workflow
from app.video_runtime.fingerprints import WorkflowGraphDriftError, topology_hash
from app.video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph
from app.video_runtime.workflow_resolver import resolve_from_scene_params

BATCH_A = dict(
    positive="slow push-in on a rain-lit window",
    negative="",
    width=768,
    height=512,
    length=121,  # 5s @ 24fps
    fps=24,
    seed=11,
    start_image="batchA_start.png",
    steps=8,
    filename_prefix="studio/scene1_batchA",
)

# Batch B differs in EVERY dynamic dimension a Timeline batch may vary.
BATCH_B = dict(
    positive="aerial orbit over neon city — completely different prompt",
    negative="low quality",
    width=1280,
    height=720,
    length=241,  # 8s @ 30fps
    fps=30,
    seed=987654321,
    start_image="batchB_different_start_frame.png",
    steps=20,
    filename_prefix="studio/scene1_batchB",
)


def _resolve_ltx_i2v():
    contract = resolve_from_scene_params(
        engine="ltx",
        start_asset_id="asset-start-frame",
        intent="scene_render",
    )
    assert contract.leaf_workflow_key == "ltx.simple_i2v"
    return contract


def _build(contract, bindings):
    return build_leaf_graph(contract, settings=settings, **bindings)


def test_two_legitimate_ltx_batches_pass_via_topology_path(caplog):
    contract = _resolve_ltx_i2v()
    leaf = get_workflow("ltx.simple_i2v")
    assert leaf is not None and leaf.fingerprints.topology_hash, (
        "certified registry entry must carry fingerprints.topologyHash (gate is vacuous otherwise)"
    )

    graph_a = _build(contract, BATCH_A)
    graph_b = _build(contract, BATCH_B)

    # Non-vacuous: the two builds genuinely differ in dynamic bindings yet are
    # topologically identical to each other and to the certified reference.
    assert graph_a != graph_b
    assert topology_hash(graph_a) == topology_hash(graph_b) == leaf.fingerprints.topology_hash

    with caplog.at_level(logging.INFO, logger="app.video_runtime.workflow_execute"):
        prepare_executable_graph(contract, graph_a, enforce_certified_fingerprint=True)
        prepare_executable_graph(contract, graph_b, enforce_certified_fingerprint=True)

    lines = [r.getMessage() for r in caplog.records if "workflowFingerprint" in r.getMessage()]
    assert len(lines) == 2, f"expected one instrumentation line per prepare call: {lines}"
    for line in lines:
        assert "workflow=ltx.simple_i2v@" in line
        assert "selectedPath=topology" in line
        assert "topologyMatch=true" in line
        assert "bindingsValid=true" in line
        assert "legacyGraphHashCheck=false" in line


def test_topology_mutation_blocks_on_production_path():
    """Node added to the built graph: passes static validation (all required
    nodes + saver still present) but changes the topology multiset — the drift
    gate must block it."""
    contract = _resolve_ltx_i2v()
    graph = _build(contract, BATCH_A)

    mutated = {nid: dict(node) for nid, node in graph.items()}
    mutated["99"] = {
        "class_type": "LTXVConditioning",
        "inputs": {"positive": ["2", 0], "negative": ["3", 0], "frame_rate": 24},
    }

    with pytest.raises(WorkflowGraphDriftError) as excinfo:
        prepare_executable_graph(contract, mutated, enforce_certified_fingerprint=True)
    assert "topologyHash mismatch" in str(excinfo.value)


def test_link_rewire_blocks_on_production_path():
    """Rewire LTXVConditioning.negative from the CLIPTextEncode to the text
    encoder loader: target node exists (no dangling link), every required node
    type and the saver remain — static validation passes — but the upstream
    signature changes, so the topology gate must block."""
    contract = _resolve_ltx_i2v()
    graph = _build(contract, BATCH_A)

    mutated = {nid: dict(node) for nid, node in graph.items()}
    conditioning = next(nid for nid, n in mutated.items() if n.get("class_type") == "LTXVConditioning")
    inputs = dict(mutated[conditioning]["inputs"])
    assert inputs["negative"][0] != "1b"
    inputs["negative"] = ["1b", 0]  # LTXAVTextEncoderLoader instead of CLIPTextEncode
    mutated[conditioning] = {**mutated[conditioning], "inputs": inputs}

    with pytest.raises(WorkflowGraphDriftError) as excinfo:
        prepare_executable_graph(contract, mutated, enforce_certified_fingerprint=True)
    assert "topologyHash mismatch" in str(excinfo.value)


def test_legacy_fallback_error_explains_selection_reason(monkeypatch):
    """If an unmigrated Certified entry (graphHash but no topologyHash) is ever
    encountered, the raised drift error must say WHY graphHash was selected."""
    contract = _resolve_ltx_i2v()
    graph = _build(contract, BATCH_A)
    leaf = get_workflow("ltx.simple_i2v")
    assert leaf is not None

    unmigrated = type(leaf)(
        **{**leaf.__dict__, "fingerprints": type(leaf.fingerprints)(graph_hash="sha256:deadbeef")}
    )
    monkeypatch.setattr(workflow_execute, "get_workflow", lambda key: unmigrated)

    with pytest.raises(WorkflowGraphDriftError) as excinfo:
        prepare_executable_graph(contract, graph, enforce_certified_fingerprint=True)
    message = str(excinfo.value)
    assert "graphHash mismatch" in message
    assert "legacy graphHash selected because" in message
    assert "topologyHash" in message
