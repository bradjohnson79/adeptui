from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.orm import Session

from .types import HealthCheckDefinition, RecoveryAction, HealthStatus, StatusMode

ProbeResult = dict[str, Any]
ProbeFn = Callable[["StatusContext"], Awaitable[ProbeResult]]


@dataclass
class StatusContext:
    db: Session
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    workspace: Optional[str] = None
    mode: StatusMode = "standard"
    shared: Any = None  # SharedProbeBundle from probe_context when set by runner
    force_refresh: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: Any) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _result(
    status: HealthStatus,
    summary: str,
    *,
    message: str = "",
    details: Optional[dict[str, Any]] = None,
    blockers: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    recovery_actions: Optional[list[RecoveryAction]] = None,
    readiness_class: Optional[str] = None,
    v11_requirement: Optional[str] = None,
    workflow_scope: Optional[str] = None,
    production_effect: Optional[str] = None,
    severity: Optional[str] = None,
) -> ProbeResult:
    payload: ProbeResult = {
        "status": status,
        "summary": summary,
        "message": message,
        "details": details or {},
        "blockers": blockers or [],
        "warnings": warnings or [],
        "recoveryActions": recovery_actions or [],
    }
    if readiness_class:
        payload["readinessClass"] = readiness_class
    if v11_requirement:
        payload["v11Requirement"] = v11_requirement
    if workflow_scope:
        payload["workflowScope"] = workflow_scope
    if production_effect:
        payload["productionEffect"] = production_effect
    if severity:
        payload["severity"] = severity
    return payload


def _project_actions() -> list[RecoveryAction]:
    return [
        RecoveryAction(id="open-projects", label="Select Project", kind="open_route", path="/#projects-library"),
        RecoveryAction(id="create-project", label="Create Project", kind="open_route", path="/?create=1"),
    ]


def _provider_actions() -> list[RecoveryAction]:
    return [
        RecoveryAction(id="open-status-model", label="Open Model", kind="open_panel", panel="provider"),
        RecoveryAction(id="open-setup", label="Open Setup", kind="open_route", path="?workspace=setup&setupMode=ai_guided"),
    ]


def _setup_actions() -> list[RecoveryAction]:
    return [
        RecoveryAction(id="open-setup", label="Open Setup", kind="open_route", path="?workspace=setup&setupMode=ai_guided"),
        RecoveryAction(id="open-source-manager", label="Open Setup", kind="open_route", path="?workspace=setup&setupMode=ai_guided"),
        RecoveryAction(id="open-jobs", label="Open Jobs", kind="open_panel", panel="jobs"),
    ]


def _content_actions() -> list[RecoveryAction]:
    return [
        RecoveryAction(id="open-bible", label="Open Production Bible", kind="open_route", path="?workspace=bible"),
        RecoveryAction(id="open-approvals", label="Open Approvals", kind="open_panel", panel="approvals"),
    ]


async def _probe_api_health(ctx: StatusContext) -> ProbeResult:
    from ...routers.api import health

    payload = await health()
    operator = payload.operator or {}
    partial = list(operator.get("partialErrors") or [])
    if not payload.ok:
        return _result(
            "blocked",
            "Studio API health is not operational.",
            message=payload.message or "The API health endpoint did not report a ready state.",
            details=payload.model_dump(mode="json"),
            blockers=[payload.message or "API health is offline."],
            recovery_actions=_setup_actions(),
        )
    if partial:
        return _result(
            "degraded",
            "Studio API is up, but some health probes are degraded.",
            message=payload.message or "Partial health probes failed.",
            details=payload.model_dump(mode="json"),
            warnings=partial,
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        "Studio API and operator health look good.",
        message=payload.message or "The main health endpoint returned a clean result.",
        details=payload.model_dump(mode="json"),
    )


def _blocker_row(item: Any) -> dict[str, Any]:
    return {
        "capabilityId": getattr(item, "capabilityId", "") or getattr(item, "id", "") or "",
        "displayName": getattr(item, "displayName", "") or "",
        "subsystem": getattr(item, "subsystem", "") or "",
        "reasonCode": getattr(item, "reasonCode", "") or "",
        "message": getattr(item, "message", "") or "",
        "status": str(getattr(item, "status", "") or ""),
        "readinessClass": getattr(item, "readinessClass", "") or "",
        "v11Requirement": getattr(item, "v11Requirement", "") or "",
        "workflowScope": getattr(item, "workflowScope", "") or "",
        "severity": getattr(item, "severity", "") or "",
        "productionEffect": getattr(item, "productionEffect", "") or "",
        "recommendedAction": getattr(item, "recommendedAction", "") or "",
        "componentIds": list(getattr(item, "componentIds", []) or []),
    }


async def _probe_capabilities(ctx: StatusContext) -> ProbeResult:
    from ...capabilities import service as capability_service
    from ...readiness.v11_policy import (
        ReadinessClass,
        class_affects_production,
        worst_class,
    )

    force = bool(getattr(ctx, "force_refresh", False))
    snapshot = getattr(ctx.shared, "capabilities", None) if ctx.shared is not None else None
    if snapshot is None:
        snapshot = (
            await capability_service.get_project_capabilities(ctx.project_id, force=force)
            if ctx.project_id
            else await capability_service.get_capabilities(force=force)
        )
    blocker_objs = list(getattr(snapshot, "blockers", []) or [])
    cap_rows = list(getattr(snapshot, "capabilities", []) or [])
    production = [item for item in blocker_objs if class_affects_production(getattr(item, "readinessClass", "optional"))]
    workflow = [
        item
        for item in blocker_objs
        if str(getattr(item, "readinessClass", "") or "") == ReadinessClass.WORKFLOW_DEGRADED.value
    ]
    # OPTIONAL leftovers (e.g. gated IC-LoRA) stay visible on the snapshot but
    # do not own the registry Status warning. True review/continuity rows do.
    advisory = [
        item
        for item in blocker_objs
        if str(getattr(item, "readinessClass", "") or "") == ReadinessClass.ADVISORY_REVIEW_DEGRADED.value
    ]
    seen = {
        getattr(item, "capabilityId", "") or getattr(item, "id", "")
        for item in [*production, *workflow, *advisory]
    }
    for item in cap_rows:
        status = str(getattr(item, "status", "") or getattr(getattr(item, "status", None), "value", "") or "")
        cap_id = getattr(item, "id", "") or getattr(item, "capabilityId", "")
        if not cap_id or cap_id in seen:
            continue
        if status not in {"degraded", "CapabilityStatus.DEGRADED"}:
            continue
        cls_raw = getattr(item, "readinessClass", "") or "optional"
        if class_affects_production(cls_raw):
            # Usable-but-reduced production rows must not disappear or score as 100.
            workflow.append(item)
        elif str(cls_raw) == ReadinessClass.ADVISORY_REVIEW_DEGRADED.value:
            advisory.append(item)
        # OPTIONAL leftovers and usable WORKFLOW DEGRADED rows stay on the snapshot
        # without owning the registry Status warning (they must not recap 84).
        seen.add(cap_id)
    callable_count = len(getattr(snapshot, "callable", []) or [])
    total = int(getattr(snapshot, "readinessTotal", 0) or len(getattr(snapshot, "capabilities", []) or []))
    incomplete = bool(getattr(snapshot, "snapshotIncomplete", False))
    details = snapshot.model_dump(mode="json")
    details["blockerDetails"] = [_blocker_row(item) for item in blocker_objs]
    details["productionBlockerDetails"] = [_blocker_row(item) for item in production]
    details["workflowBlockerDetails"] = [_blocker_row(item) for item in workflow]
    details["advisoryBlockerDetails"] = [_blocker_row(item) for item in advisory]
    details["forceRefresh"] = force
    details["snapshotIncomplete"] = incomplete
    def _class_for(items: list[Any], fallback: str) -> str:
        worst = worst_class(getattr(item, "readinessClass", "") for item in items)
        return worst.value if worst else fallback

    if production:
        return _result(
            "blocked",
            f"{len(production)} production-critical capability blocker(s) are open.",
            message="Capability Registry production blockers match this Status run.",
            details=details,
            blockers=[getattr(item, "message", "") or getattr(item, "displayName", "") for item in production[:8]],
            recovery_actions=_setup_actions(),
            readiness_class=_class_for(production, ReadinessClass.PRODUCTION_CRITICAL.value),
        )
    if workflow:
        return _result(
            "warning",
            f"{len(workflow)} workflow capability gap(s) are open.",
            message="A supported creator workflow is degraded. Core production may still run.",
            details=details,
            warnings=[getattr(item, "message", "") or getattr(item, "displayName", "") for item in workflow[:8]],
            recovery_actions=_setup_actions(),
            readiness_class=ReadinessClass.WORKFLOW_DEGRADED.value,
        )
    if advisory:
        titles = [getattr(item, "displayName", "") or getattr(item, "capabilityId", "") for item in advisory[:8]]
        return _result(
            "warning",
            f"{len(advisory)} advisory / review capability gap(s) are open.",
            message="Review assistance is reduced. This is not a core production outage.",
            details=details,
            warnings=titles,
            recovery_actions=_setup_actions(),
            readiness_class=ReadinessClass.ADVISORY_REVIEW_DEGRADED.value,
        )
    if incomplete:
        return _result(
            "warning",
            "Capability snapshot is incomplete — Setup verification did not finish.",
            message="Production Assurance will not treat an incomplete snapshot as fully ready.",
            details=details,
            warnings=["Capability snapshot is incomplete."],
            recovery_actions=_setup_actions(),
            readiness_class=ReadinessClass.ADVISORY_REVIEW_DEGRADED.value,
        )
    if callable_count == 0 and total:
        return _result(
            "warning",
            "Capabilities loaded, but nothing is callable yet.",
            message="The capability snapshot loaded without an immediately usable surface.",
            details=details,
            warnings=["No callable capabilities were reported."],
            recovery_actions=_setup_actions(),
            readiness_class=ReadinessClass.WORKFLOW_DEGRADED.value,
        )
    return _result(
        "healthy",
        f"{callable_count} callable capabilities are available.",
        message="Capability readiness returned without production, workflow, or advisory blockers.",
        details=details,
        readiness_class=ReadinessClass.OPTIONAL.value,
    )


async def _probe_codirector_provider(ctx: StatusContext) -> ProbeResult:
    from ...codirector import service as codirector_service
    from ...codirector.inference_activity import snapshot as inference_snapshot

    activity = inference_snapshot()
    if activity.busy:
        return _result(
            "busy",
            "BUSY — selected model is processing an active request.",
            message=(
                f"Active inference in progress ({activity.label or 'turn'}). "
                "Production Assurance did not interrupt the conversation."
            ),
            details={
                "busy": True,
                "activeCount": activity.activeCount,
                "startedAt": activity.startedAt,
            },
            warnings=["Active inference — not a failure."],
            recovery_actions=_provider_actions(),
        )

    health = await codirector_service.get_health()
    details = health.to_dict()
    if not health.reachable:
        return _result(
            "offline",
            "Co-Director's model provider is offline.",
            message=health.message,
            details=details,
            blockers=[health.message or "Provider unreachable."],
            recovery_actions=_provider_actions(),
        )
    if not health.model_available:
        return _result(
            "blocked",
            "Co-Director is connected, but no usable model is selected.",
            message=health.message,
            details=details,
            blockers=[health.message or "No usable Co-Director model is available."],
            recovery_actions=_provider_actions(),
        )
    return _result(
        "healthy",
        f"{health.display_name} is connected and ready.",
        message=health.status,
        details=details,
        warnings=(["Test-only provider in use."] if details.get("testOnly") or details.get("honesty") == "mocked" else []),
        recovery_actions=_provider_actions(),
    )


async def _probe_session_binding(ctx: StatusContext) -> ProbeResult:
    import asyncio

    from ...codirector.session_context import build_session_context

    payload = await asyncio.to_thread(
        build_session_context,
        ctx.db,
        project_id=ctx.project_id,
        active_scene_id=ctx.scene_id,
        active_workspace=ctx.workspace,
    )
    if not payload.get("projectId"):
        return _result(
            "blocked",
            "No project is currently bound to Co-Director.",
            message="Project binding is required for production assurance.",
            details=payload,
            blockers=["Co-Director is running without an active project."],
            recovery_actions=_project_actions(),
        )
    blockers = list(payload.get("unresolvedBlockers") or [])
    if blockers:
        return _result(
            "warning",
            "A project is bound, but unresolved session blockers remain.",
            message="Session context returned active blockers.",
            details=payload,
            warnings=blockers[:8],
            recovery_actions=_project_actions(),
        )
    return _result(
        "healthy",
        f"Bound to project {payload.get('projectName') or payload.get('projectId')}.",
        message="Session context is bound and usable.",
        details=payload,
    )


async def _probe_tool_registry(ctx: StatusContext) -> ProbeResult:
    from ...codirector.tools import registry as tool_registry
    from ...codirector.tools.execution import ToolExecutionService

    catalog = tool_registry.catalog()
    details: dict[str, Any] = {"toolCount": len(catalog), "catalogSample": catalog[:12]}
    if not catalog:
        return _result(
            "blocked",
            "The Co-Director tool registry is empty.",
            message="No bounded tools were available to Co-Director.",
            details=details,
            blockers=["The tool registry returned no tools."],
            recovery_actions=_content_actions(),
        )
    if not ctx.project_id:
        return _result(
            "warning",
            f"{len(catalog)} tools are registered, but project-scoped availability was not checked.",
            message="Project binding is required for full tool availability checks.",
            details=details,
            warnings=["Project-scoped tool availability was skipped."],
            recovery_actions=_project_actions(),
        )
    # Standard mode: Layer-3 registry check only (catalog + project binding).
    # Full per-tool availability is Layer-5 and reserved for deep diagnostics so
    # Production Assurance does not monopolize the API for tens of seconds.
    if ctx.mode != "deep":
        return _result(
            "healthy",
            f"{len(catalog)} Co-Director tools are registered for project-scoped use.",
            message=(
                "Standard cross-check verified the tool registry. "
                "Run a deep diagnostic for full per-tool availability."
            ),
            details={**details, "availabilityMode": "standard_catalog_only", "projectId": ctx.project_id},
        )
    availability, capability_map = await ToolExecutionService.availability(ctx.db, ctx.project_id)
    offered = [item for item in availability if item.available]
    blocked = [item.reason for item in availability if not item.available and item.reason]
    unavailability_reasons = [item.reason for item in availability if not item.available and item.reason]
    total = len(availability)
    details["availabilityCount"] = len(offered)
    details["availabilityTotal"] = total
    details["unavailableCount"] = total - len(offered)
    details["capabilities"] = capability_map
    details["availabilityMode"] = "deep"
    if not offered:
        return _result(
            "blocked",
            "The tool registry loaded, but no project tools are currently available.",
            message="Tool availability returned no usable actions for this project.",
            details=details,
            blockers=blocked[:8] or ["No project tools are available."],
            recovery_actions=_setup_actions(),
        )
    # >=90% available is a healthy registry with an informational note about the few
    # unavailable tools. Only warn when a significant portion (>25%) is blocked.
    available_ratio = len(offered) / total if total else 0.0
    if available_ratio >= 0.9:
        return _result(
            "healthy",
            f"{len(offered)} of {total} Co-Director tools are available.",
            message=(
                f"{total - len(offered)} tool(s) unavailable — informational. "
                "Tool availability is healthy."
            ),
            details={**details, "availableRatio": round(available_ratio, 3)},
            warnings=unavailability_reasons[:8],
        )
    if available_ratio > 0.75:
        return _result(
            "healthy",
            f"{len(offered)} of {total} Co-Director tools are available.",
            message=(
                f"{total - len(offered)} tool(s) unavailable — informational. "
                "Tool availability is within the healthy threshold."
            ),
            details={**details, "availableRatio": round(available_ratio, 3)},
            warnings=unavailability_reasons[:8],
        )
    return _result(
        "warning",
        f"{len(offered)} of {total} tools are available, but a significant portion is blocked.",
        message=f"{total - len(offered)} tools are blocked ({100 - round(available_ratio * 100)}%).",
        details={**details, "availableRatio": round(available_ratio, 3)},
        warnings=blocked[:8],
        recovery_actions=_setup_actions(),
    )


async def _probe_proposals(ctx: StatusContext) -> ProbeResult:
    if not ctx.project_id:
        return _result(
            "not_applicable",
            "Proposal-service checks need an active project.",
            message="Proposal flows are project-scoped.",
            recovery_actions=_project_actions(),
        )
    from ...codirector.bible.proposals import ProposalService

    proposals = ProposalService.list(ctx.db, ctx.project_id)
    pending = [p for p in proposals if getattr(p, "status", "") in {"pending", "revision_requested", "executing"}]
    return _result(
        "healthy",
        f"Proposal service responded with {len(proposals)} proposals.",
        message="Proposal-service reads are working.",
        details={"projectId": ctx.project_id, "proposalCount": len(proposals), "pendingCount": len(pending)},
        warnings=(["Pending proposals still need review."] if pending else []),
        recovery_actions=_content_actions(),
    )


def _comfy_true_death(payload: dict[str, Any]) -> bool:
    if payload.get("trueDeath") is True:
        return True
    refused = bool(payload.get("connectionRefused") or payload.get("errorKind") == "refused")
    return refused and payload.get("listenerPresent") is False


def _comfy_lkg_or_live(payload: dict[str, Any]) -> bool:
    """True when a transient miss must not be reported as offline / Blocked 35."""
    if payload.get("reachable"):
        return True
    if _comfy_true_death(payload):
        return False
    if payload.get("listenerPresent") is True:
        return True
    generation = payload.get("generationActive")
    if isinstance(generation, dict) and generation.get("active"):
        return True
    from .probe_context import LKG_WINDOW_SEC, seconds_since_healthy

    seconds = seconds_since_healthy("comfy.health")
    return seconds is not None and seconds <= LKG_WINDOW_SEC


async def _probe_comfy(ctx: StatusContext) -> ProbeResult:
    # Fast path: reachability + version + GPU only. No node catalog or model inventory.
    # Deep diagnostics (node catalog, model filesystem) run only in "deep" mode.
    if ctx.mode != "deep":
        from ...comfy_health import comfy_health_fast

        payload = getattr(ctx.shared, "comfy_health", None) if ctx.shared is not None else None
        if not isinstance(payload, dict) or payload.get("models") is not None:
            # Shared bundle carries the full (deep) payload; do not use it for fast path.
            payload = await comfy_health_fast(timeout_sec=8.0)
        if not payload.get("reachable") and not _comfy_true_death(payload):
            try:
                from ...codirector.video_intelligence.gpu_lease import comfy_generation_active

                activity = comfy_generation_active()
                payload = dict(payload)
                payload["generationActive"] = activity
            except Exception:  # noqa: BLE001
                pass
        if not payload.get("reachable"):
            if payload.get("timeout") or payload.get("status") == "timeout" or _comfy_lkg_or_live(payload):
                from .probe_context import last_healthy_at, last_healthy_summary, seconds_since_healthy

                seconds = seconds_since_healthy("comfy.health")
                details = dict(payload)
                details["lastKnownGood"] = seconds is not None
                details["lastHealthyAt"] = last_healthy_at("comfy.health")
                details["lastHealthySummary"] = last_healthy_summary("comfy.health")
                details["secondsSinceHealthy"] = int(seconds) if seconds is not None else None
                generation = payload.get("generationActive")
                busy = isinstance(generation, dict) and bool(generation.get("active"))
                # A proven :8188 listener (or active generation) means Comfy is up.
                # timed_out would increment advisory warningChecks and cap 100 at 94.
                if payload.get("listenerPresent") is True or busy:
                    return _result(
                        "busy" if busy else "healthy",
                        "ComfyUI is reachable and GPU is available."
                        if not busy
                        else "ComfyUI is busy with a live generation.",
                        message=(
                            "ComfyUI is listening; a late /system_stats probe is not proof the runtime is down."
                            if not busy
                            else "ComfyUI is generating; health probe was late."
                        ),
                        details=details,
                        warnings=["ComfyUI health probe was late; the runtime is still present."],
                        recovery_actions=_setup_actions(),
                    )
                return _result(
                    "timed_out",
                    "ComfyUI Runtime timed out.",
                    message=str(payload.get("message") or "ComfyUI did not answer in time."),
                    details=details,
                    warnings=["ComfyUI health timed out. A late probe is not proof the runtime is down."],
                    recovery_actions=_setup_actions(),
                )
            return _result(
                "offline",
                "ComfyUI is offline.",
                message=str(payload.get("message") or "The render backend is unreachable."),
                details=payload,
                blockers=[str(payload.get("message") or "ComfyUI is unreachable.")],
                recovery_actions=_setup_actions(),
            )
        return _result(
            "healthy",
            "ComfyUI is reachable and GPU is available.",
            message=payload.get("message", "ready"),
            details=payload,
        )

    from ...comfy_health import comfy_health

    payload = getattr(ctx.shared, "comfy_health", None) if ctx.shared is not None else None
    if not isinstance(payload, dict):
        payload = await comfy_health(include_nodes=True)
    # Runtime health must reflect REQUIRED-core readiness, not optional/generator-
    # specific components. A missing LTX 2.5 text encoder (optional at the runtime
    # level; required only for the LTX 2.5 generator) must not flip a reachable,
    # responding ComfyUI to "degraded". The capability layer owns per-generator
    # readiness; this probe owns runtime reachability + core API health.
    missing_required = list(payload.get("missingRequiredModelComponentIds") or [])
    if not payload.get("reachable"):
        return _result(
            "offline",
            "ComfyUI is offline.",
            message=str(payload.get("message") or "The render backend is unreachable."),
            details=payload,
            blockers=[str(payload.get("message") or "ComfyUI is unreachable.")],
            recovery_actions=_setup_actions(),
        )
    if payload.get("status") == "degraded" and not payload.get("nodeCatalogAvailable"):
        return _result(
            "starting",
            "STARTING — API is reachable; custom-node registry is still loading.",
            message=str(payload.get("message") or "Node catalogue not ready yet."),
            details=payload,
            warnings=["ComfyUI node catalogue is still loading."],
            recovery_actions=_setup_actions(),
        )
    # Only missing REQUIRED core components degrade runtime health. Missing
    # optional/generator-specific components are reported to the capability layer
    # and surfaced separately in the UI — they do not collapse into a runtime
    # warning here.
    missing_optional = [
        cid for cid in (payload.get("missingModelComponentIds") or [])
        if cid not in missing_required
    ]
    warnings: list[str] = []
    if missing_required:
        warnings.extend(missing_required[:8])
    if missing_optional:
        # Surface optional-missing as informational warnings only; runtime stays healthy.
        warnings.extend(f"{cid} (optional / generator-specific)" for cid in missing_optional[:8])
    if missing_required:
        return _result(
            "warning",
            f"ComfyUI is reachable, but {len(missing_required)} required model components are missing.",
            message=str(payload.get("message") or "ComfyUI reported missing required model components."),
            details=payload,
            warnings=warnings,
            recovery_actions=_setup_actions(),
        )
    runtime_status = "healthy"
    runtime_label = "ComfyUI is reachable and did not report missing required components."
    if missing_optional:
        # Healthy runtime, but some optional/generator components incomplete — note it
        # without degrading the runtime verdict. Per-generator readiness is owned by
        # the capability layer and the Model Readiness UI.
        runtime_label = (
            f"ComfyUI is reachable. {len(missing_optional)} optional/generator component(s) "
            "incomplete — see Model Readiness."
        )
    return _result(
        runtime_status,
        runtime_label,
        message=str(payload.get("status") or "ready"),
        details=payload,
        warnings=warnings,
    )


async def _probe_gpu(ctx: StatusContext) -> ProbeResult:
    from ...vram_profiles import query_gpu_stats

    payload = query_gpu_stats()
    gpus = list(payload.get("gpus") or [])
    if not payload.get("ok"):
        return _result(
            "unknown",
            "GPU stats could not be read.",
            message=str(payload.get("message") or "GPU stats are unavailable."),
            details=payload,
            warnings=[str(payload.get("message") or "GPU stats unavailable.")],
        )
    if not gpus:
        return _result(
            "warning",
            "GPU stats loaded, but no active GPU was reported.",
            message="The runtime did not report a usable GPU device.",
            details=payload,
            warnings=["No GPU devices were returned."],
        )
    return _result(
        "healthy",
        f"GPU stats are available for {gpus[0].get('name') or 'the active device'}.",
        message="GPU stats returned successfully.",
        details=payload,
    )


async def _probe_source_manager(ctx: StatusContext) -> ProbeResult:
    from ...source_manager.registry import detect_all, overview_payload

    overview = overview_payload()
    providers = [item.to_dict() for item in detect_all()]
    assignments = overview.get("assignments") or []
    details = {**overview, "detectedProviders": providers}
    if not providers:
        return _result(
            "warning",
            "Source Manager loaded, but no providers were detected.",
            message="No Source Manager providers were reported.",
            details=details,
            warnings=["No source providers detected."],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        f"Source Manager detected {len(providers)} providers and {len(assignments)} assignments.",
        message="Source Manager overview returned successfully.",
        details=details,
        recovery_actions=_setup_actions(),
    )


async def _probe_install_jobs(ctx: StatusContext) -> ProbeResult:
    from ...source_manager.install_jobs.service import list_jobs

    try:
        jobs = list_jobs(active_only=False)
    except Exception as exc:  # noqa: BLE001
        return _result(
            "unknown",
            "Install job status could not be read cleanly.",
            message=str(exc),
            details={"error": {"type": type(exc).__name__, "message": str(exc)}},
            warnings=[str(exc)],
            recovery_actions=_setup_actions(),
        )
    active = [job for job in jobs if job.get("active")]
    stalled: list[str] = []
    for job in active:
        updated = _parse_dt(job.get("updatedAt") or job.get("updated_at"))
        if updated and _now() - updated > timedelta(minutes=20):
            stalled.append(str(job.get("componentId") or job.get("id") or "install-job"))
    if stalled:
        return _result(
            "warning",
            f"{len(stalled)} install jobs may be stalled.",
            message="Some install jobs have not updated recently.",
            details={"jobs": jobs[:20]},
            warnings=stalled[:8],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy" if not active else "connected",
        "Install jobs are responding normally." if active else "No active install jobs are blocking readiness.",
        message=f"{len(active)} active install jobs.",
        details={"jobs": jobs[:20], "activeCount": len(active)},
        recovery_actions=_setup_actions(),
    )


async def _probe_production_control(ctx: StatusContext) -> ProbeResult:
    from ...production_control.router import get_models
    from ...production_control.status import aggregate_status

    status_payload = aggregate_status()
    llm_models = get_models("llm", "generate")
    details = {"status": status_payload, "llmModels": llm_models}
    selections = list(llm_models.get("models") or [])
    if not status_payload.get("localAvailable") and not status_payload.get("apiAvailable"):
        return _result(
            "blocked",
            "Production Control reports no usable local or hosted runtime path.",
            message="Neither local nor hosted runtime is available.",
            details=details,
            blockers=["No local or hosted runtime path is available."],
            recovery_actions=_setup_actions(),
        )
    if not selections:
        return _result(
            "warning",
            "Production Control is up, but no LLM selections were returned.",
            message="Model resolution is present without an immediately selectable model.",
            details=details,
            warnings=["No LLM models were returned by Production Control."],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        f"Production Control resolved {len(selections)} LLM model choices.",
        message="Production Control status and models returned successfully.",
        details=details,
    )


async def _probe_production_queue(ctx: StatusContext) -> ProbeResult:
    from ...production_control.status import _queue_counts

    queue = _queue_counts()
    if queue.get("queued") is None and queue.get("running") is None:
        return _result(
            "unknown",
            "Production queue counts are unavailable.",
            message="Queue counts could not be read.",
            details=queue,
            warnings=["Queue counts unavailable."],
        )
    queued = int(queue.get("queued") or 0)
    running = int(queue.get("running") or 0)
    status: HealthStatus = "healthy"
    summary = "Production queues are responsive."
    warnings: list[str] = []
    if queued >= 10:
        status = "warning"
        summary = "Production queues are backing up."
        warnings.append(f"{queued} queued jobs are waiting.")
    return _result(
        status,
        summary,
        message=f"{queued} queued, {running} running.",
        details=queue,
        warnings=warnings,
        recovery_actions=[RecoveryAction(id="open-jobs", label="Open Jobs", kind="open_panel", panel="jobs")],
    )


async def _probe_image_runtime(ctx: StatusContext) -> ProbeResult:
    import asyncio

    from ...image_runtime.readiness import generate_readiness_report

    payload = await asyncio.to_thread(generate_readiness_report)
    blocked = list((payload.get("summary") or {}).get("blocked") or [])
    available = list((payload.get("summary") or {}).get("availableForCertification") or [])
    deferred = list((payload.get("summary") or {}).get("deferred") or [])
    # Optional cloud / non-release image keys must not degrade the local production path.
    _OPTIONAL_IMAGE_BLOCKERS = {
        "imagen.txt2img",
        "imagen.edit",
        "imagen.reference",
        "flux.kontext_edit",
        "flux.fill",
    }
    required_blocked = [item for item in blocked if item not in _OPTIONAL_IMAGE_BLOCKERS]
    optional_blocked = [item for item in blocked if item in _OPTIONAL_IMAGE_BLOCKERS]
    if not payload.get("CapabilityDetectionOperational"):
        return _result(
            "blocked",
            "Image runtime capability detection is not operational.",
            message="Image runtime capability probing failed.",
            details=payload,
            blockers=["Image runtime capability detection is unavailable."],
            recovery_actions=_setup_actions(),
        )
    if required_blocked:
        return _result(
            "warning",
            f"Image runtime is available, but {len(required_blocked)} required workflows are blocked.",
            message="Some required image workflows are still blocked.",
            details={**payload, "optionalBlocked": optional_blocked, "deferredCount": len(deferred)},
            warnings=required_blocked[:8],
            recovery_actions=_setup_actions(),
        )
    details = {**payload, "optionalBlocked": optional_blocked, "deferredCount": len(deferred)}
    if available:
        return _result(
            "healthy",
            f"Image runtime is ready with {len(available)} local workflows available for certification.",
            message=(
                f"{len(optional_blocked)} optional cloud/advanced workflows remain unavailable "
                "and are not counted as current-release blockers."
                if optional_blocked
                else f"{len(available)} workflows available for certification."
            ),
            details=details,
            warnings=(
                [f"Optional not installed: {name}" for name in optional_blocked[:5]]
                if optional_blocked
                else []
            ),
        )
    return _result(
        "warning",
        "Image runtime is present but not yet certification-ready.",
        message="No image workflows are currently available for certification.",
        details=details,
    )


async def _probe_video_runtime(ctx: StatusContext) -> ProbeResult:
    if ctx.mode == "deep":
        from ...video_runtime.diagnostics import build_diagnostics

        payload = await build_diagnostics(ctx.db)
        health = str(payload.get("health") or "Unknown")
        if health == "Unavailable":
            return _result(
                "blocked",
                "Video runtime diagnostics report the stack as unavailable.",
                message="Video runtime diagnostics returned Unavailable.",
                details=payload,
                blockers=["Video runtime diagnostics reported Unavailable."],
                recovery_actions=_setup_actions(),
            )
        if health in {"Degraded", "Busy"}:
            return _result(
                "warning",
                f"Video runtime diagnostics report {health}.",
                message="Video runtime is up but not fully clear.",
                details=payload,
                warnings=[f"Video runtime health: {health}."],
                recovery_actions=_setup_actions(),
            )
        return _result(
            "healthy",
            "Video runtime diagnostics look healthy.",
            message=f"Video runtime health: {health}.",
            details=payload,
        )

    from ...video_runtime.api import wave6_gate

    payload = wave6_gate()
    if not payload.get("wave6WiringUnlocked"):
        return _result(
            "warning",
            "Video runtime gate is present, but production wiring is not fully unlocked.",
            message=str(payload.get("message") or "Video runtime gate is not fully unlocked."),
            details=payload,
            warnings=[str(payload.get("message") or "Video runtime gate not fully unlocked.")],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        "Video runtime gate is reachable and reports an unlocked wiring path.",
        message=str(payload.get("message") or "Video runtime gate returned successfully."),
        details=payload,
    )


async def _probe_voice_runtime(ctx: StatusContext) -> ProbeResult:
    from ...voice_performance.m410_service import get_capabilities, get_runtime_status

    runtime = get_runtime_status()
    capabilities = get_capabilities()
    details = {"runtime": runtime, "capabilities": capabilities}
    if not runtime.get("installed"):
        return _result(
            "not_installed",
            "Voice runtime is not installed yet.",
            message=str(runtime.get("message") or "Voice runtime is not installed."),
            details=details,
            blockers=[str(runtime.get("message") or "Voice runtime is not installed.")],
            recovery_actions=_setup_actions(),
        )
    if not runtime.get("ready"):
        return _result(
            "warning",
            "Voice runtime is installed, but not ready yet.",
            message=str(runtime.get("message") or "Voice runtime is not ready."),
            details=details,
            warnings=[str(runtime.get("message") or "Voice runtime not ready.")],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        "Voice runtime is installed and ready.",
        message=str(runtime.get("message") or "ready"),
        details=details,
    )


async def _probe_voice_environment_runtime(ctx: StatusContext) -> ProbeResult:
    from ...voice_environment.service import runtime_status

    payload = runtime_status()
    status_label = str(payload.get("status") or "Unknown")
    capabilities = payload.get("capabilities") or {}
    warnings = [str(reason) for reason in (payload.get("reasons") or [])]
    if status_label == "Repair Required" or not payload.get("ok"):
        return _result(
            "blocked",
            "Voice Environment runtime requires repair before processing can continue.",
            message=status_label,
            details=payload,
            blockers=warnings or ["Voice Environment runtime is not ready."],
            recovery_actions=_setup_actions(),
        )
    if warnings:
        return _result(
            "warning",
            "Voice Environment runtime is up, but some checks are degraded.",
            message=status_label,
            details=payload,
            warnings=warnings,
            recovery_actions=_setup_actions(),
        )
    if not all(bool(capabilities.get(key)) for key in ("preview", "render")):
        return _result(
            "warning",
            "Voice Environment runtime is reachable, but preview/render is not fully available.",
            message=status_label,
            details=payload,
            warnings=["Preview or render capability is not ready."],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        "Voice Environment runtime is ready for preview and render.",
        message=status_label,
        details=payload,
    )


async def _probe_magi(ctx: StatusContext) -> ProbeResult:
    from ...magi.readiness import readiness_payload

    payload = readiness_payload()
    production_surfaces = list(payload.get("productionSurfaces") or [])
    deferred = list(payload.get("deferredSurfaces") or [])
    return _result(
        "healthy" if production_surfaces else "warning",
        f"MAGI reported {len(production_surfaces)} production surfaces and {len(deferred)} deferred surfaces.",
        message="MAGI readiness returned successfully.",
        details=payload,
    )


async def _probe_library_preflight(ctx: StatusContext) -> ProbeResult:
    if not ctx.project_id:
        return _result(
            "not_applicable",
            "Library persistence checks need an active project.",
            message="Library storage planning is project-scoped.",
            recovery_actions=_project_actions(),
        )
    import asyncio
    from pathlib import Path

    from ...project_library.codirector import storage_preflight

    payload = await asyncio.to_thread(
        storage_preflight, ctx.db, ctx.project_id, task="codirector_status_cross_check"
    )
    if payload.get("ambiguous"):
        return _result(
            "warning",
            "Project library preflight found ambiguous target choices.",
            message=str(payload.get("reason") or "Library target is ambiguous."),
            details=payload,
            warnings=[str(payload.get("reason") or "Ambiguous library target.")],
        )
    if not payload.get("ready"):
        return _result(
            "blocked",
            "Project library preflight could not resolve a safe target.",
            message=str(payload.get("reason") or "Library preflight failed."),
            details=payload,
            blockers=[str(payload.get("reason") or "Library preflight failed.")],
        )

    # Functional persistence smoke against the project's on-disk assets root (not the
    # library display path, which is a virtual taxonomy path).
    write_ok = False
    write_error = ""
    assets_root = ""
    try:
        from ...config import settings

        assets_root = str(Path(settings.data_dir) / "projects" / ctx.project_id / "assets")
    except Exception as exc:  # noqa: BLE001
        write_error = f"Could not resolve project assets root: {exc}"

    if assets_root:
        probe_dir = Path(assets_root) / ".pending" / ".gate"
        probe_file = probe_dir / ".adept_library_persistence_probe.txt"

        def _write_probe() -> None:
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe_file.write_text("adept-library-persistence-ok", encoding="utf-8")
            text = probe_file.read_text(encoding="utf-8")
            if text != "adept-library-persistence-ok":
                raise RuntimeError("probe readback mismatch")
            probe_file.unlink(missing_ok=True)

        try:
            await asyncio.to_thread(_write_probe)
            write_ok = True
        except Exception as exc:  # noqa: BLE001
            write_error = str(exc)

    details = {
        **payload,
        "assetsRoot": assets_root or None,
        "writeProbePassed": write_ok,
        "writeProbeError": write_error or None,
    }
    if not write_ok:
        return _result(
            "blocked",
            "Library target resolved, but a write/read persistence probe failed.",
            message=write_error or "Could not write a probe file into the project library.",
            details=details,
            blockers=[write_error or "Library write probe failed."],
        )
    return _result(
        "healthy",
        "Project library preflight and persistence probe passed.",
        message=str(payload.get("targetPath") or payload.get("folderSystemKey") or "ready"),
        details=details,
    )


async def _probe_bible(ctx: StatusContext) -> ProbeResult:
    if not ctx.project_id:
        return _result(
            "not_applicable",
            "Production Bible checks need an active project.",
            message="Bible readiness is project-scoped.",
            recovery_actions=_project_actions(),
        )
    from ...codirector.bible import service as bible_service
    from ...codirector.errors import CoDirectorError

    try:
        payload = bible_service.get_bible_out(ctx.db, ctx.project_id)
        versions = bible_service.list_versions_out(ctx.db, ctx.project_id)
    except CoDirectorError as exc:
        # No Production Bible yet is informational, not a failure. Only a Bible that
        # exists but is corrupt/unreadable (e.g. validation failure) should warn.
        if exc.code == "BIBLE_NOT_FOUND":
            return _result(
                "not_configured",
                "This project does not have a Production Bible yet.",
                message="Bible presence is informational — create one when the project is ready.",
                details={"projectId": ctx.project_id, "code": exc.code},
                recovery_actions=_content_actions(),
            )
        return _result(
            "warning",
            "The Production Bible exists but could not be read cleanly.",
            message=str(exc.message),
            details={"projectId": ctx.project_id, "code": exc.code, "error": exc.to_dict()},
            warnings=[str(exc.message)],
            recovery_actions=_content_actions(),
        )
    if payload is None:
        return _result(
            "not_configured",
            "This project does not have a Production Bible yet.",
            message="Bible presence is informational — create one when the project is ready.",
            details={"projectId": ctx.project_id},
            recovery_actions=_content_actions(),
        )
    return _result(
        "healthy",
        f"Production Bible is available with {len(versions)} versions.",
        message="Bible reads succeeded.",
        details={
            "bible": payload.model_dump(mode="json") if payload is not None else None,
            "versionCount": len(versions),
        },
        recovery_actions=_content_actions(),
    )


async def _probe_scriptwriter(ctx: StatusContext) -> ProbeResult:
    if not ctx.project_id:
        return _result(
            "not_applicable",
            "Scriptwriter checks need an active project.",
            message="Scriptwriter readiness is project-scoped.",
            recovery_actions=_project_actions(),
        )
    from ...scriptwriter import service as scriptwriter_service
    from ...scriptwriter.store import list_documents

    scriptwriter_service.ensure_ready()
    docs = list_documents(ctx.db, ctx.project_id)
    return _result(
        "healthy" if docs else "warning",
        f"Scriptwriter returned {len(docs)} documents." if docs else "Scriptwriter is ready, but no documents were found yet.",
        message="Scriptwriter read completed successfully.",
        details={"documentCount": len(docs), "projectId": ctx.project_id},
    )


async def _probe_timeline_preflight(ctx: StatusContext) -> ProbeResult:
    if not ctx.project_id or not ctx.scene_id:
        return _result(
            "not_applicable",
            "Timeline preflight is not applicable — no active scene is bound.",
            message="A timeline without a bound scene is a normal project state, not a health failure.",
            details={"projectId": ctx.project_id, "sceneId": ctx.scene_id},
        )
    from ...director_timeline_w46 import orchestrator, service as timeline_service

    bundle = timeline_service.load_timeline_bundle(ctx.db, ctx.project_id, ctx.scene_id)
    if not bundle.get("ok"):
        return _result(
            "blocked",
            "Timeline bundle could not be loaded for the active scene.",
            message=str(bundle.get("error") or "Timeline bundle missing."),
            details=bundle,
            blockers=[str(bundle.get("error") or "Timeline bundle missing.")],
        )
    findings = orchestrator.run_preflight(
        bundle["master"],
        lipsync_tracks=bundle.get("lipsyncTracks"),
        db=ctx.db,
        project_id=ctx.project_id,
        scene_id=ctx.scene_id,
    )
    severe = [item for item in findings if str(item.get("severity") or "").lower() in {"error", "blocked", "fail"}]
    if severe:
        return _result(
            "warning",
            f"Timeline preflight returned {len(severe)} serious findings.",
            message="Timeline preflight surfaced issues that need review.",
            details={"findings": findings},
            warnings=[str(item.get("message") or item.get("title") or "Timeline finding") for item in severe[:8]],
        )
    return _result(
        "healthy",
        "Timeline preflight completed without severe findings.",
        message=f"{len(findings)} findings returned.",
        details={"findings": findings},
    )


async def _probe_create_path(ctx: StatusContext) -> ProbeResult:
    from ...db import Project
    from ...routers import api as projects_api

    if not callable(getattr(projects_api, "create_project", None)) or not callable(
        getattr(projects_api, "list_projects", None)
    ):
        return _result(
            "blocked",
            "CREATE path handlers are missing.",
            message="Project create/list routes are not importable.",
            blockers=["CREATE path is not wired."],
            recovery_actions=_project_actions(),
        )
    try:
        count = int(ctx.db.query(Project).count())
    except Exception as exc:  # noqa: BLE001
        return _result(
            "blocked",
            "CREATE path cannot read projects.",
            message=str(exc),
            blockers=[str(exc)],
            recovery_actions=_project_actions(),
        )
    if ctx.project_id:
        row = ctx.db.get(Project, ctx.project_id)
        if row is None:
            return _result(
                "blocked",
                "The bound project cannot be opened.",
                message="CREATE/open path failed for the active project.",
                details={"projectId": ctx.project_id, "projectCount": count},
                blockers=["Active project is missing."],
                recovery_actions=_project_actions(),
            )
    return _result(
        "healthy",
        "CREATE path can list and open projects.",
        message="Project create/list handlers are present. No project was created.",
        details={"projectCount": count, "projectId": ctx.project_id, "createdProject": False},
    )


async def _probe_timeline_generator_truth(ctx: StatusContext) -> ProbeResult:
    from ...director_timeline_w46.capabilities import list_generators, registry_snapshot

    snapshot = registry_snapshot()
    generators = list_generators()
    details = {
        "generatorCount": len(generators),
        "mock": bool(snapshot.get("mock")),
        "ids": [getattr(item, "id", "") for item in generators[:20]],
    }
    if snapshot.get("mock"):
        return _result(
            "blocked",
            "Timeline generator catalog reported a mock snapshot.",
            message="Generator truth must come from Production Control, not a fixture.",
            details=details,
            blockers=["Timeline generator snapshot is mocked."],
        )
    if not generators:
        return _result(
            "blocked",
            "Timeline has no honest generator rows.",
            message="Creators cannot choose a Timeline generator.",
            details=details,
            blockers=["Timeline generator catalog is empty."],
        )
    missing_labels = [item.id for item in generators if not getattr(item, "label", None)]
    if missing_labels:
        return _result(
            "warning",
            "Some Timeline generators are missing display names.",
            message="Generator catalog loaded, but some rows are incomplete.",
            details={**details, "missingLabels": missing_labels[:8]},
            warnings=missing_labels[:8],
        )
    return _result(
        "healthy",
        f"Timeline generator catalog has {len(generators)} honest rows.",
        message="No generation was run. Catalog truth only.",
        details=details,
    )


async def _probe_timeline_context_binding(ctx: StatusContext) -> ProbeResult:
    if not ctx.project_id:
        return _result(
            "blocked",
            "Timeline context cannot bind without a project.",
            message="Open a project before using Timeline.",
            blockers=["No project is bound."],
            recovery_actions=_project_actions(),
        )
    if not ctx.scene_id:
        return _result(
            "not_applicable",
            "Timeline context binding is waiting for an active scene.",
            message="A project without a bound scene is a normal state, not a production outage.",
            details={"projectId": ctx.project_id},
        )
    from ...director_timeline_w46 import service as timeline_service

    bundle = timeline_service.load_timeline_bundle(ctx.db, ctx.project_id, ctx.scene_id)
    if not bundle.get("ok"):
        return _result(
            "blocked",
            "Timeline cannot load the bound scene.",
            message=str(bundle.get("error") or "Timeline bundle missing."),
            details={"projectId": ctx.project_id, "sceneId": ctx.scene_id, "error": bundle.get("error")},
            blockers=[str(bundle.get("error") or "Timeline bundle missing.")],
        )
    return _result(
        "healthy",
        "Timeline is bound to the active project and scene.",
        message="Context binding is usable. No generation was run.",
        details={"projectId": ctx.project_id, "sceneId": ctx.scene_id, "ok": True},
    )


async def _probe_posecraft_identity_nav(ctx: StatusContext) -> ProbeResult:
    # v1.1: dormant subsystem. Do not advertise or block platform health.
    return _result(
        "healthy",
        "Dormant staging probe is not part of Adept UI v1.1 readiness.",
        message="Skipped. This check does not affect Setup or platform health.",
        details={"projectId": ctx.project_id, "shelved": "v1_2_cloud"},
    )


async def _probe_codirector_grounded_routing(ctx: StatusContext) -> ProbeResult:
    import yaml

    from ...codirector import service as codirector_service
    from ...codirector.knowledgebase.loader import KB_ROOT
    from ...codirector.knowledgebase.platform_replies import knowledge_reply

    manifest_path = KB_ROOT / "MANIFEST.yaml"
    if not manifest_path.is_file():
        return _result(
            "warning",
            "Co-Director knowledge foundation is not landed.",
            message="DEPENDENCY OPEN — CO-DIRECTOR KNOWLEDGE FOUNDATION",
            details={"manifestPath": str(manifest_path), "landed": False},
            warnings=["DEPENDENCY OPEN — CO-DIRECTOR KNOWLEDGE FOUNDATION"],
        )
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return _result(
            "warning",
            "Co-Director knowledge manifest could not be read.",
            message=str(exc),
            details={"manifestPath": str(manifest_path)},
            warnings=[str(exc)],
        )
    schema = str(manifest.get("schema") or "")
    version = str(manifest.get("version") or "")
    entries = list(manifest.get("entries") or [])
    hook = getattr(codirector_service, "_maybe_platform_knowledge_reply", None)
    hook_callable = callable(hook)
    replyable = callable(knowledge_reply)
    r2v_query = "What is Timeline?"
    r2v_direct = knowledge_reply(r2v_query) if replyable else None
    hook_reply = None
    if hook_callable:
        try:
            hook_reply = hook(
                r2v_query,
                getattr(ctx, "workspace", None),
                project_id=getattr(ctx, "project_id", None),
                consumer="codirector.status.probe",
            )
        except TypeError:
            hook_reply = hook(r2v_query, getattr(ctx, "workspace", None))
        except Exception:
            hook_reply = None
    from ...codirector.knowledgebase.routing_receipt import last_routing_receipt

    receipt = last_routing_receipt(project_id=getattr(ctx, "project_id", None))
    r2v_text = str(hook_reply or r2v_direct or "").lower()
    timeline_production = bool(r2v_text) and "wide area network" not in r2v_text and (
        "reference-to-video" in r2v_text
        or "reference to video" in r2v_text
        or ("picture" in r2v_text and "video" in r2v_text)
        or ("prompt name" in r2v_text and "video" in r2v_text)
    )
    routed = bool(hook_callable and hook_reply and receipt and receipt.get("query"))
    destination_accepted = bool(hook_reply) and bool(receipt and receipt.get("landed"))
    landed = (
        schema.startswith("adept-codirector-knowledge/")
        and bool(entries)
        and routed
        and replyable
        and destination_accepted
        and timeline_production
    )
    details = {
        "schema": schema,
        "version": version,
        "entryCount": len(entries),
        "routed": routed,
        "replyable": replyable,
        "landed": landed,
        "r2vContentNotReimplemented": not timeline_production,
        "routingReceipt": receipt,
        "timelineSpokenCard": timeline_production,
        "probeQuery": r2v_query,
    }
    if not landed:
        return _result(
            "warning",
            "Co-Director knowledge foundation is only partly wired.",
            message="DEPENDENCY OPEN — CO-DIRECTOR KNOWLEDGE FOUNDATION",
            details=details,
            warnings=["DEPENDENCY OPEN — CO-DIRECTOR KNOWLEDGE FOUNDATION"],
        )
    return _result(
        "healthy",
        "Co-Director knowledge foundation is landed and routed.",
        message="Dependency check only — no generator glossary was added here.",
        details=details,
    )


_CERT_PROBE_TARGETS = {"vi95_cert_probe"}
_TEMPORAL_ADVISORY = {
    "readiness_class": "advisory_review_degraded",
    "v11_requirement": "advisory",
    "workflow_scope": "codirector.temporal_continuity",
    "production_effect": (
        "The bound scene's latest production Temporal Continuity handoff is not ready. "
        "Timeline generation can continue."
    ),
    "severity": "advisory",
}


def _packet_as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except TypeError:
            return dump()
    return {}


def _is_cert_probe_packet(pkt: dict[str, Any]) -> bool:
    source = pkt.get("source") if isinstance(pkt.get("source"), dict) else {}
    target = str(source.get("targetBatchId") or "")
    extras = pkt.get("extras") if isinstance(pkt.get("extras"), dict) else {}
    return target in _CERT_PROBE_TARGETS or "cert_probe" in target.lower() or bool(extras.get("certProbe"))


def _batch_has_completed_take(batch: Any) -> bool:
    try:
        from ...director_timeline_w46.current_take import current_take_asset_id

        if current_take_asset_id(batch):
            return True
    except Exception:  # noqa: BLE001
        pass
    clip = getattr(batch, "approvedClip", None)
    return bool(getattr(clip, "assetId", None) if clip else False)


def _latest_production_handoff(master: Any) -> dict[str, Any] | None:
    packets = [_packet_as_dict(item) for item in (getattr(master, "temporalPackets", None) or [])]
    production = [item for item in packets if item and not _is_cert_probe_packet(item)]
    if not production:
        return None
    return max(production, key=lambda item: str(item.get("createdAt") or ""))


async def _probe_temporal_continuity(ctx: StatusContext) -> ProbeResult:
    """Bound-scene latest production handoff packet (not the cert probe).

    Read-only. Does not run a second review engine. InternVideo3 absence is
    optional extras and must not warn.
    """
    if not ctx.project_id or not ctx.scene_id:
        return _result(
            "not_applicable",
            "Temporal Continuity handoff is not applicable — no bound scene.",
            message="A project without a bound scene has no production handoff packet.",
            details={"projectId": ctx.project_id, "sceneId": ctx.scene_id},
            **_TEMPORAL_ADVISORY,
        )
    from ...director_timeline_w46 import service as timeline_service

    bundle = timeline_service.load_timeline_bundle(ctx.db, ctx.project_id, ctx.scene_id)
    if not bundle.get("ok"):
        return _result(
            "warning",
            "Temporal Continuity could not load the bound scene timeline.",
            message=str(bundle.get("error") or "Timeline bundle missing."),
            details={"projectId": ctx.project_id, "sceneId": ctx.scene_id},
            warnings=[str(bundle.get("error") or "Timeline bundle missing.")],
            **_TEMPORAL_ADVISORY,
        )
    master = bundle["master"]
    batches = sorted(getattr(master, "batchBlocks", None) or [], key=lambda item: int(getattr(item, "order", 0) or 0))
    completed = [item for item in batches if _batch_has_completed_take(item)]
    if not completed:
        return _result(
            "not_applicable",
            "No completed take on the bound scene — Temporal Continuity handoff is not due.",
            message="Handoff review waits for a completed take.",
            details={"projectId": ctx.project_id, "sceneId": ctx.scene_id, "completedTakeCount": 0},
            **_TEMPORAL_ADVISORY,
        )
    latest = _latest_production_handoff(master)
    successor_due = len(batches) >= 2 and any(
        not _batch_has_completed_take(item) or item.id != completed[-1].id for item in batches[1:]
    )
    if latest is None:
        if len(completed) < 2 and not successor_due:
            return _result(
                "not_applicable",
                "Completed take exists, but no production handoff is due yet.",
                message="A single completed take does not require a Batch N→N+1 packet.",
                details={"projectId": ctx.project_id, "sceneId": ctx.scene_id, "completedTakeCount": len(completed)},
                **_TEMPORAL_ADVISORY,
            )
        return _result(
            "warning",
            "The latest production Temporal Continuity handoff is missing.",
            message="A completed take has no bound-scene production handoff packet.",
            details={
                "projectId": ctx.project_id,
                "sceneId": ctx.scene_id,
                "completedTakeCount": len(completed),
                "packetId": None,
            },
            warnings=["Latest production Temporal Continuity handoff is missing."],
            **_TEMPORAL_ADVISORY,
        )
    extras = latest.get("extras") if isinstance(latest.get("extras"), dict) else {}
    availability = str(latest.get("availability") or "")
    details = {
        "projectId": ctx.project_id,
        "sceneId": ctx.scene_id,
        "packetId": latest.get("packetId"),
        "availability": availability,
        "reason": latest.get("reason"),
        "sourceBatchId": (latest.get("source") or {}).get("batchId") if isinstance(latest.get("source"), dict) else None,
        "targetBatchId": (latest.get("source") or {}).get("targetBatchId") if isinstance(latest.get("source"), dict) else None,
        "perceptionModelId": (latest.get("source") or {}).get("perceptionModelId")
        if isinstance(latest.get("source"), dict)
        else None,
        "deepReviewSkipped": extras.get("deepReviewSkipped"),
        "certProbeExcluded": True,
    }
    if availability == "ready":
        return _result(
            "healthy",
            "The bound scene's latest production Temporal Continuity handoff is ready.",
            message="Production handoff packet is ready on VideoChat3.",
            details=details,
            **_TEMPORAL_ADVISORY,
        )
    return _result(
        "warning",
        "The latest production Temporal Continuity handoff is unavailable or degraded.",
        message=str(latest.get("reason") or "Production handoff packet is not ready."),
        details=details,
        warnings=[str(latest.get("reason") or "Production handoff packet is not ready.")],
        **_TEMPORAL_ADVISORY,
    )


async def _probe_runtime_authority(ctx: StatusContext) -> ProbeResult:
    from runtime_supervisor.constants import LEGACY_TASK_NAMES, TASK_NAME
    from runtime_supervisor.windows_task import list_legacy_owners, query_task

    canonical = query_task(TASK_NAME)
    leftover = list_legacy_owners()
    leftover_states = {name: query_task(name).exists for name in leftover}
    details = {
        "canonicalTask": TASK_NAME,
        "taskRegistered": bool(canonical.exists),
        "legacyTaskNames": list(LEGACY_TASK_NAMES),
        "legacyOwners": leftover,
        "legacyOwnerExists": leftover_states,
        "liveSessionOwner": "Adept Runtime Supervisor",
        "legacyAffectsCurrentSession": False,
        "leftoverMayAffectNextLogon": bool(leftover),
        "retiredThisRun": False,
        "singleAuthority": "Adept Runtime Supervisor",
    }
    if leftover:
        return _result(
            "warning",
            "A leftover Windows startup name is still registered.",
            message=(
                "This session is owned by Adept Runtime Supervisor. "
                "A leftover scheduled-task name is still registered and may still "
                "run at the next Windows sign-in. It was not retired because "
                "AdeptRuntimeService is not a proven logon owner on this machine."
            ),
            details=details,
            warnings=[f"Leftover scheduled task: {name}" for name in leftover],
        )
    return _result(
        "healthy",
        "Adept Runtime Supervisor is the single live runtime authority.",
        message="No leftover scheduled-task owner is registered.",
        details=details,
    )


_CHECKS = [
    HealthCheckDefinition(id="api.health", title="Studio API", description="Top-level API and operator readiness.", category="core", criticality="critical", recoveryActions=_setup_actions(), standard=True, deep=True),
    HealthCheckDefinition(id="capabilities.registry", title="Capability Registry", description="Existing capability blockers and callable surfaces.", category="core", criticality="high", recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="codirector.provider", title="Co-Director Model Runtime", description="Co-Director provider reachability and selected model readiness.", category="provider", criticality="critical", recoveryActions=_provider_actions()),
    HealthCheckDefinition(id="session.binding", title="Project Binding", description="Project/session binding for Co-Director.", category="project", criticality="critical", recoveryActions=_project_actions()),
    HealthCheckDefinition(id="tools.registry", title="Tool Registry", description="Co-Director tool catalog and project availability.", category="integration", criticality="critical", projectScoped=True, recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="proposal.service", title="Proposal Service", description="Co-Director proposal reads and approval surface.", category="persistence", criticality="critical", projectScoped=True, recoveryActions=_content_actions()),
    HealthCheckDefinition(id="comfy.health", title="ComfyUI Runtime", description="Render backend reachability and required model presence.", category="runtime", criticality="high", recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="gpu.stats", title="GPU Readiness", description="Live GPU stats for runtime verification.", category="runtime", criticality="standard", standard=False, deep=True),
    HealthCheckDefinition(id="source_manager.overview", title="Source Manager", description="Model sources, assignments, and provider detection.", category="provider", criticality="standard", recoveryActions=_setup_actions(), standard=False, deep=True),
    HealthCheckDefinition(id="install_jobs.status", title="Install Jobs", description="Install queue activity and potential stalls.", category="jobs", criticality="standard", recoveryActions=_setup_actions(), standard=False, deep=True),
    HealthCheckDefinition(id="production_control.status", title="Production Control", description="Runtime path and LLM model resolution.", category="provider", criticality="high", recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="production_control.queue", title="Production Queue", description="Queued and running production jobs.", category="jobs", criticality="standard", recoveryActions=[RecoveryAction(id="open-jobs", label="Open Jobs", kind="open_panel", panel="jobs")], standard=False, deep=True),
    HealthCheckDefinition(id="image_runtime.readiness", title="Image Runtime", description="Image runtime readiness and blocked workflow review.", category="creative_studio", criticality="high", recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="video_runtime.readiness", title="Video Runtime", description="Video runtime diagnostics and queue health.", category="creative_studio", criticality="high", recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="voice_runtime.readiness", title="Voice Runtime", description="M410 voice runtime install and ready state.", category="creative_studio", criticality="high", recoveryActions=_setup_actions(), standard=False, deep=True),
    HealthCheckDefinition(id="voice_environment.runtime", title="Voice Environment Runtime", description="Voice Environment preview/render runtime readiness.", category="creative_studio", criticality="standard", recoveryActions=_setup_actions()),
    HealthCheckDefinition(id="magi.readiness", title="MAGI Editor", description="MAGI readiness and deferred-surface disclosure.", category="creative_studio", criticality="standard", standard=False, deep=True),
    HealthCheckDefinition(id="library.preflight", title="Library Persistence", description="Project library target resolution and storage readiness.", category="persistence", criticality="critical", projectScoped=True),
    HealthCheckDefinition(id="bible.versions", title="Production Bible", description="Bible presence and version readback.", category="project", criticality="high", projectScoped=True, recoveryActions=_content_actions(), standard=False, deep=True),
    HealthCheckDefinition(id="scriptwriter.documents", title="Scriptwriter", description="Scriptwriter document access for the active project.", category="creative_studio", criticality="standard", projectScoped=True, standard=False, deep=True),
    HealthCheckDefinition(id="timeline.preflight", title="Director Timeline", description="Scene-scoped timeline preflight and findings.", category="integration", criticality="standard", projectScoped=True, sceneScoped=True, standard=False, deep=True),
    HealthCheckDefinition(id="create.path", title="CREATE Path", description="Project create/open path is usable without creating a new project.", category="project", criticality="critical", projectScoped=True),
    HealthCheckDefinition(id="timeline.generator_truth", title="Timeline Generators", description="Timeline generator catalog is honest and present.", category="integration", criticality="high"),
    HealthCheckDefinition(id="timeline.context_binding", title="Timeline Context", description="Timeline can bind the open project and scene.", category="integration", criticality="high", projectScoped=True),
    HealthCheckDefinition(id="posecraft.identity_nav", title="Staging scene load", description="Dormant v1.2 scene-load probe. Not a v1.1 creator studio check.", category="creative_studio", criticality="optional", projectScoped=True, standard=False, deep=True),
    HealthCheckDefinition(id="codirector.grounded_routing", title="Co-Director Routing", description="Knowledge foundation is landed and routed. Does not rebuild knowledge files.", category="integration", criticality="standard"),
    HealthCheckDefinition(
        id="codirector.temporal_continuity",
        title="Temporal Continuity Handoff",
        description="Bound-scene latest production Temporal Continuity packet (not the cert probe).",
        category="integration",
        criticality="standard",
        projectScoped=True,
        sceneScoped=True,
        readinessClass="advisory_review_degraded",
    ),
    HealthCheckDefinition(id="runtime.authority", title="Runtime Authority", description="Adept Runtime Supervisor remains the single live owner.", category="runtime", criticality="optional"),
]

_PROBES: dict[str, ProbeFn] = {
    "api.health": _probe_api_health,
    "capabilities.registry": _probe_capabilities,
    "codirector.provider": _probe_codirector_provider,
    "session.binding": _probe_session_binding,
    "tools.registry": _probe_tool_registry,
    "proposal.service": _probe_proposals,
    "comfy.health": _probe_comfy,
    "gpu.stats": _probe_gpu,
    "source_manager.overview": _probe_source_manager,
    "install_jobs.status": _probe_install_jobs,
    "production_control.status": _probe_production_control,
    "production_control.queue": _probe_production_queue,
    "image_runtime.readiness": _probe_image_runtime,
    "video_runtime.readiness": _probe_video_runtime,
    "voice_runtime.readiness": _probe_voice_runtime,
    "voice_environment.runtime": _probe_voice_environment_runtime,
    "magi.readiness": _probe_magi,
    "library.preflight": _probe_library_preflight,
    "bible.versions": _probe_bible,
    "scriptwriter.documents": _probe_scriptwriter,
    "timeline.preflight": _probe_timeline_preflight,
    "create.path": _probe_create_path,
    "timeline.generator_truth": _probe_timeline_generator_truth,
    "timeline.context_binding": _probe_timeline_context_binding,
    "posecraft.identity_nav": _probe_posecraft_identity_nav,
    "codirector.grounded_routing": _probe_codirector_grounded_routing,
    "codirector.temporal_continuity": _probe_temporal_continuity,
    "runtime.authority": _probe_runtime_authority,
}


def registry_definitions() -> list[HealthCheckDefinition]:
    return list(_CHECKS)


def get_definition(check_id: str) -> HealthCheckDefinition:
    for item in _CHECKS:
        if item.id == check_id:
            return item
    raise KeyError(check_id)


def selected_definitions(mode: StatusMode, check_ids: Optional[list[str]] = None) -> list[HealthCheckDefinition]:
    if check_ids:
        return [get_definition(check_id) for check_id in check_ids]
    selected = list(_CHECKS)
    if mode == "deep":
        return [item for item in selected if item.deep]
    return [item for item in selected if item.standard]


async def run_probe(check_id: str, ctx: StatusContext) -> ProbeResult:
    return await _PROBES[check_id](ctx)
