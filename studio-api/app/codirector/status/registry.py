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
) -> ProbeResult:
    return {
        "status": status,
        "summary": summary,
        "message": message,
        "details": details or {},
        "blockers": blockers or [],
        "warnings": warnings or [],
        "recoveryActions": recovery_actions or [],
    }


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


async def _probe_capabilities(ctx: StatusContext) -> ProbeResult:
    from ...capabilities import service as capability_service

    snapshot = getattr(ctx.shared, "capabilities", None) if ctx.shared is not None else None
    if snapshot is None:
        snapshot = (
            await capability_service.get_project_capabilities(ctx.project_id, force=False)
            if ctx.project_id
            else await capability_service.get_capabilities(force=False)
        )
    blockers = [b.message for b in getattr(snapshot, "blockers", [])]
    callable_count = len(getattr(snapshot, "callable", []) or [])
    total = int(getattr(snapshot, "readinessTotal", 0) or len(getattr(snapshot, "capabilities", []) or []))
    details = snapshot.model_dump(mode="json")
    if blockers:
        return _result(
            "blocked",
            f"{len(blockers)} capability blockers are preventing full readiness.",
            message="Capability blockers need attention before all Co-Director actions can run.",
            details=details,
            blockers=blockers[:8],
            recovery_actions=_setup_actions(),
        )
    if callable_count == 0 and total:
        return _result(
            "warning",
            "Capabilities loaded, but nothing is callable yet.",
            message="The capability snapshot loaded without an immediately usable surface.",
            details=details,
            warnings=["No callable capabilities were reported."],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        f"{callable_count} callable capabilities are available.",
        message="Capability readiness returned without blockers.",
        details=details,
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
    details["availabilityCount"] = len(offered)
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
    if blocked:
        return _result(
            "warning",
            f"{len(offered)} tools are available, but some tools are still blocked.",
            message="Tool availability returned a partial result.",
            details=details,
            warnings=blocked[:8],
            recovery_actions=_setup_actions(),
        )
    return _result(
        "healthy",
        f"{len(offered)} Co-Director tools are available for this project.",
        message="Tool catalog and project availability look healthy.",
        details=details,
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


async def _probe_comfy(ctx: StatusContext) -> ProbeResult:
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
        return _result(
            "not_configured",
            "This project does not have a Production Bible yet.",
            message=str(exc.message),
            details={"projectId": ctx.project_id, "error": exc.to_dict()},
            warnings=[str(exc.message)],
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
            "not_tested",
            "Timeline preflight was skipped because no active scene is bound.",
            message="Scene-scoped timeline checks require a scene.",
            warnings=["No active scene is available for timeline preflight."],
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
    findings = orchestrator.run_preflight(bundle["master"], director_timeline=bundle["directorTimeline"])
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
