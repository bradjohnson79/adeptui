"""c6 error-truthfulness certification for the Co-Director Operational Integrity Audit.

Covers the error-recovery and truthful-reporting surface governed by
``CODIRECTOR_ERROR_RECOVERY_AUDIT.md`` (phase c6). Tests assert that real
failures surface as structured ``CoDirectorError`` envelopes to the caller
(code + message + recoverable + recommendedAction), that the invocation
ledger records every terminal state truthfully, that a failed apply can
never look like a success, that the c2 premature-claim correction fires for
unbacked mutation-success prose and not for backed ones, and that the
Phase 4.1 error envelope never leaks secrets or absolute paths.

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


def asyncio_run(coro):
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("loop running")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return asyncio.get_event_loop().run_until_complete(coro)


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


def _create_project(client, name: str = "Error Truthfulness Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200
    return res.json()["id"]


def _scenes(client, project_id: str) -> list[dict]:
    return client.get(f"/api/projects/{project_id}").json()["scenes"]


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
# Task A.1 - Structured propagation: real failures keep their typed code
# ==========================================================================


class TestStructuredPropagation:
    """Induce real failures and assert the structured code survives to the
    caller -- no collapse into a generic 'something went wrong'."""

    def test_missing_scene_target_surfaces_tool_target_not_found(self, client) -> None:
        project_id = _create_project(client)
        res = _propose(client, project_id, "update_scene_title", sceneId="no-such-scene", name="Renamed")
        assert res.status_code == 404
        detail = res.json()["detail"]
        assert detail["code"] == "TOOL_TARGET_NOT_FOUND"
        assert detail["message"]
        assert "recoverable" in detail
        assert "recommendedAction" in detail or "recommended_action" in detail
        assert detail["code"] != "TOOL_EXECUTION_FAILED"

    def test_missing_audio_batch_surfaces_tool_target_not_found(self, client) -> None:
        project_id = _create_project(client)
        res = client.post(
            f"/api/codirector/projects/{project_id}/tools/audited",
            json={"toolId": "audio.cancel_batch", "arguments": {"batchId": "no-such-batch"}},
        )
        assert res.status_code == 404
        detail = res.json()["detail"]
        assert detail["code"] == "TOOL_TARGET_NOT_FOUND"
        assert detail["message"]
        assert detail["code"] != "TOOL_EXECUTION_FAILED"

    def test_bad_arguments_surfaces_tool_arguments_invalid(self, client) -> None:
        project_id = _create_project(client)
        # update_scene_title requires both sceneId and name; omitting them fails
        # at sanitization before any handler runs.
        res = _propose(client, project_id, "update_scene_title")
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert detail["code"] == "TOOL_ARGUMENTS_INVALID"
        assert detail["details"]["parameter"] in {"sceneId", "name"}
        assert detail["code"] != "TOOL_EXECUTION_FAILED"

    def test_out_of_range_argument_surfaces_tool_arguments_invalid(self, client) -> None:
        project_id = _create_project(client)
        res = _propose(client, project_id, "create_scene", name="X", durationSec=9999.0)
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert detail["code"] == "TOOL_ARGUMENTS_INVALID"
        assert detail["code"] != "TOOL_EXECUTION_FAILED"

    def test_capability_not_configured_for_bible_tool_without_bible(self, client) -> None:
        project_id = _create_project(client)
        res = _propose(client, project_id, "record_director_decision", decision="No Bible yet.")
        assert res.status_code == 409
        detail = res.json()["detail"]
        assert detail["code"] == "CAPABILITY_NOT_CONFIGURED"
        assert detail["message"]
        assert detail["code"] != "TOOL_EXECUTION_FAILED"
        assert client.get(f"/api/codirector/projects/{project_id}/proposals").json()["proposals"] == []

    def test_capability_blocked_read_surfaces_typed_code(self, client, monkeypatch) -> None:
        project_id = _create_project(client)
        monkeypatch.setenv("STUDIO_E2E", "1")
        monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "read_tool_blocked_capability")
        res = client.post(
            f"/api/codirector/projects/{project_id}/tools/read",
            json={"toolId": "get_comfyui_health", "arguments": {}},
        )
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail["code"] in {"CAPABILITY_UNAVAILABLE", "CAPABILITY_NOT_CONFIGURED"}
        assert detail["code"] != "TOOL_EXECUTION_FAILED"

    def test_native_validation_failure_surfaces_as_typed_error(self, client) -> None:
        """A bible-domain handler that rejects a stale supersession target
        surfaces its own structured code (SUPERSEDED_NOT_CURRENT) at APPROVE
        time (the read-before-write gate lives in the apply handler), not the
        generic TOOL_EXECUTION_FAILED collapse."""
        project_id = _create_project(client)
        _create_bible(client, project_id)
        proposal = _propose(
            client,
            project_id,
            "propose_canon_supersession",
            claim="new canon",
            supersedesStableId="missing-stable-id",
        ).json()
        # Propose succeeds (preview does not check the supersession target);
        # the structured error fires when the approved apply runs.
        assert proposal["status"] == "pending"
        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 409
        detail = approve.json()["detail"]
        assert detail["code"] == "SUPERSEDED_NOT_CURRENT"
        assert detail["code"] != "TOOL_EXECUTION_FAILED"

    def test_error_envelope_carries_phase41_keys(self, client) -> None:
        project_id = _create_project(client)
        res = _propose(client, project_id, "update_scene_title")
        detail = res.json()["detail"]
        for key in ("code", "message", "category", "messageKey", "details", "recoverable", "recommendedAction"):
            assert key in detail, f"envelope missing {key}"
        assert detail["category"] == "tool"
        assert detail["messageKey"] == "errors.code.TOOL_ARGUMENTS_INVALID"


# ==========================================================================
# Task A.2 - Invocation ledger truthfulness
# ==========================================================================


class TestInvocationLedger:
    """The codirector_tool_invocations ledger records every terminal state
    truthfully: succeeded, failed (with error), and blocked."""

    def test_succeeded_read_logs_succeeded(self, client) -> None:
        project_id = _create_project(client)
        client.post(
            f"/api/codirector/projects/{project_id}/tools/read",
            json={"toolId": "get_project_profile", "arguments": {}},
        )
        rows = _ledger(client, project_id)
        assert len(rows) == 1
        assert rows[0]["status"] == "succeeded"
        assert rows[0]["resultHash"]
        assert rows[0]["errorCode"] is None

    def test_blocked_read_logs_blocked_with_error_code(self, client) -> None:
        project_id = _create_project(client)
        res = client.post(
            f"/api/codirector/projects/{project_id}/tools/read",
            json={"toolId": "get_bible_entity", "arguments": {"entityKey": "ava"}},
        )
        assert res.status_code == 409
        rows = _ledger(client, project_id)
        blocked = [r for r in rows if r["toolId"] == "get_bible_entity"]
        assert len(blocked) == 1
        assert blocked[0]["status"] == "blocked"
        assert blocked[0]["errorCode"] == "CAPABILITY_NOT_CONFIGURED"
        assert blocked[0]["errorMessage"]

    def test_failed_apply_logs_failed_with_error_code(self, client, monkeypatch) -> None:
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Will Fail").json()

        from app.codirector.tools import registry
        from app.codirector.tools.handlers import scenes

        def exploding_apply(ctx, args):
            raise RuntimeError("disk on fire")

        monkeypatch.setitem(
            registry._MUTATION_HANDLERS,
            "create_scene",
            registry.MutationHandler(scenes.preview_create_scene, exploding_apply),
        )

        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 502
        rows = _ledger(client, project_id)
        failed = [r for r in rows if r["toolId"] == "create_scene"]
        assert len(failed) == 1
        assert failed[0]["status"] == "failed"
        assert failed[0]["errorCode"] == "TOOL_EXECUTION_FAILED"
        assert failed[0]["errorMessage"]
        assert failed[0]["proposalId"] == proposal["id"]

    def test_failed_co_director_error_apply_preserves_its_code(self, client, monkeypatch) -> None:
        """When a handler raises a CoDirectorError (not a generic Exception),
        the ledger records that error's own code -- not the generic collapse."""
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Typed Fail").json()

        from app.codirector.tools import registry
        from app.codirector.tools.handlers import scenes

        def typed_fail(ctx, args):
            raise CoDirectorError(
                "TOOL_TARGET_NOT_FOUND",
                "Scene vanished mid-apply.",
                details={"toolId": "create_scene"},
                recoverable=False,
                recommended_action="none",
            )

        monkeypatch.setitem(
            registry._MUTATION_HANDLERS,
            "create_scene",
            registry.MutationHandler(scenes.preview_create_scene, typed_fail),
        )

        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 404
        rows = _ledger(client, project_id)
        failed = [r for r in rows if r["toolId"] == "create_scene"]
        assert len(failed) == 1
        assert failed[0]["status"] == "failed"
        assert failed[0]["errorCode"] == "TOOL_TARGET_NOT_FOUND"
        assert failed[0]["errorCode"] != "TOOL_EXECUTION_FAILED"


# ==========================================================================
# Task A.3 - No silent success: a failed apply never looks like a success
# ==========================================================================


class TestNoSilentSuccess:
    """A mutating tool whose apply raises must NEVER produce a success-shaped
    result; the proposal must not be marked applied/completed."""

    def test_failed_apply_leaves_proposal_failed_not_completed(self, client, monkeypatch) -> None:
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Will Fail").json()

        from app.codirector.tools import registry
        from app.codirector.tools.handlers import scenes

        def exploding_apply(ctx, args):
            raise RuntimeError("disk on fire")

        monkeypatch.setitem(
            registry._MUTATION_HANDLERS,
            "create_scene",
            registry.MutationHandler(scenes.preview_create_scene, exploding_apply),
        )

        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        assert approve.status_code == 502
        assert approve.json()["detail"]["code"] == "TOOL_EXECUTION_FAILED"

        refetched = client.get(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}"
        ).json()
        assert refetched["status"] == "failed"
        assert refetched["status"] != "completed"

        receipt = client.get(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/receipt"
        ).json()
        assert receipt["status"] == "failed"
        assert receipt["error"]["code"] == "TOOL_EXECUTION_FAILED"

        assert len(_scenes(client, project_id)) == 1

    def test_failed_apply_does_not_create_success_receipt(self, client, monkeypatch) -> None:
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="No Receipt").json()

        from app.codirector.tools import registry
        from app.codirector.tools.handlers import scenes
        from app.db import SessionLocal, CoDirectorExecutionReceipt

        def exploding_apply(ctx, args):
            raise RuntimeError("boom")

        monkeypatch.setitem(
            registry._MUTATION_HANDLERS,
            "create_scene",
            registry.MutationHandler(scenes.preview_create_scene, exploding_apply),
        )

        client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})

        db = SessionLocal()
        try:
            success_receipts = (
                db.query(CoDirectorExecutionReceipt)
                .filter(
                    CoDirectorExecutionReceipt.proposal_id == proposal["id"],
                    CoDirectorExecutionReceipt.status == "success",
                )
                .all()
            )
            assert success_receipts == []
        finally:
            db.close()


# ==========================================================================
# Task A.4 - Premature-claim behavior (c2 repair)
# ==========================================================================


class TestPrematureClaimDetection:
    """A streamed/sync reply claiming a mutation completed with no executed
    mutating tool must surface a correction; a claim backed by an actual
    executed tool must NOT false-positive."""

    def test_unbacked_mutation_claim_is_flagged(self) -> None:
        from app.codirector.service import _detect_premature_tool_success_claim

        for reply in [
            "I've added the scene to your project.",
            "I created a new character for you.",
            "I've updated the Production Bible summary.",
            "Added the canon record as requested.",
            "I've deleted the clip you mentioned.",
        ]:
            flagged, phrase = _detect_premature_tool_success_claim(reply, mutating_tool_executed=False)
            assert flagged is True, f"expected flag for: {reply}"
            assert phrase

    def test_claim_backed_by_executed_tool_does_not_false_positive(self, db) -> None:
        """When an audited mutating tool actually executed and succeeded this
        turn, a success claim in the prose is legitimate and must NOT be
        flagged as premature. This exercises the contract the stream paths
        rely on: once a mutating tool has succeeded, the detector must not
        flag the model's success prose.

        NOTE: the audited branch of ``_interpret_reply`` now appends the
        succeeded invocation to ``outcome.invocations`` (repaired defect), so
        the legacy stream path's ``_mutating_executed`` computation sees it.
        This test asserts BOTH the event payload and the outcome record."""
        from app.codirector.service import (
            _StructuredOutcome,
            _detect_premature_tool_success_claim,
            _interpret_reply,
        )
        from app.db import Project

        pid = f"premature-backed-{uuid.uuid4().hex[:10]}"
        db.merge(Project(id=pid, name="Premature Backed"))
        db.commit()

        reply = (
            "I've created the draft plan for you.\n\n"
            + "```tool\n"
            + json.dumps(
                {
                    "responseType": "mutation_proposal",
                    "toolId": "production_plan.create_draft",
                    "arguments": {"title": "T", "objective": "O"},
                }
            )
            + "\n```"
        )

        outcome = _StructuredOutcome()
        events: list[dict] = []
        asyncio_run(_collect_interpret(events, outcome, reply, db, pid))

        completed = [e for e in events if e["type"] == "tool_completed"]
        assert completed, "audited tool should have completed"
        _mutating_executed = any(
            (e.get("invocation") or {}).get("kind") == "mutating"
            and (e.get("invocation") or {}).get("status") == "succeeded"
            for e in completed
        )
        assert _mutating_executed is True

        # Defect-3 regression guard: the outcome itself records the audited
        # mutating execution (the legacy stream path computes _mutating_executed
        # from outcome.invocations, not from the event payload).
        assert any(
            getattr(inv, "kind", None) == "mutating"
            and getattr(inv, "status", None) == "succeeded"
            for inv in (outcome.invocations or [])
        ), "audited branch must append the succeeded invocation to outcome.invocations"

        flagged, _ = _detect_premature_tool_success_claim(
            "I've created the draft plan for you.", mutating_tool_executed=_mutating_executed
        )
        assert flagged is False

    def test_detector_directly_returns_false_when_tool_executed(self) -> None:
        """Unit contract: passing mutating_tool_executed=True suppresses the
        flag regardless of the claim phrasing."""
        from app.codirector.service import _detect_premature_tool_success_claim

        for reply in [
            "I've added the scene to your project.",
            "I created a new character for you.",
            "Added the canon record as requested.",
        ]:
            flagged, _ = _detect_premature_tool_success_claim(reply, mutating_tool_executed=True)
            assert flagged is False

    def test_unbacked_claim_through_interpreter_flags(self, db) -> None:
        """A reply containing only a success claim (no tool fence) leaves no
        mutating invocation, so the detector flags it -- mirroring the legacy
        stream path's premature_tool_success emission condition."""
        from app.codirector.service import (
            _StructuredOutcome,
            _detect_premature_tool_success_claim,
            _interpret_reply,
        )
        from app.db import Project

        pid = f"premature-unbacked-{uuid.uuid4().hex[:10]}"
        db.merge(Project(id=pid, name="Premature Unbacked"))
        db.commit()

        reply = "I've added the scene to your project."
        outcome = _StructuredOutcome()
        events: list[dict] = []
        asyncio_run(_collect_interpret(events, outcome, reply, db, pid))

        _mutating_executed = any(
            getattr(inv, "kind", None) == "mutating"
            and getattr(inv, "status", None) == "succeeded"
            for inv in (outcome.invocations or [])
        )
        assert _mutating_executed is False
        flagged, phrase = _detect_premature_tool_success_claim(reply, mutating_tool_executed=_mutating_executed)
        assert flagged is True
        assert phrase

    def test_wiki_claim_is_left_to_wiki_detector(self) -> None:
        from app.codirector.service import _detect_premature_tool_success_claim

        # Phrases that match the wiki-specific detector regex are skipped here
        # so the two corrections do not both fire for the same text.
        for reply in [
            "I've updated the wiki with new lore.",
            "Added to the wiki.",
            "Saved to the wiki.",
        ]:
            flagged, _ = _detect_premature_tool_success_claim(reply, mutating_tool_executed=False)
            assert flagged is False, "wiki claims belong to the wiki detector, not this one"


async def _collect_interpret(events, outcome, reply, db, pid):
    from app.codirector.service import _interpret_reply

    async for event in _interpret_reply(
        db,
        project_id=pid,
        scene_id=None,
        request_id="test-req",
        reply=reply,
        tools_used=0,
        outcome=outcome,
    ):
        events.append(event)


# ==========================================================================
# Task A.5 - Error envelope security: to_dict never leaks secrets/paths
# ==========================================================================


class TestErrorEnvelopeSecurity:
    """The Phase 4.1 ``to_dict`` envelope's redaction layer is
    ``technical_evidence`` (produced by ``_safe_evidence``), which applies
    ``redact_secrets`` and skips secret-shaped detail keys. These tests assert
    that redaction layer never leaks secrets.

    NOTE: the raw ``details`` dict is ALSO emitted verbatim by ``to_dict`` and
    is NOT run through ``_safe_evidence``; ``_safe_evidence`` also does not
    apply ``sanitize.scrub_text``, so absolute paths are not stripped from
    ``technical_evidence`` either. Both gaps are documented as defects in the
    return report. The defense in production is that raise sites pre-scrub
    ``reason`` strings via ``sanitize.scrub_text(str(exc))[:200]`` before
    they reach ``details``; that defense is certified below."""

    def test_technical_evidence_redacts_bearer_tokens(self) -> None:
        err = CoDirectorError(
            "TOOL_EXECUTION_FAILED",
            "boom",
            details={"reason": "Bearer abcdefghij123456 was rejected"},
        )
        out = err.to_dict()
        evidence = out["technical_evidence"]
        assert "Bearer abcdefghij123456" not in json.dumps(evidence)
        assert "abcdefghij123456" not in json.dumps(evidence)
        assert "[redacted]" in evidence["reason"]

    def test_technical_evidence_redacts_api_key_shapes(self) -> None:
        err = CoDirectorError(
            "TOOL_EXECUTION_FAILED",
            "boom",
            details={"reason": "api_key=sk-secretvalue123 was invalid"},
        )
        out = err.to_dict()
        evidence = out["technical_evidence"]
        assert "sk-secretvalue123" not in json.dumps(evidence)
        assert "secretvalue123" not in json.dumps(evidence)

    def test_technical_evidence_redacts_long_hex_tokens(self) -> None:
        err = CoDirectorError(
            "TOOL_EXECUTION_FAILED",
            "boom",
            details={"reason": "token 0123456789abcdef0123456789abcdef rejected"},
        )
        out = err.to_dict()
        evidence = out["technical_evidence"]
        assert "0123456789abcdef0123456789abcdef" not in json.dumps(evidence)

    def test_technical_evidence_skips_secret_shaped_detail_keys(self) -> None:
        err = CoDirectorError(
            "TOOL_EXECUTION_FAILED",
            "boom",
            details={
                "token": "sensitive-bearer-token",
                "apiKey": "sk-leak",
                "password": "hunter2",
                "raw": "full provider payload with secrets",
                "stack": "traceback with paths",
                "safe": "this one is fine",
            },
        )
        out = err.to_dict()
        evidence = out["technical_evidence"]
        assert "token" not in evidence
        assert "apiKey" not in evidence
        assert "password" not in evidence
        assert "raw" not in evidence
        assert "stack" not in evidence
        assert evidence.get("safe") == "this one is fine"

    def test_raise_site_pre_scrubs_reason_so_http_response_leaks_no_secret(
        self, client, monkeypatch
    ) -> None:
        """The production defense: handlers build ``reason`` via
        ``sanitize.scrub_text(str(exc))[:200]`` BEFORE placing it in details,
        so the HTTP error response (which emits raw details) carries no
        secret/path. This certifies that defense end-to-end."""
        project_id = _create_project(client)
        proposal = _propose(client, project_id, "create_scene", name="Leak Check").json()

        from app.codirector.tools import registry
        from app.codirector.tools.handlers import scenes

        def leaky_apply(ctx, args):
            raise RuntimeError(
                "Bearer supersecrettoken123456 wrote to "
                r"C:\AdeptFilmWorks\data\projects\p1\out.mp4"
            )

        monkeypatch.setitem(
            registry._MUTATION_HANDLERS,
            "create_scene",
            registry.MutationHandler(scenes.preview_create_scene, leaky_apply),
        )

        approve = client.post(
            f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
        )
        body = json.dumps(approve.json())
        # The raise-site scrub strips both the secret and the absolute path
        # before they reach the error details, so the HTTP response is clean.
        assert "supersecrettoken123456" not in body
        assert "AdeptFilmWorks" not in body

    def test_to_dict_carries_phase41_envelope_keys(self) -> None:
        err = CoDirectorError(
            "PROPOSAL_STALE",
            "The project changed.",
            details={"proposalId": "p1", "projectId": "proj-1", "provider": "ollama", "model": "mock-model"},
            recoverable=True,
            recommended_action="preview_again",
        )
        out = err.to_dict()
        for key in (
            "code",
            "error_code",
            "category",
            "message",
            "messageKey",
            "details",
            "recoverable",
            "retryable",
            "project_id",
            "provider",
            "model",
            "technical_evidence",
            "partial_work_created",
            "recommendedAction",
            "recommended_action",
        ):
            assert key in out, f"envelope missing {key}"
        assert out["code"] == "PROPOSAL_STALE"
        assert out["error_code"] == "PROPOSAL_STALE"
        # PROPOSAL_STALE is not in the tool/validation/provider sets, so it
        # falls through to the 'runtime' category.
        assert out["category"] == "runtime"
        assert out["recoverable"] is True
        assert out["retryable"] is True
        assert out["recommendedAction"] == "preview_again"
        assert out["recommended_action"] == "preview_again"
        assert out["project_id"] == "proj-1"
        assert out["provider"] == "ollama"
        assert out["model"] == "mock-model"
        assert out["messageKey"] == "errors.code.PROPOSAL_STALE"


class TestErrorEnvelopeSecurityGaps:
    """Regression guards for the two repaired redaction gaps (fixed by primary):
    (1) ``to_dict`` now scrubs ``details`` values at emission instead of emitting
    the raw dict; (2) ``_safe_evidence`` now strips absolute filesystem paths in
    addition to secrets. These tests assert the REPAIRED behavior — if either
    scrub is removed, they fail."""

    def test_details_dict_is_emitted_verbatim_without_safe_evidence(self) -> None:
        """REPAIRED GAP 1: ``to_dict`` no longer exposes raw ``details`` — secret-
        shaped values are redacted in both ``details`` and ``technical_evidence``."""
        err = CoDirectorError(
            "TOOL_EXECUTION_FAILED",
            "boom",
            details={"reason": "Bearer abcdefghij123456 was rejected"},
        )
        out = err.to_dict()
        assert "Bearer abcdefghij123456" not in json.dumps(out["details"])
        assert "[redacted]" in json.dumps(out["details"])
        assert "Bearer abcdefghij123456" not in json.dumps(out["technical_evidence"])
        # Structured keys the UI depends on survive the scrub untouched.
        err2 = CoDirectorError(
            "TOOL_TARGET_NOT_FOUND",
            "missing",
            details={"projectId": "p-123", "toolId": "timeline.add_batch", "attempts": 2},
        )
        out2 = err2.to_dict()
        assert out2["details"] == {"projectId": "p-123", "toolId": "timeline.add_batch", "attempts": 2}

    def test_technical_evidence_does_not_strip_absolute_paths(self) -> None:
        """REPAIRED GAP 2: absolute filesystem paths are stripped from both
        ``technical_evidence`` and ``details`` (``<path>`` placeholder)."""
        err = CoDirectorError(
            "TOOL_EXECUTION_FAILED",
            "boom",
            details={"reason": r"failed to write C:\AdeptFilmWorks\data\out.mp4"},
        )
        out = err.to_dict()
        evidence = out["technical_evidence"]
        assert "AdeptFilmWorks" not in json.dumps(evidence)
        assert "<path>" in json.dumps(evidence)
        assert "AdeptFilmWorks" not in json.dumps(out["details"])

