"""Immutable image workflow fingerprinting and drift detection (M42 W2)."""

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
        "prompt",
        "filename_prefix",
        "noise_seed",
        "seed",
        "unet_name",
        "vae_name",
        "clip_name",
        "clip_vision_name",
        "ckpt_name",
        "model_name",
    }
)


def _redact_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in inputs.items():
        if isinstance(v, list) and len(v) >= 1 and not isinstance(v[0], (dict, list)):
            out[k] = v
        elif str(k) in _VOLATILE_INPUT_KEYS:
            out[k] = "<redacted>"
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = v
    return out


def canonicalize_graph(graph: Mapping[str, Any] | None) -> str:
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


def file_content_hash(path: Path | str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return _sha256_hex(p.read_bytes())


def builder_source_hash(builder_path: str | None, *, repo_root: Path | None = None) -> str | None:
    if not builder_path or ":" not in builder_path:
        return None
    module_path, _fn = builder_path.split(":", 1)
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
