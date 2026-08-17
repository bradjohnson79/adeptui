"""CDX-084 — TOOL-kind capability approval bridge (execution/approval path).

A TOOL-kind capability with a non-DIRECT approval policy (e.g.
`script.propose_edit`, NEEDS_CHOICE) must COMPLETE after user confirmation
instead of erroring:
- deterministic dispatch creates a durable Proposal (ProposalService) and
  returns a PREVIEW plan carrying `proposal_id`;
- the approve endpoint (and the chat confirmation path) execute it through
  ProposalService.approve -> ToolExecutionService.execute_approved_proposal;
- CAPABILITY_HANDLER approval behavior is unchanged.

TESTS ONLY. No app/ source is modified here.
"""

from __future__ import annotations

import asyncio
import json

import pytest


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


@pytest.fixture()
def db():
    from app.db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _create_project(client, name: str = "Tool Approval Bridge") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200
    return res.json()["id"]


def _mk_script_doc(client, project_id: str) -> str:
    """Create the canonical script document (CDX-054: GET no longer creates)."""
    created = client.post(f"/api/projects/{project_id}/scriptwriter/documents")
    assert created.status_code == 200, created.text
    return created.json()["document"]["id"]


def _dispatch(client, project_id: str, capability: str, *, context: dict | None = None, pre_approved: bool = False) -> dict:
    body: dict = {"capability": capability, "context": context or {}, "pre_approved": pre_approved}
    res = client.post(f"/api/codirector/projects/{project_id}/executions", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _approve(client, project_id: str, execution_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/executions/{execution_id}/approve")


def _proposal_row(db, proposal_id: str):
    from app.db import CoDirectorProposal

    return db.get(CoDirectorProposal, proposal_id)


TOOL_PARAMS = {
    "documentId": "doc-placeholder",
    "type": "action",
    "text": "The rain fell on the empty street.",
}


def test_dispatch_creates_proposal_and_approve_completes(client, db, mock_provider_env):
    """Spec §50: a NEEDS_CHOICE TOOL capability bridges to ProposalService.

    dispatch -> PREVIEW with proposal_id; approve endpoint executes the
    proposal through the approved tool path and the plan completes.
    """
    project_id = _create_project(client)
    doc_id = _mk_script_doc(client, project_id)
    params = {**TOOL_PARAMS, "documentId": doc_id}

    plan = _dispatch(client, project_id, "script.propose_edit", context={"tool_params": params})
    assert plan["status"] == "preview"
    assert plan["error"] == "APPROVAL_REQUIRED"
    assert plan["proposal_id"], "dispatch must record a proposal id for TOOL-kind capabilities"

    row = _proposal_row(db, plan["proposal_id"])
    assert row is not None, "a Proposal row must exist after dispatch"
    assert row.status == "pending"
    assert row.proposal_type == "tool_call"
    payload = json.loads(row.payload_json)
    assert payload["toolId"] == "script.propose_insert"
    assert payload["arguments"]["documentId"] == doc_id

    res = _approve(client, project_id, plan["execution_id"])
    assert res.status_code == 200, res.text
    approved = res.json()
    assert approved["status"] == "completed", approved.get("error")
    assert approved["child_jobs"][0]["status"] == "completed"

    # The approval ran in the app's session — expire the cached row so the
    # assert reads the committed state.
    row = _proposal_row(db, plan["proposal_id"])
    db.expire(row)
    assert row.status == "completed"

    # The mutation was really applied through the approved path.
    body = client.get(f"/api/projects/{project_id}/scriptwriter").json()
    texts = [e["text"] for e in body["document"]["elements"]]
    assert any("The rain fell" in t for t in texts), texts


def test_chat_confirmation_path_approves_proposal(client, db, mock_provider_env):
    """Spec §4 + §35: "yes, proceed" on a pending TOOL execution approves the
    proposal instead of re-dispatching into "requires an approved proposal"."""
    from app.codirector.execution.pack_store import load_pack
    from app.codirector.execution.pending_store import PendingExecution, save_pending
    from app.codirector.service import _handle_pending_execution_confirmation

    project_id = _create_project(client)
    doc_id = _mk_script_doc(client, project_id)
    params = {**TOOL_PARAMS, "documentId": doc_id}

    plan = _dispatch(client, project_id, "script.propose_edit", context={"tool_params": params})
    proposal_id = plan["proposal_id"]
    assert proposal_id

    pending = PendingExecution(
        execution_id=plan["execution_id"],
        capability="script.propose_edit",
        project_id=project_id,
        intent="EXECUTION",
        unified_intent={
            "intent": "EXECUTION",
            "capability": "script.propose_edit",
            "confidence": 0.9,
            "dispatch": "DETERMINISTIC",
            "classifier_source": "deterministic",
        },
        resolved_context={"tool_params": params},
        confirmation_required=True,
        state="AWAITING_CONFIRMATION",
    )
    save_pending(db, project_id, pending)

    handled, events = asyncio.run(
        _handle_pending_execution_confirmation(db, project_id, "req-cdx084", "yes, proceed")
    )
    assert handled is True
    assert any(e.get("type") == "execution_status" for e in events)

    pack = load_pack(db, project_id, plan["execution_id"])
    assert pack is not None
    assert pack.status.value == "completed", pack.error
    assert _proposal_row(db, proposal_id).status == "completed"

    body = client.get(f"/api/projects/{project_id}/scriptwriter").json()
    texts = [e["text"] for e in body["document"]["elements"]]
    assert any("The rain fell" in t for t in texts), texts


def test_capability_handler_approval_path_unchanged(client, mock_provider_env, monkeypatch):
    """CAPABILITY_HANDLER (storyboard.generate, NEEDS_APPROVAL) keeps its
    plan_only -> PREVIEW -> handler approval flow; it is NOT bridged to
    ProposalService and no proposal row is created."""
    project_id = _create_project(client)

    plan = _dispatch(
        client,
        project_id,
        "storyboard.generate",
        context={"count": 2, "user_instructions": "two shots"},
    )
    assert plan["status"] == "preview"
    assert plan["error"] == "APPROVAL_REQUIRED"
    assert plan["proposal_id"] is None, "CAPABILITY_HANDLER must not be bridged to proposals"
    assert plan["plan_data"], "plan_only must produce a shot plan"

    # Approve: the handler branch must run (patched to avoid real GPU jobs) and
    # must NOT hit the old "non-capability handler" rejection.
    from app.codirector.execution import dispatcher as dispatch_mod

    def fake_handle(**kwargs):
        return {
            "child_jobs": [{"job_id": "job-1", "status": "queued", "label": "Shot 1", "child_index": 0}],
            "planned_steps": [],
            "surface_type": "storyboard_generation",
        }

    monkeypatch.setattr(dispatch_mod, "_resolve_handler", lambda cap_id: fake_handle)
    res = _approve(client, project_id, plan["execution_id"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "queued"
    # Unchanged CAPABILITY_HANDLER behavior: the handler branch runs and the
    # plan leaves PREVIEW (the stale APPROVAL_REQUIRED error text is retained,
    # exactly as before CDX-084 — the old hard rejection would have kept the
    # plan in PREVIEW with "APPROVE_FAILED: non-capability handler").
    assert body["error"] != "APPROVE_FAILED: non-capability handler"
    assert body["child_jobs"][0]["job_id"] == "job-1"


def test_pre_approved_tool_dispatch_executes_through_approved_path(client, db, mock_provider_env):
    """pre_approved=True still goes through the proposal + approval machinery
    so the decision stays in the audit ledger (never an un-audited apply)."""
    from app.codirector.bible.proposals import ProposalService
    from app.db import CoDirectorToolInvocation

    project_id = _create_project(client)
    doc_id = _mk_script_doc(client, project_id)
    params = {**TOOL_PARAMS, "documentId": doc_id}

    plan = _dispatch(
        client,
        project_id,
        "script.propose_edit",
        context={"tool_params": params},
        pre_approved=True,
    )
    assert plan["status"] == "completed", plan.get("error")
    proposal_id = plan["proposal_id"]
    assert proposal_id
    assert _proposal_row(db, proposal_id).status == "completed"

    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    applied = [i for i in ledger if i.get("proposalId") == proposal_id]
    assert applied, "the approved execution must write an invocation ledger row"
    assert applied[0]["status"] == "succeeded"
    assert applied[0]["toolId"] == "script.propose_insert"

    # The proposal id is also reachable through the receipt surface.
    receipt = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/receipt")
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "success"


def test_direct_read_tool_dispatch_completes(client, db, mock_provider_env):
    """CDX-084 regression: DIRECT TOOL read capabilities (script.inspect)
    execute through execute_read and complete instead of erroring."""
    project_id = _create_project(client)
    doc_id = _mk_script_doc(client, project_id)

    plan = _dispatch(client, project_id, "script.read", context={"tool_params": {"documentId": doc_id}})
    assert plan["status"] == "completed", plan.get("error")
    assert plan["child_jobs"][0]["status"] == "completed"
    assert plan["proposal_id"] is None, "DIRECT capabilities need no proposal"