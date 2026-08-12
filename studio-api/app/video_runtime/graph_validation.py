"""Static Comfy graph validation before queue_prompt (M41 4.1B)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .certified_registry import CertifiedWorkflow, get_workflow


@dataclass
class GraphValidationIssue:
    field: str
    message: str


@dataclass
class GraphValidationResult:
    valid: bool
    issues: list[GraphValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [{"field": i.field, "message": i.message} for i in self.issues],
        }


def _link_targets(graph: Mapping[str, Any]) -> set[str]:
    ids = set(graph.keys())
    return ids


def validate_comfy_graph(
    graph: Mapping[str, Any] | None,
    *,
    workflow_key: str | None = None,
    entry: CertifiedWorkflow | None = None,
    available_nodes: set[str] | None = None,
    available_models: set[str] | None = None,
) -> GraphValidationResult:
    issues: list[GraphValidationIssue] = []
    if not graph or not isinstance(graph, Mapping):
        return GraphValidationResult(False, [GraphValidationIssue("graph", "Graph is empty or not an object")])

    wf = entry or (get_workflow(workflow_key) if workflow_key else None)

    # Node ids + class types
    class_types: list[str] = []
    save_like = 0
    for nid, node in graph.items():
        if not isinstance(node, Mapping):
            issues.append(GraphValidationIssue(str(nid), "Node is not an object"))
            continue
        ct = node.get("class_type")
        if not ct:
            issues.append(GraphValidationIssue(str(nid), "Missing class_type"))
            continue
        class_types.append(str(ct))
        # PreviewAny is a valid Comfy terminal for packs that return path strings
        # (e.g. D_LatentSyncNode) rather than IMAGE/VIDEO tensors.
        if str(ct) in {
            "SaveVideo",
            "VHS_VideoCombine",
            "SaveImage",
            "PreviewImage",
            "PreviewAny",
        }:
            save_like += 1
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, Mapping):
            issues.append(GraphValidationIssue(str(nid), "inputs must be an object"))
            continue
        for k, v in inputs.items():
            if isinstance(v, list) and len(v) >= 1:
                ref = str(v[0])
                if ref not in graph:
                    issues.append(
                        GraphValidationIssue(
                            f"{nid}.{k}",
                            f"Disconnected link to missing node id '{ref}'",
                        )
                    )

    if save_like == 0 and wf and not wf.orchestration and wf.provider_kind.value == "local":
        issues.append(
            GraphValidationIssue(
                "outputs",
                "No SaveVideo/VHS_VideoCombine/SaveImage/PreviewAny output node",
            )
        )
    if save_like > 2:
        issues.append(GraphValidationIssue("outputs", f"Duplicate/ambiguous outputs ({save_like} savers)"))

    if wf:
        if not wf.workflow_version:
            issues.append(GraphValidationIssue("workflowVersion", "Missing workflow version metadata"))
        required = set(wf.required_nodes)
        # Alias groups: if any alias present, satisfy the group
        present = set(class_types)
        missing = set()
        for req in required:
            if req in present:
                continue
            satisfied = False
            for group in wf.node_alias_groups:
                if req in group and present & group:
                    satisfied = True
                    break
            if not satisfied:
                # Only flag if none of an alias group is in required∩present logic
                alias_hit = False
                for group in wf.node_alias_groups:
                    if req in group:
                        alias_hit = True
                        if not (present & group):
                            missing.add("/".join(sorted(group)))
                        break
                if not alias_hit:
                    missing.add(req)
        if available_nodes is not None:
            for m in list(missing):
                parts = m.split("/")
                if any(p in available_nodes for p in parts):
                    # required in graph but may still be ok if graph uses it — check graph
                    if not any(p in present for p in parts):
                        continue
            # Missing from runtime object_info
            runtime_missing = []
            for req in required:
                if req in present or any(req in g and present & g for g in wf.node_alias_groups):
                    # check availability
                    if req not in available_nodes and not any(
                        (available_nodes & g) for g in wf.node_alias_groups if req in g
                    ):
                        runtime_missing.append(req)
            for rm in runtime_missing:
                issues.append(GraphValidationIssue("requiredNodes", f"Node not available in Comfy: {rm}"))
        for m in missing:
            issues.append(GraphValidationIssue("requiredNodes", f"Required node type missing from graph: {m}"))

        if available_models is not None and wf.required_models:
            # Soft: model keys are logical component names; only warn via issue if explicitly empty set probe
            pass

    return GraphValidationResult(valid=not issues, issues=issues)


def assert_graph_valid(
    graph: Mapping[str, Any],
    *,
    workflow_key: str,
    available_nodes: set[str] | None = None,
) -> None:
    result = validate_comfy_graph(
        graph, workflow_key=workflow_key, available_nodes=available_nodes
    )
    if not result.valid:
        detail = "; ".join(f"{i.field}: {i.message}" for i in result.issues)
        raise RuntimeError(f"workflow_invalid:{workflow_key}: {detail}")
