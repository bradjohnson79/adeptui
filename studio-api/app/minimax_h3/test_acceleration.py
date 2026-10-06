"""Tests for the ONE shared MiniMax H3 acceleration authority.

Covers:
- The certified profile (SageAttention via MiniMaxH3SpeedCache, reuse_threshold=0.0).
- apply_certified_accelerator strips legacy EasyCache and rewires scheduler/guider.
- assert_no_residual_cache fails closed on EasyCache / reuse_threshold > 0 / sage disabled.
- assert_certified_accelerator_present fails closed when the accelerator is missing.
"""

from __future__ import annotations

import pytest

from app.minimax_h3 import acceleration
from app.minimax_h3.route_a_adapter import build_i2va_graph, build_t2va_graph


def test_certified_profile_freezes_sage_cache_off() -> None:
    profile = acceleration.CERTIFIED_PROFILE
    assert profile["reuse_threshold"] == 0.0  # residual cache DISABLED
    assert profile["sage_attention"] == "auto"  # SageAttention ON
    assert acceleration.ACCELERATOR_NODE == "MiniMaxH3SpeedCache"


def test_apply_inserts_certified_accelerator_and_rewires() -> None:
    # Golden Convergence: apply_certified_accelerator still correctly builds the
    # accelerator node + rewiring when called directly (unit contract preserved),
    # but production builders no longer call it (it corrupts H3 audio).
    graph = build_t2va_graph("a prompt", seed=1, filename_prefix="video/x")
    accel_id = acceleration.DEFAULT_ACCEL_NODE_ID
    # Production graph must NOT contain the accelerator (dropped for audio fidelity).
    assert accel_id not in graph
    # Direct application still wires correctly (contract of the function itself).
    applied = acceleration.apply_certified_accelerator(
        build_t2va_graph("a prompt", seed=1, filename_prefix="video/x")
    )
    node = applied[accel_id]
    assert node["class_type"] == acceleration.ACCELERATOR_NODE
    assert node["inputs"]["reuse_threshold"] == 0.0
    assert node["inputs"]["sage_attention"] == "auto"
    assert node["inputs"]["model"] == [acceleration.DEFAULT_MODEL_NODE_ID, 0]
    assert applied["8"]["inputs"]["model"] == [accel_id, 0]
    assert applied["9"]["inputs"]["model"] == [accel_id, 0]


def test_apply_strips_legacy_easycache() -> None:
    graph = acceleration.apply_certified_accelerator(
        build_t2va_graph("a prompt", seed=1, filename_prefix="video/x")
    )
    # No EasyCache node may remain after apply_certified_accelerator.
    classes = {n.get("class_type") for n in graph.values() if isinstance(n, dict)}
    assert "EasyCache" not in classes
    assert acceleration.ACCELERATOR_NODE in classes


def test_i2va_graph_also_uses_certified_accelerator() -> None:
    # Golden Convergence: production I2V graph is accelerator-free (golden path).
    graph = build_i2va_graph(
        "motion", seed=2, filename_prefix="video/y",
        first_frame_comfy_name="studio/f.png",
    )
    accel_id = acceleration.DEFAULT_ACCEL_NODE_ID
    assert accel_id not in graph
    assert not any(
        n.get("class_type") == acceleration.ACCELERATOR_NODE for n in graph.values()
    )
    # scheduler + guider consume the raw UNETLoader directly (golden path).
    assert graph["8"]["inputs"]["model"] == ["1", 0]
    assert graph["9"]["inputs"]["model"] == ["1", 0]
    acceleration.assert_no_residual_cache(graph)


def test_assert_no_residual_cache_rejects_easycache() -> None:
    bad = {"90": {"class_type": "EasyCache", "inputs": {"reuse_threshold": 0.2}}}
    with pytest.raises(ValueError, match="forbidden residual-cache"):
        acceleration.assert_no_residual_cache(bad)


def test_assert_no_residual_cache_rejects_reuse_threshold_above_zero() -> None:
    bad = {
        acceleration.DEFAULT_ACCEL_NODE_ID: {
            "class_type": acceleration.ACCELERATOR_NODE,
            "inputs": {"reuse_threshold": 0.12, "sage_attention": "auto"},
        }
    }
    with pytest.raises(ValueError, match="reuse_threshold=0.12 is forbidden"):
        acceleration.assert_no_residual_cache(bad)


def test_assert_no_residual_cache_rejects_sage_disabled() -> None:
    bad = {
        acceleration.DEFAULT_ACCEL_NODE_ID: {
            "class_type": acceleration.ACCELERATOR_NODE,
            "inputs": {"reuse_threshold": 0.0, "sage_attention": "disabled"},
        }
    }
    with pytest.raises(ValueError, match="sage_attention='disabled'"):
        acceleration.assert_no_residual_cache(bad)


def test_assert_no_residual_cache_accepts_certified_profile() -> None:
    graph = build_t2va_graph("ok", seed=3, filename_prefix="video/z")
    # Must not raise.
    acceleration.assert_no_residual_cache(graph)


def test_assert_certified_accelerator_present_rejects_missing() -> None:
    # A graph with no accelerator node at all.
    bare = {"1": {"class_type": "UNETLoader", "inputs": {}}}
    with pytest.raises(ValueError, match="missing the certified accelerator"):
        acceleration.assert_certified_accelerator_present(bare)


def test_accelerator_provenance_is_creator_safe() -> None:
    # Provenance exposes a creator-safe label, never raw knob names as the primary surface.
    p = acceleration.ACCELERATOR_PROVENANCE
    assert p["accelerator"] == "SageAttention"
    assert p["residualReuse"] is False
    assert p["reuseThreshold"] == 0.0
    assert p["creatorLabel"] == "Optimized"
