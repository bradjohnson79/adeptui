"""Capability evaluation: static registry + live probes → honest status per capability.

Evaluation order matters:

1. Start from the registry baseline (what the code can do at all).
2. Apply the capability's own live evaluator (what the environment allows right now).
3. Propagate dependency failures, so a capability is never advertised as usable while one of
   its dependencies is blocked.
4. Apply project scope, so a project-scoped capability for a missing project is blocked
   rather than falsely global.

A live evaluator may only *lower* confidence relative to the baseline. It can resolve
`unknown`, it can turn `locally_verified` into `blocked`, and it can turn a code-level
`backend_only` into `locally_verified` **only** when the probe proves the real dependency is
present (never when a mock answered).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Optional

from . import errors
from .models import (
    BLOCKING_STATUSES,
    USABLE_STATUSES,
    CapabilityBlockerOut,
    CapabilityDefinition,
    CapabilityEvaluation,
    CapabilityOut,
    CapabilitySnapshotOut,
    CapabilityStatus,
)
from .probes import ProbeSnapshot, build_snapshot
from .registry import CAPABILITIES, get_definition

S = CapabilityStatus

#: How long a snapshot may be reused before a read re-probes. Refresh is also explicit via
#: POST /api/capabilities/refresh.
SNAPSHOT_TTL_SEC = 20.0

_cache: dict[str, Any] = {"snapshot": None, "at": 0.0, "project_id": None}
_lock = asyncio.Lock()

Evaluator = Callable[[CapabilityDefinition, ProbeSnapshot], CapabilityEvaluation]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _ok(status: CapabilityStatus, message: str = "", **kwargs: Any) -> CapabilityEvaluation:
    return CapabilityEvaluation(
        status=status,
        available=status in USABLE_STATUSES,
        message=message,
        **kwargs,
    )


def _blocked(
    reason_code: str,
    message: str,
    *,
    recommended_action: str,
    component_ids: tuple[str, ...] = (),
    configured: bool = True,
    healthy: bool = False,
    status: CapabilityStatus = S.BLOCKED,
    details: dict[str, Any] | None = None,
) -> CapabilityEvaluation:
    return CapabilityEvaluation(
        status=status,
        available=False,
        configured=configured,
        healthy=healthy,
        reason_code=reason_code,
        message=message,
        recommended_action=recommended_action,
        component_ids=component_ids,
        details=details or {},
    )


def _baseline(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    """Default evaluation for capabilities with no live dependency of their own."""
    status = definition.baseline_status
    if status == S.NOT_IMPLEMENTED:
        return CapabilityEvaluation(
            status=status,
            available=False,
            configured=False,
            healthy=True,
            reason_code=errors.CAPABILITY_NOT_IMPLEMENTED,
            message=definition.baseline_reason or f"{definition.display_name} is not implemented in this build.",
            recommended_action="none",
        )
    if status == S.UI_ONLY:
        return CapabilityEvaluation(
            status=status,
            available=False,
            configured=True,
            healthy=True,
            reason_code=errors.CAPABILITY_UI_ONLY,
            message=definition.baseline_reason or "A UI affordance exists with no durable backend.",
            recommended_action="none",
        )
    if status == S.NOT_CONFIGURED:
        return CapabilityEvaluation(
            status=status,
            available=False,
            configured=False,
            healthy=True,
            reason_code=errors.DEPENDENCY_NOT_CONFIGURED,
            message=definition.baseline_reason or definition.summary,
            recommended_action="enable_feature_flag",
        )
    if status in (S.PARTIALLY_WIRED, S.BACKEND_ONLY, S.MOCK_VERIFIED, S.UNKNOWN):
        return CapabilityEvaluation(
            status=status,
            available=False,
            configured=True,
            healthy=True,
            reason_code=errors.CAPABILITY_UNVERIFIED,
            message=definition.baseline_reason or definition.summary,
            recommended_action="verify_slice",
        )
    return _ok(status, definition.summary)


def _requires_storage(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> Optional[CapabilityEvaluation]:
    if snapshot.storage_writable is False:
        return _blocked(
            errors.STORAGE_NOT_WRITABLE,
            snapshot.storage_message,
            recommended_action="choose_data_directory",
        )
    return None


def _requires_database(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> Optional[CapabilityEvaluation]:
    if snapshot.database_ok is False:
        return _blocked(
            errors.STORAGE_NOT_WRITABLE,
            snapshot.database_message,
            recommended_action="run_diagnostics",
        )
    return None


# ---------------------------------------------------------------------------
# per-capability evaluators
# ---------------------------------------------------------------------------


def _eval_storage(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    if snapshot.storage_writable is None:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "Storage writability could not be checked.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    if not snapshot.storage_writable:
        return _blocked(
            errors.STORAGE_NOT_WRITABLE,
            snapshot.storage_message,
            recommended_action="choose_data_directory",
        )
    return _ok(S.LOCALLY_VERIFIED, snapshot.storage_message)


def _eval_database(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    if snapshot.database_ok is None:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "Project database state could not be checked.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    if not snapshot.database_ok:
        return _blocked(
            errors.STORAGE_NOT_WRITABLE,
            snapshot.database_message,
            recommended_action="run_diagnostics",
        )
    return _ok(S.LOCALLY_VERIFIED, snapshot.database_message)


def _eval_db_backed(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    """Projects/scenes/assets: verified slices whose only dependency is local storage."""
    blocked = _requires_database(definition, snapshot) or (
        _requires_storage(definition, snapshot) if not definition.read_only else None
    )
    if blocked:
        return blocked
    return _baseline(definition, snapshot)


def _eval_comfy_health(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    comfy = snapshot.comfy
    if comfy is None:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "ComfyUI health could not be probed.",
            recommended_action="run_diagnostics",
            component_ids=("comfyui",),
            status=S.UNKNOWN,
        )
    if not comfy.get("reachable"):
        return _blocked(
            errors.DEPENDENCY_UNAVAILABLE,
            str(comfy.get("message") or "ComfyUI is not reachable."),
            recommended_action=str(comfy.get("recommendedAction") or "start_comfyui"),
            component_ids=("comfyui",),
            details={"baseUrl": comfy.get("baseUrl")},
        )
    if comfy.get("status") == "degraded":
        return CapabilityEvaluation(
            status=S.DEGRADED,
            available=True,
            configured=True,
            healthy=False,
            reason_code=str(comfy.get("reasonCode") or errors.DEPENDENCY_DEGRADED),
            message=str(comfy.get("message") or ""),
            recommended_action=str(comfy.get("recommendedAction") or "open_source_manager"),
            component_ids=("comfyui",),
            details={
                "version": comfy.get("version"),
                "nodeTypeCount": comfy.get("nodeTypeCount"),
                "missingModelComponentIds": comfy.get("missingModelComponentIds"),
            },
        )
    return CapabilityEvaluation(
        status=S.LOCALLY_VERIFIED,
        available=True,
        message=str(comfy.get("message") or "ComfyUI is reachable."),
        details={
            "version": comfy.get("version"),
            "nodeTypeCount": comfy.get("nodeTypeCount"),
            "devices": comfy.get("devices"),
        },
    )


def _eval_comfy_dependent(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    comfy = snapshot.comfy
    if comfy is None or not comfy.get("reachable"):
        return _blocked(
            errors.DEPENDENCY_UNAVAILABLE,
            "ComfyUI is not reachable, so this capability cannot run.",
            recommended_action="start_comfyui",
            component_ids=("comfyui",),
        )
    return _baseline(definition, snapshot)


def _eval_extensions_ready(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    if snapshot.node_types is None:
        return _blocked(
            errors.WORKFLOW_READINESS_UNKNOWN,
            "ComfyUI's node catalogue is unavailable, so extension readiness is unknown.",
            recommended_action="start_comfyui",
            component_ids=("comfyui",),
            status=S.UNKNOWN,
        )
    missing: set[str] = set()
    for workflow in snapshot.workflows:
        missing.update(workflow.get("missingExtensions") or [])
    if missing:
        return _blocked(
            errors.EXTENSION_MISSING,
            "Required ComfyUI node types are missing: " + ", ".join(sorted(missing)) + ".",
            recommended_action="install_comfyui_extensions",
            component_ids=("comfyui",),
            details={"missingExtensions": sorted(missing)},
        )
    return _ok(
        S.LOCALLY_VERIFIED,
        "All node types required by registered workflows are installed.",
        details={"nodeTypeCount": len(snapshot.node_types)},
    )


def _model_component_eval(
    definition: CapabilityDefinition,
    snapshot: ProbeSnapshot,
    *,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> CapabilityEvaluation:
    if not snapshot.setup_components:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "Component verification is unavailable, so model readiness is unknown.",
            recommended_action="run_diagnostics",
            component_ids=required,
            status=S.UNKNOWN,
        )
    missing = [cid for cid in required if snapshot.component_ready(cid) is not True]
    if missing:
        pending = [
            cid
            for cid in missing
            if str((snapshot.component(cid) or {}).get("status"))
            in ("source_pending", "download_unavailable")
        ]
        reason = errors.MODEL_SOURCE_PENDING if pending else errors.MODEL_MISSING
        detail_names = ", ".join(
            str((snapshot.component(cid) or {}).get("name") or cid) for cid in missing
        )
        return _blocked(
            reason,
            f"Not installed: {detail_names}.",
            recommended_action="open_source_manager",
            component_ids=tuple(missing),
            configured=not pending,
            status=S.NOT_CONFIGURED if pending else S.BLOCKED,
            details={
                "missingComponentIds": missing,
                "componentStatuses": {
                    cid: str((snapshot.component(cid) or {}).get("status") or "unknown")
                    for cid in required + optional
                },
            },
        )
    missing_optional = [cid for cid in optional if snapshot.component_ready(cid) is not True]
    if missing_optional:
        return CapabilityEvaluation(
            status=S.DEGRADED,
            available=True,
            healthy=False,
            reason_code=errors.MODEL_MISSING,
            message=(
                "Required weights are installed; optional components are missing: "
                + ", ".join(missing_optional)
                + "."
            ),
            recommended_action="open_source_manager",
            component_ids=tuple(missing_optional),
            details={"missingOptionalComponentIds": missing_optional},
        )
    return _ok(S.LOCALLY_VERIFIED, "Required model components are verified on disk.")


def _eval_models_image(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    return _model_component_eval(definition, snapshot, required=("ltx_checkpoint",))


def _eval_models_video(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    return _model_component_eval(
        definition, snapshot, required=("ltx_checkpoint",), optional=("wan_models",)
    )


def _workflow_aggregate(
    definition: CapabilityDefinition,
    snapshot: ProbeSnapshot,
    *,
    modality: str | None,
) -> CapabilityEvaluation:
    workflows = (
        snapshot.workflows if modality is None else snapshot.workflows_for_modality(modality)
    )
    if not workflows:
        return _blocked(
            errors.WORKFLOW_READINESS_UNKNOWN,
            "Workflow readiness is unavailable.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    ready = [item for item in workflows if item.get("status") == "ready"]
    if ready:
        return _ok(
            S.LOCALLY_VERIFIED,
            f"{len(ready)} of {len(workflows)} workflow(s) have all required nodes and models.",
            details={"readyWorkflowIds": [item["id"] for item in ready]},
        )
    unknown = [item for item in workflows if item.get("status") == "unknown"]
    if len(unknown) == len(workflows):
        return _blocked(
            errors.WORKFLOW_READINESS_UNKNOWN,
            str(unknown[0].get("message") or "Workflow readiness is unknown."),
            recommended_action=str(unknown[0].get("recommendedAction") or "start_comfyui"),
            component_ids=("comfyui",),
            status=S.UNKNOWN,
        )
    blocked = [item for item in workflows if item.get("status") == "blocked"]
    missing_models: list[str] = []
    missing_extensions: list[str] = []
    for item in blocked:
        missing_models.extend(entry["componentId"] for entry in item.get("missingModels") or [])
        missing_extensions.extend(item.get("missingExtensions") or [])
    reason = errors.WORKFLOW_MISSING_EXTENSIONS if missing_extensions else errors.WORKFLOW_MISSING_MODELS
    bits: list[str] = []
    if missing_extensions:
        bits.append("missing ComfyUI nodes: " + ", ".join(sorted(set(missing_extensions))))
    if missing_models:
        bits.append("missing model components: " + ", ".join(sorted(set(missing_models))))
    return _blocked(
        reason,
        "No workflow is runnable — " + "; ".join(bits) + ".",
        recommended_action="open_source_manager" if missing_models else "install_comfyui_extensions",
        component_ids=tuple(sorted(set(missing_models))) or ("comfyui",),
        details={
            "missingModelComponentIds": sorted(set(missing_models)),
            "missingExtensions": sorted(set(missing_extensions)),
            "blockedWorkflowIds": [item["id"] for item in blocked],
        },
    )


def _eval_workflows_ready(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    return _workflow_aggregate(definition, snapshot, modality=None)


def _eval_workflows_image(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    return _workflow_aggregate(definition, snapshot, modality="image")


def _eval_workflows_video(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    return _workflow_aggregate(definition, snapshot, modality="video")


def _eval_workflow_discovery(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    if not snapshot.workflows:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "The workflow registry could not be read.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    return _ok(
        S.LOCALLY_VERIFIED,
        f"{len(snapshot.workflows)} workflow(s) registered.",
        details={"workflowCount": len(snapshot.workflows)},
    )


def _eval_codirector_provider(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    health = snapshot.codirector
    if health is None:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "The local model provider could not be probed.",
            recommended_action="run_diagnostics",
            component_ids=("ollama",),
            status=S.UNKNOWN,
        )
    if health.get("providerId") == "mock":
        # The deterministic E2E double must never be reported as local truth.
        return CapabilityEvaluation(
            status=S.MOCK_VERIFIED,
            available=False,
            configured=True,
            healthy=True,
            reason_code=errors.CAPABILITY_UNVERIFIED,
            message="The deterministic mock provider is active (E2E run); this is not a real local model.",
            recommended_action="use_real_provider",
            details={"providerId": "mock"},
        )
    if not health.get("reachable"):
        return _blocked(
            errors.DEPENDENCY_UNAVAILABLE,
            str(health.get("message") or "The local model provider is not reachable."),
            recommended_action=str(health.get("recommendedAction") or "start_ollama"),
            component_ids=("ollama",),
        )
    if not health.get("modelAvailable"):
        return _blocked(
            errors.DEPENDENCY_NOT_CONFIGURED,
            str(health.get("message") or "No local model is selected or installed."),
            recommended_action="select_model",
            component_ids=("ollama",),
            configured=False,
            status=S.NOT_CONFIGURED,
            details={"modelCount": health.get("modelCount")},
        )
    return _ok(
        S.LOCALLY_VERIFIED,
        f"{health.get('providerId')} is reachable with model {health.get('selectedModel')}.",
        details={"providerId": health.get("providerId"), "modelCount": health.get("modelCount")},
    )


def _eval_codirector_chat(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    provider = _eval_codirector_provider(definition, snapshot)
    if provider.status in (S.LOCALLY_VERIFIED, S.DEGRADED):
        return _ok(S.LOCALLY_VERIFIED, "Co-Director chat can reach the local model provider.")
    if provider.status == S.MOCK_VERIFIED:
        return provider
    return provider


def _eval_source_manager_read(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    if snapshot.source_manager_ok is None:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "The Source Manager overview could not be read.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    if not snapshot.source_manager_ok:
        return _blocked(
            errors.DEPENDENCY_DEGRADED,
            "The Source Manager overview is currently unavailable.",
            recommended_action="run_diagnostics",
            status=S.DEGRADED,
        )
    return _ok(
        S.LOCALLY_VERIFIED,
        "Source Manager overview available.",
        details={
            "availableProviders": snapshot.provider_available_count,
            "activeDownloads": snapshot.active_download_count,
        },
    )


def _eval_source_manager_install(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    """Install is only offered where a component actually has a usable source."""
    if not snapshot.setup_components:
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "Component states are unavailable, so install eligibility is unknown.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    installable = [
        cid
        for cid, item in snapshot.setup_components.items()
        if item.get("source_available") or str(item.get("status")) in ("not_installed", "update_available")
    ]
    pending = [
        cid
        for cid, item in snapshot.setup_components.items()
        if str(item.get("status")) in ("source_pending", "download_unavailable")
    ]
    if not installable:
        return _blocked(
            errors.MODEL_SOURCE_PENDING,
            (
                "No component currently has a published or user-supplied source, so nothing can "
                "be installed. Add a Source URL or link an existing folder."
            ),
            recommended_action="add_source_url",
            component_ids=tuple(pending),
            configured=False,
            status=S.NOT_CONFIGURED,
            details={"sourcePendingComponentIds": pending},
        )
    return CapabilityEvaluation(
        status=S.PARTIALLY_WIRED,
        available=False,
        reason_code=errors.CAPABILITY_UNVERIFIED,
        message=(
            "Install is available for components with a verified source. Packs without a "
            "published archive stay disabled; no download starts without explicit approval."
        ),
        recommended_action="open_source_manager",
        component_ids=tuple(pending),
        details={"installableComponentIds": installable, "sourcePendingComponentIds": pending},
    )


def _eval_references_project_scoped(
    definition: CapabilityDefinition, snapshot: ProbeSnapshot
) -> CapabilityEvaluation:
    storage = _requires_storage(definition, snapshot)
    if storage:
        return storage
    return _baseline(definition, snapshot)


def _eval_references_ic_lora(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    caps = snapshot.project_reference_capabilities
    if caps is None:
        if snapshot.project_id is None:
            return _blocked(
                errors.CAPABILITY_UNVERIFIED,
                "Ingredients IC-LoRA readiness is project-scoped; request it with a project id.",
                recommended_action="request_project_scope",
                status=S.UNKNOWN,
            )
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "Ingredients IC-LoRA readiness could not be probed.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    if caps.get("ic_lora_option_enabled"):
        return _ok(S.LOCALLY_VERIFIED, "Ingredients IC-LoRA model and ComfyUI nodes are present.")
    blockers = [str(item) for item in caps.get("blockers") or []]
    model_ready = bool(caps.get("model_ready"))
    return _blocked(
        errors.MODEL_MISSING if not model_ready else errors.EXTENSION_MISSING,
        " ".join(blockers) or "Ingredients IC-LoRA is not ready.",
        recommended_action="open_source_manager" if not model_ready else "install_comfyui_extensions",
        component_ids=("ltx23_ic_lora_ingredients",) if not model_ready else ("comfyui",),
        configured=model_ready,
        status=S.NOT_CONFIGURED if not model_ready else S.BLOCKED,
        details={"nodesAvailable": bool(caps.get("nodes_available"))},
    )


def _eval_vision(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    """Flag-gated vision validation: mock path is honest when enabled; never fake Comfy/ML pass."""

    try:
        from ..feature_flags import feature_flags
    except Exception:  # noqa: BLE001
        feature_flags = None
    enabled = bool(getattr(feature_flags, "vision_validation_v1", False)) if feature_flags else False
    if not enabled:
        return CapabilityEvaluation(
            status=S.NOT_CONFIGURED,
            available=False,
            configured=False,
            healthy=True,
            reason_code=errors.DEPENDENCY_NOT_CONFIGURED,
            message="Vision validation flag is off (STUDIO_FEATURE_VISION_VALIDATION_V1).",
            recommended_action="enable_feature_flag",
        )
    return CapabilityEvaluation(
        status=S.MOCK_VERIFIED,
        available=True,
        configured=True,
        healthy=True,
        reason_code=None,
        message="Vision validation mock provider is ready; local ML adapters remain inconclusive stubs.",
        recommended_action="none",
        details={"provider": "mock", "localMl": "stub_inconclusive"},
    )


def _eval_generation_queue(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    """Generation is only callable when Comfy, a workflow, and the weights all line up."""
    comfy = snapshot.comfy
    if comfy is None or not comfy.get("reachable"):
        return _blocked(
            errors.DEPENDENCY_UNAVAILABLE,
            "ComfyUI is not reachable, so generation jobs cannot run. Jobs would queue and fail.",
            recommended_action="start_comfyui",
            component_ids=("comfyui",),
        )
    modality = "image" if definition.id == "generation.image.queue" else "video"
    workflows = _workflow_aggregate(definition, snapshot, modality=modality)
    if workflows.status not in (S.LOCALLY_VERIFIED, S.DEGRADED):
        return CapabilityEvaluation(
            status=workflows.status if workflows.status != S.UNKNOWN else S.UNKNOWN,
            available=False,
            configured=workflows.configured,
            healthy=False,
            reason_code=workflows.reason_code,
            message=workflows.message,
            recommended_action=workflows.recommended_action,
            component_ids=workflows.component_ids or definition.component_ids,
            details=workflows.details,
        )
    return CapabilityEvaluation(
        status=S.PARTIALLY_WIRED,
        available=False,
        reason_code=errors.CAPABILITY_UNVERIFIED,
        message=(
            "ComfyUI, a workflow, and the required weights are present, but no end-to-end "
            "generation has been verified in this environment yet."
        ),
        recommended_action="run_verification_render",
        details=workflows.details,
    )


EVALUATORS: dict[str, Evaluator] = {
    "storage.project_data": _eval_storage,
    "storage.database": _eval_database,
    "project.create": _eval_db_backed,
    "project.list": _eval_db_backed,
    "project.read": _eval_db_backed,
    "project.update": _eval_db_backed,
    "project.delete": _eval_db_backed,
    "project.duplicate": _eval_db_backed,
    "project.archive": _eval_db_backed,
    "project.scenes.read": _eval_db_backed,
    "project.scenes.create": _eval_db_backed,
    "project.scenes.update": _eval_db_backed,
    "project.scenes.delete": _eval_db_backed,
    "project.timeline.apply": _eval_db_backed,
    "assets.upload": _eval_db_backed,
    "assets.read": _eval_db_backed,
    "assets.tag": _eval_db_backed,
    "assets.file": _eval_db_backed,
    "generation.jobs.read": _eval_db_backed,
    "codirector.bible.read": _eval_db_backed,
    "codirector.bible.propose": _eval_db_backed,
    "codirector.bible.approve": _eval_db_backed,
    "references.upload": _eval_references_project_scoped,
    "references.read": _eval_references_project_scoped,
    "references.attach.project": _eval_references_project_scoped,
    "references.exclude": _eval_references_project_scoped,
    "references.sheet.build": _eval_references_project_scoped,
    "references.ic_lora.ready": _eval_references_ic_lora,
    "codirector.provider": _eval_codirector_provider,
    "codirector.chat": _eval_codirector_chat,
    "comfyui.health": _eval_comfy_health,
    "comfyui.queue": _eval_comfy_dependent,
    "comfyui.cancel": _eval_comfy_dependent,
    "comfyui.outputs": _eval_comfy_dependent,
    "extensions.comfyui.ready": _eval_extensions_ready,
    "models.image.ready": _eval_models_image,
    "models.video.ready": _eval_models_video,
    "workflows.discover": _eval_workflow_discovery,
    "workflows.validate": _eval_workflow_discovery,
    "workflows.ready": _eval_workflows_ready,
    "workflows.image.ready": _eval_workflows_image,
    "workflows.video.ready": _eval_workflows_video,
    "source_manager.read": _eval_source_manager_read,
    "source_manager.install": _eval_source_manager_install,
    "downloads.read": _eval_source_manager_read,
    "generation.image.queue": _eval_generation_queue,
    "generation.video.queue": _eval_generation_queue,
    "codirector.vision.validate": _eval_vision,
    "codirector.vision.review": _eval_vision,
}


# ---------------------------------------------------------------------------
# evaluation pipeline
# ---------------------------------------------------------------------------


def _evaluate_one(definition: CapabilityDefinition, snapshot: ProbeSnapshot) -> CapabilityEvaluation:
    evaluator = EVALUATORS.get(definition.id, _baseline)
    try:
        evaluation = evaluator(definition, snapshot)
    except Exception:  # noqa: BLE001 - one bad evaluator must not break the registry read
        snapshot.warnings.append(f"evaluator_failed:{definition.id}")
        return _blocked(
            errors.CAPABILITY_PROBE_FAILED,
            "This capability could not be evaluated in the current environment.",
            recommended_action="run_diagnostics",
            status=S.UNKNOWN,
        )
    if not evaluation.component_ids:
        evaluation.component_ids = definition.component_ids
    return evaluation


def _apply_dependencies(
    definitions: tuple[CapabilityDefinition, ...],
    results: dict[str, CapabilityEvaluation],
) -> None:
    """Downgrade a capability when a dependency is unusable. Repeats until stable."""
    for _ in range(len(definitions) + 1):
        changed = False
        for definition in definitions:
            evaluation = results[definition.id]
            if evaluation.status in (S.NOT_IMPLEMENTED, S.UI_ONLY):
                continue
            for dependency_id in definition.dependencies:
                dependency = results.get(dependency_id)
                if dependency is None:
                    continue
                if dependency.status in USABLE_STATUSES:
                    continue
                if dependency.status in (S.MOCK_VERIFIED,) and evaluation.status == S.MOCK_VERIFIED:
                    continue
                blocking = dependency.status in BLOCKING_STATUSES or dependency.status in (
                    S.NOT_IMPLEMENTED,
                    S.UNKNOWN,
                )
                if not blocking:
                    continue
                new_status = (
                    S.UNKNOWN
                    if dependency.status == S.UNKNOWN
                    else S.NOT_CONFIGURED
                    if dependency.status == S.NOT_CONFIGURED
                    else S.BLOCKED
                )
                if evaluation.status == new_status and evaluation.reason_code == errors.DEPENDENCY_UNAVAILABLE:
                    continue
                if evaluation.status in (S.BLOCKED, S.NOT_CONFIGURED) and evaluation.reason_code:
                    # Keep the capability's own, more specific reason.
                    continue
                results[definition.id] = CapabilityEvaluation(
                    status=new_status,
                    available=False,
                    configured=dependency.configured,
                    healthy=False,
                    reason_code=errors.DEPENDENCY_UNAVAILABLE
                    if dependency.status != S.NOT_CONFIGURED
                    else errors.DEPENDENCY_NOT_CONFIGURED,
                    message=(
                        f"Blocked by dependency {dependency_id}: {dependency.message}".strip()
                    ),
                    recommended_action=dependency.recommended_action or "review_capability",
                    component_ids=dependency.component_ids or definition.component_ids,
                    details={"blockedBy": dependency_id},
                )
                evaluation = results[definition.id]
                changed = True
        if not changed:
            break


def _apply_project_scope(
    definitions: tuple[CapabilityDefinition, ...],
    results: dict[str, CapabilityEvaluation],
    snapshot: ProbeSnapshot,
) -> None:
    if snapshot.project_id is None or snapshot.project_exists is not False:
        return
    for definition in definitions:
        if definition.scope != "project":
            continue
        if results[definition.id].status in (S.NOT_IMPLEMENTED, S.UI_ONLY):
            continue
        results[definition.id] = _blocked(
            errors.PROJECT_NOT_FOUND,
            f"Project {snapshot.project_id} does not exist.",
            recommended_action="open_project",
        )


def _to_out(
    definition: CapabilityDefinition,
    evaluation: CapabilityEvaluation,
    snapshot: ProbeSnapshot,
) -> CapabilityOut:
    return CapabilityOut(
        id=definition.id,
        displayName=definition.display_name,
        subsystem=definition.subsystem,
        status=evaluation.status,
        available=evaluation.available,
        configured=evaluation.configured,
        healthy=evaluation.healthy,
        readOnly=definition.read_only,
        requiresApproval=definition.requires_approval,
        dependencies=list(definition.dependencies),
        reasonCode=evaluation.reason_code,
        message=evaluation.message,
        recommendedAction=evaluation.recommended_action,
        componentIds=list(evaluation.component_ids or definition.component_ids),
        serviceRef=definition.service_ref,
        httpRef=definition.http_ref,
        scope=definition.scope,
        summary=definition.summary,
        details=errors.public_details(evaluation.details),
        lastCheckedAt=snapshot.checked_at,
    )


def _snapshot_out(snapshot: ProbeSnapshot) -> CapabilitySnapshotOut:
    definitions = CAPABILITIES
    results = {item.id: _evaluate_one(item, snapshot) for item in definitions}
    _apply_dependencies(definitions, results)
    _apply_project_scope(definitions, results, snapshot)

    capabilities = [_to_out(item, results[item.id], snapshot) for item in definitions]
    counts: dict[str, int] = {}
    for item in capabilities:
        counts[item.status.value] = counts.get(item.status.value, 0) + 1
    blockers = [
        CapabilityBlockerOut(
            capabilityId=item.id,
            displayName=item.displayName,
            subsystem=item.subsystem,
            status=item.status,
            reasonCode=item.reasonCode,
            message=item.message,
            recommendedAction=item.recommendedAction,
            componentIds=item.componentIds,
        )
        for item in capabilities
        if item.status in BLOCKING_STATUSES
    ]
    return CapabilitySnapshotOut(
        projectId=snapshot.project_id,
        generatedAt=snapshot.checked_at,
        correlationId=snapshot.correlation_id,
        counts=counts,
        capabilities=capabilities,
        blockers=blockers,
        callable=[item.id for item in capabilities if item.available],
        probeWarnings=sorted(set(snapshot.warnings)),
    )


async def _get_snapshot(*, project_id: str | None, force: bool) -> ProbeSnapshot:
    async with _lock:
        cached = _cache.get("snapshot")
        fresh = (
            cached is not None
            and not force
            and _cache.get("project_id") == project_id
            and (time.monotonic() - float(_cache.get("at") or 0.0)) < SNAPSHOT_TTL_SEC
        )
        if fresh:
            return cached  # type: ignore[return-value]
        snapshot = await build_snapshot(project_id=project_id)
        _cache["snapshot"] = snapshot
        _cache["at"] = time.monotonic()
        _cache["project_id"] = project_id
        return snapshot


async def get_capabilities(
    *, project_id: str | None = None, force: bool = False
) -> CapabilitySnapshotOut:
    snapshot = await _get_snapshot(project_id=project_id, force=force)
    return _snapshot_out(snapshot)


async def get_project_capabilities(
    project_id: str, *, force: bool = False
) -> CapabilitySnapshotOut:
    """Project-scoped read that 404s on a missing project.

    The global read reports project-scoped capabilities as `blocked` for an unknown project,
    which is right for a dashboard. Asking for one project's capabilities by id is a different
    question, and answering it with a full snapshot of blockers would let a typo'd id look like
    a broken studio.
    """
    snapshot = await _get_snapshot(project_id=project_id, force=force)
    if snapshot.project_exists is False:
        raise errors.CapabilityError(
            code=errors.PROJECT_NOT_FOUND,
            message=f"Project {project_id} does not exist.",
            details={"projectId": project_id},
            recoverable=False,
            recommended_action="open_project",
        )
    return _snapshot_out(snapshot)


async def get_capability(capability_id: str, *, project_id: str | None = None) -> CapabilityOut:
    try:
        definition = get_definition(capability_id)
    except KeyError as exc:
        raise errors.CapabilityError(
            code=errors.CAPABILITY_NOT_FOUND,
            message=f"Unknown capability '{capability_id}'.",
            details={"capabilityId": capability_id},
            recoverable=False,
            recommended_action="list_capabilities",
        ) from exc
    scope_project = project_id or (None if definition.scope != "project" else None)
    snapshot = await _get_snapshot(project_id=scope_project, force=False)
    evaluation = _evaluate_one(definition, snapshot)
    results = {definition.id: evaluation}
    # Dependency propagation for a single read needs its dependencies evaluated too.
    for dependency_id in definition.dependencies:
        try:
            dep_def = get_definition(dependency_id)
        except KeyError:  # pragma: no cover - registry validated at import
            continue
        results[dependency_id] = _evaluate_one(dep_def, snapshot)
    _apply_dependencies((definition,), results)
    _apply_project_scope((definition,), results, snapshot)
    return _to_out(definition, results[definition.id], snapshot)


def invalidate_cache() -> None:
    _cache["snapshot"] = None
    _cache["at"] = 0.0
    _cache["project_id"] = None
