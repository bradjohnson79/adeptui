"""c7 approval/destructive-safety certification for the Co-Director Operational
Integrity Audit.

Covers the approval/persistence surface governed by
``CODIRECTOR_APPROVAL_PERSISTENCE_AUDIT.md`` (phase c7). Tests assert that
meaningful-change previews describe CURRENT vs PROPOSED, that reject preserves
authoritative state byte-identically, that approved replay is argument-pinned
to the ORIGINAL sanitized arguments (tampered approve-time args are ignored),
that destructive tools are proposal-gated (the audited set is exactly the
four documented tools), that the c2 staleness-at-creation signal surfaces when
a pinned base resource moves, and that the schema-version guard rejects
older payloads at approve time.

TESTS ONLY. No app/ source is modified here. Defects are documented in the
return report, not patched in place.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.codirector.errors import CoDirectorError


# --------------------------------------------------------------------------
# Fixtures (mirror the patterns in test_codirector_c2_routing_repairs.py)
# --------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient

    from app.main import app, job_queue
    from app.routers import api

    monkeypatch.setattr(job_queue, "start", lambda: None)
    monkeypatch.setattr(api.job_queue, "enqueue", AsyncMock())

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db() -> Session:
    from app.db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _create_project(client, name: str = "Approval Safety Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200
    return res.json()["id"]


def _scenes(client, project_id: str) -> list[dict]:
    return client.get(f"/api/projects/{project_id}").json()["scenes"]


def _first_scene(client, project_id: str) -> dict:
    scenes = _scenes(client, project_id)
    assert scenes
    return scenes[0]


def _add_scene(client, project_id: str, name: str = "Opening") -> dict:
    res = client.post(
        f"/api/projects/{project_id}/scenes", json={"name": name, "prompt": "Wide establishing shot."}
    )
    assert res.status_code == 200
    return res.json()


def _create_bible(client, project_id: str) -> dict:
    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={}).json()
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"], "summary": preview.get("summary", "")},
    )
    assert res.status_code == 200
    return res.json()


def _propose(client, project_id: str, tool_id: str, **arguments) -> dict:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _ledger(client, project_id: str) -> list[dict]:
    return client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]


# ==========================================================================
# Task B.1 - Meaningful-change preview: CURRENT vs PROPOSED
# ==========================================================================


class TestMeaningfulChangePreview:
    """Representative mutating tools carry a server-built preview (summary/
    lines) describing CURRENT vs PROPOSED where the contract supports it."""

    def test_update_scene_title_preview_shows_current_and_proposed(self, client) -> None:
        project_id = _create_project(client)
        scene = _add_scene(client, project_id, "Working Title")
        proposal = _propose(
            client, project_id, "update_scene_title", sceneId=scene["id"], name="Final Title"
        ).json()
        preview = proposal["toolCall"]["preview"]
        assert preview["summary"]
        assert preview["resourceId"] == scene["id"]
        # The lines explicitly contrast current vs proposed.
        joined = "\n".join(preview["lines"])
        assert "Current title: Working Title" in joined
        assert "New title: Final Title" in joined

    def test_set_scene_prompt_preview_shows_current_and_proposed(self, client) -> None:
        project_id = _create_project(client)
        scene = _add_scene(client, project_id, "Scene A")
        proposal = _propose(
            client, project_id, "set_scene_prompt", sceneId=scene["id"], prompt="Slow dolly through rain."
        ).json()
        preview = proposal["toolCall"]["preview"]
        joined = "\n".join(preview["lines"])
        assert "Current prompt:" in joined
        assert "New prompt:" in joined

    def test_timeline_propose_add_batch_preview_describes_action(self, client) -> None:
        project_id = _create_project(client)
        scene = _first_scene(client, project_id)
        proposal = _propose(
            client, project_id, "timeline.propose_add_batch", sceneId=scene["id"], label="Rooftop Batch"
        ).json()
        preview = proposal["toolCall"]["preview"]
        assert preview["summary"]
        assert "Rooftop Batch" in preview["summary"]
        # Lines describe what the mutation does.
        assert preview["lines"]

    def test_propose_character_update_preview_describes_fields(self, client) -> None:
        project_id = _create_project(client)
        _create_bible(client, project_id)
        proposal = _propose(
            client,
            project_id,
            "propose_character_update",
            entityKey="ava",
            displayName="Ava",
            data={"description": "Protagonist.", "appearanceSummary": "Scar above left eyebrow."},
        ).json()
        preview = proposal["toolCall"]["preview"]
        assert preview["summary"]
        assert preview["resourceKind"] == "bible"
        # The preview lists the fields being updated.
        joined = "\n".join(preview["lines"])
        assert "description" in joined or "appearanceSummary" in joined

    def test_preview_endpoint_returns_stored_preview_not_rederived(self, client) -> None:
        """A tool proposal's preview is the one stored at propose time; the
        preview endpoint reports staleness instead of silently re-deriving
        against a changed world."""
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Previewed").json()
        res = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/preview")
        assert res.status_code == 200
        body = res.json()
        assert body["entityDiff"] == []
        assert body["toolPreview"]["summary"]
        assert body["isStale"] is False


# ==========================================================================
# Task B.2 - Reject preserves original (byte-identical authoritative state)
# ==========================================================================


class TestRejectPreservesOriginal:
    """Rejecting a proposal performs no apply; authoritative state is
    byte-identical to before (reload and compare)."""

    def test_reject_scene_title_change_preserves_original(self, client) -> None:
        project_id = _create_project(client)
        scene = _add_scene(client, project_id, "Original Title")
        before = _scenes(client, project_id)

        proposal = _propose(
            client, project_id, "update_scene_title", sceneId=scene["id"], name="Rejected Title"
        ).json()
        rejected = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/reject",
            json={"note": "nope"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        after = _scenes(client, project_id)
        assert after == before
        assert after[1]["name"] == "Original Title"

    def test_reject_bible_entity_update_preserves_original(self, client) -> None:
        project_id = _create_project(client)
        _create_bible(client, project_id)
        before_bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()

        proposal = _propose(
            client,
            project_id,
            "propose_character_update",
            entityKey="ava",
            displayName="Ava Renamed",
            data={"description": "Tampered."},
        ).json()
        rejected = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/reject", json={}
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        after_bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
        # The current version id and number are unchanged (no new version was
        # created by the reject).
        assert after_bible["currentVersion"]["id"] == before_bible["currentVersion"]["id"]
        assert after_bible["currentVersion"]["versionNumber"] == before_bible["currentVersion"]["versionNumber"]
        # No execution receipt exists for a rejected proposal.
        receipt_res = client.get(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/receipt"
        )
        assert receipt_res.status_code == 404
        assert receipt_res.json()["detail"]["code"] == "RECEIPT_NOT_FOUND"

    def test_reject_creates_no_invocation_ledger_row(self, client) -> None:
        """Reject runs no handler apply, so no mutating invocation row is
        written for the rejected proposal."""
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Never").json()
        client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/reject", json={})
        rows = _ledger(client, project_id)
        assert all(r.get("proposalId") != proposal["id"] for r in rows)
        assert len(_scenes(client, project_id)) == 1


# ==========================================================================
# Task B.3 - Argument-pinned replay: approved mutation matches ORIGINAL args
# ==========================================================================


class TestArgumentPinnedReplay:
    """Approval replays the sanitized arguments stored at proposal time; the
    model gets no second say. Tampered approve-time arguments (if the API
    surface allowed them) are ignored, and the applied mutation matches the
    ORIGINAL sanitized arguments exactly."""

    def test_stored_arguments_are_sanitized_ignoring_unknown_keys(self, client) -> None:
        project_id = _create_project(client)
        res = _propose(
            client,
            project_id,
            "create_scene",
            name="Clean",
            rmRf="/",
            engine="ltx",
        )
        assert res.status_code == 200
        # Unknown keys are dropped; only declared keys survive to the stored
        # payload that approval will replay.
        assert res.json()["toolCall"]["arguments"] == {"name": "Clean", "engine": "ltx"}

    def test_approve_replays_original_sanitized_arguments(self, client) -> None:
        """An unknown key sent at propose time is sanitized away, so approval
        replays only the declared arguments -- the applied scene carries the
        original name and engine, never the dropped key."""
        project_id = _create_project(client)
        proposal = _propose(
            client,
            project_id,
            "create_scene",
            name="Pinned",
            rmRf="/",
            engine="ltx",
        ).json()
        receipt = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert receipt.status_code == 200
        scenes = _scenes(client, project_id)
        created = next(s for s in scenes if s["name"] == "Pinned")
        assert created["name"] == "Pinned"
        # The ledger records the sanitized arguments that were replayed.
        rows = _ledger(client, project_id)
        applied = [r for r in rows if r["proposalId"] == proposal["id"]][0]
        assert applied["arguments"] == {"name": "Pinned", "engine": "ltx"}
        assert "rmRf" not in applied["arguments"]

    def test_approve_endpoint_does_not_accept_override_arguments(self, client) -> None:
        """The approve endpoint body carries only note/decidedBy -- there is
        no field to pass replacement arguments, so approval cannot be steered
        to different arguments than those pinned at propose time."""
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Original").json()
        # Attempt to smuggle replacement arguments through the approve body.
        receipt = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve",
            json={"note": "ok", "decidedBy": "user", "arguments": {"name": "Tampered"}, "toolId": "create_scene"},
        )
        assert receipt.status_code == 200
        # The applied scene name is the ORIGINAL sanitized argument, not the
        # tampered approve-time value.
        scenes = _scenes(client, project_id)
        assert any(s["name"] == "Original" for s in scenes)
        assert not any(s["name"] == "Tampered" for s in scenes)

    def test_approved_execution_uses_proposal_project_id_not_args(self, client) -> None:
        """ctx.project_id is derived from the proposal row, not from model
        args, so a proposal cannot be redirected to another project at apply."""
        project_id = _create_project(client)
        proposal = _propose(
            client,
            project_id,
            "create_scene",
            name="Scoped",
            projectId="other-project-attempt",
        ).json()
        # The unknown projectId arg is sanitized away.
        assert "projectId" not in proposal["toolCall"]["arguments"]
        receipt = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert receipt.status_code == 200
        # The scene was created in the ORIGINAL project, not redirected.
        assert any(s["name"] == "Scoped" for s in _scenes(client, project_id))


# ==========================================================================
# Task B.4 - Destructive operations require approval (audited set = 4 tools)
# ==========================================================================


EXPECTED_AUDITED_MUTATING_TOOLS = {
    "audio.cancel_batch",
    "production_plan.create_draft",
    "minimax_h3.offer_ltx_fallback",
    "minimax_h3.cancel",
}


class TestDestructiveRequiresApproval:
    """Destructive tools (timeline remove_item, batch delete, etc.) must be
    proposal-gated (requires_approval=True in the registry) and must NOT
    execute via execute_audited. The audited set is exactly the four
    documented tools."""

    def test_timeline_remove_item_requires_approval(self) -> None:
        from app.codirector.tools import registry

        definition = registry.get("timeline.remove_item")
        assert definition.kind == "mutating"
        assert definition.requires_approval is True

    def test_timeline_restore_removed_item_requires_approval(self) -> None:
        from app.codirector.tools import registry

        definition = registry.get("timeline.restore_removed_item")
        assert definition.kind == "mutating"
        assert definition.requires_approval is True

    def test_create_scene_requires_approval(self) -> None:
        from app.codirector.tools import registry

        definition = registry.get("create_scene")
        assert definition.kind == "mutating"
        assert definition.requires_approval is True

    def test_propose_character_update_requires_approval(self) -> None:
        from app.codirector.tools import registry

        definition = registry.get("propose_character_update")
        assert definition.kind == "mutating"
        assert definition.requires_approval is True

    def test_audited_set_is_exactly_four_documented_tools(self) -> None:
        from app.codirector.tools import registry

        audited = {
            d.tool_id
            for d in registry.all_definitions()
            if d.kind == "mutating" and d.requires_approval is False
        }
        assert audited == EXPECTED_AUDITED_MUTATING_TOOLS

    def test_execute_audited_refuses_approval_gated_tool(self, client) -> None:
        """A tool that requires approval must NOT execute via the audited
        endpoint -- it raises TOOL_EXECUTION_FAILED (non-recoverable)."""
        project_id = _create_project(client)
        res = client.post(
            f"/api/codirector/projects/{project_id}/tools/audited",
            json={"toolId": "create_scene", "arguments": {"name": "Sneaky"}},
        )
        assert res.status_code == 502
        detail = res.json()["detail"]
        assert detail["code"] == "TOOL_EXECUTION_FAILED"
        assert detail["recoverable"] is False
        # Nothing was created.
        assert len(_scenes(client, project_id)) == 1

    def test_destructive_remove_item_cannot_bypass_proposal(self, client) -> None:
        """timeline.remove_item via the audited endpoint is refused; it must
        go through propose -> approve."""
        project_id = _create_project(client)
        scene = _first_scene(client, project_id)
        res = client.post(
            f"/api/codirector/projects/{project_id}/tools/audited",
            json={
                "toolId": "timeline.remove_item",
                "arguments": {"sceneId": scene["id"], "itemKind": "batchBlock", "itemId": "no-such"},
            },
        )
        assert res.status_code == 502
        assert res.json()["detail"]["code"] == "TOOL_EXECUTION_FAILED"
        assert res.json()["detail"]["recoverable"] is False


# ==========================================================================
# Task B.5 - Staleness at creation (c2 repair) + approval-time staleness
# ==========================================================================


class TestStalenessAtCreation:
    """The c2 repair surfaces staleness at proposal creation (not only at
    approval). When a pinned base resource moves out from under a proposal,
    the staleness signal is surfaced -- at creation-time flag and/or
    approval-time rejection per the repaired contract."""

    def test_create_tool_proposal_computes_is_stale_field(self, db) -> None:
        """create_tool_proposal computes is_stale at creation (c2/D10),
        making the field authoritative from the moment the proposal exists."""
        from app.codirector.bible.proposals import ProposalService
        from app.codirector.tools.definitions import ToolCallPayload, ToolPreview
        from app.db import Project

        pid = f"stale-create-{uuid.uuid4().hex[:10]}"
        db.merge(Project(id=pid, name="Stale Create"))
        db.commit()
        # Seed a bible so the bible capability is configured.
        from app.codirector.bible import operations as ops
        from app.codirector.bible.schemas import BibleEntity

        ops.create_bible_with_first_version(
            db,
            project_id=pid,
            entities=[BibleEntity(entityType="project_profile", entityKey="project-profile",
                                  displayName="Project Profile", data={"description": "seed"})],
            facts=[],
            summary="seed",
            change_reason="seed",
            created_by="test",
        )
        payload = ToolCallPayload(
            toolId="propose_canon_record",
            arguments={"claim": "test canon"},
            preview=ToolPreview(summary="preview"),
            baseResourceVersions={"bible": "stale-version-id"},
        )
        proposal = ProposalService.create_tool_proposal(
            db, project_id=pid, payload=payload, title="test", summary="preview", created_by="test"
        )
        # isStale is a real boolean computed by the service at creation. With a
        # deliberately-stale pinned bible version, it must be True.
        assert hasattr(proposal, "isStale")
        assert proposal.isStale is True

    def test_bible_scoped_proposal_goes_stale_when_bible_moves(self, client) -> None:
        """A bible-scoped tool proposal built against the current bible is
        detected as stale at approval after the bible is bumped."""
        project_id = _create_project(client)
        _create_bible(client, project_id)
        proposal = _propose(
            client, project_id, "record_director_decision", decision="Rain in every exterior."
        ).json()
        # Bump the bible out from under the proposal.
        bump = client.post(
            f"/api/codirector/projects/{project_id}/bible/versions",
            json={
                "mutations": {
                    "entityMutations": [{"entityType": "prop", "entityKey": "umbrella", "displayName": "Umbrella"}],
                    "factMutations": [],
                }
            },
        )
        assert bump.status_code == 200
        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 409
        assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"
        refetched = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}").json()
        assert refetched["status"] == "stale"

    def test_scene_scoped_proposal_goes_stale_when_scene_changes(self, client) -> None:
        project_id = _create_project(client)
        scene = _add_scene(client, project_id, "Before")
        proposal = _propose(
            client, project_id, "update_scene_title", sceneId=scene["id"], name="Proposed"
        ).json()
        edited = client.patch(
            f"/api/projects/{project_id}/scenes/{scene['id']}",
            json={"name": "Edited By Hand", "prompt": "Wide establishing shot.", "continuity_json": ""},
        )
        assert edited.status_code == 200
        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 409
        assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"

    def test_preview_reports_staleness(self, client) -> None:
        project_id = _create_project(client)
        _create_bible(client, project_id)
        proposal = _propose(
            client, project_id, "record_director_decision", decision="Rain."
        ).json()
        client.post(
            f"/api/codirector/projects/{project_id}/bible/versions",
            json={"mutations": {"entityMutations": [{"entityType": "prop", "entityKey": "x", "displayName": "X"}], "factMutations": []}},
        )
        preview = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/preview").json()
        assert preview["isStale"] is True


# ==========================================================================
# Task B.6 - Schema-version guard: older schema_version rejected at approve
# ==========================================================================


class TestSchemaVersionGuard:
    """A proposal stored with an older schema_version is rejected at approve
    time (existing contract -- regression-cover it)."""

    def test_older_schema_version_rejected_at_approve(self, client) -> None:
        from app.db import SessionLocal, CoDirectorProposal

        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Versioned").json()

        # Tamper the stored payload's toolSchemaVersion to an older value.
        db = SessionLocal()
        try:
            row = db.get(CoDirectorProposal, proposal["id"])
            payload = json.loads(row.payload_json)
            payload["toolSchemaVersion"] = payload["toolSchemaVersion"] - 1
            row.payload_json = json.dumps(payload)
            db.commit()
        finally:
            db.close()

        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 409
        detail = approve.json()["detail"]
        assert detail["code"] == "TOOL_SCHEMA_VERSION_MISMATCH"
        assert detail["recoverable"] is False
        # Nothing was created.
        assert len(_scenes(client, project_id)) == 1

    def test_registry_check_schema_version_raises_on_mismatch(self) -> None:
        from app.codirector.tools import registry

        definition = registry.get("create_scene")
        with pytest.raises(CoDirectorError) as excinfo:
            registry.check_schema_version(definition, definition.schema_version + 1)
        assert excinfo.value.code == "TOOL_SCHEMA_VERSION_MISMATCH"
        assert excinfo.value.recoverable is False

    def test_unreadable_payload_treated_as_stale(self, client) -> None:
        """A payload that no longer parses can never be applied -- only
        cancelled (existing contract, regression-cover)."""
        from app.db import SessionLocal, CoDirectorProposal

        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Corrupt").json()
        db = SessionLocal()
        try:
            row = db.get(CoDirectorProposal, proposal["id"])
            row.payload_json = "{ not json"
            db.commit()
        finally:
            db.close()
        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 409
        assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"
        # A stale proposal can still be cancelled (the only safe action).
        cancel = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/cancel", json={}
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"


# ==========================================================================
# Task B (extra) - Project-scope + terminal-state guards on approval
# ==========================================================================


class TestApprovalGuards:
    """The approval surface enforces project scope and terminal-state guards
    so a proposal from one project cannot be acted on from another, and a
    terminal proposal cannot be re-acted."""

    def test_cross_project_approve_is_rejected(self, client) -> None:
        project_a = _create_project(client, "A")
        project_b = _create_project(client, "B")
        proposal = _propose(client, project_a, "create_scene", name="Cross").json()
        approve = client.post(
            f"/api/codirector/projects/{project_b}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 403
        assert approve.json()["detail"]["code"] == "PROJECT_SCOPE_VIOLATION"

    def test_reject_then_approve_is_invalid_state(self, client) -> None:
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Rev").json()
        client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/reject", json={})
        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 409
        assert approve.json()["detail"]["code"] == "PROPOSAL_INVALID_STATE"

    def test_idempotent_reapprove_returns_same_receipt(self, client) -> None:
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Once").json()
        first = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
        assert first.status_code == 200
        second = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
        assert second.status_code == 200
        assert second.json()["proposalId"] == first.json()["proposalId"]
        assert second.json()["id"] == first.json()["id"]
        assert len(_scenes(client, project_id)) == 2

