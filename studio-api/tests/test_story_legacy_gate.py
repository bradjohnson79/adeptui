"""CDX-060: legacy story_documents store is migration-only.

PUT /projects/{id}/story must be rejected (410 Gone) once a project has
canonical story_entries — residual writers must not create story_documents
content the Wiki / Co-Director never reads. The migration window (no
story_entries yet) still allows the write, and all reads (GET /story,
GET /story/status, migrate_from_legacy) stay available. The legacy store is
NOT deleted.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _e2e_on(monkeypatch):
    monkeypatch.setenv("STUDIO_E2E", "1")


def _mk_project(client):
    res = client.post("/api/projects", json={"name": "CDX-060 Legacy Story Gate"})
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


def test_put_story_allowed_in_migration_window_before_story_entries(client):
    """A project with no story_entries can still write the legacy doc (the
    one-time migration source)."""
    p = _mk_project(client)
    pid = p["id"]

    saved = client.put(f"/api/projects/{pid}/story", json={"content": "<p>Legacy draft</p>"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["wordCount"] > 0
    assert _count_rows("story_documents", pid) == 1


def test_put_story_rejected_410_when_story_entries_exist(client):
    """Once canonical story_entries exist, legacy writes are refused (410) and
    no story_documents row is created."""
    p = _mk_project(client)
    pid = p["id"]

    created = client.post(
        f"/api/projects/{pid}/story-entries",
        json={"title": "Korri", "logline": "A tide-worn dreamweaver."},
    )
    assert created.status_code == 201, created.text

    rejected = client.put(
        f"/api/projects/{pid}/story", json={"content": "<p>Must not persist</p>"}
    )
    assert rejected.status_code == 410, rejected.text
    assert rejected.json()["detail"] == "legacy_story_writes_disabled_story_entries_active"
    # The rejected write must not create a legacy row.
    assert _count_rows("story_documents", pid) == 0


def test_story_reads_stay_available_for_gated_project(client):
    """GET /story and GET /story/status remain read-only for a project whose
    legacy writes are gated; reads never create rows."""
    p = _mk_project(client)
    pid = p["id"]
    client.post(
        f"/api/projects/{pid}/story-entries",
        json={"title": "Korri", "logline": "v1"},
    )

    status = client.get(f"/api/projects/{pid}/story/status")
    assert status.status_code == 200, status.text

    story = client.get(f"/api/projects/{pid}/story")
    assert story.status_code == 200, story.text
    assert story.json()["content"] == ""
    assert _count_rows("story_documents", pid) == 0


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
