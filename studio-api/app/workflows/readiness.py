"""Public discovery and readiness for registered workflows.

`registry.py` already knows, per workflow, which ComfyUI node types the graph will reference.
This module turns that static metadata into an answerable question — *can this workflow run
right now?* — by comparing it against the live ComfyUI node catalogue and the verified state of
catalogued model components.

Two invariants:

* Readiness never queues anything. It is a read-only pre-flight surface.
* A workflow whose gaps are *known* is never submitted: `ensure_queueable()` raises a
  structured error. When the node catalogue cannot be read, readiness reports `unknown` and
  the guard stays out of the way rather than blocking a run on a guess.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .registry import DEFAULT_WORKFLOW_REGISTRY, WorkflowMetadata

#: Catalogued Setup/Source Manager components each workflow needs on disk.
#: Workflows whose checkpoints are configured by name only (`settings.imagegen_*`,
#: `settings.zimage_*`) have no catalogue entry, so their model requirement is reported as
#: `unknown` instead of being silently treated as satisfied.
WORKFLOW_MODEL_COMPONENTS: dict[str, tuple[str, ...]] = {
    "ltx.scene": ("ltx_checkpoint",),
    "ltx.simple_i2v": ("ltx_checkpoint",),
    "ltx.ingredients_ic_lora": ("ltx_checkpoint", "ltx23_ic_lora_ingredients"),
    "wan.first_last_frame": ("wan_models",),
    "lipsync.latentsync": (),
    # Still-image production path uses catalogued Z-Image Turbo weights (not FLUX name-only).
    "image.txt2img": ("zimage_models",),
    "image.img2img_edit": ("zimage_models",),
    "image.zimage_reference": ("zimage_models",),
}

WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
WORKFLOW_MISSING_MODELS = "WORKFLOW_MISSING_MODELS"
WORKFLOW_MISSING_EXTENSIONS = "WORKFLOW_MISSING_EXTENSIONS"
WORKFLOW_READINESS_UNKNOWN = "WORKFLOW_READINESS_UNKNOWN"

READY = "ready"
BLOCKED = "blocked"
UNKNOWN = "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _describe(metadata: WorkflowMetadata) -> dict[str, Any]:
    return {
        "id": metadata.key,
        "family": metadata.family,
        "modality": metadata.modality,
        "capabilities": list(metadata.capabilities),
        "templateVersion": metadata.template_version,
        "engine": metadata.compatibility.engine,
        "requiredInputs": [item.name for item in metadata.required_inputs],
        "requiredNodeTypes": list(metadata.compatibility.required_node_types),
        "requiredModelComponentIds": list(WORKFLOW_MODEL_COMPONENTS.get(metadata.key, ())),
        "modelRequirementsKnown": bool(WORKFLOW_MODEL_COMPONENTS.get(metadata.key)),
    }


def list_workflows() -> list[dict[str, Any]]:
    """Static description of every registered workflow. No probing, no side effects."""
    return [_describe(metadata) for metadata in DEFAULT_WORKFLOW_REGISTRY.list()]


def _component_states(component_ids: Iterable[str]) -> list[dict[str, Any]]:
    from ..setup.catalog import get_component
    from ..setup.diagnostics import verify_component

    states: list[dict[str, Any]] = []
    for component_id in component_ids:
        try:
            definition = get_component(component_id)
            verification = verify_component(component_id)
            states.append(
                {
                    "componentId": component_id,
                    "name": definition.name,
                    "present": bool(verification.healthy),
                    "issueCode": verification.issue_code,
                    "summary": verification.summary,
                }
            )
        except Exception:  # noqa: BLE001
            states.append(
                {
                    "componentId": component_id,
                    "name": component_id,
                    "present": False,
                    "issueCode": "verification_failed",
                    "summary": "Component verification could not be completed.",
                }
            )
    return states


def workflow_readiness(
    workflow_id: str,
    *,
    node_types: set[str] | None = None,
    model_states: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Readiness for one workflow.

    `node_types` is the live ComfyUI catalogue (None when unreadable). `model_states` lets a
    caller reuse component verification it already performed.
    """
    try:
        metadata = DEFAULT_WORKFLOW_REGISTRY.get(workflow_id)
    except KeyError as exc:
        raise KeyError(workflow_id) from exc

    payload = _describe(metadata)
    required_nodes = tuple(metadata.compatibility.required_node_types)
    required_components = WORKFLOW_MODEL_COMPONENTS.get(workflow_id, ())

    if model_states is None:
        states = _component_states(required_components)
    else:
        states = [
            {
                "componentId": component_id,
                "name": component_id,
                "present": bool(model_states.get(component_id)),
                "issueCode": None if model_states.get(component_id) else "component_not_verified",
                "summary": "",
            }
            for component_id in required_components
        ]

    missing_models = [item for item in states if not item["present"]]
    node_catalog_available = node_types is not None
    missing_extensions = (
        sorted(name for name in required_nodes if name not in node_types)
        if node_types is not None
        else []
    )

    if missing_extensions:
        status = BLOCKED
        reason_code = WORKFLOW_MISSING_EXTENSIONS
        message = (
            f"{workflow_id} needs ComfyUI node types that are not installed: "
            + ", ".join(missing_extensions)
            + "."
        )
        recommended_action = "install_comfyui_extensions"
    elif missing_models:
        status = BLOCKED
        reason_code = WORKFLOW_MISSING_MODELS
        message = (
            f"{workflow_id} needs model components that are not installed: "
            + ", ".join(item["componentId"] for item in missing_models)
            + "."
        )
        recommended_action = "open_source_manager"
    elif not node_catalog_available:
        status = UNKNOWN
        reason_code = WORKFLOW_READINESS_UNKNOWN
        message = (
            "ComfyUI's node catalogue is unavailable, so extension requirements for "
            f"{workflow_id} could not be checked."
        )
        recommended_action = "start_comfyui"
    elif not payload["modelRequirementsKnown"] and required_nodes:
        status = UNKNOWN
        reason_code = WORKFLOW_READINESS_UNKNOWN
        message = (
            f"{workflow_id} has all required ComfyUI nodes, but its checkpoint is configured by "
            "name only and has no catalogued component, so model presence is unverified."
        )
        recommended_action = "verify_model_path"
    else:
        status = READY
        reason_code = None
        message = f"{workflow_id} has all required ComfyUI nodes and model components."
        recommended_action = None

    payload.update(
        {
            "status": status,
            "reasonCode": reason_code,
            "message": message,
            "recommendedAction": recommended_action,
            "nodeCatalogAvailable": node_catalog_available,
            "missingExtensions": missing_extensions,
            "missingModels": [
                {
                    "componentId": item["componentId"],
                    "name": item["name"],
                    "issueCode": item["issueCode"],
                    "summary": item["summary"],
                }
                for item in missing_models
            ],
            "modelComponents": states,
            "checkedAt": _now(),
        }
    )
    return payload


def readiness_report(
    *,
    node_types: set[str] | None = None,
    model_states: Mapping[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """Readiness for every registered workflow, sharing one probe snapshot."""
    return [
        workflow_readiness(metadata.key, node_types=node_types, model_states=model_states)
        for metadata in DEFAULT_WORKFLOW_REGISTRY.list()
    ]


def graph_node_types(graph: Mapping[str, Any]) -> list[str]:
    """`class_type` of every node in a ComfyUI prompt graph, in first-seen order."""
    seen: dict[str, None] = {}
    for node in graph.values():
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("class_type")
        if isinstance(class_type, str) and class_type:
            seen.setdefault(class_type, None)
    return list(seen)


def missing_graph_nodes(
    graph: Mapping[str, Any], node_types: set[str] | None
) -> list[str] | None:
    """Node types the graph needs that ComfyUI does not offer, or None when unknowable."""
    if node_types is None:
        return None
    return sorted(name for name in graph_node_types(graph) if name not in node_types)


def assert_graph_runnable(graph: Mapping[str, Any], node_types: set[str] | None) -> None:
    """Raise before submitting a graph whose node types are provably absent.

    This is the choke point for "never queue an invalid workflow": it inspects the compiled
    graph rather than a workflow id, so every producer (scene render, Txt2Vid, ImageGen,
    lip sync, IC-LoRA) is covered without each call site remembering to ask.

    Unknown is not treated as invalid: when the catalogue cannot be read we submit anyway, so
    a slow `/object_info` never breaks a working install.
    """
    missing = missing_graph_nodes(graph, node_types)
    if not missing:
        return
    from ..capabilities.errors import EXTENSION_MISSING, CapabilityError

    raise CapabilityError(
        code=EXTENSION_MISSING,
        message=(
            "This job needs ComfyUI node types that are not installed: "
            + ", ".join(missing)
            + ". Install the required ComfyUI extensions, then retry."
        ),
        details={"missingExtensions": missing},
        recoverable=True,
        recommended_action="install_comfyui_extensions",
    )


def ensure_queueable(workflow_id: str, *, node_types: set[str] | None) -> dict[str, Any]:
    """Raise when a workflow is *known* to be unrunnable; return its readiness otherwise.

    Deliberately permissive about the unknown case: if ComfyUI's catalogue cannot be read we
    do not block the submission, because refusing on missing evidence would break a working
    install whose `/object_info` is merely slow. What we never do is submit a graph whose
    required nodes are provably absent.
    """
    readiness = workflow_readiness(workflow_id, node_types=node_types)
    if readiness["status"] == BLOCKED:
        from ..capabilities.errors import CapabilityError

        raise CapabilityError(
            code=str(readiness["reasonCode"]),
            message=str(readiness["message"]),
            details={
                "workflowId": workflow_id,
                "missingExtensions": readiness["missingExtensions"],
                "missingModels": [item["componentId"] for item in readiness["missingModels"]],
            },
            recoverable=True,
            recommended_action=str(readiness["recommendedAction"] or "open_source_manager"),
        )
    return readiness
