"""Phase 3 — Script Writer canonical content + project scoping (CDX-051/053).

Covers:
- Typed HTML drives the navigator scene list (not the default placeholder).
- Stats (scenes/words) match the typed HTML content.
- analyze_scene / prepare_timeline use the typed dialogue.
- document-level routes reject cross-project access with
  404/PROJECT_SCOPE_VIOLATION (GET, autosave, insert, undo, revisions, ...).
- project_segments() returns the canonical scene/segment projection.
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
from app.scriptwriter.htmltext import document_text, html_scene_elements
from app.scriptwriter.models import ScriptDocument, ScriptElement
from app.scriptwriter.stats import compute_stats
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

TIPTAP_HTML = (
    "<h1>INT. LAB - DAY</h1>"
    '<p data-indent="240">ARIA</p>'
    '<p data-indent="240">Stay with me.</p>'
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
    session.add(Project(id="proj-b", name="Project B"))
    session.commit()
    yield session
    session.close()


def _html_doc(db, *, project_id="proj-a", html=TYPED_HTML, doc_id="doc-canon") -> ScriptDocument:
    """A v2 document whose canonical content is typed HTML, while its stored
    elements still carry the default placeholder (the CDX-051 trap)."""
    doc = ScriptDocument(
        id=doc_id,
        projectId=project_id,
        title="Canonical Test",
        elements=[
            ScriptElement(id="stale1", type="scene_heading", text="INT. LOCATION - DAY", order=0, sceneNumber="1"),
            ScriptElement(id="stale2", type="action", text="", order=1),
        ],
        contentHtml=html,
        contentType="html",
    )
    save_document(db, doc)
    return doc


# ── CDX-051: navigator / stats / analysis / timeline from typed HTML ──────


def test_navigator_lists_typed_html_scenes(db):
    """Typing 2+ scenes must list those scenes — never the placeholder."""
    doc = _html_doc(db)
    nav = service.navigator_scenes(doc)
    assert [n["heading"] for n in nav] == ["INT. CAFE - DAY", "EXT. ROOFTOP - NIGHT"]
    ids = [n["sceneHeadingId"] for n in nav]
    assert len(ids) == 2
    assert all(i.startswith("html-scene-") for i in ids)
    assert ids[0] != ids[1], "distinct scenes must have distinct ids"
    # ids are deterministic: same content -> same id (survives reload)
    nav2 = service.navigator_scenes(doc)
    assert [n["sceneHeadingId"] for n in nav2] == ids
    # not the placeholder
    assert "INT. LOCATION - DAY" not in [n["heading"] for n in nav]


def test_stats_match_typed_html_content(db):
    """Scene/word stats must reflect the typed HTML, not stale elements."""
    doc = _html_doc(db)
    stats = compute_stats(doc)
    assert stats.scenes == 2
    assert stats.words == len(document_text(doc).split())
    assert stats.words > 0
    assert stats.dialoguePercent > 0, "typed dialogue must count toward dialogue share"
    assert stats.actionPercent > 0, "typed action must count toward action share"
    assert stats.characters == 2, "KORRI and JACE detected from HTML"
    # the stale placeholder (1 scene) must not leak in
    assert stats.scenes != 1


def test_analyze_scene_and_timeline_prep_use_typed_dialogue(db):
    doc = _html_doc(db)
    scene_id = service.navigator_scenes(doc)[0]["sceneHeadingId"]

    analysis = service.analyze_scene(db, doc.id, scene_id)
    assert analysis["analysis"]["characters"] == ["KORRI"]
    assert analysis["analysis"]["dialogueLines"] == 1
    assert "Rain on glass" in analysis["analysis"]["scenePurpose"]

    prep = service.prepare_timeline(db, doc.id, scene_id)
    proposal = prep["proposal"]
    assert proposal["sceneHeading"] == "INT. CAFE - DAY"
    assert proposal["characters"] == ["KORRI"]
    assert proposal["actionBeats"] == ["Rain on glass. A stranger enters."]
    assert len(proposal["dialogue"]) == 1
    assert proposal["dialogue"][0]["text"] == "We keep going."
    assert proposal["dialogue"][0]["speaker"] == "KORRI"
    assert proposal["lipSyncNeeded"] is True
    assert "dialogue track" in proposal["audioRequirements"]


def test_tiptap_style_html_parses_indented_dialogue(db):
    """TipTap renders indentation as data-indent + margin-left; both must parse."""
    doc = _html_doc(db, html=TIPTAP_HTML, doc_id="doc-tiptap")
    nav = service.navigator_scenes(doc)
    assert [n["heading"] for n in nav] == ["INT. LAB - DAY"]
    prep = service.prepare_timeline(db, doc.id, nav[0]["sceneHeadingId"])
    assert prep["proposal"]["characters"] == ["ARIA"]
    assert prep["proposal"]["dialogue"][0]["text"] == "Stay with me."
    assert prep["proposal"]["dialogue"][0]["speaker"] == "ARIA"


def test_html_scene_elements_marks_speaker_metadata(db):
    els = html_scene_elements(TYPED_HTML)
    dialogue = [e for e in els if e.type == "dialogue"]
    assert [e.metadata.get("speaker") for e in dialogue] == ["KORRI", "JACE"]


def test_legacy_elements_docs_unaffected(db):
    """Elements-mode documents keep using their stored elements."""
    doc = ScriptDocument(
        id="doc-legacy",
        projectId="proj-a",
        elements=[
            ScriptElement(id="l1", type="scene_heading", text="INT. BAR - NIGHT", order=0, sceneNumber="1"),
            ScriptElement(id="l2", type="action", text="Neon hums.", order=1),
        ],
    )
    save_document(db, doc)
    nav = service.navigator_scenes(doc)
    assert [n["heading"] for n in nav] == ["INT. BAR - NIGHT"]
    stats = compute_stats(doc)
    assert stats.scenes == 1


# ── CDX-052 projection: canonical v2 -> segments (pure, no writes) ─────────


def test_projection_returns_canonical_scenes_from_html(db):
    doc = _html_doc(db)
    segs = service.project_segments(doc)
    types = [s["segmentType"] for s in segs]
    assert types.count("scene_heading") == 2
    assert types.count("dialogue") == 2
    assert [s["sceneNumber"] for s in segs if s["segmentType"] == "scene_heading"] == ["1", "2"]
    dialogue = [s for s in segs if s["segmentType"] == "dialogue"]
    assert [d["speaker"] for d in dialogue] == ["KORRI", "JACE"]
    assert [d["text"] for d in dialogue] == ["We keep going.", "Not tonight."]
    heading = [s for s in segs if s["segmentType"] == "scene_heading"][0]
    assert heading["location"] == "CAFE"
    assert heading["timeOfDay"] == "DAY"
    assert heading["source"] == "scriptwriter:v2"
    # pure: the projection performs no writes
    reloaded = load_document(db, doc.id)
    assert reloaded.contentHtml == TYPED_HTML


def test_projection_from_legacy_elements(db):
    doc = ScriptDocument(
        id="doc-legacy2",
        projectId="proj-a",
        elements=[
            ScriptElement(id="s1", type="scene_heading", text="INT. BAR - NIGHT", order=0, sceneNumber="1"),
            ScriptElement(id="s2", type="action", text="Neon hums.", order=1),
            ScriptElement(id="s3", type="character", text="KORRI", order=2),
            ScriptElement(id="s4", type="dialogue", text="Pour one.", order=3),
        ],
    )
    save_document(db, doc)
    segs = service.project_segments(doc)
    dialogue = [s for s in segs if s["segmentType"] == "dialogue"]
    assert len(dialogue) == 1
    assert dialogue[0]["speaker"] == "KORRI"
    assert dialogue[0]["text"] == "Pour one."


# ── CDX-053: document routes are project-scoped ────────────────────────────


@pytest.fixture(autouse=True)
def _e2e_on(monkeypatch):
    monkeypatch.setenv("STUDIO_E2E", "1")


def _mk_project(client, name: str):
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()


def _assert_scope_violation(resp, label: str):
    assert resp.status_code == 404, f"{label}: expected 404, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert detail["code"] == "PROJECT_SCOPE_VIOLATION", f"{label}: {resp.text}"


def test_document_routes_reject_cross_project_access(client):
    a = _mk_project(client, "Scope A")
    b = _mk_project(client, "Scope B")
    created = client.post(f"/api/projects/{a['id']}/scriptwriter/documents")
    assert created.status_code == 200, created.text
    doc_id = created.json()["document"]["id"]
    path = f"/api/projects/{b['id']}/scriptwriter/documents/{doc_id}"

    _assert_scope_violation(client.get(path), "GET document")
    _assert_scope_violation(
        client.post(f"{path}/autosave", json={"html": "<p>sneak</p>"}), "autosave"
    )
    _assert_scope_violation(
        client.post(f"{path}/scenes/insert", json={"heading": "INT. X - DAY"}), "insert scene"
    )
    _assert_scope_violation(client.post(f"{path}/undo"), "undo")
    _assert_scope_violation(
        client.post(f"{path}/revisions", json={"name": "Blue"}), "create revision"
    )
    _assert_scope_violation(
        client.post(f"{path}/recovery/restore"), "recovery restore"
    )
    _assert_scope_violation(
        client.post(f"{path}/scenes/delete", json={"sceneHeadingId": "x"}), "delete scene"
    )
    _assert_scope_violation(
        client.post(f"{path}/scenes/move", json={"sceneHeadingId": "x", "toIndex": 1}), "move scene"
    )
    _assert_scope_violation(
        client.post(f"{path}/timeline/prepare", json={"sceneHeadingId": "x"}), "timeline prepare"
    )
    _assert_scope_violation(
        client.post(f"{path}/timeline/apply-metadata", json={"sceneHeadingId": "x"}), "timeline apply"
    )
    _assert_scope_violation(
        client.post(f"{path}/analyze/scene", json={"sceneHeadingId": "x"}), "analyze scene"
    )
    _assert_scope_violation(
        client.post(f"{path}/search-replace", json={"find": "a", "replace": "b"}), "search-replace"
    )
    _assert_scope_violation(client.post(f"{path}/bible/propose"), "bible propose")

    # the owning project is unaffected (positive control)
    own = client.get(f"/api/projects/{a['id']}/scriptwriter/documents/{doc_id}")
    assert own.status_code == 200, own.text
    assert own.json()["document"]["id"] == doc_id

    # a truly unknown document under the right project stays 400 SCRIPT_LOAD_FAILED
    missing = client.get(f"/api/projects/{a['id']}/scriptwriter/documents/no-such-id")
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == "SCRIPT_LOAD_FAILED"


def test_cross_project_cannot_mutate_owning_document(client):
    """The scope violation must not corrupt the owning project doc."""
    a = _mk_project(client, "Mutate A")
    b = _mk_project(client, "Mutate B")
    created = client.post(f"/api/projects/{a['id']}/scriptwriter/documents")
    doc_id = created.json()["document"]["id"]
    rev_before = created.json()["document"]["revision"]

    r = client.post(
        f"/api/projects/{b['id']}/scriptwriter/documents/{doc_id}/autosave",
        json={"html": "<h1>EXT. EVIL - NIGHT</h1><p>Hijacked.</p>"},
    )
    _assert_scope_violation(r, "cross-project autosave")

    own = client.get(f"/api/projects/{a['id']}/scriptwriter/documents/{doc_id}").json()
    assert own["document"]["revision"] == rev_before
    assert own["document"]["contentHtml"] is None or "EVIL" not in own["document"]["contentHtml"]


