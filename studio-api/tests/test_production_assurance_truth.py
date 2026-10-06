"""Production Assurance truth: fresh registry, semantic severity, no false-green."""

from __future__ import annotations

from app.capabilities.models import CapabilityBlockerOut, CapabilityStatus
from app.codirector.status.registry import StatusContext, _probe_capabilities
from app.codirector.status.types import HealthCheckResult
from app.codirector.status.weighting import band_for_score, summarize_results
from app.readiness.v11_policy import POLICY_VERSION, SCORE_SEMANTICS, ReadinessClass


def _result(
    check_id: str,
    *,
    status: str,
    criticality: str = "standard",
    category: str = "core",
    summary: str = "ok",
    readiness_class: str | None = None,
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
        checkedAt="2026-09-04T00:00:00+00:00",
        readinessClass=readiness_class,
    )


def _blocker(**kwargs) -> CapabilityBlockerOut:
    payload = {
        "capabilityId": "codirector.video_intelligence.ready",
        "displayName": "Co-Director Temporal Continuity",
        "subsystem": "codirector",
        "status": CapabilityStatus.BLOCKED,
        "reasonCode": "MODEL_MISSING",
        "message": "Not installed: VideoChat3 4B.",
        "recommendedAction": "open_source_manager",
        "componentIds": ["videochat3_4b"],
        "readinessClass": "advisory_review_degraded",
        "v11Requirement": "continuity_review",
        "workflowScope": "codirector.temporal_continuity",
        "severity": "advisory",
        "productionEffect": "Temporal Continuity review is degraded. Generation still works.",
    }
    payload.update(kwargs)
    return CapabilityBlockerOut(**payload)


def test_owner_band_labels_do_not_change_score_thresholds() -> None:
    assert band_for_score(20, "Blocked") == "Blocked"
    assert band_for_score(84, "Degraded") == "Workflow Degraded"
    assert band_for_score(94, "Operational") == "Advisory"
    assert band_for_score(95, "Operational") == "Operational"
    assert band_for_score(100, "Operational") == "Operational"


def test_advisory_registry_blocker_does_not_cap_at_84_or_100() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "capabilities.registry",
            status="warning",
            criticality="high",
            summary="Temporal Continuity review is degraded",
            readiness_class=ReadinessClass.ADVISORY_REVIEW_DEGRADED.value,
        ),
        _result("comfy.health", status="healthy", criticality="high"),
    ]
    summary, _categories, explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.score <= 94
    assert summary.score != 100
    assert summary.score >= 85
    assert summary.band == "Advisory"
    assert summary.scoreSemantics == SCORE_SEMANTICS
    assert summary.readinessPolicyVersion == POLICY_VERSION
    assert any("Advisory" in line or "review" in line.lower() for line in explain.reasons)


def test_optional_leftover_does_not_cap_excellent() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "runtime.authority",
            status="warning",
            criticality="optional",
            readiness_class=ReadinessClass.OPTIONAL.value,
            summary="Leftover scheduled-task name",
        ),
        _result("comfy.health", status="healthy", criticality="high"),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.score >= 95
    assert summary.band == "Operational"
    # OPTIONAL leftovers never own the warning/blocked tallies.
    assert summary.warningChecks == 0
    assert summary.blockedChecks == 0


def test_optional_not_configured_never_warns_or_caps() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "references.ic_lora.ready",
            status="not_configured",
            criticality="optional",
            readiness_class=ReadinessClass.OPTIONAL.value,
            summary="Ingredients IC-LoRA weights are not installed",
        ),
        _result("comfy.health", status="healthy", criticality="high"),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.warningChecks == 0
    assert summary.blockedChecks == 0
    # Frozen 0.2 optional weight still applies arithmetically — (100*1.0 + 38*0.2
    # + 100*0.8) / 2.0 = 93.8 → 94 — but no 35/84/94 cap is applied.
    assert summary.score == 94


def test_optional_blocking_status_never_enters_issue_lists() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "runtime.authority",
            status="blocked",
            criticality="optional",
            readiness_class=ReadinessClass.OPTIONAL.value,
            summary="Leftover scheduled-task name",
        ),
        _result("comfy.health", status="healthy", criticality="high"),
    ]
    summary, _categories, explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.warningChecks == 0
    assert summary.blockedChecks == 0
    assert explain.blockers == []
    assert explain.warnings == []
    assert explain.dominantChecks == []
    # Arithmetic only: (100*1.0 + 20*0.2 + 100*0.8) / 2.0 = 92. No Degraded 84 cap.
    assert summary.score == 92


def test_timeline_propose_is_optional_policy() -> None:
    """Consumer audit: only the menu-hidden legacy Generate Timeline panel calls
    POST /api/projects/{projectId}/timeline/propose. Co-Director production chat/tools
    and Timeline H3 generate do not, so the capability must not own Status warnings."""
    from app.readiness.v11_policy import V11Requirement, classify_capability

    assignment = classify_capability("project.timeline.propose")
    assert assignment.readiness_class == ReadinessClass.OPTIONAL
    assert assignment.v11_requirement == V11Requirement.OPTIONAL


def test_temporal_continuity_packet_check_is_advisory_continuity() -> None:
    """The bound-scene handoff-packet check must warn (advisory) without Blocking 35,
    and must never treat missing InternVideo3 (optional deep-review) as a warning."""
    from app.readiness.v11_policy import V11Requirement, classify_status_check

    for check_id in ("codirector.temporal_continuity.packet", "codirector.temporal_continuity"):
        assignment = classify_status_check(check_id)
        assert assignment is not None, check_id
        assert assignment.readiness_class == ReadinessClass.ADVISORY_REVIEW_DEGRADED
        assert assignment.v11_requirement == V11Requirement.CONTINUITY_REVIEW

    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "codirector.temporal_continuity.packet",
            status="warning",
            criticality="high",
            summary="Latest Temporal Continuity handoff packet is unavailable for the bound scene",
            readiness_class=ReadinessClass.ADVISORY_REVIEW_DEGRADED.value,
        ),
        _result("comfy.health", status="healthy", criticality="high"),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.blockedChecks == 0
    assert summary.warningChecks == 1
    assert 85 <= summary.score <= 94
    assert summary.band == "Advisory"


def test_registry_timeout_fallback_is_advisory_not_84() -> None:
    from app.readiness.v11_policy import classify_status_check

    assignment = classify_status_check("capabilities.registry")
    assert assignment is not None
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "capabilities.registry",
            status="timed_out",
            criticality="high",
            readiness_class=assignment.readiness_class.value,
            summary="Capability Registry timed out",
        ),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert 85 <= summary.score <= 94
    assert summary.band == "Advisory"


def test_production_critical_registry_blocker_blocks() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "comfy.health",
            status="offline",
            criticality="high",
            summary="ComfyUI is offline",
            readiness_class=ReadinessClass.PRODUCTION_CRITICAL.value,
        ),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Blocked"
    assert summary.score <= 35
    assert summary.band == "Blocked"


def test_production_probe_timeout_is_not_degraded_84() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "comfy.health",
            status="timed_out",
            criticality="high",
            summary="ComfyUI Runtime timed out",
            readiness_class=ReadinessClass.PRODUCTION_CRITICAL.value,
        ),
        _result(
            "capabilities.registry",
            status="warning",
            criticality="high",
            readiness_class=ReadinessClass.ADVISORY_REVIEW_DEGRADED.value,
        ),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.score <= 94
    assert summary.score >= 85
    assert summary.band == "Advisory"


def test_workflow_degraded_caps_at_84() -> None:
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "voice_runtime.readiness",
            status="not_installed",
            criticality="high",
            readiness_class=ReadinessClass.WORKFLOW_DEGRADED.value,
        ),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Degraded"
    assert summary.score <= 84
    assert summary.band == "Workflow Degraded"


def test_critical_check_without_readiness_class_still_blocks() -> None:
    results = [
        _result("provider", status="blocked", criticality="critical", category="provider", summary="Provider down"),
        _result("gpu", status="healthy", criticality="standard", category="runtime"),
    ]
    summary, _categories, explainability = summarize_results(results, "standard")
    assert summary.statusIndicator == "Blocked"
    assert summary.score <= 35
    assert "provider" in explainability.dominantChecks


def test_probe_capabilities_classifies_advisory_not_blocked(monkeypatch) -> None:
    import asyncio

    advisory = _blocker()

    class Snapshot:
        blockers = [advisory]
        callable = ["project.read"]
        readinessTotal = 10
        snapshotIncomplete = False

        def model_dump(self, mode="json"):
            return {"blockers": [advisory.model_dump(mode="json")], "callable": self.callable}

    async def _fake_get(*_args, **kwargs):
        assert kwargs.get("force") is True
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "warning"
    assert payload["readinessClass"] == "advisory_review_degraded"
    assert not payload["blockers"]
    assert payload["warnings"]
    assert payload["details"]["advisoryBlockerDetails"][0]["capabilityId"] == "codirector.video_intelligence.ready"


def test_probe_capabilities_production_blocker_is_blocked(monkeypatch) -> None:
    import asyncio

    production = _blocker(
        capabilityId="comfyui.health",
        displayName="ComfyUI reachability",
        subsystem="comfyui",
        readinessClass="production_critical",
        v11Requirement="required",
        workflowScope="local.runtime",
        severity="high",
        productionEffect="Local picture/video runtime is unreachable.",
        message="ComfyUI is offline.",
    )

    class Snapshot:
        blockers = [production]
        callable = []
        readinessTotal = 10
        snapshotIncomplete = False

        def model_dump(self, mode="json"):
            return {"blockers": [production.model_dump(mode="json")]}

    async def _fake_get(*_args, **kwargs):
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "blocked"
    assert payload["readinessClass"] == "production_critical"


def test_probe_capabilities_optional_blockers_do_not_warn(monkeypatch) -> None:
    """OPTIONAL leftovers (IC-LoRA, InternVideo3 deep-review) stay visible on the
    snapshot but must not appear as production/workflow/advisory blockers and must
    not turn the registry Status check into a warning."""
    import asyncio

    ic_lora = _blocker(
        capabilityId="references.ic_lora.ready",
        displayName="Ingredients IC-LoRA",
        subsystem="references",
        status=CapabilityStatus.NOT_CONFIGURED,
        reasonCode="MODEL_MISSING",
        message="Ingredients IC-LoRA weights are not installed.",
        componentIds=["ltx_ic_lora"],
        readinessClass="optional",
        v11Requirement="optional",
        workflowScope="references.ic_lora",
        severity="optional",
        productionEffect="Ingredients IC-LoRA is an optional LTX 2.3 path. Timeline generation does not require it.",
    )
    internvideo = _blocker(
        capabilityId="codirector.video_intelligence.deep_review",
        displayName="InternVideo3 deep review",
        subsystem="codirector",
        status=CapabilityStatus.NOT_CONFIGURED,
        reasonCode="MODEL_MISSING",
        message="InternVideo3 8B optional deep-review weights are not installed.",
        componentIds=["internvideo3_8b"],
        readinessClass="optional",
        v11Requirement="optional",
        workflowScope="codirector.temporal_continuity",
        severity="optional",
        productionEffect="Optional deep review is unavailable; VideoChat3 Temporal Continuity still runs.",
    )

    class Snapshot:
        blockers = [ic_lora, internvideo]
        callable = ["project.read"]
        readinessTotal = 10
        snapshotIncomplete = False

        def model_dump(self, mode="json"):
            return {"blockers": [item.model_dump(mode="json") for item in self.blockers]}

    async def _fake_get(*_args, **kwargs):
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "healthy"
    assert payload["details"]["productionBlockerDetails"] == []
    assert payload["details"]["workflowBlockerDetails"] == []
    assert payload["details"]["advisoryBlockerDetails"] == []
    # OPTIONAL rows stay visible on the snapshot for transparency.
    assert len(payload["details"]["blockerDetails"]) == 2

    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "capabilities.registry",
            status=payload["status"],
            criticality="high",
            readiness_class=payload["readinessClass"],
        ),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.warningChecks == 0
    assert summary.blockedChecks == 0


def test_probe_capabilities_surfaces_degraded_advisory(monkeypatch) -> None:
    import asyncio

    from app.capabilities.models import CapabilityOut

    row = CapabilityOut(
        id="codirector.video_intelligence.ready",
        displayName="Co-Director Temporal Continuity",
        subsystem="codirector",
        status=CapabilityStatus.DEGRADED,
        available=True,
        configured=True,
        healthy=False,
        readOnly=True,
        requiresApproval=False,
        lastCheckedAt="2026-09-04T00:00:00Z",
        reasonCode="MODEL_MISSING",
        message="Optional InternVideo3 missing.",
        readinessClass="advisory_review_degraded",
        v11Requirement="continuity_review",
        workflowScope="codirector.temporal_continuity",
        severity="advisory",
        productionEffect="Temporal Continuity review is degraded. Generation still works.",
    )

    class Snapshot:
        blockers = []
        capabilities = [row]
        callable = [row.id]
        readinessTotal = 10
        snapshotIncomplete = False

        def model_dump(self, mode="json"):
            return {"capabilities": [row.model_dump(mode="json")], "blockers": []}

    async def _fake_get(*_args, **kwargs):
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "warning"
    assert payload["readinessClass"] == "advisory_review_degraded"
    assert "Co-Director Temporal Continuity" in payload["warnings"]


def test_probe_capabilities_production_degraded_is_workflow_not_blocked(monkeypatch) -> None:
    import asyncio

    from app.capabilities.models import CapabilityOut

    row = CapabilityOut(
        id="models.video.ready",
        displayName="Local video models",
        subsystem="models",
        status=CapabilityStatus.DEGRADED,
        available=True,
        configured=True,
        healthy=False,
        readOnly=True,
        requiresApproval=False,
        lastCheckedAt="2026-09-04T00:00:00Z",
        reasonCode="DEPENDENCY_DEGRADED",
        message="Required video path is usable with reduced function.",
        readinessClass="production_critical",
        v11Requirement="required",
        workflowScope="video.generate",
        severity="high",
        productionEffect="Required local video weights are missing.",
    )
    advisory = CapabilityOut(
        id="codirector.video_intelligence.ready",
        displayName="Co-Director Temporal Continuity",
        subsystem="codirector",
        status=CapabilityStatus.DEGRADED,
        available=True,
        configured=True,
        healthy=False,
        readOnly=True,
        requiresApproval=False,
        lastCheckedAt="2026-09-04T00:00:00Z",
        reasonCode="MODEL_MISSING",
        message="Optional InternVideo3 missing.",
        readinessClass="advisory_review_degraded",
        v11Requirement="continuity_review",
        workflowScope="codirector.temporal_continuity",
        severity="advisory",
        productionEffect="Temporal Continuity review is degraded. Generation still works.",
    )

    class Snapshot:
        blockers = []
        capabilities = [row, advisory]
        callable = [row.id, advisory.id]
        readinessTotal = 10
        snapshotIncomplete = False

        def model_dump(self, mode="json"):
            return {"capabilities": [item.model_dump(mode="json") for item in self.capabilities], "blockers": []}

    async def _fake_get(*_args, **kwargs):
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "warning"
    assert payload["readinessClass"] == "workflow_degraded"
    assert not payload["blockers"]


def test_probe_capabilities_workflow_degraded_row_is_advisory_not_84(monkeypatch) -> None:
    import asyncio

    from app.capabilities.models import CapabilityOut

    row = CapabilityOut(
        id="project.timeline.propose",
        displayName="Propose scenes from a brief",
        subsystem="project",
        status=CapabilityStatus.DEGRADED,
        available=True,
        configured=True,
        healthy=False,
        readOnly=True,
        requiresApproval=False,
        lastCheckedAt="2026-09-04T00:00:00Z",
        message="Propose 2-8 scenes from a brief.",
        readinessClass="workflow_degraded",
        v11Requirement="workflow",
        workflowScope="timeline.context",
        severity="standard",
        productionEffect="Timeline propose is unavailable.",
    )
    advisory = CapabilityOut(
        id="codirector.video_intelligence.ready",
        displayName="Co-Director Temporal Continuity",
        subsystem="codirector",
        status=CapabilityStatus.DEGRADED,
        available=True,
        configured=True,
        healthy=False,
        readOnly=True,
        requiresApproval=False,
        lastCheckedAt="2026-09-04T00:00:00Z",
        reasonCode="MODEL_MISSING",
        message="Optional InternVideo3 missing.",
        readinessClass="advisory_review_degraded",
        v11Requirement="continuity_review",
        workflowScope="codirector.temporal_continuity",
        severity="advisory",
        productionEffect="Temporal Continuity review is degraded. Generation still works.",
    )

    class Snapshot:
        blockers = []
        capabilities = [row, advisory]
        callable = [row.id, advisory.id]
        readinessTotal = 10
        snapshotIncomplete = False

        def model_dump(self, mode="json"):
            return {"capabilities": [item.model_dump(mode="json") for item in self.capabilities], "blockers": []}

    async def _fake_get(*_args, **kwargs):
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "warning"
    assert payload["readinessClass"] == "advisory_review_degraded"
    assert "Co-Director Temporal Continuity" in payload["warnings"]
    results = [
        _result("api.health", status="healthy", criticality="critical"),
        _result(
            "capabilities.registry",
            status=payload["status"],
            criticality="high",
            readiness_class=payload["readinessClass"],
        ),
    ]
    summary, _categories, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert 85 <= summary.score <= 94


def test_incomplete_snapshot_is_not_healthy(monkeypatch) -> None:
    import asyncio

    class Snapshot:
        blockers = []
        callable = ["project.read"]
        readinessTotal = 10
        snapshotIncomplete = True

        def model_dump(self, mode="json"):
            return {"probeWarnings": ["setup_status_probe_failed"]}

    async def _fake_get(*_args, **kwargs):
        return Snapshot()

    monkeypatch.setattr("app.capabilities.service.get_capabilities", _fake_get)
    ctx = StatusContext(db=None, force_refresh=True)  # type: ignore[arg-type]
    payload = asyncio.run(_probe_capabilities(ctx))
    assert payload["status"] == "warning"
    assert "incomplete" in payload["summary"].lower()


def test_recheck_request_defaults_force_refresh_false() -> None:
    from app.codirector.status.types import StatusCheckRequest

    body = StatusCheckRequest(projectId="proj-1")
    assert body.forceRefresh is False
    body = StatusCheckRequest(projectId="proj-1", forceRefresh=True)
    assert body.forceRefresh is True


def test_deep_diagnostic_contract_is_read_only() -> None:
    from app.codirector.status import router as status_router

    source = open(status_router.__file__, encoding="utf-8").read()
    assert "restart" not in source.lower() or "Deep Diagnostic" in source
    assert "install" not in source.lower() or "confirm" in source.lower()
    text = source
    assert "run_status_check" in text
    assert "mode=\"deep\"" in text or "mode='deep'" in text or 'mode="deep"' in text


def test_status_registry_includes_creator_path_checks() -> None:
    from app.codirector.status.registry import registry_definitions

    ids = {item.id for item in registry_definitions()}
    assert {
        "create.path",
        "timeline.generator_truth",
        "timeline.context_binding",
        "posecraft.identity_nav",
        "codirector.grounded_routing",
        "runtime.authority",
    }.issubset(ids)


def test_capabilities_snapshot_exposes_readiness_class(client) -> None:
    from app.capabilities import service as capability_service

    capability_service.invalidate_cache()
    res = client.get("/api/capabilities")
    assert res.status_code == 200
    payload = res.json()
    assert payload["readinessPolicyVersion"] == "v1.1"
    row = next(item for item in payload["capabilities"] if item["id"] == "codirector.video_intelligence.ready")
    assert row["readinessClass"] == "advisory_review_degraded"
    assert row["v11Requirement"] == "continuity_review"
    video_blockers = [item for item in payload["blockers"] if item["capabilityId"] == "codirector.video_intelligence.ready"]
    if video_blockers:
        assert video_blockers[0]["readinessClass"] == "advisory_review_degraded"
        assert video_blockers[0]["reasonCode"] in {"MODEL_MISSING", "MODEL_SOURCE_PENDING", "CAPABILITY_PROBE_FAILED"}


def test_retired_video_components_are_not_production_required() -> None:
    from app.capabilities.registry import CAPABILITIES
    from app.readiness.v11_policy import (
        ReadinessClass,
        classify_capability,
    )
    from app.setup.catalog import RETIRED_VIDEO_SETUP_COMPONENT_IDS

    video_ready = next(item for item in CAPABILITIES if item.id == "models.video.ready")
    assert set(video_ready.component_ids) == {
        "ltx_2_5_checkpoint",
        "ltx_2_5_text_encoder",
        "ltx_2_5_video_vae",
    }
    assert not (set(video_ready.component_ids) & RETIRED_VIDEO_SETUP_COMPONENT_IDS)

    ic_lora = classify_capability("references.ic_lora.ready")
    assert ic_lora.readiness_class == ReadinessClass.OPTIONAL
    assert "LTX 2.5" in classify_capability("models.video.ready").production_effect or (
        "MiniMax H3" in classify_capability("models.video.ready").production_effect
    )
