"""CDX-096 — Notes subsystem API coverage: list / dismiss / promote semantics.

Covers the Notes working desk contract (app/codirector/notes):
- GET  /api/codirector/projects/{project_id}/notes        -> list
- POST /api/codirector/projects/{project_id}/notes/dismiss -> dismiss
- POST /api/codirector/projects/{project_id}/wiki/promote  -> promote

Includes the Phase 1C / CDX-056 snapshot revision neutrality guarantee: the
GET /notes read path must never persist or bump the conversation snapshot
revision, while the write paths (dismiss / promote) DO persist and bump it.

TESTS ONLY. No app/ source is modified here.
"""

from __future__ import annotations

import json

import pytest


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


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


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(client, name: str = "Notes Subsystem Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _seed_notes(db, project_id: str, texts: list[str]) -> None:
    """Persist RAW notes through the real service write path."""
    from app.codirector.notes.service import upsert_notes_from_texts

    upsert_notes_from_texts(db, project_id, texts)


def _snapshot_revision(db, project_id: str) -> int:
    """Read the persisted snapshot revision from project settings (no writes)."""
    from app.db import Project

    project = db.get(Project, project_id)
    assert project is not None
    settings = json.loads(project.settings_json or "{}")
    payload = (settings.get("projectIntelligence") or {}) if isinstance(settings, dict) else {}
    return int(payload.get("revision") or 0)


def _list_notes(client, project_id: str) -> dict:
    res = client.get(f"/api/codirector/projects/{project_id}/notes")
    assert res.status_code == 200, res.text
    return res.json()


def _dismiss(client, project_id: str, note_id: str):
    return client.post(f"/api/codirector/projects/{project_id}/notes/dismiss", json={"noteId": note_id})


def _promote(client, project_id: str, **body):
    return client.post(f"/api/codirector/projects/{project_id}/wiki/promote", json=body)


# ==========================================================================
# list
# ==========================================================================


def test_list_notes_returns_working_desk(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    _seed_notes(db, project_id, ["Ava is a detective in New Harbor.", "The rain never stops."])

    body = _list_notes(client, project_id)
    assert body["ok"] is True
    assert body["layer"] == "notes_working_memory"
    assert body["count"] == 2
    texts = [n["text"] for n in body["notes"]]
    assert "Ava is a detective in New Harbor." in texts
    assert "The rain never stops." in texts
    assert all(n["promotionStatus"] == "RAW" for n in body["notes"])


def test_list_notes_empty_project_returns_empty_desk(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    body = _list_notes(client, project_id)
    assert body["ok"] is True
    assert body["count"] == 0
    assert body["notes"] == []


# ==========================================================================
# Phase 1C / CDX-056 — GET /notes is read-only (snapshot revision neutrality)
# ==========================================================================


def test_list_notes_never_bumps_snapshot_revision(client, db, mock_provider_env) -> None:
    """GET /notes must not persist or bump the conversation snapshot revision
    (CDX-056: read paths are in-memory only; the bridge persists on first write)."""
    project_id = _create_project(client)
    _seed_notes(db, project_id, ["The setting is a flooded city."])
    before = _snapshot_revision(db, project_id)
    assert before >= 1, "seeding through upsert must have persisted a snapshot"

    first = _list_notes(client, project_id)
    mid = _snapshot_revision(db, project_id)
    second = _list_notes(client, project_id)
    after = _snapshot_revision(db, project_id)

    # Read is idempotent AND revision-neutral.
    assert first["count"] == second["count"] == 1
    assert before == mid == after


# ==========================================================================
# dismiss
# ==========================================================================


def test_dismiss_note_hides_it_and_persists(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    _seed_notes(db, project_id, ["Discarded idea: everything happens in space."])
    note_id = _list_notes(client, project_id)["notes"][0]["id"]

    rev_before = _snapshot_revision(db, project_id)
    res = _dismiss(client, project_id, note_id)
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    assert res.json()["noteId"] == note_id
    rev_after = _snapshot_revision(db, project_id)
    assert rev_after > rev_before, "dismiss is a write path and must bump the snapshot revision"

    listed = _list_notes(client, project_id)["notes"]
    assert all(n["id"] != note_id for n in listed), "dismissed note must be hidden from the desk"


def test_dismiss_unknown_note_reports_ok_false(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    res = _dismiss(client, project_id, "note-does-not-exist")
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is False


# ==========================================================================
# promote
# ==========================================================================


def test_promote_note_flags_it_promoted(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    _seed_notes(db, project_id, ["The city is called New Harbor."])
    note_id = _list_notes(client, project_id)["notes"][0]["id"]

    rev_before = _snapshot_revision(db, project_id)
    res = _promote(client, project_id, noteId=note_id, destination="story")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["promotedText"] == "The city is called New Harbor."
    assert body["destination"] == "story"
    rev_after = _snapshot_revision(db, project_id)
    assert rev_after > rev_before, "promote is a write path and must bump the snapshot revision"

    notes = _list_notes(client, project_id)["notes"]
    promoted = next(n for n in notes if n["id"] == note_id)
    assert promoted["promotionStatus"] == "PROMOTED"


def test_promote_free_text_creates_promoted_note(client, db, mock_provider_env) -> None:
    """Promoting raw text without a note id creates a new PROMOTED note."""
    project_id = _create_project(client)
    res = _promote(client, project_id, text="Brand new canon: the moon is blue.", destination="world")
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    notes = _list_notes(client, project_id)["notes"]
    assert any(
        n["text"] == "Brand new canon: the moon is blue." and n["promotionStatus"] == "PROMOTED"
        for n in notes
    )


def test_promote_nothing_is_not_ok(client, db, mock_provider_env) -> None:
    project_id = _create_project(client)
    res = _promote(client, project_id)
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is False
