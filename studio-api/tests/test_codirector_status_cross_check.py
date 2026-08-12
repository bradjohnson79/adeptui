from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from app.codirector.status import runner, store
from app.codirector.status.registry import StatusContext
from app.codirector.status.redaction import redact_payload
from app.codirector.status.types import (
    HealthCheckResult,
    HealthExplainability,
    HealthRun,
    HealthRunSummary,
    StatusCheckRequest,
)
from app.codirector.status.weighting import summarize_results


def _result(
    check_id: str,
    *,
    status: str,
    criticality: str = "standard",
    category: str = "core",
    summary: str = "ok",
) -> HealthCheckResult:
    return HealthCheckResult(
        checkId=check_id,
        title=check_id,
        category=category,  # type: ignore[arg-type]
        criticality=criticality,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        score=100,
        summary=summary,
        message=summary,
        checkedAt="2026-08-02T05:00:00+00:00",
    )


def _run(run_id: str) -> HealthRun:
    summary = HealthRunSummary(
        statusIndicator="Operational",
        score=98,
        band="Excellent",
        mode="standard",
        totalChecks=1,
        healthyChecks=1,
        warningChecks=0,
        blockedChecks=0,
        checkedAt="2026-08-02T05:00:00+00:00",
        scoreExplanation="1 checks healthy, 0 warning, 0 blocked.",
    )
    return HealthRun(
        runId=run_id,
        mode="standard",
        projectId="proj-1",
        sceneId="scene-1",
        startedAt="2026-08-02T05:00:00+00:00",
        completedAt="2026-08-02T05:00:01+00:00",
        summary=summary,
        categories=[],
        explainability=HealthExplainability(band="Excellent"),
        results=[],
    )


def test_redaction_recursively_hides_sensitive_fields():
    payload = {
        "endpoint": "http://127.0.0.1:11434",
        "nested": {
            "token": "abc123",
            "authorization": "Bearer secret",
            "safe": "visible",
        },
        "items": [{"source_url": "https://example.com/private"}],
    }

    redacted = redact_payload(payload)

    assert redacted["endpoint"] == "[redacted]"
    assert redacted["nested"]["token"] == "[redacted]"
    assert redacted["nested"]["authorization"] == "[redacted]"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["source_url"] == "[redacted]"


def test_weighting_blocks_when_critical_check_fails():
    results = [
        _result("provider", status="blocked", criticality="critical", category="provider", summary="Provider down"),
        _result("gpu", status="healthy", criticality="standard", category="runtime"),
        _result("scriptwriter", status="healthy", criticality="optional", category="creative_studio"),
    ]

    summary, categories, explainability = summarize_results(results, "standard")

    assert summary.statusIndicator == "Blocked"
    assert summary.score <= 35
    assert summary.blockedChecks == 1
    assert any(item.category == "provider" and item.blocked == 1 for item in categories)
    assert "provider" in explainability.dominantChecks


def test_store_keeps_latest_twenty_runs(isolated_data_dir):
    for index in range(21):
        store.persist_run(_run(f"run-{index:02d}"))

    rows = store.list_runs(project_id="proj-1", scene_id="scene-1", limit=25)

    assert len(rows) == 20
    assert rows[0].runId == "run-20"
    assert rows[-1].runId == "run-01"


def test_deep_diagnostic_requires_confirmation(client):
    response = client.post("/api/codirector/status/deep-diagnostic", json={"projectId": "proj-1"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CONFIRM_REQUIRED"


def test_status_check_endpoint_returns_run(client, monkeypatch):
    async def _fake_run_status_check(ctx, body, mode="standard"):
        return _run("api-run")

    monkeypatch.setattr("app.codirector.status.router.run_status_check", _fake_run_status_check)
    response = client.post("/api/codirector/status/check", json={"projectId": "proj-1", "sceneId": "scene-1"})

    assert response.status_code == 200
    assert response.json()["runId"] == "api-run"


def test_run_status_check_executes_independent_probes_concurrently(monkeypatch):
    async def _fake_execute_one(ctx, check_id, timeout_seconds):
        await asyncio.sleep(0.05)
        return _result(check_id, status="healthy")

    async def _fake_warm(project_id=None):
        return SimpleNamespace(comfy_health=None, capabilities=None, warm_errors=[], warmed_at="t")

    monkeypatch.setattr(
        runner,
        "selected_definitions",
        lambda mode, check_ids: [SimpleNamespace(id="check-a"), SimpleNamespace(id="check-b")],
    )
    monkeypatch.setattr(runner, "_execute_one", _fake_execute_one)
    monkeypatch.setattr(runner, "persist_run", lambda run: None)
    monkeypatch.setattr(runner, "warm_shared_bundle", _fake_warm)

    started = time.perf_counter()
    run = asyncio.run(
        runner.run_status_check(
            StatusContext(db=None, project_id="proj-1"),  # type: ignore[arg-type]
            StatusCheckRequest(projectId="proj-1"),
        )
    )
    elapsed = time.perf_counter() - started

    assert [result.checkId for result in run.results] == ["check-a", "check-b"]
    assert elapsed < 0.09


def test_busy_inference_is_not_classified_as_timeout(monkeypatch):
    from app.codirector import inference_activity
    from app.codirector.status import probe_context

    async def _hang(_check_id, _ctx):
        await asyncio.sleep(5)

    monkeypatch.setattr("app.codirector.status.runner.run_probe", _hang)
    monkeypatch.setattr(probe_context, "timeout_for_check", lambda check_id, mode="standard": 0.05)
    inference_activity.begin_inference("unit_test")
    try:
        result = asyncio.run(
            runner._execute_one(
                StatusContext(db=None, project_id="proj-1"),  # type: ignore[arg-type]
                "codirector.provider",
                0.05,
            )
        )
    finally:
        inference_activity.end_inference()

    assert result.status == "busy"
    assert result.timedOut is False
    assert "BUSY" in result.summary


def test_timeout_includes_dependency_and_limit(monkeypatch):
    async def _hang(_check_id, _ctx):
        await asyncio.sleep(5)

    monkeypatch.setattr("app.codirector.status.runner.run_probe", _hang)
    result = asyncio.run(
        runner._execute_one(
            StatusContext(db=None),  # type: ignore[arg-type]
            "comfy.health",
            0.05,
        )
    )
    assert result.status == "timed_out"
    assert result.timedOut is True
    assert result.timeoutMs == 50
    assert result.awaitedDependency
    assert "Last verified healthy" in result.message


def test_scenecraft_not_in_status_registry():
    from app.codirector.status.registry import registry_definitions
    from app.capabilities.registry import CAPABILITIES

    checks = registry_definitions()
    assert all("scenecraft" not in item.id.lower() and "scenecraft" not in item.title.lower() for item in checks)
    assert all("scenecraft" not in item.id.lower() for item in CAPABILITIES)
