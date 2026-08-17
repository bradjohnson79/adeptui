"""P12 read-side-effect regression tests (CDX-054 / CDX-055 / CDX-056).

Covers:
- GET /projects/{id}/scriptwriter never creates script_documents_v2 rows.
- GET /projects/{id}/story never creates story_documents rows.
- SCRIPT_CONFLICT stores the unsaved payload server-side and
  POST /documents/{id}/recovery/restore applies it.
- GET /projects/{id}/notes never mutates the conversation snapshot or bumps
  its revision; the knowledgeEntries -> workingNotes bridge persists only via
  an explicit write path.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _e2e_on(monkeypatch):
    monkeypatch.setenv("STUDIO_E2E", "1")


def _mk_project(client):
    res = client.post("/api/projects", json={"name": "P12 Read Side Effects"})
    assert res.status_code == 200, res.text
    return res.json()


def _count_rows(table: str, project_id: str) -> int:
    from sqlalchemy import text

    from app.db import engine

    with engine.connect() as conn:
        value = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE project_id = :p"), {"p": project_id}
        ).scalar()
    return int(value or 0)


# ── CDX-054: scriptwriter GET is side-effect free ──────────────────────────


def test_scriptwriter_get_creates_no_rows_until_explicit_create(client):
    p = _mk_project(client)
    pid = p["id"]

    studio = client.get(f"/api/projects/{pid}/scriptwriter")
    assert studio.status_code == 200, studio.text
    body = studio.json()
    assert body["ok"] is True
    assert body["document"] is None
    assert body["paginationMode"] == "estimated"
    assert _count_rows("script_documents_v2", pid) == 0

    # repeated GETs stay side-effect free
    client.get(f"/api/projects/{pid}/scriptwriter")
    assert _count_rows("script_documents_v2", pid) == 0

    # explicit creation on first write (POST /documents)
    created = client.post(f"/api/projects/{pid}/scriptwriter/documents")
    assert created.status_code == 200, created.text
    doc_id = created.json()["document"]["id"]
    assert _count_rows("script_documents_v2", pid) == 1

    # GET now returns the existing document and does not create a second row
    again = client.get(f"/api/projects/{pid}/scriptwriter").json()
    assert again["document"]["id"] == doc_id
    assert _count_rows("script_documents_v2", pid) == 1

    # autosave persists to the single document
    autosave = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={"html": "<p>Hello world</p>", "expectedRevision": created.json()["document"]["revision"]},
    )
    assert autosave.status_code == 200, autosave.text
    assert autosave.json()["saveState"] == "saved"
    assert _count_rows("script_documents_v2", pid) == 1


# ── CDX-054: story GET is side-effect free ─────────────────────────────────


def test_story_get_creates_no_rows_until_first_save(client):
    p = _mk_project(client)
    pid = p["id"]

    empty = client.get(f"/api/projects/{pid}/story")
    assert empty.status_code == 200, empty.text
    assert empty.json()["content"] == ""
    assert empty.json()["title"] == "Untitled Story"
    assert _count_rows("story_documents", pid) == 0

    # repeated GETs stay side-effect free
    client.get(f"/api/projects/{pid}/story")
    assert _count_rows("story_documents", pid) == 0

    # first explicit write (PUT) creates the row
    saved = client.put(f"/api/projects/{pid}/story", json={"content": "<p>Once upon a time</p>"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["wordCount"] > 0
    assert _count_rows("story_documents", pid) == 1

    again = client.get(f"/api/projects/{pid}/story").json()
    assert again["content"] == "<p>Once upon a time</p>"
    assert _count_rows("story_documents", pid) == 1


# ── CDX-055: conflict recovery is stored and restorable ────────────────────


def test_conflict_stores_recovery_and_restore_applies_payload(client):
    p = _mk_project(client)
    pid = p["id"]

    created = client.post(f"/api/projects/{pid}/scriptwriter/documents").json()
    doc_id = created["document"]["id"]
    rev1 = created["document"]["revision"]

    # client A saves at rev1
    first = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={
            "elements": [{"id": "a1", "type": "action", "text": "First save", "order": 0}],
            "expectedRevision": rev1,
        },
    )
    assert first.status_code == 200, first.text
    rev2 = first.json()["document"]["revision"]

    # client B holds a stale revision -> SCRIPT_CONFLICT, payload stored
    conflict = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={
            "elements": [{"id": "b1", "type": "action", "text": "Unsaved work", "order": 0}],
            "expectedRevision": rev1,
        },
    )
    assert conflict.status_code == 400, conflict.text
    assert conflict.json()["detail"]["code"] == "SCRIPT_CONFLICT"

    # the bundle surfaces the recovery payload
    bundle = client.get(f"/api/projects/{pid}/scriptwriter").json()
    assert bundle["recovery"] is not None
    assert bundle["recovery"]["expectedRevision"] == rev1

    # restore applies the stored payload through a transaction
    restored = client.post(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/recovery/restore")
    assert restored.status_code == 200, restored.text
    body = restored.json()
    texts = [e["text"] for e in body["document"]["elements"]]
    assert "Unsaved work" in texts
    assert body["document"]["revision"] > rev2
    assert body["transaction"]["kind"] == "recovery_restore"
    assert body["saveState"] == "saved"

    # recovery is cleared after a successful restore
    bundle2 = client.get(f"/api/projects/{pid}/scriptwriter").json()
    assert bundle2["recovery"] is None

    # a second restore with nothing stored is rejected
    again = client.post(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/recovery/restore")
    assert again.status_code == 400
    assert again.json()["detail"]["code"] == "SCRIPT_RECOVERY_UNAVAILABLE"


def test_conflict_recovery_preserved_when_document_moves_again(client):
    p = _mk_project(client)
    pid = p["id"]

    created = client.post(f"/api/projects/{pid}/scriptwriter/documents").json()
    doc_id = created["document"]["id"]
    rev1 = created["document"]["revision"]

    client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={"html": "<p>Version A</p>", "expectedRevision": rev1},
    )

    # stale client conflicts -> recovery stored (with conflictServerRevision)
    conflict = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={"html": "<p>Unsaved B</p>", "expectedRevision": rev1},
    )
    assert conflict.status_code == 400
    assert conflict.json()["detail"]["code"] == "SCRIPT_CONFLICT"

    # a different writer advances the document (insert_scene does not clear recovery)
    inserted = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/scenes/insert",
        json={"heading": "EXT. NEW LOCATION - DAY"},
    )
    assert inserted.status_code == 200, inserted.text

    # restore is rejected because the document moved since the conflict; payload kept
    retry = client.post(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/recovery/restore")
    assert retry.status_code == 400
    assert retry.json()["detail"]["code"] == "SCRIPT_CONFLICT"
    bundle = client.get(f"/api/projects/{pid}/scriptwriter").json()
    assert bundle["recovery"] is not None
    assert bundle["recovery"]["html"] == "<p>Unsaved B</p>"


# ── CDX-056: GET /notes never mutates the snapshot ─────────────────────────


def _seed_knowledge_entry(pid: str) -> None:
    from app.codirector.conversation.knowledge import apply_wiki_candidates
    from app.codirector.conversation.schemas import WikiCandidate
    from app.codirector.conversation.snapshot import load_snapshot, save_snapshot
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        snap = load_snapshot(db, pid)
        snap = apply_wiki_candidates(
            snap,
            [
                WikiCandidate(
                    id="k1",
                    text="Korri is a tide-worn dreamweaver from Harbor Ward",
                    state="confirmed",
                    section="characters",
                )
            ],
            "seed",
        )
        save_snapshot(db, snap)
    finally:
        db.close()


def test_notes_get_never_mutates_snapshot_revision(client):
    from app.codirector.conversation.snapshot import load_snapshot
    from app.db import SessionLocal

    p = _mk_project(client)
    pid = p["id"]
    _seed_knowledge_entry(pid)

    db = SessionLocal()
    try:
        seeded_revision = load_snapshot(db, pid).revision
    finally:
        db.close()

    first = client.get(f"/api/codirector/projects/{pid}/notes")
    assert first.status_code == 200, first.text
    notes1 = first.json()["notes"]
    assert any("tide-worn" in n["text"] for n in notes1), "knowledge entry must bridge for display"

    # GET must not persist the bridge or bump the revision
    db = SessionLocal()
    try:
        after_first = load_snapshot(db, pid)
        assert after_first.revision == seeded_revision, "GET /notes bumped snapshot revision"
        assert after_first.workingNotes == [], "GET /notes persisted the workingNotes bridge"
    finally:
        db.close()

    second = client.get(f"/api/codirector/projects/{pid}/notes")
    assert second.status_code == 200
    assert second.json()["count"] == first.json()["count"]

    db = SessionLocal()
    try:
        after_second = load_snapshot(db, pid)
        assert after_second.revision == seeded_revision, "second GET /notes bumped snapshot revision"
        assert after_second.workingNotes == [], "second GET /notes persisted the bridge"
    finally:
        db.close()

    # explicit write path bridges + persists (run-on-first-write)
    dismissed = client.post(f"/api/codirector/projects/{pid}/notes/dismiss", json={"noteId": notes1[0]["id"]})
    assert dismissed.status_code == 200, dismissed.text

    db = SessionLocal()
    try:
        after_write = load_snapshot(db, pid)
        assert after_write.revision > seeded_revision, "explicit write must bump revision"
        assert len(after_write.workingNotes) > 0, "explicit write must persist the bridged notes"
    finally:
        db.close()
