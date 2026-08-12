"""Immutable workflow fingerprinting and drift detection (M41 4.1B)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class WorkflowGraphDriftError(RuntimeError):
    """Raised when a built graph no longer matches the certified fingerprint."""

    def __init__(self, message: str, *, expected: str | None = None, actual: str | None = None):
        super().__init__(message)
        self.expected = expected
        self.actual = actual


def _sha256_hex(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


_VOLATILE_INPUT_KEYS = frozenset(
    {
        "image",
        "text",
        "filename_prefix",
        "noise_seed",
        "seed",
        "video",
        "audio",
        "video_path",
        "audio_path",
        "ckpt_name",
        "unet_name",
        "vae_name",
        "clip_name",
        "model_name",
    }
)


def _redact_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Keep structure/links; redact volatile scalar values that change per job."""
    out: dict[str, Any] = {}
    for k, v in inputs.items():
        if isinstance(v, list) and len(v) >= 1 and not isinstance(v[0], (dict, list)):
            # Comfy link [node_id, slot]
            out[k] = v
        elif str(k) in _VOLATILE_INPUT_KEYS:
            out[k] = "<redacted>"
        elif isinstance(v, (str, int, float, bool)) or v is None:
            # Numeric geometry/steps kept; long free-text already covered by text key
            out[k] = v
        else:
            out[k] = v
    return out


def canonicalize_graph(graph: Mapping[str, Any] | None) -> str:
    """Stable JSON for Comfy prompt graphs (structure-focused; volatile inputs redacted)."""
    if not graph:
        return "{}"
    normalized: dict[str, Any] = {}
    for nid, node in sorted(graph.items(), key=lambda x: str(x[0])):
        if not isinstance(node, Mapping):
            normalized[str(nid)] = node
            continue
        entry: dict[str, Any] = {"class_type": node.get("class_type")}
        inputs = node.get("inputs")
        if isinstance(inputs, Mapping):
            entry["inputs"] = _redact_inputs(inputs)
        normalized[str(nid)] = entry
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def graph_hash(graph: Mapping[str, Any] | None) -> str:
    return _sha256_hex(canonicalize_graph(graph).encode("utf-8"))


def inventory_hash(items: list[str] | tuple[str, ...] | None) -> str:
    normalized = sorted({str(x).strip() for x in (items or []) if str(x).strip()})
    return _sha256_hex(json.dumps(normalized, separators=(",", ":")).encode("utf-8"))


def builder_source_hash(builder_path: str | None, *, repo_root: Path | None = None) -> str | None:
    """Hash the Python module file that owns the builder (best-effort)."""
    if not builder_path or ":" not in builder_path:
        return None
    module_path, _fn = builder_path.split(":", 1)
    # app.workflows.wan_builder → studio-api/app/workflows/wan_builder.py
    rel = Path(*module_path.split("."))
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        repo_root / "studio-api" / rel.with_suffix(".py"),
        repo_root / rel.with_suffix(".py"),
    ]
    for path in candidates:
        if path.is_file():
            return _sha256_hex(path.read_bytes())
    return _sha256_hex(builder_path.encode("utf-8"))


def compute_fingerprints(
    *,
    graph: Mapping[str, Any] | None = None,
    builder_path: str | None = None,
    required_nodes: list[str] | tuple[str, ...] | None = None,
    required_models: list[str] | tuple[str, ...] | None = None,
    repo_root: Path | None = None,
) -> dict[str, str | None]:
    return {
        "graphHash": graph_hash(graph) if graph is not None else None,
        "builderHash": builder_source_hash(builder_path, repo_root=repo_root),
        "nodeInventoryHash": inventory_hash(required_nodes),
        "modelInventoryHash": inventory_hash(required_models),
    }


def assert_no_graph_drift(
    *,
    built_graph: Mapping[str, Any],
    expected_graph_hash: str | None,
    workflow_key: str,
    workflow_version: str,
) -> str:
    """Fail closed when certified graphHash is set and does not match the built graph."""
    actual = graph_hash(built_graph)
    if not expected_graph_hash:
        return actual
    if actual != expected_graph_hash:
        raise WorkflowGraphDriftError(
            f"WORKFLOW_GRAPH_DRIFT: {workflow_key}@{workflow_version} "
            f"graphHash mismatch (certified={expected_graph_hash}, actual={actual})",
            expected=expected_graph_hash,
            actual=actual,
        )
    return actual


# ---------------------------------------------------------------------------
# Canonical fingerprint contract (Timeline drift repair, 2026-08-07)
#
# CERTIFIED TOPOLOGY FINGERPRINT (topologyHash)
#   = stable graph structure: sorted node IDs -> class_type + link inputs only.
#   All scalar inputs are dynamic bindings, never topology.
#
# RUNTIME INSTANCE VALIDATION (validate_dynamic_bindings)
#   = per-build validation of the dynamic values (prompt, seed, frames, fps,
#   geometry, steps, filename prefix, LoadImage reference, model names).
#
# The legacy graphHash above conflated the two: it hashed per-job geometry
# scalars (width/height/length/frame_rate/steps), so any Timeline batch whose
# duration/resolution/fps/steps differed from the single certification-time
# reference build tripped WORKFLOW_GRAPH_DRIFT. Topology drift still blocks.
# ---------------------------------------------------------------------------


def canonicalize_topology(graph: Mapping[str, Any] | None) -> str:
    """Stable JSON of graph STRUCTURE only, canonical under node-ID relabeling.

    Topology = the multiset of node class_types plus the link structure
    (which input of which node-class connects to which node-class). Node IDs
    are arbitrary labels — some builders (hunyuan) randomize them per build —
    so they are canonicalized away via Weisfeiler–Lehman-style signature
    refinement: every node's signature folds in its class_type and, for each
    link input, the input key and the upstream node's signature. All scalar
    inputs are dynamic bindings and excluded by definition.

    Detects: node added/removed, class_type changed, link rewired (including
    to a different input key), required model node missing, I2V→T2V downgrade.
    """
    if not graph:
        return "[]"
    nodes = {str(nid): node for nid, node in graph.items() if isinstance(node, Mapping)}
    if not nodes:
        return "[]"
    sig = {nid: str(node.get("class_type")) for nid, node in nodes.items()}
    for _ in range(len(nodes)):
        refined: dict[str, str] = {}
        for nid, node in nodes.items():
            parts: list[str] = []
            inputs = node.get("inputs")
            if isinstance(inputs, Mapping):
                for key, value in sorted(inputs.items(), key=lambda kv: str(kv[0])):
                    if isinstance(value, list) and len(value) >= 1 and not isinstance(value[0], (dict, list)):
                        target_sig = sig.get(str(value[0]), "<missing>")
                        parts.append(f"{key}<-{target_sig}")
            refined[nid] = _sha256_hex(f"{sig[nid]}|{'|'.join(parts)}".encode("utf-8"))[:16]
        sig = refined
    return json.dumps(sorted(sig.values()), separators=(",", ":"), ensure_ascii=True)


def topology_hash(graph: Mapping[str, Any] | None) -> str:
    return _sha256_hex(canonicalize_topology(graph).encode("utf-8"))


def assert_no_topology_drift(
    *,
    built_graph: Mapping[str, Any],
    expected_topology_hash: str | None,
    workflow_key: str,
    workflow_version: str,
) -> str:
    """Fail closed when certified topologyHash is set and does not match.

    True topology changes (node added/removed, class_type changed, link changed,
    required model node missing, I2V downgraded to T2V) block generation.
    """
    actual = topology_hash(built_graph)
    if not expected_topology_hash:
        return actual
    if actual != expected_topology_hash:
        raise WorkflowGraphDriftError(
            f"WORKFLOW_GRAPH_DRIFT: {workflow_key}@{workflow_version} "
            f"topologyHash mismatch (certified={expected_topology_hash}, actual={actual})",
            expected=expected_topology_hash,
            actual=actual,
        )
    return actual


# Numeric bindings that must be positive (or non-negative for seeds) to be valid.
_POSITIVE_BINDING_KEYS = frozenset(
    {"width", "height", "length", "frames", "frame_rate", "fps", "steps", "cfg"}
)
_NONNEGATIVE_BINDING_KEYS = frozenset({"seed", "noise_seed"})

# Inputs whose values are worth surfacing in the bindings report.
_NOTABLE_BINDING_KEYS = frozenset(
    {
        "text",
        "prompt",
        "seed",
        "noise_seed",
        "width",
        "height",
        "length",
        "frames",
        "frame_rate",
        "fps",
        "steps",
        "cfg",
        "filename_prefix",
        "image",
        "ckpt_name",
        "unet_name",
        "vae_name",
        "clip_name",
        "model_name",
    }
)

# File/model references must never be empty strings. Empty `text` is legitimate
# (e.g. an intentionally empty negative prompt), so it is NOT in this set.
_NONEMPTY_REF_KEYS = frozenset(
    {
        "filename_prefix",
        "image",
        "video",
        "audio",
        "video_path",
        "audio_path",
        "ckpt_name",
        "unet_name",
        "vae_name",
        "clip_name",
        "model_name",
    }
)


def validate_dynamic_bindings(graph: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate per-build dynamic values WITHOUT executing anything.

    Errors: dangling link targets, non-positive geometry/fps/steps/cfg, negative
    seeds, empty file/model references. Nulls and empty text are recorded but
    not errors (legitimate for optional inputs and empty negative prompts).
    Returns a report with the extracted notable bindings for provenance/export.
    """
    errors: list[str] = []
    bindings: dict[str, Any] = {}
    if not graph:
        return {"ok": False, "errors": ["empty graph"], "bindings": bindings}
    for nid, node in sorted(graph.items(), key=lambda x: str(x[0])):
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for key, value in inputs.items():
            skey = str(key)
            if isinstance(value, list) and len(value) >= 1 and not isinstance(value[0], (dict, list)):
                if str(value[0]) not in graph:
                    errors.append(f"node {nid} ({class_type}).{skey}: link target {value!r} not in graph")
                continue
            if value is None:
                continue
            if isinstance(value, str) and not value.strip() and skey in _NONEMPTY_REF_KEYS:
                errors.append(f"node {nid} ({class_type}).{skey}: empty file/model reference")
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if skey in _POSITIVE_BINDING_KEYS and value <= 0:
                    errors.append(f"node {nid} ({class_type}).{skey}: must be > 0 (got {value})")
                if skey in _NONNEGATIVE_BINDING_KEYS and value < 0:
                    errors.append(f"node {nid} ({class_type}).{skey}: must be >= 0 (got {value})")
            if skey in _NOTABLE_BINDING_KEYS:
                label = f"{nid}.{skey}"
                if skey == "text" and isinstance(value, str) and len(value) > 160:
                    bindings[label] = value[:160] + "…"
                else:
                    bindings[label] = value
    return {"ok": not errors, "errors": errors, "bindings": bindings}
