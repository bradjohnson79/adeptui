"""Unit tests for the Refine Wiki creator-correction system.

Covers: heuristic classification of every correction type, ambiguity →
clarification, merge alias writes, supersede-not-erase, demote-to-notes, undo
restore, creator-authority precedence, project isolation, character-section
purity (location/attribute/organization reclassification), and correction
memory influencing later extraction.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.conversation.schemas import WikiCandidate
from app.codirector.conversation.snapshot import load_snapshot, save_snapshot
from app.codirector.notes.service import demote_wiki_to_note
from app.codirector.wiki_intelligence.classification import classify_entity_type
from app.codirector.wiki_intelligence.compiled.character_compiler import resolve_characters
from app.codirector.wiki_intelligence.correction import memory
from app.codirector.wiki_intelligence.correction.apply import apply_correction, list_corrections
from app.codirector.wiki_intelligence.correction.classify import (
    _heuristic_classify,
    classify_correction,
)
from app.codirector.wiki_intelligence.correction.contracts import (
    CoDirectorLearnedCorrection,
    CorrectionPreview,
    CorrectionTarget,
    EntityReclassification,
)
from app.codirector.wiki_intelligence.correction.undo import undo_correction
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


def _seed(db, project_id: str, entries: list[WikiCandidate]) -> None:
    snapshot = load_snapshot(db, project_id)
    snapshot.knowledgeEntries = list(entries)
    save_snapshot(db, snapshot)


def _entry(id: str, text: str, section: str = "characters", state: str = "confirmed", prov: str = "") -> WikiCandidate:
    return WikiCandidate(id=id, text=text, state=state, section=section, provenance=prov)


# --- Heuristic classification -------------------------------------------------


def test_classify_location_reclassification():
    snapshot = load_snapshot  # not needed; heuristic works on a stub
    result = _heuristic_classify("Gakona is a location, not a character.", _StubSnapshot())
    assert result["correctionType"] == "RECLASSIFY"
    assert result["entityReclassifications"][0]["toType"] == "location"
    assert "Gakona" in result["learnedRule"]


def test_classify_organization_reclassification():
    result = _heuristic_classify("The FBI is an organization, not a character.", _StubSnapshot())
    assert result["correctionType"] == "RECLASSIFY"
    assert result["entityReclassifications"][0]["toType"] == "organization"


def test_classify_age_is_attribute():
    result = _heuristic_classify("Barnes is age 55.", _StubSnapshot())
    assert result["correctionType"] == "RECLASSIFY"
    assert result["entityReclassifications"][0]["toType"] == "attribute"
    assert result["entityReclassifications"][0]["attachTo"] == "Barnes"


def test_classify_merge():
    result = _heuristic_classify("Merge Barnes and Special Agent Barnes — they are the same person.", _StubSnapshot())
    assert result["correctionType"] == "MERGE"
    assert result["aliases"]


def test_classify_remove():
    result = _heuristic_classify('Remove "Gakona" from the Wiki.', _StubSnapshot())
    assert result["correctionType"] == "REMOVE"


def test_classify_summary_correction():
    result = _heuristic_classify("The summary is wrong about Barnes believing Kyung.", _StubSnapshot())
    assert result["correctionType"] == "SUMMARY_CORRECTION"
    assert result["summaryRecompile"] is True


def test_classify_ambiguity_asks_clarification():
    result = _heuristic_classify("Change the character.", _StubSnapshot())
    assert result["clarificationQuestion"]


class _StubSnapshot:
    knowledgeEntries: list = []
    compiledWiki: dict = {}


# --- classify_correction (async, heuristic fallback) ---------------------------


def test_classify_correction_returns_preview(db):
    preview = asyncio.run(
        classify_correction(
            db,
            "proj-a",
            "Gakona is a location, not a character.",
            target=CorrectionTarget(pageType="CHARACTER", label="Gakona"),
            provider=None,
            preview_id="prev_test1",
        )
    )
    assert isinstance(preview, CorrectionPreview)
    assert preview.correctionType == "RECLASSIFY"
    assert preview.entityReclassifications[0].toType == "location"
    assert preview.proposedChanges


# --- Apply: supersede-not-erase + confirmed creator record --------------------


def test_apply_reclassify_supersedes_and_creates(db):
    _seed(
        db,
        "proj-a",
        [_entry("e1", "Gakona is a covert operative.", section="characters", state="confirmed")],
    )
    preview = CorrectionPreview(
        previewId="prev_apply1",
        projectId="proj-a",
        instruction="Gakona is a location, not a character.",
        correctionType="RECLASSIFY",
        entityReclassifications=[
            EntityReclassification(name="Gakona", fromType="character", toType="location")
        ],
        learnedRule="Gakona is a location, not a character.",
    )
    result = apply_correction(db, "proj-a", preview)
    assert result["ok"] is True
    assert result["supersededCount"] >= 1
    snapshot = load_snapshot(db, "proj-a")
    old = next(e for e in snapshot.knowledgeEntries if e.id == "e1")
    # Superseded, never erased (provenance preserved).
    assert old.state == "superseded"
    # New confirmed creator record exists with explicit-write provenance.
    new = [e for e in snapshot.knowledgeEntries if e.id != "e1"]
    assert any("explicit_wiki_write" in (e.provenance or "") for e in new)


def test_apply_merge_writes_alias_to_memory(db):
    _seed(db, "proj-a", [_entry("e1", "Special Agent Barnes appears.", section="characters")])
    preview = CorrectionPreview(
        previewId="prev_apply2",
        projectId="proj-a",
        instruction="Merge Special Agent Barnes into Barnes.",
        correctionType="MERGE",
        aliases={"Special Agent Barnes": "Barnes"},
        learnedRule="Special Agent Barnes and Barnes are the same identity.",
    )
    result = apply_correction(db, "proj-a", preview)
    assert result["ok"] is True
    aliases = memory.active_aliases(db, "proj-a")
    assert aliases.get("Special Agent Barnes") == "Barnes"


def test_apply_persists_learned_correction_entity_override(db):
    _seed(db, "proj-a", [])
    preview = CorrectionPreview(
        previewId="prev_apply3",
        projectId="proj-a",
        instruction="Gakona is a location.",
        correctionType="RECLASSIFY",
        entityReclassifications=[
            EntityReclassification(name="Gakona", fromType="character", toType="location")
        ],
    )
    apply_correction(db, "proj-a", preview)
    overrides = memory.entity_type_overrides(db, "proj-a")
    assert overrides.get("gakona") == "location"


# --- Undo ---------------------------------------------------------------------


def test_undo_restores_snapshot_and_deactivates_memory(db):
    _seed(db, "proj-a", [_entry("e1", "Gakona is a covert operative.", section="characters")])
    preview = CorrectionPreview(
        previewId="prev_undo1",
        projectId="proj-a",
        instruction="Gakona is a location.",
        correctionType="RECLASSIFY",
        entityReclassifications=[
            EntityReclassification(name="Gakona", fromType="character", toType="location")
        ],
    )
    result = apply_correction(db, "proj-a", preview)
    correction_id = result["correction"]["id"]
    # Sanity: override is active before undo.
    assert memory.entity_type_overrides(db, "proj-a").get("gakona") == "location"

    undo = undo_correction(db, "proj-a", correction_id)
    assert undo["ok"] is True
    snapshot = load_snapshot(db, "proj-a")
    old = next(e for e in snapshot.knowledgeEntries if e.id == "e1")
    assert old.state == "confirmed"  # restored
    # Learned correction deactivated.
    assert memory.entity_type_overrides(db, "proj-a").get("gakona") is None


# --- Project isolation ---------------------------------------------------------


def test_correction_memory_is_project_scoped(db):
    _seed(db, "proj-a", [])
    _seed(db, "proj-b", [])
    preview = CorrectionPreview(
        previewId="prev_iso1",
        projectId="proj-a",
        instruction="Gakona is a location.",
        correctionType="RECLASSIFY",
        entityReclassifications=[
            EntityReclassification(name="Gakona", fromType="character", toType="location")
        ],
    )
    apply_correction(db, "proj-a", preview)
    assert memory.entity_type_overrides(db, "proj-a").get("gakona") == "location"
    # Project B is unaffected.
    assert memory.entity_type_overrides(db, "proj-b").get("gakona") is None


# --- Character-section purity --------------------------------------------------


def test_classify_entity_type_overrides_win():
    assert classify_entity_type("Gakona", entity_type_overrides={"gakona": "location"}) == "location"
    assert classify_entity_type("Gakona research station", hinted_section="characters") == "location"


def test_classify_entity_type_age_is_attribute():
    assert classify_entity_type("Barnes, age 55") == "attribute"
    assert classify_entity_type("Kyung is 55 years old") == "attribute"


def test_classify_entity_type_known_orgs():
    assert classify_entity_type("The FBI investigates") == "organization"
    assert classify_entity_type("DW6 Research Facility operates in secret") == "organization"
    assert classify_entity_type("NSA surveillance program") == "organization"


def test_resolve_characters_blocks_overridden_entities():
    pages = resolve_characters(
        ["Gakona", "Barnes is an agent."],
        entity_type_overrides={"gakona": "location"},
    )
    titles = [p["title"] for p in pages]
    assert "Gakona" not in titles
    assert any("Barnes" in t for t in titles)


def test_resolve_characters_alias_collapse():
    pages = resolve_characters(
        ["Barnes is an agent.", "Special Agent Barnes enters."],
        alias_map={"Special Agent Barnes": "Barnes"},
    )
    # Only one canonical Barnes page.
    barnes = [p for p in pages if "Barnes" in p["title"]]
    assert len(barnes) == 1


# --- Creator-authority precedence in classification ----------------------------


def test_explicit_creator_write_is_fact_not_specialist():
    from app.codirector.wiki_intelligence.compiled.story_summary_editor.evidence import _classify

    fact, cinterp, sinterp = _classify(
        "Barnes is skeptical.", "confirmed", "explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE"
    )
    assert fact == "Barnes is skeptical."
    assert sinterp is None


# --- Demote Wiki → Notes -------------------------------------------------------


def test_demote_wiki_to_note(db):
    _seed(db, "proj-a", [_entry("e1", "Unverified rumor about the Adept.", section="storyAndEpisodes")])
    result = demote_wiki_to_note(db, "proj-a", "e1")
    assert result["ok"] is True
    snapshot = load_snapshot(db, "proj-a")
    old = next(e for e in snapshot.knowledgeEntries if e.id == "e1")
    assert old.state == "superseded"
    notes = getattr(snapshot, "workingNotes", None) or []
    assert any("Unverified rumor" in (n.get("text") or "") for n in notes)


# --- list_corrections ----------------------------------------------------------


def test_list_corrections_returns_history(db):
    _seed(db, "proj-a", [])
    preview = CorrectionPreview(
        previewId="prev_list1",
        projectId="proj-a",
        instruction="Gakona is a location.",
        correctionType="RECLASSIFY",
        entityReclassifications=[
            EntityReclassification(name="Gakona", fromType="character", toType="location")
        ],
    )
    apply_correction(db, "proj-a", preview)
    history = list_corrections(db, "proj-a")
    assert len(history) == 1
    assert history[0]["instruction"] == "Gakona is a location."
