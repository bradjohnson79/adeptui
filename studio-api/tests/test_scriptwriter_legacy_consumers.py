"""Phase 3B — CDX-052: legacy consumers read the canonical v2 script.

Covers:
- script_search finds typed text from a v2 HTML doc (script_documents_v2) and
  falls back to legacy script_segments when no v2 content exists.
- script_get excerpts come from the canonical projection (typed HTML), never
  the stale elements snapshot.
- timeline_prep uses the v2 canonical projection for panels linked to a
  Script Writer scene (meta.scriptwriterSceneId); legacy segments remain the
  fallback.
- storyboard_jobs prompt body prefers the v2 projection for linked panels.
- scene_segment_readout() pure projection helper.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, Project, SessionLocal, engine
from app.script_storyboard import ScriptDocRow, ScriptSegmentRow, StoryboardPanelRow
from app.scriptwriter import service as sw_service
from app.scriptwriter.models import ScriptDocument, ScriptElement
from app.scriptwriter.store import save_document

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


@pytest.fixture(scope="session", autouse=True)
def _real_engine_tables():
    """Create the shared app tables once for real-engine integration tests."""
    Base.metadata.create_all(bind=engine)
    yield


def _html_doc(db, project_id: str, *, html: str = TYPED_HTML, doc_id: str) -> ScriptDocument:
    """A v2 document whose canonical content is typed HTML, while its stored
    elements still carry the default placeholder (the CDX-051 trap)."""
    doc = ScriptDocument(
        id=doc_id,
        projectId=project_id,
        title="Canonical Script",
        elements=[
            ScriptElement(id="stale1", type="scene_heading", text="INT. LOCATION - DAY", order=0, sceneNumber="1"),
            ScriptElement(id="stale2", type="action", text="", order=1),
        ],
        contentHtml=html,
        contentType="html",
    )
    save_document(db, doc)
    return doc


def _make_ctx(db, project_id: str):
    return SimpleNamespace(db=db, project_id=project_id, scene_id=None, request_id=None, capabilities={}, unlock_token=None)


def _mk_project(db, project_id: str, name: str = "Phase 3B") -> None:
    db.add(Project(id=project_id, name=name))
    db.commit()


# ── script_search: v2-first, legacy fallback (CDX-052) ────────────────────


def test_script_search_finds_typed_text_from_v2_html():
    """script_search must return the typed Script Writer text, not the stale
    legacy segment snapshot."""
    from app.codirector.tools.handlers.wave3_reads import script_search

    db = SessionLocal()
    try:
        pid = "proj-search-v2"
        _mk_project(db, pid)
        # Legacy snapshot carries different (stale) text.
        db.add(ScriptDocRow(id="legacy-doc", project_id=pid, title="Legacy"))
        db.add(
            ScriptSegmentRow(
                id="legacy-seg-1", project_id=pid, doc_id="legacy-doc", index=0,
                text="Old text from the legacy snapshot.",
            )
        )
        _html_doc(db, pid, doc_id="v2-doc-search")
        db.commit()

        ctx = _make_ctx(db, pid)
        res = asyncio.run(script_search(ctx, {"query": "We keep going."}))
        matches = res["matches"]
        assert matches, "typed dialogue must be found"
        assert all(m["scriptId"] == "v2-doc-search" for m in matches)
        assert any("We keep going." in m["excerpt"] for m in matches)
        assert not any("Old text" in m["excerpt"] for m in matches), "stale legacy text must not leak"
        assert res["_evidence"][0]["repository"] == "scriptwriter"

        # Scene headings typed in the HTML are searchable too.
        res2 = asyncio.run(script_search(ctx, {"query": "ROOFTOP"}))
        assert any("ROOFTOP" in m["excerpt"] for m in res2["matches"])
    finally:
        db.close()


def test_script_search_falls_back_to_legacy_segments_when_no_v2_doc():
    from app.codirector.tools.handlers.wave3_reads import script_search

    db = SessionLocal()
    try:
        pid = "proj-search-legacy"
        _mk_project(db, pid)
        db.add(ScriptDocRow(id=f"{pid}-doc", project_id=pid, title="Main"))
        db.add(
            ScriptSegmentRow(
                id=f"{pid}-seg-1", project_id=pid, doc_id=f"{pid}-doc", index=0,
                text="Mother Sphere rises at dawn.",
            )
        )
        db.commit()

        ctx = _make_ctx(db, pid)
        res = asyncio.run(script_search(ctx, {"query": "Mother Sphere"}))
        assert res["matches"]
        assert res["matches"][0]["scriptId"] == f"{pid}-doc"
        assert res["matches"][0]["segmentId"] == f"{pid}-seg-1"
        assert res["_evidence"][0]["repository"] == "script_storyboard"
    finally:
        db.close()


def test_script_search_blank_v2_doc_falls_back_to_legacy():
    """A v2 doc with no visible content must not shadow real legacy segments."""
    from app.codirector.tools.handlers.wave3_reads import script_search

    db = SessionLocal()
    try:
        pid = "proj-search-blank-v2"
        _mk_project(db, pid)
        db.add(ScriptDocRow(id=f"{pid}-doc", project_id=pid, title="Main"))
        db.add(
            ScriptSegmentRow(
                id=f"{pid}-seg-1", project_id=pid, doc_id=f"{pid}-doc", index=0,
                text="Only legacy text here.",
            )
        )
        # A v2 doc with NO content (no visible HTML, no elements) has
        # nothing to search -> the legacy snapshot must be used.
        blank = ScriptDocument(
            id="v2-blank", projectId=pid, title="Blank", elements=[],
            contentHtml="<p></p>", contentType="html",
        )
        save_document(db, blank)
        db.commit()

        ctx = _make_ctx(db, pid)
        res = asyncio.run(script_search(ctx, {"query": "Only legacy"}))
        assert res["matches"]
        assert res["matches"][0]["scriptId"] == f"{pid}-doc"
        assert res["_evidence"][0]["repository"] == "script_storyboard"
    finally:
        db.close()


def test_script_search_script_id_scoping_respects_both_stores():
    from app.codirector.tools.handlers.wave3_reads import script_search

    db = SessionLocal()
    try:
        pid = "proj-search-scope"
        _mk_project(db, pid)
        db.add(ScriptDocRow(id=f"{pid}-doc", project_id=pid, title="Main"))
        db.add(
            ScriptSegmentRow(
                id=f"{pid}-seg-1", project_id=pid, doc_id=f"{pid}-doc", index=0,
                text="Legacy-only needle.",
            )
        )
        _html_doc(db, pid, doc_id="v2-doc-scope")
        db.commit()

        ctx = _make_ctx(db, pid)
        # Scoping to the v2 doc searches only that doc.
        res = asyncio.run(script_search(ctx, {"query": "Legacy-only", "scriptId": "v2-doc-scope"}))
        assert res["matches"] == []
        # Scoping to the legacy doc falls back to the legacy store.
        res2 = asyncio.run(script_search(ctx, {"query": "Legacy-only", "scriptId": f"{pid}-doc"}))
        assert res2["matches"]
        assert res2["matches"][0]["scriptId"] == f"{pid}-doc"
    finally:
        db.close()


# ── script_get: canonical excerpts (CDX-051/052) ──────────────────────────


def test_script_get_excerpts_use_canonical_html_not_stale_elements():
    from app.codirector.tools.handlers.wave3_reads import script_get

    db = SessionLocal()
    try:
        pid = "proj-get-v2"
        _mk_project(db, pid)
        _html_doc(db, pid, doc_id="v2-doc-get")
        db.commit()

        ctx = _make_ctx(db, pid)
        res = asyncio.run(script_get(ctx, {"scriptId": "v2-doc-get"}))
        texts = " ".join(e["text"] for e in res["excerpts"])
        assert "INT. CAFE - DAY" in texts, "typed heading must appear"
        assert "INT. LOCATION - DAY" not in texts, "stale placeholder must not leak"
        assert res["model"] == "scriptwriter"
    finally:
        db.close()


# ── scene_segment_readout pure helper ──────────────────────────────────────


def test_scene_segment_readout_typed_html():
    db = SessionLocal()
    try:
        pid = "proj-readout"
        _mk_project(db, pid)
        doc = _html_doc(db, pid, doc_id="v2-doc-readout")
        db.commit()
        heading_id = sw_service.navigator_scenes(doc)[0]["sceneHeadingId"]
        ro = sw_service.scene_segment_readout(doc, heading_id)
        assert ro is not None
        assert ro["heading"] == "INT. CAFE - DAY"
        assert ro["dialogue"] == "We keep going."
        assert ro["action"] == "Rain on glass. A stranger enters."
        assert ro["speaker"] == "KORRI"
        assert sw_service.scene_segment_readout(doc, "no-such-scene") is None
    finally:
        db.close()


def test_scene_segment_readout_legacy_elements_doc():
    db = SessionLocal()
    try:
        pid = "proj-readout-legacy"
        _mk_project(db, pid)
        doc = ScriptDocument(
            id="v2-doc-legacy",
            projectId=pid,
            title="Legacy Elements",
            elements=[
                ScriptElement(id="s1", type="scene_heading", text="INT. BAR - NIGHT", order=0, sceneNumber="1"),
                ScriptElement(id="s2", type="action", text="Neon hums.", order=1),
                ScriptElement(id="s3", type="character", text="KORRI", order=2),
                ScriptElement(id="s4", type="dialogue", text="Pour one.", order=3),
            ],
        )
        save_document(db, doc)
        db.commit()
        ro = sw_service.scene_segment_readout(doc, "s1")
        assert ro is not None
        assert ro["heading"] == "INT. BAR - NIGHT"
        assert ro["dialogue"] == "Pour one."
        assert ro["speaker"] == "KORRI"
    finally:
        db.close()


# ── timeline_prep: v2 projection read-through (CDX-052) ───────────────────


def _seed_tp_panel(pid: str, panel_id: str, seg_id: str, meta: dict) -> None:
    # seg_id is accepted for call-site clarity; the row id is derived from the
    # panel id so the shared test DB never collides across projects.
    db = SessionLocal()
    try:
        _mk_project(db, pid)
        db.add(
            ScriptSegmentRow(
                id=f"seg-{panel_id}", project_id=pid, doc_id=f"doc-{panel_id}", index=0,
                text="Stale.", dialogue="Stale line.", scene_id="proj-scene-1",
            )
        )
        db.add(
            StoryboardPanelRow(
                id=panel_id, project_id=pid, doc_id=f"doc-{panel_id}", segment_id=f"seg-{panel_id}",
                panel_index=0, label="Panel A", status="complete", approval="draft",
                meta_json=json.dumps(meta),
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_tp_v2_doc(pid: str) -> str:
    db = SessionLocal()
    try:
        doc = _html_doc(db, pid, doc_id=f"v2-doc-{pid}")
        db.commit()
        return sw_service.navigator_scenes(doc)[0]["sceneHeadingId"]
    finally:
        db.close()


def test_timeline_prep_uses_v2_projection_for_linked_panel():
    from app.storyboard_studio.timeline_prep import prepare_timeline_from_storyboard

    pid = "proj-tp-v2"
    heading_id = _seed_tp_v2_doc(pid)
    _seed_tp_panel(pid, "panel-v2-1", "legacy-seg-1", {"scriptwriterSceneId": heading_id})

    proposal = prepare_timeline_from_storyboard(pid, panel_ids=["panel-v2-1"], approved_only=False)
    assert proposal.shots, "proposal must contain the panel shot"
    shot = proposal.shots[0]
    assert shot.dialogue == "We keep going.", "typed v2 dialogue must win over the stale legacy line"
    # sceneId field semantics unchanged: project scene id from the legacy link.
    assert shot.sceneId == "proj-scene-1"


def test_timeline_prep_falls_back_to_legacy_segment_when_no_v2_link():
    from app.storyboard_studio.timeline_prep import prepare_timeline_from_storyboard

    pid = "proj-tp-legacy"
    _seed_tp_panel(pid, "panel-legacy-1", "legacy-seg-1", {})

    proposal = prepare_timeline_from_storyboard(pid, panel_ids=["panel-legacy-1"], approved_only=False)
    assert proposal.shots
    assert proposal.shots[0].dialogue == "Stale line.", "legacy segment is the fallback"


# ── storyboard_jobs: v2 read-through in the segment region (CDX-052) ──────


def _seed_sj_panel(pid: str, panel_id: str, seg_id: str, meta: dict) -> None:
    # seg_id is accepted for call-site clarity; the row id is derived from the
    # panel id so the shared test DB never collides across projects.
    db = SessionLocal()
    try:
        _mk_project(db, pid)
        db.add(
            ScriptSegmentRow(
                id=f"seg-{panel_id}", project_id=pid, doc_id=f"doc-{panel_id}", index=0,
                text="Stale.", action="Stale action.", dialogue="Stale line.",
            )
        )
        db.add(
            StoryboardPanelRow(
                id=panel_id, project_id=pid, doc_id=f"doc-{panel_id}", segment_id=f"seg-{panel_id}",
                panel_index=0, label="Panel A", status="draft",
                meta_json=json.dumps(meta),
            )
        )
        db.commit()
    finally:
        db.close()


def _patch_generate_images(monkeypatch):
    """Replace the image-product enqueue with a recording stub."""
    import uuid

    from app.db import Job

    captured = {}

    def fake_generate_images(db, *, project_id, body):
        captured["body"] = body
        job_id = f"job-{uuid.uuid4()}"
        job = Job(id=job_id, project_id=project_id)
        db.add(job)
        db.commit()
        return {"jobId": job_id, "imageRuntime": {}, "recommendation": None}

    monkeypatch.setattr("app.image_product.service.generate_images", fake_generate_images)
    return captured


def test_storyboard_jobs_prompt_prefers_v2_projection(monkeypatch):
    from app import storyboard_jobs

    pid = "proj-sj-v2"
    heading_id = _seed_tp_v2_doc(pid)
    _seed_sj_panel(pid, "panel-sj-1", "legacy-seg-1", {"scriptwriterSceneId": heading_id})
    captured = _patch_generate_images(monkeypatch)

    db = SessionLocal()
    try:
        res = storyboard_jobs.prepare_storyboard_generate(db, pid, {"panel_id": "panel-sj-1"})
    finally:
        db.close()
    assert "We keep going." in res["params"]["prompt"], "v2 dialogue must reach the prompt"
    assert "Stale line." not in res["params"]["prompt"], "stale legacy line must not leak"
    assert captured.get("body", {}).get("prompt") == res["params"]["prompt"]


def test_storyboard_jobs_prompt_falls_back_to_legacy_segment(monkeypatch):
    from app import storyboard_jobs

    pid = "proj-sj-legacy"
    _seed_sj_panel(pid, "panel-sj-2", "legacy-seg-1", {})
    _patch_generate_images(monkeypatch)

    db = SessionLocal()
    try:
        res = storyboard_jobs.prepare_storyboard_generate(db, pid, {"panel_id": "panel-sj-2"})
    finally:
        db.close()
    assert "Stale line." in res["params"]["prompt"]


def test_ensure_scene_segment_is_write_first_and_not_a_script_read():
    """Documented boundary (CDX-052): ensure_scene_segment creates a legacy
    segment from the caller-supplied prompt — it never reads canonical script
    text, so no v2 projection is warranted there."""
    from app.storyboard_jobs import ensure_scene_segment

    pid = "proj-sj-boundary"
    db = SessionLocal()
    try:
        _mk_project(db, pid)
        seg = ensure_scene_segment(db, pid, "scene-x", prompt="Executive prompt text")
        assert seg.scene_id == "scene-x"
        assert seg.text == "Executive prompt text"
        assert seg.action == "Executive prompt text"
    finally:
        db.close()
