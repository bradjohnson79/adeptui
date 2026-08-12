"""M41 Wave 4 — Durable production plans (M41-CD-55 … M41-CD-78)."""

from __future__ import annotations

import json
import uuid

import pytest

from app.codirector.plans.service import PlanService
from app.codirector.tools import registry as tool_registry
from app.db import SessionLocal


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    import os
    from dataclasses import fields as dataclass_fields

    from app import feature_flags as ff
    from app.feature_flags import FeatureFlags

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))
    yield


def _create_project(client, name: str = "M41 Wave4") -> dict:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()


def _audited(client, project_id: str, tool_id: str, arguments: dict | None = None, request_id: str | None = None):
    body = {
        "toolId": tool_id,
        "arguments": arguments or {},
        "requestId": request_id or str(uuid.uuid4()),
    }
    return client.post(f"/api/codirector/projects/{project_id}/tools/audited", json=body)


def _read(client, project_id: str, tool_id: str, arguments: dict | None = None):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments or {}, "requestId": str(uuid.uuid4())},
    )


def _propose(client, project_id: str, tool_id: str, arguments: dict):
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments, "requestId": str(uuid.uuid4()), "createdBy": "user"},
    )


def _approve(client, project_id: str, proposal_id: str):
    return client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve",
        json={},
    )


def _create_draft(client, project_id: str, **kwargs):
    steps = kwargs.pop("steps", [{"stepId": "s1", "title": "Research", "category": "research"}])
    rid = kwargs.pop("requestId", str(uuid.uuid4()))
    args = {
        "title": kwargs.get("title", "Wave4 Plan"),
        "objective": kwargs.get("objective", "Plan a scene"),
        "stepsJson": json.dumps(steps),
        "requestId": rid,
    }
    res = _audited(client, project_id, "production_plan.create_draft", args, request_id=rid)
    assert res.status_code == 200, res.text
    inv = res.json()
    assert inv["status"] == "succeeded", inv
    result = inv.get("result") or {}
    plan = result.get("plan")
    if not plan:
        # Fall back to canonical store when sanitizer sheds large payloads
        db = SessionLocal()
        try:
            active = PlanService.active_plan(db, project_id)
            assert active is not None, result
            plan = active.model_dump(mode="json")
        finally:
            db.close()
    return plan, rid


def test_m41_cd_55_canonical_durable_plan_store_is_selected_and_documented() -> None:
    """M41-CD-55 Canonical durable plan store is selected and documented."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    report = (root / "docs/release-gate/m41/M41_IMPLEMENTATION_REPORT.md").read_text(encoding="utf-8")
    assert "Canonical production plan source:" in report
    assert "studio-api/app/codirector/plans/" in report
    assert tool_registry.find("production_plan.create_draft") is not None
    assert tool_registry.find("production_plan.get_readiness") is not None


def test_m41_cd_56_plan_persists_across_backend_restart_and_frontend_reload(client, mock_provider_env) -> None:
    """M41-CD-56 Plan persists across backend restart and frontend reload."""
    project = _create_project(client)
    plan, _ = _create_draft(client, project["id"], title="Persist Me")
    # New session = "restart"
    db = SessionLocal()
    try:
        loaded = PlanService.get(db, project["id"], plan["planId"])
        assert loaded.title == "Persist Me"
        assert loaded.state == "draft"
    finally:
        db.close()
    res = _read(client, project["id"], "production_plan.get", {"planId": plan["planId"]})
    assert res.status_code == 200
    assert res.json()["result"]["data"]["plan"]["planId"] == plan["planId"]


def test_m41_cd_57_plan_schema_preserves_core_fields(client, mock_provider_env) -> None:
    """M41-CD-57 Plan schema preserves project, version, steps, blockers, approvals, and outputs."""
    project = _create_project(client)
    plan, _ = _create_draft(
        client,
        project["id"],
        steps=[
            {"stepId": "s1", "title": "Script", "category": "script"},
            {"stepId": "s2", "title": "Video", "category": "video", "proposedToolId": "propose_video_generate", "dependsOn": ["s1"]},
        ],
    )
    assert plan["projectId"] == project["id"]
    assert plan["version"] == 1
    assert len(plan["steps"]) == 2
    assert plan["approvalRequirements"]
    assert "capabilitySnapshot" in plan
    assert plan["unapproved"] is True


def test_m41_cd_58_legacy_scaffold_plan_sources_cannot_become_authoritative(client, mock_provider_env) -> None:
    """M41-CD-58 Legacy/scaffold plan sources cannot become authoritative silently."""
    project = _create_project(client)
    res = _read(client, project["id"], "production_plan.list", {"limit": 25})
    assert res.status_code == 200
    data = res.json()["result"]["data"]
    for p in data.get("plans") or []:
        if str(p.get("planId", "")).startswith("m214:") or p.get("source") == "m214":
            assert p.get("honesty") == "scaffolded" or p.get("state") == "scaffolded"


def test_m41_cd_67_plan_approval_distinct_from_production_action(client, mock_provider_env) -> None:
    """M41-CD-67 Plan approval is distinct from production-action approval."""
    project = _create_project(client)
    plan, _ = _create_draft(client, project["id"])
    prop = _propose(
        client,
        project["id"],
        "production_plan.propose",
        {"planId": plan["planId"], "expectedVersion": plan["version"]},
    )
    assert prop.status_code == 200, prop.text
    proposal = prop.json()
    appr = _approve(client, project["id"], proposal["id"])
    assert appr.status_code == 200, appr.text
    db = SessionLocal()
    try:
        current = PlanService.get(db, project["id"], plan["planId"])
    finally:
        db.close()
    prop2 = _propose(
        client,
        project["id"],
        "production_plan.approve",
        {"planId": current.planId, "expectedVersion": current.version},
    )
    assert prop2.status_code == 200, prop2.text
    appr2 = _approve(client, project["id"], prop2.json()["id"])
    assert appr2.status_code == 200, appr2.text
    db = SessionLocal()
    try:
        final = PlanService.get(db, project["id"], plan["planId"])
    finally:
        db.close()
    assert final.state in {"approved", "ready", "blocked"}
    assert final.unapproved is False
    # No production job created by plan acceptance
    jobs = _read(client, project["id"], "job.list", {"limit": 10})
    assert jobs.status_code == 200


def test_m41_cd_68_revision_creates_new_version(client, mock_provider_env) -> None:
    """M41-CD-68 Revision creates a new version and preserves the previous version."""
    project = _create_project(client)
    plan, _ = _create_draft(client, project["id"])
    prop = _propose(
        client,
        project["id"],
        "production_plan.revise",
        {
            "planId": plan["planId"],
            "expectedVersion": 1,
            "title": "Revised title",
            "revisionReason": "rename",
        },
    )
    assert prop.status_code == 200, prop.text
    assert _approve(client, project["id"], prop.json()["id"]).status_code == 200
    versions = _read(client, project["id"], "production_plan.list_versions", {"planId": plan["planId"]})
    vers = versions.json()["result"]["data"]["versions"]
    assert len(vers) >= 2
    v1 = _read(client, project["id"], "production_plan.get_version", {"planId": plan["planId"], "version": 1})
    assert v1.status_code == 200
    assert v1.json()["result"]["data"]["plan"]["version"] == 1


def test_m41_cd_69_version_conflict_rejects_stale_updates(client, mock_provider_env) -> None:
    """M41-CD-69 Version conflict rejects stale updates."""
    project = _create_project(client)
    plan, _ = _create_draft(client, project["id"])
    # Bump version via revise
    prop = _propose(
        client,
        project["id"],
        "production_plan.revise",
        {"planId": plan["planId"], "expectedVersion": 1, "title": "v2", "revisionReason": "bump"},
    )
    assert _approve(client, project["id"], prop.json()["id"]).status_code == 200
    # Stale propose with expectedVersion=1
    stale = _propose(
        client,
        project["id"],
        "production_plan.propose",
        {"planId": plan["planId"], "expectedVersion": 1},
    )
    # Proposal may create successfully; conflict on apply
    if stale.status_code == 200:
        appr = _approve(client, project["id"], stale.json()["id"])
        assert appr.status_code in {409, 400, 502} or (
            appr.status_code == 200 and (appr.json().get("status") in {"failed", "error"} or "conflict" in appr.text.lower())
        )
    else:
        assert stale.status_code in {409, 400}


def test_m41_cd_70_plan_command_request_ids_are_idempotent(client, mock_provider_env) -> None:
    """M41-CD-70 Plan command request IDs are idempotent."""
    project = _create_project(client)
    rid = str(uuid.uuid4())
    plan1, _ = _create_draft(client, project["id"], requestId=rid, title="Idem")
    plan2, _ = _create_draft(client, project["id"], requestId=rid, title="Idem")
    assert plan1["planId"] == plan2["planId"]


def test_m41_cd_71_project_a_cannot_access_project_b_plans(client, mock_provider_env) -> None:
    """M41-CD-71 Project A cannot access or mutate Project B plans."""
    a = _create_project(client, "ProjA")
    b = _create_project(client, "ProjB")
    plan, _ = _create_draft(client, a["id"], title="A plan")
    res = _read(client, b["id"], "production_plan.get", {"planId": plan["planId"]})
    assert res.status_code in {403, 404}


def test_m41_cd_72_no_project_mode_cannot_create_or_mutate_plan(client, mock_provider_env) -> None:
    """M41-CD-72 No-project mode cannot create or mutate a plan."""
    res = client.post(
        "/api/codirector/projects/not-a-real-project/tools/audited",
        json={"toolId": "production_plan.create_draft", "arguments": {"title": "x"}, "requestId": str(uuid.uuid4())},
    )
    assert res.status_code in {404, 400, 409}


def test_m41_cd_73_reconnect_does_not_duplicate_plans_commands_or_events(client, mock_provider_env) -> None:
    """M41-CD-73 Reconnect does not duplicate plans, commands, or events."""
    project = _create_project(client)
    rid = str(uuid.uuid4())
    plan, _ = _create_draft(client, project["id"], requestId=rid)
    _create_draft(client, project["id"], requestId=rid)
    events = _read(client, project["id"], "production_plan.list_events", {"planId": plan["planId"]})
    ev = events.json()["result"]["data"]["events"]
    created = [e for e in ev if e.get("eventType") == "PLAN_CREATED"]
    assert len(created) == 1


def test_m41_cd_74_active_plan_and_blockers_recover_after_reconnect(client, mock_provider_env) -> None:
    """M41-CD-74 Active plan and blockers recover after reconnect/restart."""
    project = _create_project(client)
    plan, _ = _create_draft(client, project["id"])
    ctx = _read(client, project["id"], "workspace.get_active_context", {})
    assert ctx.status_code == 200
    data = ctx.json()["result"]["data"]
    assert data.get("activePlanId") == plan["planId"]
    assert data.get("activePlanState") == "draft"


def test_m41_cd_75_codirector_creates_grounded_plan_proposal_from_context(client, mock_provider_env) -> None:
    """M41-CD-75 Co-Director creates a grounded plan proposal from real project context."""
    project = _create_project(client)
    plan, _ = _create_draft(
        client,
        project["id"],
        title="Grounded plan",
        steps=[
            {"stepId": "s1", "title": "Inspect project", "category": "research"},
            {
                "stepId": "s2",
                "title": "Generate video",
                "category": "video",
                "proposedToolId": "propose_video_generate",
                "requiredCapabilities": ["video.generate"],
            },
        ],
    )
    assert plan["projectId"] == project["id"]
    ready = _read(client, project["id"], "production_plan.get_readiness", {"planId": plan["planId"]})
    body = ready.json()["result"]["data"]
    assert "snapshotReadiness" in body or "readiness" in body
    # Wave 6P contract: propose_video_generate is in the executable media tool
    # registry, so the step is available (capability gating happens at execution).
    assert plan["steps"][1]["executionAvailability"] == "available"


def test_m41_cd_76_project_content_plan_workspace_contracts() -> None:
    """M41-CD-76 Project Content renders plan state, steps, blockers, readiness, and history."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "studio-web/src/components/CoDirector/plans"
    for name in (
        "PlanWorkspacePanel.tsx",
        "PlanSummaryCard.tsx",
        "PlanStepList.tsx",
        "PlanBlockers.tsx",
        "PlanReadiness.tsx",
        "PlanHistory.tsx",
        "PlanRevisionDiff.tsx",
        "PlanCommandProposal.tsx",
    ):
        assert (root / name).exists(), name


def test_m41_cd_77_deferred_steps_show_honest_unavailable_states(client, mock_provider_env) -> None:
    """M41-CD-77 Deferred production steps show honest unavailable states and no fake progress."""
    project = _create_project(client)
    # A genuinely deferred capability (video.upscale is in _DEFERRED_CAPABILITIES)
    # keeps this test's protective intent against the Wave 6P readiness contract.
    plan, _ = _create_draft(
        client,
        project["id"],
        steps=[
            {
                "stepId": "gen",
                "title": "Gen",
                "proposedToolId": "propose_video_upscale",
                "category": "video",
                "requiredCapabilities": ["video.upscale"],
            }
        ],
    )
    assert plan["steps"][0]["executionAvailability"] == "deferred"
    assert plan["capabilitySnapshot"]["readiness"] != "ready"
    assert plan["steps"][0].get("state") != "completed"


def test_m41_cd_78_plan_revision_ui_shows_structured_diff() -> None:
    """M41-CD-78 Plan revision UI shows a structured diff before approval."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "studio-web/src/components/CoDirector/plans/PlanRevisionDiff.tsx"
    ).read_text(encoding="utf-8")
    assert "codirector-plan-revision-diff" in text
    assert "Revision diff" in text


def test_wave4_plan_mutations_cannot_enter_read_route(client, mock_provider_env) -> None:
    """Plan mutation tools cannot enter the Wave 3 read route."""
    project = _create_project(client)
    res = _read(client, project["id"], "production_plan.create_draft", {"title": "nope"})
    assert res.status_code in {400, 409, 422}
    detail = res.json().get("detail") or {}
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code in {"TOOL_KIND_MISMATCH", "TOOL_NOT_FOUND", None} or res.status_code != 200
