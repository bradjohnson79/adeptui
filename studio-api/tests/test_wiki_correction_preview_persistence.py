"""CDX-061: Wiki correction previews survive restarts via the preview store.

The preview store persists CorrectionPreview rows as JSON in a dedicated
lightweight table (bounded per project + TTL), replacing the in-process
module dict whose loss on restart made apply return 404 "preview_not_found".

Covers: round-trip persistence, unknown-id None, single-use delete,
per-project bounds, apply from a store-reconstructed preview, and an HTTP
preview -> apply round trip where the preview is read back from the DB
(the restart-survival property).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.wiki_intelligence.correction.contracts import (
    CorrectionPreview,
    EntityReclassification,
)
from app.codirector.wiki_intelligence.correction.preview_store import (
    _KEEP_PER_PROJECT,
    delete_preview,
    load_preview,
    save_preview,
)
from app.db import Base, Project


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-a", name="Alpha"))
    session.add(Project(id="proj-b", name="Beta"))
    session.commit()
    yield session
    session.close()


def _preview(
    preview_id: str,
    project_id: str = "proj-a",
    instruction: str = "Gakona is a location, not a character.",
) -> CorrectionPreview:
    return CorrectionPreview(
        previewId=preview_id,
        projectId=project_id,
        instruction=instruction,
        correctionType="RECLASSIFY",
        entityReclassifications=[
            EntityReclassification(name="Gakona", fromType="character", toType="location")
        ],
        learnedRule="Gakona is a location, not a character.",
    )


def test_preview_round_trips_through_the_store(db):
    save_preview(db, _preview("prev_rt1"))
    loaded = load_preview(db, "prev_rt1")
    assert loaded is not None
    assert loaded.previewId == "prev_rt1"
    assert loaded.projectId == "proj-a"
    assert loaded.correctionType == "RECLASSIFY"
    assert loaded.entityReclassifications[0].toType == "location"
    assert loaded.learnedRule == "Gakona is a location, not a character."
    assert loaded.instruction == "Gakona is a location, not a character."


def test_load_unknown_preview_returns_none(db):
    assert load_preview(db, "never-created") is None


def test_delete_preview_consumes_preview(db):
    save_preview(db, _preview("prev_del1"))
    assert load_preview(db, "prev_del1") is not None
    delete_preview(db, "prev_del1")
    assert load_preview(db, "prev_del1") is None


def test_store_is_bounded_per_project(db):
    for i in range(40):
        save_preview(db, _preview(f"prev_b{i}", project_id="proj-a"))
    remaining = [load_preview(db, f"prev_b{i}") for i in range(40)]
    present = [p for p in remaining if p is not None]
    assert len(present) <= _KEEP_PER_PROJECT
    # Newest survives; oldest is purged.
    assert load_preview(db, "prev_b39") is not None
    assert load_preview(db, "prev_b0") is None


def test_preview_store_is_project_scoped_by_id(db):
    save_preview(db, _preview("prev_iso", project_id="proj-a"))
    assert load_preview(db, "prev_iso") is not None
    # Bounding for project A must not remove project B rows.
    save_preview(db, _preview("prev_iso_b", project_id="proj-b"))
    assert load_preview(db, "prev_iso") is not None
    assert load_preview(db, "prev_iso_b") is not None


def test_apply_can_use_preview_reconstructed_from_store(db):
    """apply_correction must work with a preview loaded from the store — the
    exact path apply_wiki_correction uses after a restart."""
    from app.codirector.conversation.snapshot import load_snapshot
    from app.codirector.wiki_intelligence.correction.apply import apply_correction

    save_preview(db, _preview("prev_apply_store"))
    loaded = load_preview(db, "prev_apply_store")
    assert loaded is not None

    result = apply_correction(db, "proj-a", loaded)
    assert result["ok"] is True
    snapshot = load_snapshot(db, "proj-a")
    assert any("explicit_wiki_write" in (e.provenance or "") for e in snapshot.knowledgeEntries)


@pytest.fixture(autouse=True)
def _e2e_on(monkeypatch):
    monkeypatch.setenv("STUDIO_E2E", "1")


def test_http_preview_then_apply_round_trip(client):
    """POST preview persists a row; a fresh DB read finds it (restart survival);
    POST apply consumes it and a second apply is rejected."""
    from app.codirector.wiki_intelligence.correction.preview_store import load_preview
    from app.db import SessionLocal

    p = client.post("/api/projects", json={"name": "CDX-061 Preview Persistence"})
    assert p.status_code == 200, p.text
    pid = p.json()["id"]

    created = client.post(
        f"/api/codirector/projects/{pid}/wiki/correction/preview",
        json={"instruction": "Gakona is a location, not a character."},
    )
    assert created.status_code == 200, created.text
    preview_id = created.json()["preview"]["previewId"]

    # The preview must live in the DB (fresh session), not an in-process dict.
    db = SessionLocal()
    try:
        stored = load_preview(db, preview_id)
    finally:
        db.close()
    assert stored is not None, "preview must be persisted, not only in-memory"
    assert stored.projectId == pid
    assert stored.correctionType == "RECLASSIFY"

    applied = client.post(
        f"/api/codirector/projects/{pid}/wiki/correction/apply",
        json={"previewId": preview_id},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["ok"] is True

    # Single-use: a second apply finds the consumed preview missing.
    again = client.post(
        f"/api/codirector/projects/{pid}/wiki/correction/apply",
        json={"previewId": preview_id},
    )
    assert again.status_code == 404, again.text
    assert again.json()["detail"] == "preview_not_found"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
