"""Co-Director M2.1: Production Bible, durable proposals/approvals/execution.

Covers: versioned Bible CRUD (import preview/confirm, manual version edits), the
propose -> approve/reject/request-revision/cancel lifecycle, staleness detection,
idempotent execution, bounded `ProjectContextService` context injection, structured
```proposal fence extraction from provider replies (including the malformed case), and
schema parity between `Base.metadata.create_all` and the `M002` migration.

Uses the same `client` / `isolated_data_dir` fixtures as `test_codirector_provider.py`
(from `conftest.py`) and the same `STUDIO_E2E` + `ADEPT_CODIRECTOR_PROVIDER=mock` gating
pattern for chat-integration tests that need a deterministic provider.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


def _create_project(client, name: str = "Bible Test Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Moody neo-noir look, rain-soaked streets."})
    assert res.status_code == 200
    return res.json()["id"]


def _upload_asset(client, project_id: str, *, tag: str, filename: str = "asset.png", kind: str = "image") -> dict:
    res = client.post(
        f"/api/projects/{project_id}/assets",
        data={"tag": tag, "kind": kind},
        files={"file": (filename, b"fake-asset-bytes", "image/png")},
    )
    assert res.status_code == 200
    return res.json()


# --------------------------------------------------------------------------
# Bible: not-found before creation, import preview/confirm
# --------------------------------------------------------------------------


def test_bible_not_found_before_creation(client) -> None:
    project_id = _create_project(client)
    res = client.get(f"/api/codirector/projects/{project_id}/bible")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "BIBLE_NOT_FOUND"


def test_import_preview_does_not_persist_anything(client) -> None:
    project_id = _create_project(client)
    res = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["projectId"] == project_id
    assert any(e["entityType"] == "project_profile" for e in body["entities"])
    assert any(e["entityType"] == "visual_style" for e in body["entities"])

    # Nothing was persisted by preview alone.
    still_missing = client.get(f"/api/codirector/projects/{project_id}/bible")
    assert still_missing.status_code == 404


def test_import_preview_groups_character_images_under_character_references(client) -> None:
    project_id = _create_project(client, "Bible Classifier Test")
    _upload_asset(client, project_id, tag="Korri Character", filename="korri-front.png")
    _upload_asset(client, project_id, tag="Korri Character", filename="korri-side.png")
    _upload_asset(client, project_id, tag="Skybridge Rooftop Location", filename="roof.png")

    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={})
    assert preview.status_code == 200
    body = preview.json()

    korri = next(e for e in body["entities"] if e["entityKey"] == "korri-character")
    assert korri["entityType"] == "character"
    assert len(korri["data"]["referenceAssets"]) == 2
    assert not any(
        e["entityType"] == "prop" and e["entityKey"] == "korri-character" for e in body["entities"]
    )

    characters_group = next(group for group in body["discoveries"] if group["id"] == "characters")
    korri_item = next(item for item in characters_group["items"] if item["entityKey"] == "korri-character")
    assert len(korri_item["referenceAssets"]) == 2
    assert korri_item["needsReview"] is False


def test_import_confirm_creates_version_1(client) -> None:
    project_id = _create_project(client)
    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={}).json()

    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"], "summary": preview["summary"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["currentVersion"]["versionNumber"] == 1
    assert body["versionCount"] == 1

    fetched = client.get(f"/api/codirector/projects/{project_id}/bible")
    assert fetched.status_code == 200
    assert fetched.json()["currentVersion"]["versionNumber"] == 1


def test_import_confirm_ignores_preview_only_asset_kind_metadata(client) -> None:
    project_id = _create_project(client, "Bible Import Preview Metadata")
    _upload_asset(client, project_id, tag="character_voice", filename="korri-line.wav", kind="audio")
    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={}).json()

    character_voice = next(e for e in preview["entities"] if e["entityKey"] == "character-voice")
    character_voice["data"]["kind"] = "audio"

    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"], "summary": preview["summary"]},
    )
    assert res.status_code == 200

    persisted = next(e for e in res.json()["currentVersion"]["entities"] if e["entityKey"] == "character-voice")
    assert persisted["entityType"] == "character"
    assert persisted["data"]["sourceTag"] == "character_voice"
    assert "kind" not in persisted["data"]


def test_import_confirm_twice_conflicts(client) -> None:
    project_id = _create_project(client)
    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={}).json()
    first = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"]},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"]},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "BIBLE_ALREADY_EXISTS"


# --------------------------------------------------------------------------
# Versions: manual edits are copy-on-write, immutable once created
# --------------------------------------------------------------------------


def _create_bible(client, project_id: str) -> dict:
    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={}).json()
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"]},
    )
    assert res.status_code == 200
    return res.json()


def test_manual_entity_add_creates_new_version(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)

    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/versions",
        json={
            "mutations": {
                "entityMutations": [
                    {
                        "entityType": "character",
                        "entityKey": "ava",
                        "displayName": "Ava",
                        "data": {"description": "Protagonist, mid-20s."},
                    }
                ],
                "factMutations": [],
                "summary": "Added Ava",
                "changeReason": "manual_edit",
            },
            "createdBy": "user",
        },
    )
    assert res.status_code == 200
    version = res.json()
    assert version["versionNumber"] == 2
    keys = {e["entityKey"] for e in version["entities"]}
    assert "ava" in keys
    # Prior entities (project_profile, visual_style) carried forward — copy-on-write.
    assert "project-profile" in keys


def test_versions_are_immutable_and_listable(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    client.post(
        f"/api/codirector/projects/{project_id}/bible/versions",
        json={
            "mutations": {
                "entityMutations": [{"entityType": "character", "entityKey": "ava", "displayName": "Ava"}],
                "factMutations": [],
            }
        },
    )

    versions = client.get(f"/api/codirector/projects/{project_id}/bible/versions").json()["versions"]
    assert [v["versionNumber"] for v in versions] == [2, 1]

    v1 = client.get(f"/api/codirector/projects/{project_id}/bible/versions/1").json()
    assert not any(e["entityKey"] == "ava" for e in v1["entities"])
    v2 = client.get(f"/api/codirector/projects/{project_id}/bible/versions/2").json()
    assert any(e["entityKey"] == "ava" for e in v2["entities"])


def test_get_missing_version_returns_404(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    res = client.get(f"/api/codirector/projects/{project_id}/bible/versions/99")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "BIBLE_VERSION_NOT_FOUND"


def test_entity_removal_mutation_drops_from_next_version(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    client.post(
        f"/api/codirector/projects/{project_id}/bible/versions",
        json={"mutations": {"entityMutations": [{"entityType": "character", "entityKey": "ava", "displayName": "Ava"}], "factMutations": []}},
    )
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/versions",
        json={"mutations": {"entityMutations": [{"entityType": "character", "entityKey": "ava", "remove": True}], "factMutations": []}},
    )
    assert res.status_code == 200
    assert not any(e["entityKey"] == "ava" for e in res.json()["entities"])


# --------------------------------------------------------------------------
# Proposals: create -> approve/reject/request-revision/cancel
# --------------------------------------------------------------------------


def _create_proposal(client, project_id: str, *, entity_key: str = "ava") -> dict:
    res = client.post(
        f"/api/codirector/projects/{project_id}/proposals",
        json={
            "proposal_type": "entity_update",
            "title": f"Update {entity_key}",
            "summary": "Test proposal",
            "payload": {
                "entityMutations": [
                    {"entityType": "character", "entityKey": entity_key, "displayName": entity_key.title()}
                ],
                "factMutations": [],
                "summary": "Test proposal",
                "changeReason": "test",
            },
        },
    )
    assert res.status_code == 200
    return res.json()


def test_create_and_list_proposal(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)
    assert proposal["status"] == "pending"
    assert proposal["basedOnVersionId"]

    listed = client.get(f"/api/codirector/projects/{project_id}/proposals").json()["proposals"]
    assert any(p["id"] == proposal["id"] for p in listed)

    filtered = client.get(f"/api/codirector/projects/{project_id}/proposals?status=pending").json()["proposals"]
    assert any(p["id"] == proposal["id"] for p in filtered)


def test_approve_proposal_creates_new_version_and_receipt(client) -> None:
    project_id = _create_project(client)
    bible = _create_bible(client, project_id)
    v1_id = bible["currentVersion"]["id"]
    proposal = _create_proposal(client, project_id)
    assert proposal["basedOnVersionId"] == v1_id

    receipt = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert receipt.status_code == 200
    receipt_body = receipt.json()
    assert receipt_body["status"] == "success"
    assert receipt_body["resultingVersionNumber"] == 2

    updated_proposal = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}").json()
    assert updated_proposal["status"] == "completed"

    new_bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
    assert new_bible["currentVersion"]["versionNumber"] == 2
    assert any(e["entityKey"] == "ava" for e in new_bible["currentVersion"]["entities"])

    fetched_receipt = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/receipt").json()
    assert fetched_receipt["id"] == receipt_body["id"]


def test_approve_completed_proposal_again_is_rejected(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)
    first = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert first.status_code == 200

    second = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "APPROVAL_ALREADY_RECORDED"


def test_reject_proposal(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)
    res = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/reject", json={"note": "Not needed"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    # Bible untouched — still version 1.
    bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
    assert bible["currentVersion"]["versionNumber"] == 1

    cannot_approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert cannot_approve.status_code == 409
    assert cannot_approve.json()["detail"]["code"] == "PROPOSAL_INVALID_STATE"


def test_request_revision_then_approve(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)
    revision = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/request-revision",
        json={"note": "Add more detail"},
    )
    assert revision.status_code == 200
    assert revision.json()["status"] == "revision_requested"

    # revision_requested is still reviewable — approving from there is allowed.
    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 200


def test_cancel_proposal(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)
    res = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/cancel", json={})
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"

    cannot_cancel_again = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/cancel", json={})
    assert cannot_cancel_again.status_code == 409


def test_approve_unknown_proposal_returns_404(client) -> None:
    project_id = _create_project(client)
    res = client.post(f"/api/codirector/projects/{project_id}/proposals/does-not-exist/approve", json={})
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "PROPOSAL_NOT_FOUND"


def test_proposal_scope_violation_across_projects(client) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    _create_bible(client, project_a)
    proposal = _create_proposal(client, project_a)

    res = client.get(f"/api/codirector/projects/{project_b}/proposals/{proposal['id']}")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "PROJECT_SCOPE_VIOLATION"


def test_approve_stale_proposal_returns_409_and_marks_stale(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)

    # The Bible moves on to version 2 via an unrelated manual edit before the proposal is
    # reviewed — the proposal's basis is now out of date.
    bump = client.post(
        f"/api/codirector/projects/{project_id}/bible/versions",
        json={"mutations": {"entityMutations": [{"entityType": "prop", "entityKey": "lantern", "displayName": "Lantern"}], "factMutations": []}},
    )
    assert bump.status_code == 200

    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 409
    assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"

    refetched = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}").json()
    assert refetched["status"] == "stale"

    # Stale proposals can still be cancelled.
    cancelled = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/cancel", json={})
    assert cancelled.status_code == 200


def test_preview_proposal_shows_entity_diff(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id, entity_key="ava")
    res = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["wouldCreateVersionNumber"] == 2
    assert any(d["entityKey"] == "ava" and d["op"] == "add" for d in body["entityDiff"])
    assert body["isStale"] is False


def test_receipt_not_found_before_approval(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _create_proposal(client, project_id)
    res = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/receipt")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "RECEIPT_NOT_FOUND"


def test_proposal_without_existing_bible_creates_bible_on_approve(client) -> None:
    """A proposal can be created (and approved) even before the project has a Bible yet —
    approval implicitly creates the Bible shell and version 1."""
    project_id = _create_project(client)
    proposal = _create_proposal(client, project_id, entity_key="new-character")
    assert proposal["basedOnVersionId"] is None

    receipt = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert receipt.status_code == 200
    assert receipt.json()["resultingVersionNumber"] == 1

    bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
    assert bible["currentVersion"]["versionNumber"] == 1
    assert any(e["entityKey"] == "new-character" for e in bible["currentVersion"]["entities"])


# --------------------------------------------------------------------------
# ProjectContextService: bounded excerpt + manifest
# --------------------------------------------------------------------------


def test_context_service_empty_when_no_bible(client) -> None:
    from app.codirector.bible.context import ProjectContextService
    from app.db import SessionLocal

    project_id = _create_project(client)
    db = SessionLocal()
    try:
        excerpt, manifest = ProjectContextService.build(db, project_id)
        assert excerpt == ""
        assert manifest.bibleVersionId is None
        assert manifest.includedEntityKeys == []
    finally:
        db.close()


def test_context_service_returns_empty_for_missing_project_id() -> None:
    from app.codirector.bible.context import ProjectContextService
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        excerpt, manifest = ProjectContextService.build(db, None)
        assert excerpt == ""
        assert manifest.projectId == ""
    finally:
        db.close()


def test_context_service_includes_entities_and_respects_token_budget(client) -> None:
    from app.codirector.bible.context import ProjectContextService
    from app.db import SessionLocal

    project_id = _create_project(client)
    bible = _create_bible(client, project_id)
    # Add several more entities so the excerpt has enough content to truncate.
    mutations = {
        "entityMutations": [
            {
                "entityType": "character",
                "entityKey": f"char-{i}",
                "displayName": f"Character {i}",
                "data": {"description": "A fairly detailed description to consume token budget. " * 4},
            }
            for i in range(8)
        ],
        "factMutations": [],
    }
    client.post(f"/api/codirector/projects/{project_id}/bible/versions", json={"mutations": mutations})

    db = SessionLocal()
    try:
        full_excerpt, full_manifest = ProjectContextService.build(db, project_id, token_budget=100_000)
        assert full_manifest.truncated is False
        assert len(full_manifest.includedEntityKeys) >= 8

        tight_excerpt, tight_manifest = ProjectContextService.build(db, project_id, token_budget=20)
        assert tight_manifest.truncated is True
        assert len(tight_manifest.includedEntityKeys) < len(full_manifest.includedEntityKeys)
        assert tight_manifest.estimatedTokens <= full_manifest.estimatedTokens
        assert len(tight_excerpt) < len(full_excerpt)
    finally:
        db.close()
    assert bible["currentVersion"]["versionNumber"] == 1  # sanity: fixture unaffected by later mutation


# --------------------------------------------------------------------------
# Structured provider output: ```proposal fence extraction (mock provider scenarios)
# --------------------------------------------------------------------------


def test_extract_proposal_block_parses_well_formed_fence() -> None:
    from app.codirector.structured_output import extract_proposal_block

    reply = (
        "Here's what I'd like to change.\n\n```proposal\n"
        + json.dumps(
            {
                "proposalType": "entity_update",
                "title": "Update Ava",
                "summary": "Add scar detail",
                "entityMutations": [{"entityType": "character", "entityKey": "ava", "displayName": "Ava"}],
                "factMutations": [],
            }
        )
        + "\n```"
    )
    result = extract_proposal_block(reply)
    assert result is not None
    assert result.error is None
    assert result.mutations is not None
    assert result.mutations.entityMutations[0].entityKey == "ava"


def test_extract_proposal_block_reports_malformed_json() -> None:
    from app.codirector.structured_output import extract_proposal_block

    reply = "I propose a change.\n\n```proposal\n{ not valid json,,, \n```"
    result = extract_proposal_block(reply)
    assert result is not None
    assert result.error is not None
    assert result.mutations is None


def test_extract_proposal_block_returns_none_without_fence() -> None:
    from app.codirector.structured_output import extract_proposal_block

    assert extract_proposal_block("Just a normal chat reply, nothing structured.") is None


def test_chat_with_proposal_scenario_persists_proposal(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "proposal_character_update")

    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "She has a scar now"}], "project_id": project_id},
    )
    assert res.status_code == 200
    body = res.json()
    assert "```proposal" not in body["reply"]
    assert body["proposal"] is not None
    assert body["proposal"]["status"] == "pending"
    assert body["proposal"]["payload"]["entityMutations"][0]["entityKey"] == "ava"

    listed = client.get(f"/api/codirector/projects/{project_id}/proposals").json()["proposals"]
    assert any(p["id"] == body["proposal"]["id"] for p in listed)


def test_chat_with_malformed_proposal_scenario_returns_structured_error(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "malformed_proposal")

    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "propose something"}], "project_id": project_id},
    )
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "STRUCTURED_OUTPUT_INVALID"

    # No proposal should have been persisted from a malformed fence.
    listed = client.get(f"/api/codirector/projects/{project_id}/proposals").json()["proposals"]
    assert listed == []


def test_stream_emits_proposal_created_and_context_manifest_events(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "proposal_character_update")

    events: list[dict] = []
    with client.stream(
        "POST",
        "/api/codirector/chat/stream",
        json={"messages": [{"role": "user", "content": "update her look"}], "project_id": project_id},
    ) as res:
        assert res.status_code == 200
        for line in res.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            events.append(json.loads(line[len("data:") :].strip()))

    types = [e["type"] for e in events]
    assert "context_manifest" in types
    assert "proposal_created" in types
    assert "completed" in types
    proposal_event = next(e for e in events if e["type"] == "proposal_created")
    assert proposal_event["proposal"]["status"] == "pending"


def test_stream_without_bible_has_no_context_manifest_event(client, mock_provider_env) -> None:
    project_id = _create_project(client)
    events: list[dict] = []
    with client.stream(
        "POST",
        "/api/codirector/chat/stream",
        json={"messages": [{"role": "user", "content": "hello"}], "project_id": project_id},
    ) as res:
        assert res.status_code == 200
        for line in res.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            events.append(json.loads(line[len("data:") :].strip()))
    types = [e["type"] for e in events]
    assert "context_manifest" not in types
    assert "completed" in types


# --------------------------------------------------------------------------
# Migration <-> SQLAlchemy model schema parity
# --------------------------------------------------------------------------


def test_migration_and_create_all_produce_the_same_bible_tables(tmp_path) -> None:
    from sqlalchemy import create_engine, inspect

    from app.db import Base
    from app.migrations import DEFAULT_REGISTRY, MigrationRunner

    tables = (
        "production_bibles",
        "production_bible_versions",
        "production_bible_entities",
        "production_bible_facts",
        "codirector_proposals",
        "codirector_approvals",
        "codirector_execution_receipts",
        "bible_audit_events",
    )

    migrated_engine = create_engine(f"sqlite:///{tmp_path / 'migrated.db'}")
    MigrationRunner(migrated_engine, DEFAULT_REGISTRY).apply_pending()
    migrated_inspector = inspect(migrated_engine)

    created_engine = create_engine(f"sqlite:///{tmp_path / 'created.db'}")
    Base.metadata.create_all(bind=created_engine)
    created_inspector = inspect(created_engine)

    for table in tables:
        migrated_cols = {c["name"] for c in migrated_inspector.get_columns(table)}
        created_cols = {c["name"] for c in created_inspector.get_columns(table)}
        assert migrated_cols == created_cols, f"Column mismatch for {table}: {migrated_cols} vs {created_cols}"


# --------------------------------------------------------------------------
# M2.3: domain layer, lifecycle, export, cascade
# --------------------------------------------------------------------------


def test_m23_domain_create_character_has_stable_id(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/characters",
        json={
            "entityKey": "ava",
            "displayName": "Ava",
            "data": {
                "description": "Protagonist",
                "personality": "Bold",
                "motivation": "Justice",
                "appearanceSummary": "Red coat",
            },
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["stableId"]
    assert body["lifecycleStatus"] == "draft"
    assert body["contentRevision"] >= 1


def test_m23_bible_summary_and_health(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    summary = client.get(f"/api/codirector/projects/{project_id}/bible/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["projectId"] == project_id
    assert data["health"]["entityCount"] >= 1


def test_m23_lock_rejects_direct_patch(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    created = client.post(
        f"/api/codirector/projects/{project_id}/bible/characters",
        json={"entityKey": "nova", "displayName": "Nova", "data": {"description": "Lead"}},
    ).json()
    stable_id = created["stableId"]
    client.post(f"/api/codirector/projects/{project_id}/bible/characters/{stable_id}/approve")
    client.post(f"/api/codirector/projects/{project_id}/bible/characters/{stable_id}/lock")
    patch = client.patch(
        f"/api/codirector/projects/{project_id}/bible/characters/{stable_id}",
        json={"data": {"description": "Changed"}, "contentRevision": created["contentRevision"]},
    )
    assert patch.status_code == 409
    assert patch.json()["detail"]["code"] == "LOCKED_ENTITY_REQUIRES_APPROVAL"


def test_m23_concurrent_modification_on_stale_revision(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    created = client.post(
        f"/api/codirector/projects/{project_id}/bible/characters",
        json={"entityKey": "kai", "displayName": "Kai", "data": {"description": "A"}},
    ).json()
    stable_id = created["stableId"]
    first = client.patch(
        f"/api/codirector/projects/{project_id}/bible/characters/{stable_id}",
        json={"data": {"description": "B"}, "contentRevision": created["contentRevision"]},
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/api/codirector/projects/{project_id}/bible/characters/{stable_id}",
        json={"data": {"description": "C"}, "contentRevision": created["contentRevision"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "CONCURRENT_MODIFICATION"


def test_m23_export_json(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    res = client.get(f"/api/codirector/projects/{project_id}/bible/export")
    assert res.status_code == 200
    body = res.json()
    assert body["schemaVersion"] == "m2.3"
    assert "entities" in body
    assert "health" in body


def test_m23_project_delete_cascades_bible(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/codirector/projects/{project_id}/bible")
    assert missing.status_code == 404


def test_m23_seed_demo_bible(client) -> None:
    project_id = _create_project(client)
    res = client.post(f"/api/codirector/projects/{project_id}/bible/seed-demo")
    assert res.status_code == 200
    assert res.json()["seeded"] is True
    chars = client.get(f"/api/codirector/projects/{project_id}/bible/characters")
    assert chars.status_code == 200
    assert len(chars.json()["characters"]) >= 2


def test_m23_context_character_package(client) -> None:
    project_id = _create_project(client)
    client.post(f"/api/codirector/projects/{project_id}/bible/seed-demo")
    chars = client.get(f"/api/codirector/projects/{project_id}/bible/characters").json()["characters"]
    stable_id = chars[0]["stableId"]
    ctx = client.get(f"/api/codirector/projects/{project_id}/bible/context/character/{stable_id}")
    assert ctx.status_code == 200
    assert ctx.json()["found"] is True


def test_m23_bible_domain_read_tool(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": "get_production_bible_summary", "arguments": {}},
    )
    assert res.status_code == 200
    assert res.json()["result"]["projectId"] == project_id
