"""Script Writer simplification — title rename + HTML-canonical scene ops.

Mission gates covered here:
- SCRIPT TITLE EDITING: rename_document persists the canonical title.
- SCENE ADD/REMOVE: insert/delete/move operate on the typed HTML (the
  canonical content for v2 documents) so the mutation is actually visible
  in the navigator — previously these ops mutated only the stale stored
  elements and were invisible for HTML documents (live-proven defect).
- REVISIONS: revision snapshots capture canonical elements + contentHtml,
  compare reads canonical content, and restore brings back the HTML.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, Project
from app.scriptwriter import service
from app.scriptwriter.models import ScriptDocument, ScriptElement
from app.scriptwriter.store import load_document, save_document

TYPED_HTML = (
    "<h1>INT. CAFE - DAY</h1>"
    "<p>Rain on glass. A stranger enters.</p>"
    '<p style="margin-left: 240px">KORRI</p>'
    '<p style="margin-left: 240px">We keep going.</p>'
    "<h1>EXT. ROOFTOP - NIGHT</h1>"
    "<p>Wind howls.</p>"
    '<p style="margin-left: 240px">JACE</p>'
    '<p style="margin-left: 240px">Not tonight.</p>'
)


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
    session.add(Project(id="proj-a", name="Project A"))
    session.commit()
    yield session
    session.close()


def _html_doc(db, *, html=TYPED_HTML, doc_id="doc-m") -> ScriptDocument:
    doc = ScriptDocument(
        id=doc_id,
        projectId="proj-a",
        title="Untitled Script",
        elements=[
            ScriptElement(id="stale1", type="scene_heading", text="INT. LOCATION - DAY", order=0, sceneNumber="1"),
            ScriptElement(id="stale2", type="action", text="", order=1),
        ],
        contentHtml=html,
        contentType="html",
    )
    save_document(db, doc)
    return doc


# ── SCRIPT TITLE EDITING ──────────────────────────────────────────────────


def test_rename_document_persists_title(db):
    _html_doc(db)
    before = load_document(db, "doc-m").revision
    result = service.rename_document(db, "doc-m", "The Adept Chronicles")
    assert result["ok"] is True
    assert result["document"]["title"] == "The Adept Chronicles"
    reloaded = load_document(db, "doc-m")
    assert reloaded.title == "The Adept Chronicles"
    # Title is metadata: no revision bump (in-flight autosaves must not conflict)
    assert reloaded.revision == before


def test_rename_document_blank_keeps_untitled(db):
    _html_doc(db)
    result = service.rename_document(db, "doc-m", "   ")
    assert result["document"]["title"] == "Untitled Script"


def test_rename_document_missing_doc_raises(db):
    with pytest.raises(service.ScriptwriterError):
        service.rename_document(db, "nope", "X")


def test_rename_document_never_clobbers_content_or_revision(db):
    """Rename/autosave race regression: rename must be a title-only UPDATE.

    Previously rename_document loaded the doc, set the title, and called
    save_document — which rewrites EVERY column from the in-memory doc. A
    rename whose read raced a debounced autosave would restore stale content
    and regress the revision counter (also causing spurious SCRIPT_CONFLICT
    on the next autosave carrying expectedRevision).
    """
    _html_doc(db)
    stale_read = load_document(db, "doc-m")  # what a pre-autosave rename read
    # The debounced autosave lands first: new content + revision bump.
    service.autosave_html(
        db,
        "doc-m",
        TYPED_HTML + "<h1>INT. NEW SCENE - DAY</h1>",
        expected_revision=stale_read.revision,
    )
    after_save = load_document(db, "doc-m")
    assert after_save.revision == stale_read.revision + 1
    assert "INT. NEW SCENE - DAY" in (after_save.contentHtml or "")
    # The rename commits now.
    result = service.rename_document(db, "doc-m", "Renamed")
    assert result["document"]["title"] == "Renamed"
    reloaded = load_document(db, "doc-m")
    assert reloaded.title == "Renamed"
    assert reloaded.revision == after_save.revision  # not regressed
    assert "INT. NEW SCENE - DAY" in (reloaded.contentHtml or "")  # content intact


# ── SCENE ADD / REMOVE / MOVE on HTML-canonical documents ────────────────


def test_insert_scene_visible_in_navigator(db):
    doc = _html_doc(db)
    result = service.insert_scene(db, "doc-m", heading="INT. CORRIDOR - NIGHT")
    assert result["ok"] is True
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    assert [n["heading"] for n in nav] == [
        "INT. CAFE - DAY",
        "EXT. ROOFTOP - NIGHT",
        "INT. CORRIDOR - NIGHT",
    ]


def test_insert_scene_after_active_scene(db):
    _html_doc(db)
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    first_id = nav[0]["sceneHeadingId"]
    service.insert_scene(db, "doc-m", heading="INT. VENTURE - BRIDGE", after_scene_id=first_id)
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    assert [n["heading"] for n in nav] == [
        "INT. CAFE - DAY",
        "INT. VENTURE - BRIDGE",
        "EXT. ROOFTOP - NIGHT",
    ]


def test_delete_scene_removes_html_block(db):
    _html_doc(db)
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    target = nav[0]["sceneHeadingId"]
    result = service.delete_scene(db, "doc-m", target)
    assert result["ok"] is True
    doc = load_document(db, "doc-m")
    nav = service.navigator_scenes(doc)
    assert [n["heading"] for n in nav] == ["EXT. ROOFTOP - NIGHT"]
    # untouched scene content preserved byte-for-byte
    assert "Wind howls." in doc.contentHtml
    assert "Not tonight." in doc.contentHtml
    assert "Rain on glass." not in doc.contentHtml


def test_move_scene_reorders_html(db):
    _html_doc(db)
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    second = nav[1]["sceneHeadingId"]
    result = service.move_scene(db, "doc-m", second, to_index=0)
    assert result["ok"] is True
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    assert [n["heading"] for n in nav] == ["EXT. ROOFTOP - NIGHT", "INT. CAFE - DAY"]


def test_scene_ops_preserve_inline_formatting_outside_touched_scene(db):
    html = (
        "<h1>INT. A - DAY</h1><p>Keep <em>this</em> emphasis.</p>"
        "<h1>INT. B - DAY</h1><p>Delete me.</p>"
        "<h1>INT. C - DAY</h1><p>And <strong>this</strong> bold.</p>"
    )
    _html_doc(db, html=html)
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    service.delete_scene(db, "doc-m", nav[1]["sceneHeadingId"])
    doc = load_document(db, "doc-m")
    assert "<em>this</em>" in doc.contentHtml
    assert "<strong>this</strong>" in doc.contentHtml
    assert "Delete me." not in doc.contentHtml


def test_scene_ops_undo_restores_html(db):
    _html_doc(db)
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    service.delete_scene(db, "doc-m", nav[0]["sceneHeadingId"])
    assert len(service.navigator_scenes(load_document(db, "doc-m"))) == 1
    service.undo_last(db, "doc-m")
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    assert [n["heading"] for n in nav] == ["INT. CAFE - DAY", "EXT. ROOFTOP - NIGHT"]


# ── REVISIONS on HTML-canonical documents ────────────────────────────────


def test_revision_snapshot_captures_canonical_html_content(db):
    _html_doc(db)
    result = service.create_revision_set(db, "doc-m", name="v1", color="gold", note="first")
    rev = result["revision"]
    assert rev["contentType"] == "html"
    assert "INT. CAFE - DAY" in (rev["contentHtml"] or "")
    # snapshot elements are canonical (typed HTML), not the stale placeholder
    headings = [e["text"] for e in rev["elements"] if e["type"] == "scene_heading"]
    assert headings == ["INT. CAFE - DAY", "EXT. ROOFTOP - NIGHT"]


def test_compare_revisions_uses_canonical_content(db):
    _html_doc(db)
    r1 = service.create_revision_set(db, "doc-m", name="v1", color="gold", note="")["revision"]
    service.insert_scene(db, "doc-m", heading="INT. CORRIDOR - NIGHT")
    r2 = service.create_revision_set(db, "doc-m", name="v2", color="blue", note="")["revision"]
    diff = service.compare_revisions(db, "doc-m", r1["id"], r2["id"])
    assert diff["ok"] is True
    # the inserted scene must appear in the canonical comparison
    changed_texts = [
        (entry.get("b") or {}).get("text", "")
        for entry in diff["changed"]
    ]
    assert any("INT. CORRIDOR - NIGHT" in t for t in changed_texts)


def test_restore_revision_brings_back_html(db):
    _html_doc(db)
    rev = service.create_revision_set(db, "doc-m", name="v1", color="gold", note="")["revision"]
    nav = service.navigator_scenes(load_document(db, "doc-m"))
    service.delete_scene(db, "doc-m", nav[0]["sceneHeadingId"])
    assert len(service.navigator_scenes(load_document(db, "doc-m"))) == 1
    service.restore_revision(db, "doc-m", rev["id"])
    doc = load_document(db, "doc-m")
    nav = service.navigator_scenes(doc)
    assert [n["heading"] for n in nav] == ["INT. CAFE - DAY", "EXT. ROOFTOP - NIGHT"]
    assert "Rain on glass." in doc.contentHtml
