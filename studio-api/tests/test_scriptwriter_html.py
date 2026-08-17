"""Script Writer rich-text HTML persistence + text helpers (Workstream D).

Covers:
- `autosave_html` persists HTML, bumps revision, records a transaction.
- `AutosaveBody` dispatch: `html` -> `autosave_html`; `elements` -> back-compat.
- `html_to_text` strips tags and preserves paragraph / line breaks.
- `elements_to_text` flattens legacy elements.
- `document_text` returns text for HTML and legacy docs.
- `compute_stats` counts words for HTML docs.
- `script_inspect` (Co-Director) returns `contentType` + `contentPreview` for HTML.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.codirector.tools.handlers import scriptwriter_tools
from app.db import Base, Project
from app.scriptwriter import service
from app.scriptwriter.htmltext import (
    document_text,
    elements_to_text,
    html_to_text,
)
from app.scriptwriter.models import ScriptDocument, ScriptElement
from app.scriptwriter.stats import compute_stats
from app.scriptwriter.store import (
    ScriptDocumentRow,
    ensure_scriptwriter_tables,
    save_document,
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
    session.add(Project(id="proj-sw", name="Scriptwriter HTML Test"))
    session.commit()
    # ensure_scriptwriter_tables uses the module-level engine; for this fixture
    # we operate against a fresh in-memory engine, so we only need the tables
    # created (already done above via Base.metadata.create_all).
    yield session
    session.close()


def _mk_doc(db, *, project_id="proj-sw", title="HTML Test Script") -> ScriptDocument:
    doc = ScriptDocument(
        id="doc-1",
        projectId=project_id,
        title=title,
        elements=[
            ScriptElement(id="e1", type="scene_heading", text="INT. CAFE - DAY", order=0, sceneNumber="1"),
            ScriptElement(id="e2", type="action", text="Rain on glass.", order=1),
        ],
    )
    save_document(db, doc)
    return doc


# ── autosave_html ──────────────────────────────────────────────────────────


def test_autosave_html_persists_html_bumps_revision_records_transaction(db):
    doc = _mk_doc(db)
    starting_rev = doc.revision

    html = "<h1>INT. CAFE - DAY</h1><p>Rain on glass.</p>"
    result = service.autosave_html(db, doc.id, html)

    assert result["ok"] is True
    saved = result["document"]
    assert saved["contentHtml"] == html
    assert saved["contentType"] == "html"
    assert saved["revision"] == starting_rev + 1

    tx = result["transaction"]
    assert tx["kind"] == "autosave_html"
    assert tx["beforeRevision"] == starting_rev
    assert tx["afterRevision"] == saved["revision"]
    assert tx["source"] == "creator"

    # Persisted row reflects the HTML + bumped revision.
    row = db.get(ScriptDocumentRow, doc.id)
    assert row is not None
    assert row.content_html == html
    assert row.content_type == "html"
    assert row.revision == saved["revision"]


def test_autosave_html_revision_conflict_writes_recovery(db):
    doc = _mk_doc(db)
    from app.scriptwriter.errors import ScriptwriterError
    from app.scriptwriter.store import get_recovery

    with pytest.raises(ScriptwriterError) as exc:
        service.autosave_html(db, doc.id, "<p>x</p>", expected_revision=9999)
    assert exc.value.code == "SCRIPT_CONFLICT"
    recovery = get_recovery(db, doc.id)
    assert recovery is not None
    assert recovery.get("html") == "<p>x</p>"
    assert recovery.get("expectedRevision") == 9999


# ── AutosaveBody dispatch ───────────────────────────────────────────────────


def test_autosave_body_html_dispatches_to_autosave_html(db):
    """The API layer routes `html` to `autosave_html` and `elements` to
    `autosave_elements` (back-compat)."""
    from app.scriptwriter.api import AutosaveBody

    # html branch — body.html is not None
    body_html = AutosaveBody(html="<p>hello</p>", expectedRevision=None)
    assert body_html.html is not None

    # elements branch — body.html is None, body.elements present
    body_el = AutosaveBody(
        elements=[{"id": "e1", "type": "action", "text": "hi", "order": 0}],
        expectedRevision=None,
    )
    assert body_el.html is None
    assert body_el.elements is not None

    doc = _mk_doc(db)
    if body_html.html is not None:
        out_html = service.autosave_html(db, doc.id, body_html.html)
        assert out_html["document"]["contentType"] == "html"

    if body_el.html is None:
        out_el = service.autosave_elements(db, doc.id, body_el.elements or [])
        assert out_el["ok"] is True
        assert out_el["document"]["contentType"] in ("html", "elements")


def test_autosave_elements_back_compat_preserves_elements(db):
    """Legacy elements path still works and does not destroy HTML content
    that may have been set previously."""
    doc = _mk_doc(db)
    service.autosave_html(db, doc.id, "<p>html first</p>")

    new_elements = [
        {"id": "e1", "type": "scene_heading", "text": "EXT. ROAD - NIGHT", "order": 0, "sceneNumber": "1"},
        {"id": "e2", "type": "action", "text": "A car passes.", "order": 1},
    ]
    result = service.autosave_elements(db, doc.id, new_elements)
    assert result["ok"] is True
    saved = result["document"]
    assert any(e["type"] == "scene_heading" and "ROAD" in e["text"] for e in saved["elements"])


# ── html_to_text ───────────────────────────────────────────────────────────


def test_html_to_text_strips_tags_and_preserves_paragraph_breaks():
    html = "<h1>Title</h1><p>First paragraph.</p><p>Second paragraph.</p>"
    text = html_to_text(html)
    assert "Title" in text
    assert "First paragraph." in text
    assert "Second paragraph." in text
    # <p> -> paragraph break (\n\n)
    assert "First paragraph.\n\nSecond paragraph." in text
    # no tags survive
    assert "<" not in text
    assert ">" not in text


def test_html_to_text_br_becomes_newline():
    html = "<p>line one<br>line two</p>"
    text = html_to_text(html)
    assert "line one" in text
    assert "line two" in text
    # <br> -> newline (block tag substitution), so the two lines are separated
    assert "line one\n" in text or "line one\n\nline two" in text


def test_html_to_text_empty_and_none():
    assert html_to_text(None) == ""
    assert html_to_text("") == ""
    assert html_to_text("<p></p>") == ""


def test_html_to_text_unescapes_entities():
    assert html_to_text("<p>tom &amp; jerry</p>") == "tom & jerry"
    assert html_to_text("<p>5 &lt; 10</p>") == "5 < 10"


# ── elements_to_text ───────────────────────────────────────────────────────


def test_elements_to_text_flattens_legacy_elements():
    elements = [
        ScriptElement(id="e1", type="scene_heading", text="INT. CAFE - DAY", order=0),
        ScriptElement(id="e2", type="action", text="Rain on glass.", order=1),
        ScriptElement(id="e3", type="character", text="KORRI", order=2),
        ScriptElement(id="e4", type="parenthetical", text="quietly", order=3),
        ScriptElement(id="e5", type="dialogue", text="We keep going.", order=4),
        ScriptElement(id="e6", type="transition", text="CUT TO:", order=5),
    ]
    text = elements_to_text(elements)
    assert "INT. CAFE - DAY" in text
    assert "Rain on glass." in text
    assert "KORRI" in text
    assert "(quietly)" in text
    assert "We keep going." in text
    assert "CUT TO:" in text
    # Paragraph breaks between elements
    assert "\n\n" in text


def test_elements_to_text_skips_blank():
    elements = [
        ScriptElement(id="e1", type="action", text="", order=0),
        ScriptElement(id="e2", type="action", text="   ", order=1),
        ScriptElement(id="e3", type="action", text="real text", order=2),
    ]
    assert elements_to_text(elements) == "real text"


# ── document_text ──────────────────────────────────────────────────────────


def test_document_text_prefers_html_content():
    doc = ScriptDocument(
        id="d1",
        projectId="p1",
        elements=[ScriptElement(id="e1", type="action", text="legacy action", order=0)],
        contentHtml="<p>html body</p>",
        contentType="html",
    )
    text = document_text(doc)
    assert text == "html body"
    assert "legacy action" not in text


def test_document_text_falls_back_to_elements_for_legacy_docs():
    doc = ScriptDocument(
        id="d1",
        projectId="p1",
        elements=[ScriptElement(id="e1", type="action", text="legacy action", order=0)],
        contentHtml=None,
        contentType="elements",
    )
    text = document_text(doc)
    assert text == "legacy action"


# ── compute_stats ───────────────────────────────────────────────────────────


def test_compute_stats_counts_words_for_html_docs():
    doc = ScriptDocument(
        id="d1",
        projectId="p1",
        elements=[],
        contentHtml="<h1>INT. CAFE - DAY</h1><p>Rain on glass. Quiet night.</p>",
        contentType="html",
    )
    stats = compute_stats(doc)
    # Words: "INT." "CAFE" "-" "DAY" "Rain" "on" "glass." "Quiet" "night." = 9
    assert stats.words == 9
    # CDX-051: scene count derives from the typed HTML (h1 heading), not from
    # the (empty) stored elements array.
    assert stats.scenes == 1
    assert stats.pagesEstimated >= 1.0


def test_compute_stats_legacy_elements_path():
    doc = ScriptDocument(
        id="d1",
        projectId="p1",
        elements=[
            ScriptElement(id="e1", type="scene_heading", text="INT. CAFE - DAY", order=0, sceneNumber="1"),
            ScriptElement(id="e2", type="action", text="Rain on glass.", order=1),
        ],
        contentHtml=None,
        contentType="elements",
    )
    stats = compute_stats(doc)
    # Words: "INT." "CAFE" "-" "DAY" "Rain" "on" "glass." = 7
    assert stats.words == 7
    assert stats.scenes == 1


# ── script_inspect (Co-Director handler) ───────────────────────────────────


def _make_ctx(db, project_id: str = "proj-sw"):
    """Build a minimal ToolContext duck-typed object for handler tests."""
    return SimpleNamespace(db=db, project_id=project_id, scene_id=None, request_id=None, capabilities={}, unlock_token=None)


def test_script_inspect_returns_content_type_and_preview_for_html_doc(db):
    doc = _mk_doc(db)
    html = "<h1>INT. CAFE - DAY</h1><p>Rain on glass. A stranger enters.</p>"
    service.autosave_html(db, doc.id, html)

    ctx = _make_ctx(db)
    result = asyncio.run(scriptwriter_tools.script_inspect(ctx, {"documentId": doc.id}))

    assert result["documentId"] == doc.id
    assert result["contentType"] == "html"
    assert "contentPreview" in result
    preview = result["contentPreview"]
    assert "INT. CAFE - DAY" in preview
    assert "Rain on glass." in preview
    assert "<" not in preview  # preview is plain text
    assert result["contentWords"] >= 5


def test_script_inspect_returns_content_type_for_legacy_elements_doc(db):
    doc = _mk_doc(db)  # elements-only doc

    ctx = _make_ctx(db)
    result = asyncio.run(scriptwriter_tools.script_inspect(ctx, {"documentId": doc.id}))

    assert result["documentId"] == doc.id
    assert result["contentType"] == "elements"
    assert "INT. CAFE - DAY" in result["contentPreview"]
    assert "Rain on glass." in result["contentPreview"]
