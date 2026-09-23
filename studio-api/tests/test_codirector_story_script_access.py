"""Co-Director Story + Script access — live, canonical, current-scene aware.

Mission gates covered here:
- CO-DIRECTOR STORY ACCESS: project.read_context "story" pillar reads the
  canonical story_entries store (previously DISCONNECTED — it read the legacy
  freeform story document, which real projects never use).
- CO-DIRECTOR SCRIPT ACCESS: the "script" pillar reads the canonical content
  projection (typed HTML), not the stale stored elements (CDX-051 trap).
- LIVE CONTEXT FRESHNESS: story_script_context_block reads the stores on
  every call — an edit made after the last turn is visible in the next turn's
  context.
- CURRENT SCENE AWARENESS: passing a scriptwriter scene id surfaces that
  scene's heading/action/dialogue and marks it in the scene list.
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
from app.codirector.context_enrichment import story_script_context_block
from app.codirector.project_context import retrieve_project_context
from app.scriptwriter import service as sw_service
from app.scriptwriter.models import ScriptDocument, ScriptElement
from app.scriptwriter.store import save_document
from app.story import store as legacy_story_store  # noqa: F401 — registers story_documents table
from app.story_entries.models import StoryEntryCreate
from app.story_entries.store import create_entry, ensure_primary_entry, list_entries

TYPED_HTML = (
    "<h1>INT. CAFE - DAY</h1>"
    "<p>Rain on glass. A stranger enters.</p>"
    '<p style="margin-left: 240px">KORRI</p>'
    '<p style="margin-left: 240px">We keep going.</p>'
    "<h1>EXT. ROOFTOP - NIGHT</h1>"
    "<p>Wind howls.</p>"
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


def _script(db, *, html=TYPED_HTML) -> ScriptDocument:
    doc = ScriptDocument(
        id="doc-1",
        projectId="proj-a",
        title="The Adept Chronicles",
        # Stale placeholder elements — the CDX-051 trap. Canonical content is the HTML.
        elements=[
            ScriptElement(id="stale1", type="scene_heading", text="INT. LOCATION - DAY", order=0, sceneNumber="1"),
        ],
        contentHtml=html,
        contentType="html",
    )
    save_document(db, doc)
    return doc


# ── CO-DIRECTOR STORY ACCESS ──────────────────────────────────────────────


def test_story_pillar_reads_story_entries(db):
    create_entry(db, "proj-a", StoryEntryCreate(
        title="The Adept Chronicles",
        entryType="project_story",
        logline="A pilot who outran a dying star.",
        shortSummary="Korri flees the collapse of her home system.",
        longSummary="Act one: the fall. Act two: the corridor run.",
    ))
    ctx = retrieve_project_context(db, "proj-a", pillars=["story"])
    story = ctx["story"]
    assert story is not None
    assert story["source"] == "story_entries"
    assert story["entries"][0]["logline"] == "A pilot who outran a dying star."
    assert "corridor run" in story["entries"][0]["longSummary"]


def test_ensure_primary_reuses_existing_entry(db):
    first = create_entry(db, "proj-a", StoryEntryCreate(title="The Venture — Story", entryType="project_story"))
    again = ensure_primary_entry(db, "proj-a", title="Should not create")
    assert again.id == first.id
    assert len(list_entries(db, "proj-a")) == 1


def test_ensure_primary_creates_one_row_when_empty(db):
    row = ensure_primary_entry(db, "proj-a", title="The Venture — Story")
    assert row.title == "The Venture — Story"
    assert row.entry_type == "project_story"
    assert len(list_entries(db, "proj-a")) == 1
    assert ensure_primary_entry(db, "proj-a").id == row.id


def test_context_block_reads_html_story_document(db):
    create_entry(db, "proj-a", StoryEntryCreate(
        title="The Venture — Story",
        entryType="project_story",
        longSummary="<h2>Synopsis</h2><p>Korri and Anadriya walk the corridor.</p>",
    ))
    block = story_script_context_block(db, "proj-a")
    assert "Korri and Anadriya walk the corridor" in block
    assert "<h2>" not in block


def test_story_pillar_falls_back_to_legacy_only_when_no_entries(db):
    legacy_story_store.save_document(db, "proj-a", "Legacy Story", "Legacy freeform content.")
    ctx = retrieve_project_context(db, "proj-a", pillars=["story"])
    assert ctx["story"] is not None
    assert ctx["story"]["source"] == "legacy_story"
    # Once a canonical entry exists, it wins over the legacy document.
    create_entry(db, "proj-a", StoryEntryCreate(title="Canonical", entryType="project_story"))
    ctx = retrieve_project_context(db, "proj-a", pillars=["story"])
    assert ctx["story"]["source"] == "story_entries"


# ── CO-DIRECTOR SCRIPT ACCESS ─────────────────────────────────────────────


def test_script_pillar_reads_canonical_html_projection(db):
    _script(db)
    ctx = retrieve_project_context(db, "proj-a", pillars=["script"])
    script = ctx["script"]
    assert script is not None
    assert script["title"] == "The Adept Chronicles"
    headings = [s["text"] for s in script["scenes"]]
    # Canonical typed scenes — never the stale placeholder.
    assert headings == ["INT. CAFE - DAY", "EXT. ROOFTOP - NIGHT"]
    assert "INT. LOCATION - DAY" not in headings


# ── LIVE CONTEXT FRESHNESS ────────────────────────────────────────────────


def test_context_block_sees_edits_made_after_last_turn(db):
    _script(db)
    block1 = story_script_context_block(db, "proj-a")
    assert "INT. CAFE - DAY" in block1
    # Creator edits the script (a scene op on the canonical HTML).
    sw_service.insert_scene(db, "doc-1", heading="INT. CORRIDOR - NIGHT")
    block2 = story_script_context_block(db, "proj-a")
    assert "INT. CORRIDOR - NIGHT" in block2
    # Creator edits the story.
    create_entry(db, "proj-a", StoryEntryCreate(
        title="Story", entryType="project_story", logline="Fresh logline about Korri.",
    ))
    block3 = story_script_context_block(db, "proj-a")
    assert "Fresh logline about Korri" in block3


def test_context_block_empty_project_returns_empty(db):
    assert story_script_context_block(db, "proj-a") == ""
    assert story_script_context_block(db, None) == ""


# ── CURRENT SCENE AWARENESS ───────────────────────────────────────────────


def test_current_scene_readout_and_marker(db):
    _script(db)
    nav = sw_service.navigator_scenes(sw_service.get_document(db, "doc-1"))
    cafe_id = nav[0]["sceneHeadingId"]
    block = story_script_context_block(
        db, "proj-a", active_document_id="doc-1", scriptwriter_scene_id=cafe_id,
    )
    assert "← current" in block
    assert "Current scene the creator is editing: INT. CAFE - DAY" in block
    assert "We keep going." in block  # canonical dialogue from typed HTML


def test_current_scene_unknown_id_still_lists_scenes(db):
    _script(db)
    block = story_script_context_block(db, "proj-a", scriptwriter_scene_id="html-scene-nonexistent")
    assert "INT. CAFE - DAY" in block
    assert "← current" not in block


# ── PLATFORM-HELP vs PROJECT-CONTENT ROUTING ──────────────────────────────
# Regression for the _PROJECT_CONTENT_Q over-match: platform how-to questions
# containing "the script"/"the story" must still reach the curated platform
# reply, not the LLM content path.


def test_platform_help_questions_are_not_content_questions():
    from app.codirector.service import _is_project_content_question

    for msg in (
        "How do I use the script writer?",
        "How to add a scene in the script writer?",
        "Where is the story tab?",
        "Where do I find the script?",
        "What is Adept?",
        "How does Adept work?",
        "Is there a way to export the script?",
    ):
        assert _is_project_content_question(msg, "proj-a") is False, msg


def test_project_content_questions_still_route_to_llm():
    from app.codirector.service import _is_project_content_question

    for msg in (
        "What happens in the script right now?",
        "What does the current story say?",
        "What is the first scene heading in the current script?",
        "Does the story need a stronger midpoint?",
        "What is the hero's motivation in this scene?",
        "Punch up my dialogue in the current scene",
    ):
        assert _is_project_content_question(msg, "proj-a") is True, msg
    # Unbound chat never takes the project-content path.
    assert _is_project_content_question("What happens in the script?", None) is False
