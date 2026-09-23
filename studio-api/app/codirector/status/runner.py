from __future__ import annotations

import asyncio
import json
import queue
import uuid
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any, Optional

from .probe_context import (
    LKG_WINDOW_SEC,
    SharedProbeBundle,
    awaited_dependency_for,
    cache_get,
    cache_invalidate_global,
    cache_put,
    last_healthy_at,
    last_healthy_summary,
    remember_healthy,
    seconds_since_healthy,
    timeout_for_check,
    warm_shared_bundle,
)
from .redaction import redact_payload
from .registry import StatusContext, get_definition, registry_definitions, run_probe, selected_definitions
from .store import persist_run
from .types import HealthCheckResult, HealthRun, RecoveryAction, StatusCheckRequest, StatusMode
from .weighting import score_for_status, summarize_results
from ...readiness.v11_policy import classify_status_check

_RETRY_ACTION = RecoveryAction(id="retry-check", label="Retry this check", kind="refresh")

_EVENT_LOCK = RLock()
_EVENT_SEQ = 0
_RECENT_EVENTS: list[dict[str, Any]] = []
_SUBSCRIBERS: set[queue.Queue[dict[str, Any] | None]] = set()

# Target latency for "slow" classification (completed but over target).
_SLOW_TARGET_MS: dict[str, int] = {
    "capabilities.registry": 8000,
    "tools.registry": 8000,
    "comfy.health": 8000,
    "codirector.provider": 5000,
    "library.preflight": 15000,
    "image_runtime.readiness": 8000,
}

def _lkg_timeout(
    definition: Any,
    check_id: str,
    dependency: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Build a timeout result, downgrading a transient timeout to warning when a
    last-known-good healthy result exists within the window.

    Critical process death (connection refused) is NOT routed here — it raises and
    is handled as a hard failure elsewhere, so it always flips immediately.
    """
    prior = last_healthy_at(check_id)
    seconds = seconds_since_healthy(check_id)
    if seconds is not None and seconds <= LKG_WINDOW_SEC:
        # Transient timeout with a fresh last-known-good: warn, don't degrade.
        return {
            "status": "warning",
            "partial": True,
            "timed_out": True,
            "summary": f"{definition.title} timed out; using last known-good result.",
            "message": (
                f"Elapsed limit {timeout_seconds:.1f}s awaiting {dependency}. "
                f"Last verified {int(seconds)}s ago."
            ),
            "details": {
                "timeoutMs": int(timeout_seconds * 1000),
                "awaitedDependency": dependency,
                "lastHealthyAt": prior,
                "lastHealthySummary": last_healthy_summary(check_id),
                "lastKnownGood": True,
                "secondsSinceHealthy": int(seconds),
                "retry": True,
            },
            "blockers": [],
            "warnings": [
                f"This check timed out but was healthy {int(seconds)}s ago; using the last known-good result."
            ],
            "recovery_actions": list(definition.recoveryActions) + [_RETRY_ACTION],
        }
    # No usable last-known-good: report a real timeout.
    return {
        "status": "timed_out",
        "partial": True,
        "timed_out": True,
        "summary": f"{definition.title} timed out during the cross-check.",
        "message": (
            f"Elapsed limit {timeout_seconds:.1f}s awaiting {dependency}. "
            f"Last verified healthy: {prior or 'never'}."
        ),
        "details": {
            "timeoutMs": int(timeout_seconds * 1000),
            "awaitedDependency": dependency,
            "lastHealthyAt": prior,
            "lastHealthySummary": last_healthy_summary(check_id),
            "retry": True,
        },
        "blockers": [],
        "warnings": ["This check timed out and was marked partial."],
        "recovery_actions": list(definition.recoveryActions) + [_RETRY_ACTION],
    }


def _comfy_probe_true_death(details: dict[str, Any]) -> bool:
    if details.get("trueDeath") is True:
        return True
    refused = bool(details.get("connectionRefused") or details.get("errorKind") == "refused")
    return refused and details.get("listenerPresent") is False


def _lkg_unreachable(
    definition: Any,
    check_id: str,
    dependency: str,
    timeout_seconds: float,
    details: dict[str, Any],
) -> dict[str, Any] | None:
    """Rescue a transient Comfy miss. True death (refused + no listener) stays offline.

    Returns healthy when :8188 is still listening (or generation is active)
    so a flap cannot cap Production Assurance at Advisory 94 or Blocked 35.
    Timed_out is reserved for a miss with no listener proof.
    """
    if _comfy_probe_true_death(details):
        return None
    seconds = seconds_since_healthy(check_id)
    listener = details.get("listenerPresent") is True
    generation = details.get("generationActive")
    busy = isinstance(generation, dict) and bool(generation.get("active"))
    if not (listener or busy or (seconds is not None and seconds <= LKG_WINDOW_SEC)):
        return None
    prior = last_healthy_at(check_id)
    proven_live = listener or busy
    return {
        "status": "busy" if busy else "healthy" if proven_live else "timed_out",
        "partial": not proven_live,
        "timed_out": not proven_live,
        "summary": (
            f"{definition.title} is busy with a live generation."
            if busy
            else f"{definition.title} is reachable."
            if proven_live
            else f"{definition.title} was briefly unreachable; using last known-good result."
        ),
        "message": (
            "ComfyUI is generating; health probe was late."
            if busy
            else "ComfyUI is listening; a late probe is not proof the runtime is down."
            if proven_live
            else (
                f"Transient unreachable while awaiting {dependency}. "
                f"Last verified healthy: {prior or 'never'}."
            )
        ),
        "details": {
            **details,
            "timeoutMs": int(timeout_seconds * 1000),
            "awaitedDependency": dependency,
            "lastHealthyAt": prior,
            "lastHealthySummary": last_healthy_summary(check_id),
            "lastKnownGood": True,
            "secondsSinceHealthy": int(seconds) if seconds is not None else None,
            "retry": True,
        },
        "blockers": [],
        "warnings": [
            "ComfyUI was briefly unreachable; last-known-good is still within the window."
        ],
        "recovery_actions": list(definition.recoveryActions) + [_RETRY_ACTION],
    }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publish(event: dict[str, Any]) -> None:
    global _EVENT_SEQ
    with _EVENT_LOCK:
        _EVENT_SEQ += 1
        enriched = {"id": _EVENT_SEQ, **event}
        _RECENT_EVENTS.append(enriched)
        del _RECENT_EVENTS[:-200]
        for subscriber in list(_SUBSCRIBERS):
            try:
                subscriber.put(enriched)
            except Exception:
                _SUBSCRIBERS.discard(subscriber)


def subscribe_events() -> queue.Queue[dict[str, Any] | None]:
    outbound: queue.Queue[dict[str, Any] | None] = queue.Queue()
    with _EVENT_LOCK:
        _SUBSCRIBERS.add(outbound)
    return outbound


def unsubscribe_events(outbound: queue.Queue[dict[str, Any] | None]) -> None:
    with _EVENT_LOCK:
        _SUBSCRIBERS.discard(outbound)
    try:
        outbound.put(None)
    except Exception:
        pass


def recent_events(after_id: Optional[int] = None) -> list[dict[str, Any]]:
    with _EVENT_LOCK:
        events = list(_RECENT_EVENTS)
    if after_id is None:
        return events
    return [event for event in events if int(event.get("id") or 0) > after_id]


def encode_sse(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "status")
    event_id = str(event.get("id") or "")
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def _maybe_mark_slow(status: str, check_id: str, duration_ms: int) -> str:
    if status not in {"healthy", "ready", "connected"}:
        return status
    target = _SLOW_TARGET_MS.get(check_id)
    if target is not None and duration_ms > target:
        return "slow"
    return status


async def _execute_one(ctx: StatusContext, check_id: str, timeout_seconds: float) -> HealthCheckResult:
    definition = get_definition(check_id)

    # Phase BS — TTL cache: skip probe if a fresh global result exists.
    # Explicit Re-check must not reuse the status TTL cache.
    cached = cache_get(check_id)
    if cached is not None and ctx.mode != "deep" and not getattr(ctx, "force_refresh", False):
        assignment = classify_status_check(check_id)
        return HealthCheckResult(
            checkId=check_id,
            title=definition.title,
            category=definition.category,
            criticality=definition.criticality,
            status=cached.get("status", "healthy"),
            score=score_for_status(cached.get("status", "healthy")),
            summary=cached.get("summary", definition.description),
            message=cached.get("message", ""),
            durationMs=0,
            timeoutMs=int(timeout_seconds * 1000),
            awaitedDependency=awaited_dependency_for(check_id),
            lastHealthyAt=last_healthy_at(check_id),
            warnings=cached.get("warnings", []),
            blockers=cached.get("blockers", []),
            recoveryActions=cached.get("recoveryActions", []),
            details=cached.get("details", {}),
            checkedAt=_utcnow(),
            timedOut=False,
            partial=False,
            stale=False,
            readinessClass=cached.get("readinessClass") or (assignment.readiness_class.value if assignment else None),
            v11Requirement=cached.get("v11Requirement") or (assignment.v11_requirement.value if assignment else None),
            workflowScope=cached.get("workflowScope") or (assignment.workflow_scope if assignment else None),
            productionEffect=cached.get("productionEffect") or (assignment.production_effect if assignment else None),
            severity=cached.get("severity") or (assignment.severity.value if assignment else None),
        )

    started = perf_counter()
    checked_at = _utcnow()
    dependency = awaited_dependency_for(check_id)
    prior_healthy = last_healthy_at(check_id)
    raw: dict[str, Any] = {}
    _publish(
        {
            "type": "check_started",
            "runScope": "codirector-status",
            "checkId": check_id,
            "checkedAt": checked_at,
            "timeoutMs": int(timeout_seconds * 1000),
            "dependency": dependency,
            "state": "RUNNING",
        }
    )
    try:
        raw = await asyncio.wait_for(run_probe(check_id, ctx), timeout=timeout_seconds)
        status = raw["status"]
        partial = bool(raw.get("partial"))
        timed_out = False
        summary = str(raw.get("summary") or definition.description)
        message = str(raw.get("message") or "")
        details = redact_payload(dict(raw.get("details") or {}))
        blockers = [str(item) for item in raw.get("blockers") or []]
        warnings = [str(item) for item in raw.get("warnings") or []]
        recovery_actions = list(raw.get("recoveryActions") or definition.recoveryActions)
        if status == "offline" and check_id == "comfy.health":
            rescued = _lkg_unreachable(definition, check_id, dependency, timeout_seconds, details)
            if rescued is not None:
                status = rescued["status"]
                partial = rescued["partial"]
                timed_out = rescued["timed_out"]
                summary = rescued["summary"]
                message = rescued["message"]
                details = rescued["details"]
                blockers = rescued["blockers"]
                warnings = rescued["warnings"]
                recovery_actions = rescued["recovery_actions"]
        if status in {"healthy", "ready", "connected", "busy", "slow", "starting", "not_applicable"}:
            remember_healthy(check_id, summary)
    except asyncio.TimeoutError:
        # Prefer BUSY over TIMED_OUT when Co-Director is actively inferencing.
        if check_id == "codirector.provider":
            from ..inference_activity import snapshot as inference_snapshot

            activity = inference_snapshot()
            if activity.busy:
                status = "busy"
                partial = False
                timed_out = False
                summary = "BUSY — selected model is processing an active request."
                message = (
                    f"Co-Director inference is active ({activity.label or 'turn'}). "
                    f"Last verified healthy: {prior_healthy or 'never'}."
                )
                details = {
                    "busy": True,
                    "activeCount": activity.activeCount,
                    "startedAt": activity.startedAt,
                    "lastHealthyAt": prior_healthy,
                    "lastHealthySummary": last_healthy_summary(check_id),
                    "timeoutMs": int(timeout_seconds * 1000),
                    "awaitedDependency": dependency,
                }
                blockers = []
                warnings = ["Active inference — not a timeout failure."]
                recovery_actions = list(definition.recoveryActions)
            else:
                lkg = _lkg_timeout(definition, check_id, dependency, timeout_seconds)
                status = lkg["status"]
                partial = lkg["partial"]
                timed_out = lkg["timed_out"]
                summary = lkg["summary"]
                message = lkg["message"]
                details = lkg["details"]
                blockers = lkg["blockers"]
                warnings = lkg["warnings"]
                recovery_actions = lkg["recovery_actions"]
        else:
            lkg = _lkg_timeout(definition, check_id, dependency, timeout_seconds)
            status = lkg["status"]
            partial = lkg["partial"]
            timed_out = lkg["timed_out"]
            summary = lkg["summary"]
            message = lkg["message"]
            details = lkg["details"]
            blockers = lkg["blockers"]
            warnings = lkg["warnings"]
            recovery_actions = lkg["recovery_actions"]
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        partial = True
        timed_out = False
        summary = f"{definition.title} failed during the cross-check."
        message = str(exc)
        details = {"error": {"type": type(exc).__name__, "message": str(exc)}}
        blockers = [str(exc)]
        warnings = []
        recovery_actions = list(definition.recoveryActions)

    duration_ms = int(round((perf_counter() - started) * 1000))
    status = _maybe_mark_slow(status, check_id, duration_ms)
    if status == "slow":
        target = _SLOW_TARGET_MS.get(check_id, 5000)
        summary = f"SLOW — completed in {duration_ms / 1000:.1f}s; target is {target / 1000:.1f}s."
        warnings = list(warnings) + [f"Completed slower than the {target}ms target."]

    assignment = classify_status_check(check_id)
    readiness_class = raw.get("readinessClass") if isinstance(raw, dict) else None
    if not readiness_class:
        readiness_class = getattr(definition, "readinessClass", None)
    if not readiness_class and assignment is not None:
        readiness_class = assignment.readiness_class.value

    result = HealthCheckResult(
        checkId=check_id,
        title=definition.title,
        category=definition.category,
        criticality=definition.criticality,
        status=status,  # type: ignore[arg-type]
        score=score_for_status(status),  # type: ignore[arg-type]
        summary=summary,
        message=message,
        durationMs=duration_ms,
        timeoutMs=int(timeout_seconds * 1000),
        awaitedDependency=dependency,
        lastHealthyAt=last_healthy_at(check_id) or prior_healthy,
        warnings=warnings,
        blockers=blockers,
        recoveryActions=recovery_actions,
        details=details,
        checkedAt=checked_at,
        timedOut=timed_out,
        partial=partial,
        stale=bool(timed_out and prior_healthy),
        readinessClass=readiness_class,
        v11Requirement=(raw.get("v11Requirement") if isinstance(raw, dict) else None)
        or (assignment.v11_requirement.value if assignment else None),
        workflowScope=(raw.get("workflowScope") if isinstance(raw, dict) else None)
        or (assignment.workflow_scope if assignment else None),
        productionEffect=(raw.get("productionEffect") if isinstance(raw, dict) else None)
        or (assignment.production_effect if assignment else None),
        severity=(raw.get("severity") if isinstance(raw, dict) else None)
        or (assignment.severity.value if assignment else None),
    )
    _publish(
        {
            "type": "check_completed",
            "runScope": "codirector-status",
            "checkId": check_id,
            "status": result.status,
            "durationMs": result.durationMs,
            "timeoutMs": result.timeoutMs,
            "summary": result.summary,
            "checkedAt": checked_at,
            "state": "TIMED_OUT" if timed_out else result.status.upper(),
            "dependency": dependency,
            "lastHealthyAt": result.lastHealthyAt,
        }
    )
    # Phase BS — TTL cache: store global check results for reuse
    if status in ("healthy", "ready", "connected", "degraded", "warning", "blocked", "failed", "offline"):
        cache_put(check_id, raw if isinstance(raw, dict) else {"status": status, "summary": summary, "message": message, "warnings": warnings, "blockers": blockers, "recoveryActions": [r.model_dump(mode="json") for r in recovery_actions] if recovery_actions else [], "details": details})
    return result


# Ordered category phases. Core readiness first, then runtime, then creative studios.
# Checks within the same phase are independent and run concurrently; different phases
# run sequentially so downstream categories observe earlier categories' outcomes.
_PHASE_ORDER: list[tuple[list[str], str]] = [
    (["api.health", "session.binding", "capabilities.registry", "create.path"], "core"),
    (["codirector.provider", "comfy.health", "gpu.stats", "production_control.status", "tools.registry", "runtime.authority"], "runtime"),
    (["image_runtime.readiness", "video_runtime.readiness", "library.preflight", "voice_runtime.readiness", "voice_environment.runtime", "magi.readiness"], "creative_studio"),
    (["timeline.generator_truth", "timeline.context_binding", "codirector.grounded_routing", "codirector.temporal_continuity"], "creator_path"),
]


async def _execute_in_phases(ctx: StatusContext, checks: list[Any], mode: StatusMode) -> list[HealthCheckResult]:
    """Execute the given checks in ordered category phases.

    Each phase runs its independent members concurrently (wall cost = slowest member
    of that phase, not the sum). Phases themselves run sequentially to honour
    cross-category dependencies (core before runtime before creative studios).
    """
    all_results: list[HealthCheckResult] = []

    used_ids = {item.id for item in checks}
    # Build a (phase_label, [check_ids]) plan preserving the category order for known
    # ids and collecting any unrecognized ids into a trailing "other" phase.
    plan: list[tuple[str, list[str]]] = []
    for ids, _label in _PHASE_ORDER:
        phase_ids = [cid for cid in ids if cid in used_ids]
        if phase_ids:
            plan.append((_label, phase_ids))
    planned = {cid for _, ids in plan for cid in ids}
    extra_ids = [cid for cid in used_ids if cid not in planned]
    if extra_ids:
        plan.append(("other", extra_ids))

    for _label, phase_ids in plan:
        phase_checks = [item for item in checks if item.id in phase_ids]
        if not phase_checks:
            continue
        phase_results = list(
            await asyncio.gather(
                *(
                    _execute_one(ctx, definition.id, timeout_for_check(definition.id, mode))
                    for definition in phase_checks
                )
            )
        )
        all_results.extend(phase_results)

    return all_results


async def run_status_check(ctx: StatusContext, body: StatusCheckRequest, mode: StatusMode = "standard") -> HealthRun:
    started_at = _utcnow()
    run_id = f"cdr_status_{uuid.uuid4().hex[:12]}"
    checks = selected_definitions(mode, body.checkIds)
    ctx.mode = mode
    ctx.force_refresh = bool(getattr(body, "forceRefresh", False)) or mode == "deep"
    if ctx.force_refresh:
        cache_invalidate_global()
        from ...capabilities import service as capability_service

        capability_service.invalidate_cache()

    # Control-plane preflight: if api.health is in the selected set and fails critically,
    # stop before launching the full probe fan-out (queue, registry, provider, etc.).
    if mode == "standard" and any(item.id == "api.health" for item in checks):
        api_preflight = await _execute_one(ctx, "api.health", timeout_for_check("api.health", mode))
        if api_preflight.status in ("failed", "timed_out", "offline", "blocked"):
            # Phase BS — API down invalidates all cached global results
            cache_invalidate_global()
            summary, categories, explainability = summarize_results([api_preflight], mode)
            completed_at = _utcnow()
            run = HealthRun(
                runId=run_id,
                mode=mode,
                projectId=body.projectId,
                sceneId=body.sceneId,
                workspace=body.workspace,
                startedAt=started_at,
                completedAt=completed_at,
                partial=True,
                cancelled=False,
                summary=summary,
                categories=categories,
                explainability=explainability,
                results=[api_preflight],
            )
            persist_run(run)
            _publish(
                {
                    "type": "run_completed",
                    "runScope": "codirector-status",
                    "runId": run_id,
                    "mode": mode,
                    "completedAt": completed_at,
                    "projectId": body.projectId,
                    "sceneId": body.sceneId,
                    "summary": run.summary.model_dump(mode="json"),
                    "preflightStopped": True,
                    "preflightReason": "api.health",
                }
            )
            return run
        # Reuse successful preflight result; skip duplicate execute later.
        checks = [item for item in checks if item.id != "api.health"]
        preflight_results = [api_preflight]
    else:
        preflight_results = []

    # Warm shared expensive probes once so parallel checks do not stampede Comfy.
    bundle: SharedProbeBundle = await warm_shared_bundle(
        project_id=body.projectId or ctx.project_id,
        force=ctx.force_refresh,
    )
    ctx.shared = bundle

    _publish(
        {
            "type": "run_started",
            "runScope": "codirector-status",
            "runId": run_id,
            "mode": mode,
            "checkCount": len(checks),
            "startedAt": started_at,
            "projectId": body.projectId,
            "sceneId": body.sceneId,
            "sharedWarmErrors": list(bundle.warm_errors),
        }
    )
    # Independent probes run concurrently with per-check budgets (not one flat 1.5s).
    # Checks are grouped into ordered category phases: core first, then runtime,
    # then creative studios. Within a phase, independent checks run concurrently via
    # gather, so each phase costs only its slowest member. Phases run in sequence to
    # honour cross-category dependencies (core readiness before runtime/project checks).
    results = list(preflight_results) + list(
        await _execute_in_phases(ctx, checks, mode)
    )
    summary, categories, explainability = summarize_results(results, mode)
    completed_at = _utcnow()
    run = HealthRun(
        runId=run_id,
        mode=mode,
        projectId=body.projectId,
        sceneId=body.sceneId,
        workspace=body.workspace,
        startedAt=started_at,
        completedAt=completed_at,
        partial=any(item.partial for item in results),
        cancelled=False,
        summary=summary,
        categories=categories,
        explainability=explainability,
        results=results,
        readOnly=True,
        mutatesRuntime=False,
        mutatesConfig=False,
        installsModels=False,
        forceRefresh=ctx.force_refresh,
    )
    persist_run(run)
    _publish(
        {
            "type": "run_completed",
            "runScope": "codirector-status",
            "runId": run_id,
            "mode": mode,
            "completedAt": completed_at,
            "projectId": body.projectId,
            "sceneId": body.sceneId,
            "summary": run.summary.model_dump(mode="json"),
        }
    )
    return run


def registry_payload() -> dict[str, Any]:
    return {
        "checks": [item.model_dump(mode="json") for item in registry_definitions()],
        "modes": {
            "standard": [item.id for item in registry_definitions() if item.standard],
            "deep": [item.id for item in registry_definitions() if item.deep],
        },
        "timeoutBudgetsSeconds": {
            item.id: timeout_for_check(item.id, "standard") for item in registry_definitions() if item.standard
        },
    }
