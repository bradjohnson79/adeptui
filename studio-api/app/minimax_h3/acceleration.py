"""Canonical MiniMax H3 Acceleration Authority (v1.1, single source of truth).

This module is the ONE shared MiniMax H3 acceleration authority consumed by every
MiniMax H3 CREATE surface (Text2Video, 1 Frame I2V, 3 Frame multi-frame assembly).

Frozen benchmark verdict (live Comfy MCP, RTX 5090, Korri 4-step baseline):
  1 Frame I2V (Korri 1F):
    - Baseline (no accelerator)        : 347.15s, clean, AV intact
    - Speed Cache residual reuse (0.12): faster, SEVERE ghost/echo/ripple artifacts -> NO-GO
    - Speed Cache residual reuse (0.08): faster, SAME severe artifacts          -> NO-GO
    - SageAttention-only (cache OFF)   : ~161.9s, 2.14x, CLEAN, AV intact, stable
  Text2Video (T2V, 124 frames):
    - Baseline (no accelerator)        : 98.94s (cold), clean, AV intact (h264+aac)
    - SageAttention-only (cache OFF)   : 45.33s, ~2.18x, CLEAN, AV intact, stable
  3 Frame multi-frame: NOT YET CERTIFIED (plan-only; no MiniMax 3F execution orchestrator).

CERTIFIED ACCELERATOR = SageAttention.
The ``MiniMaxH3SpeedCache`` node is ONLY the delivery surface for SageAttention.
Residual reuse is DISABLED (reuse_threshold = 0.0) for v1.1 production.

Quality > speed. No surface may trade fast-motion clarity, temporal stability,
character consistency, fine detail, audio quality, or AV sync for benchmark speed.
If any surface shows quality regression with SageAttention, it is NOT certified.

This module must not be duplicated. T2V / 1F / 3F builders call
``apply_certified_accelerator`` — they do not hand-write the accelerator node.
"""

from __future__ import annotations

from typing import Any

# --- Frozen certified profile (MCP-verified on :8188) ------------------------

ACCELERATOR_NODE = "MiniMaxH3SpeedCache"
ACCELERATOR_PACK = "comfyui-speed-minimaxH3"
ACCELERATOR_DISPLAY = "MiniMax H3 Speed Cache (Safe)"

# The certified profile. reuse_threshold = 0.0 DISABLES the residual cache so
# no transformer-block residuals are reused across sampling steps (the cause of
# the severe echo/ghost/ripple artifacts on 4-step distilled sampling). Only
# SageAttention (sage_attention="auto") remains active — a non-cache attention
# backend optimization that accelerates each step without reusing residuals.
CERTIFIED_PROFILE: dict[str, Any] = {
    "reuse_threshold": 0.0,        # RESIDUAL CACHE OFF — do not re-enable
    "start_percent": 0.10,
    "end_percent": 0.90,
    "max_consecutive_skips": 2,
    "cache_device": "auto",
    "sage_attention": "auto",     # SageAttention ON (the real accelerator)
    # Optional reserves left at node defaults (omitted from graph -> Comfy uses defaults).
}

# Node ids used by the MiniMax H3 graph builders. Kept here so the authority owns
# the wiring contract. ``model_node_id`` is the UNETLoader output; consumers of it
# are rewired to the accelerator output.
DEFAULT_MODEL_NODE_ID = "1"
DEFAULT_ACCEL_NODE_ID = "16"

# Residual-cache node classes FORBIDDEN in v1.1 production CREATE graphs.
# EasyCache was the legacy accelerator in route_a_adapter.py (threshold 0.2) and
# caused the same visual regression as Speed Cache residual reuse.
FORBIDDEN_RESIDUAL_CACHE_NODES = frozenset({
    "EasyCache",
    "MiniMaxH3EasyCache",
})

# Provenance label exposed to creators (never the raw knob names).
ACCELERATOR_PROVENANCE = {
    "accelerator": "SageAttention",
    "deliveryNode": ACCELERATOR_NODE,
    "residualReuse": False,
    "reuseThreshold": 0.0,
    "sageAttention": "auto",
    "profile": "MiniMax H3 v1.1 Certified (SageAttention, cache off)",
    "creatorLabel": "Optimized",
}


def certified_accelerator_node(
    *,
    model_node_id: str = DEFAULT_MODEL_NODE_ID,
    accel_node_id: str = DEFAULT_ACCEL_NODE_ID,
) -> dict[str, Any]:
    """Return the canonical accelerator graph node (the single certified profile)."""
    return {
        "class_type": ACCELERATOR_NODE,
        "inputs": {
            "model": [model_node_id, 0],
            **CERTIFIED_PROFILE,
        },
        # NOTE: node id is assigned by the caller when inserted into the graph dict.
        # We return the node body; the caller places it under graph[accel_node_id].
    }


def apply_certified_accelerator(
    graph: dict[str, Any],
    *,
    model_node_id: str = DEFAULT_MODEL_NODE_ID,
    accel_node_id: str = DEFAULT_ACCEL_NODE_ID,
) -> dict[str, Any]:
    """Insert the ONE certified SageAttention accelerator and rewire model consumers.

    - Removes any legacy EasyCache / residual-cache node and its wiring.
    - Inserts ``MiniMaxH3SpeedCache`` with the certified profile (cache OFF, sage auto).
    - Rewires every node whose ``model`` input pointed at [model_node_id, 0] to
      [accel_node_id, 0] (scheduler, guider, and any other model consumer).

    This is the single entry point all surfaces (T2V / 1F / 3F) must call. They must
    NOT hand-write the accelerator node or re-enable residual reuse.
    """
    # 1. Strip forbidden residual-cache nodes and their wiring.
    for nid in list(graph.keys()):
        node = graph.get(nid) or {}
        if not isinstance(node, dict):
            continue
        if node.get("class_type") in FORBIDDEN_RESIDUAL_CACHE_NODES:
            graph.pop(nid, None)

    # 2. Insert the certified accelerator node (single source: certified_accelerator_node).
    #    It returns the node body (class_type + inputs incl. model + CERTIFIED_PROFILE);
    #    the caller places it under graph[accel_node_id]. Do NOT hand-write a duplicate
    #    here — that would silently diverge from certified_accelerator_node if the
    #    certified profile is ever updated.
    graph[accel_node_id] = certified_accelerator_node(
        model_node_id=model_node_id,
        accel_node_id=accel_node_id,
    )

    # 3. Rewire every model consumer that pointed at the raw UNETLoader to the
    #    accelerator output. This covers BasicScheduler, BasicGuider, and any
    #    other node whose "model" input was [model_node_id, 0].
    accel_ref = [accel_node_id, 0]
    model_ref = [model_node_id, 0]
    for nid, node in graph.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        model_in = inputs.get("model")
        # Rewire scheduler/guider/etc. that consumed the raw model directly.
        # Do NOT rewire the accelerator's own model input (it must stay [model_node_id, 0]).
        if nid == accel_node_id:
            continue
        if isinstance(model_in, list) and len(model_in) == 2 and model_in == model_ref:
            inputs["model"] = accel_ref

    return graph


def assert_no_residual_cache(graph: dict[str, Any]) -> None:
    """Fail closed if a production CREATE graph contains a residual-reuse cache.

    Enforces Phase 6: reuse_threshold must be 0.0 in v1.1 production. Any EasyCache,
    any MiniMaxH3SpeedCache with reuse_threshold > 0, or any other known residual
    cache node is a certification blocker.
    """
    for nid, node in (graph or {}).items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type") or ""
        inputs = node.get("inputs") or {}
        if cls in FORBIDDEN_RESIDUAL_CACHE_NODES:
            raise ValueError(
                f"Production MiniMax H3 graph contains forbidden residual-cache node "
                f"'{cls}' ({nid}). Residual reuse is disabled in v1.1 (visual regression). "
                f"Use apply_certified_accelerator (SageAttention, cache off)."
            )
        if cls == ACCELERATOR_NODE:
            threshold = inputs.get("reuse_threshold")
            try:
                t = float(threshold) if threshold is not None else 0.12
            except (TypeError, ValueError):
                t = 0.12
            if t > 0.0:
                raise ValueError(
                    f"MiniMaxH3SpeedCache reuse_threshold={t} is forbidden in v1.1 "
                    f"production (residual reuse causes severe visual regression). "
                    f"Certified profile requires reuse_threshold=0.0 (cache off) + "
                    f"sage_attention='auto'."
                )
            sage = str(inputs.get("sage_attention") or "auto").lower()
            if sage == "disabled":
                raise ValueError(
                    "MiniMaxH3SpeedCache sage_attention='disabled' disables the certified "
                    "accelerator. v1.1 production requires sage_attention='auto' (or 'enabled')."
                )


def assert_certified_accelerator_present(graph: dict[str, Any]) -> None:
    """Fail closed if a production MiniMax H3 CREATE graph lacks the certified accelerator."""
    found = False
    for nid, node in (graph or {}).items():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == ACCELERATOR_NODE:
            found = True
            break
    if not found:
        raise ValueError(
            "Production MiniMax H3 graph is missing the certified accelerator "
            f"({ACCELERATOR_NODE}, reuse_threshold=0.0, sage_attention='auto'). "
            f"All MiniMax H3 CREATE surfaces must consume apply_certified_accelerator."
        )
    assert_no_residual_cache(graph)
