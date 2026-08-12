from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ...comfy_health import node_types as load_node_types
from ...workflows.readiness import WORKFLOW_MODEL_COMPONENTS, workflow_readiness
from ...workflows.registry import DEFAULT_WORKFLOW_REGISTRY
from .schema import RequiredComponentResolution, RequiredNodeResolution

_KNOWN_EXTENSION_COMPONENT_IDS = (
    "comfyui_hunyuan_nodes",
    "comfyui_hunyuan_video_nodes",
)

# The catalogued ComfyUI extension representative currently installs
# Kijai's wrapper package, which exports the HyVideo* node family rather
# than the older/native HunyuanVideo15*/13B* node ids.
_KNOWN_HUNYUAN_NODES = frozenset(
    {
        "HyVideoModelLoader",
        "HyVideoSampler",
        "HyVideoTextEncode",
        "HyVideoI2VEncode",
        "HyVideoVAELoader",
        "DownloadAndLoadHyVideoTextEncoder",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _live_node_types() -> set[str] | None:
    try:
        return asyncio.run(load_node_types())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(load_node_types())
        finally:
            loop.close()


def _match_workflows(capability_id: str) -> list[str]:
    needle = capability_id.strip().lower()
    matched: list[str] = []
    family_aliases = {
        "hunyuan_video_15": "hunyuan15",
        "hunyuan_video_13b": "hunyuan13b",
    }
    family_hint = family_aliases.get(needle, needle)
    for metadata in DEFAULT_WORKFLOW_REGISTRY.list():
        family = metadata.family.lower()
        capabilities = {item.lower() for item in metadata.capabilities}
        if needle == metadata.key.lower() or needle in capabilities:
            matched.append(metadata.key)
            continue
        if family_hint.startswith("hunyuan") and family == family_hint:
            matched.append(metadata.key)
            continue
        if needle.startswith("hunyuan") and family.startswith("hunyuan"):
            matched.append(metadata.key)
    return matched


def _registered_extension_component_id() -> str | None:
    from ...setup.catalog import BY_ID

    for component_id in _KNOWN_EXTENSION_COMPONENT_IDS:
        if component_id in BY_ID:
            return component_id
    return None


def resolve_requirements(capability_id: str) -> RequiredComponentResolution:
    workflows = _match_workflows(capability_id)
    if not workflows:
        return RequiredComponentResolution(
            capabilityId=capability_id,
            workflowIds=[],
            status="unknown",
            message="No registered workflows matched this capability.",
            recommendedAction="review_workflows",
            checkedAt=_now(),
        )

    live_nodes = _live_node_types()
    required_nodes: set[str] = set()
    required_components: set[str] = set()
    missing_nodes: set[str] = set()
    missing_components: set[str] = set()
    messages: list[str] = []
    for workflow_id in workflows:
        readiness = workflow_readiness(workflow_id, node_types=live_nodes)
        required_nodes.update(readiness.get("requiredNodeTypes") or [])
        required_components.update(readiness.get("requiredComponentIds") or [])
        missing_nodes.update(readiness.get("missingExtensions") or [])
        missing_components.update(
            item.get("componentId")
            for item in readiness.get("missingModels") or []
            if isinstance(item, dict) and item.get("componentId")
        )
        if readiness.get("message"):
            messages.append(str(readiness["message"]))

    extension_component_id = _registered_extension_component_id()
    node_resolutions = []
    for node_type in sorted(missing_nodes):
        if node_type in _KNOWN_HUNYUAN_NODES:
            node_resolutions.append(
                RequiredNodeResolution(
                    nodeType=node_type,
                    extensionComponentId=extension_component_id or "comfyui_hunyuan_nodes",
                    sourceStatus="official" if extension_component_id else "user_required",
                    message=(
                        "Mapped to the Hunyuan ComfyUI extension component. Install, restart ComfyUI, then verify nodes."
                        if extension_component_id
                        else "This Hunyuan node is known, but no installable ComfyUI extension component is registered."
                    ),
                )
            )
        else:
            node_resolutions.append(
                RequiredNodeResolution(
                    nodeType=node_type,
                    extensionComponentId=None,
                    sourceStatus="user_required",
                    message="No catalogued extension component is registered for this node type.",
                )
            )

    if missing_nodes:
        status = "blocked"
        action = "install_comfyui_extensions"
    elif missing_components:
        status = "blocked"
        action = "open_source_manager"
    elif live_nodes is None:
        status = "unknown"
        action = "start_comfyui"
    else:
        status = "ready"
        action = None

    message = (
        "; ".join(dict.fromkeys(messages))
        if messages
        else "Capability requirements resolved."
    )
    return RequiredComponentResolution(
        capabilityId=capability_id,
        workflowIds=workflows,
        requiredNodeTypes=sorted(required_nodes),
        missingNodeTypes=sorted(missing_nodes),
        requiredComponentIds=sorted(required_components),
        missingComponentIds=sorted(item for item in missing_components if item),
        nodeResolutions=node_resolutions,
        status=status,
        recommendedAction=action,
        message=message,
        checkedAt=_now(),
    )
