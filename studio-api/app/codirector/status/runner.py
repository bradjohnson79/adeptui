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
    SharedProbeBundle,
    awaited_dependency_for,
    cache_get,
    cache_invalidate_global,
    cache_put,
    last_healthy_at,
    last_healthy_summary,
    remember_healthy,
    timeout_for_check,
    warm_shared_bundle,
)
from .redaction import redact_payload
from .registry import StatusContext, get_definition, registry_definitions, run_probe, selected_definitions
from .store import persist_run
from .types import HealthCheckResult, HealthRun, RecoveryAction, StatusCheckRequest, StatusMode
from .weighting import score_for_status, summarize_results

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

    # Phase BS — TTL cache: skip probe if a fresh global result exists
    cached = cache_get(check_id)
    if cached is not None and ctx.mode != "deep":
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
        )

    started = perf_counter()
    checked_at = _utcnow()
    dependency = awaited_dependency_for(check_id)
    prior_healthy = last_healthy_at(check_id)
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
                status = "timed_out"
                partial = True
                timed_out = True
                summary = f"{definition.title} timed out during the cross-check."
                message = (
                    f"Elapsed limit {timeout_seconds:.1f}s awaiting {dependency}. "
                    f"Last verified healthy: {prior_healthy or 'never'}."
                )
                details = {
                    "timeoutMs": int(timeout_seconds * 1000),
                    "awaitedDependency": dependency,
                    "lastHealthyAt": prior_healthy,
                    "lastHealthySummary": last_healthy_summary(check_id),
                    "retry": True,
                }
                blockers = []
                warnings = ["This check timed out and was marked partial."]
                recovery_actions = list(definition.recoveryActions) + [_RETRY_ACTION]
        else:
            status = "timed_out"
            partial = True
            timed_out = True
            summary = f"{definition.title} timed out during the cross-check."
            message = (
                f"Elapsed limit {timeout_seconds:.1f}s awaiting {dependency}. "
                f"Last verified healthy: {prior_healthy or 'never'}."
            )
            details = {
                "timeoutMs": int(timeout_seconds * 1000),
                "awaitedDependency": dependency,
                "lastHealthyAt": prior_healthy,
                "lastHealthySummary": last_healthy_summary(check_id),
                "retry": True,
            }
            blockers = []
            warnings = ["This check timed out and was marked partial."]
            recovery_actions = list(definition.recoveryActions) + [_RETRY_ACTION]
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


async def run_status_check(ctx: StatusContext, body: StatusCheckRequest, mode: StatusMode = "standard") -> HealthRun:
    started_at = _utcnow()
    run_id = f"cdr_status_{uuid.uuid4().hex[:12]}"
    checks = selected_definitions(mode, body.checkIds)
    ctx.mode = mode

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
    bundle: SharedProbeBundle = await warm_shared_bundle(project_id=body.projectId or ctx.project_id)
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
    results = list(preflight_results) + list(
        await asyncio.gather(
            *(
                _execute_one(ctx, definition.id, timeout_for_check(definition.id, mode))
                for definition in checks
            )
        )
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
