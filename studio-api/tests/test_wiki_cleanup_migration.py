"""Tests for the one-time Wiki cleanup migration.

Verifies that `clean_persisted_wiki_filler`:
- Cleans Story fields that contain only misclassified filler.
- Preserves legitimate user-authored story.
- Cleans filler and preserves story in mixed projects.
- Is idempotent (running twice == running once; already-blank is a no-op).
- Records an audit log entry for both cleaned and preserved actions.

Uses the canonical DB fixture pattern: `init_db()` + `SessionLocal()` with
a real `Project` row, mirroring `test_project_cleanup_cascade.py`.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from app.codirector.wiki_intelligence.cleanup_migration import (
    SETTINGS_KEY,
    clean_persisted_wiki_filler,
    clean_polluted_wiki_story,
    run_cleanup_for_all_projects,
)
from app.db import Project, SessionLocal, init_db


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_project(
    db,
    *,
    project_id: str | None = None,
    knowledge_entries: list[dict[str, Any]] | None = None,
    story_summary: dict[str, Any] | None = None,
) -> str:
    """Seed a Project row with a hand-built projectIntelligence payload."""
    pid = project_id or str(uuid.uuid4())
    db.add(Project(id=pid, name=f"Cleanup Test {pid[:8]}"))
    db.commit()

    intelligence: dict[str, Any] = {
        "projectId": pid,
        "revision": 1,
        "title": f"Cleanup Test {pid[:8]}",
        "knowledgeEntries": knowledge_entries or [],
        "compiledWiki": {
            "storySummary": story_summary or {},
        },
    }
    settings = {SETTINGS_KEY: intelligence}
    project = db.get(Project, pid)
    assert project is not None
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()
    db.refresh(project)
    return pid


def _load_intelligence(db, project_id: str) -> dict[str, Any]:
    """Read back the persisted projectIntelligence payload."""
    project = db.get(Project, project_id)
    assert project is not None
    settings = json.loads(project.settings_json or "{}")
    return settings.get(SETTINGS_KEY, {})  # type: ignore[return-value]


def _db():
    init_db()
    return SessionLocal()


# ── Test 1: only filler → all fields cleaned ──────────────────────────────


def test_only_filler_cleaned_to_blank() -> None:
    """A project whose Story fields contain only misclassified meta /
    preference filler must have all three fields cleaned to blank."""
    db = _db()
    try:
        filler_summary = {
            "logline": "Please call me friend",  # user_preference
            "shortSummary": "ok thanks will do",  # meta_conversation
            "longSummary": "Use Balanced mode for our chats",  # user_preference
        }
        pid = _make_project(db, story_summary=filler_summary)
        result = clean_persisted_wiki_filler(pid, db)

        assert result["project_id"] == pid
        assert set(result["cleaned_fields"]) == {
            "storySummary.logline",
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }, f"all three fields should be cleaned, got: {result['cleaned_fields']}"

        # Read back: every field must be genuinely blank (empty string),
        # never placeholder prose.
        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == "", f"logline not blanked: {story['logline']!r}"
        assert story["shortSummary"] == "", f"shortSummary not blanked: {story['shortSummary']!r}"
        assert story["longSummary"] == "", f"longSummary not blanked: {story['longSummary']!r}"
    finally:
        db.close()


# ── Test 2: legitimate story → preserved ──────────────────────────────────


def test_legitimate_story_preserved() -> None:
    """A project whose Story fields contain genuine narrative canon must
    have all fields preserved — the migration never erases real story."""
    db = _db()
    try:
        logline = (
            "Korri enters the coffee shop, orders a latte, tastes it, and "
            "reacts with surprise at the flavor."
        )
        short = (
            "Korri enters the coffee shop and orders a latte. She tastes it "
            "and reacts with surprise, deciding to investigate the barista."
        )
        long_summary = (
            "Korri enters the coffee shop, orders a latte, tastes it, and "
            "reacts with surprise at the flavor. She decides to investigate "
            "the mysterious barista and the origin of the beans."
        )
        legit_summary = {
            "logline": logline,
            "shortSummary": short,
            "longSummary": long_summary,
        }
        pid = _make_project(db, story_summary=legit_summary)
        result = clean_persisted_wiki_filler(pid, db)

        assert result["cleaned_fields"] == [], f"nothing should be cleaned, got: {result['cleaned_fields']}"
        assert set(result["preserved_fields"]) == {
            "storySummary.logline",
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }

        # Read back: content must be byte-for-byte preserved.
        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == logline
        assert story["shortSummary"] == short
        assert story["longSummary"] == long_summary
    finally:
        db.close()


# ── Test 3: mixed → filler cleaned, story preserved ───────────────────────


def test_mixed_filler_cleaned_and_story_preserved() -> None:
    """A project with a mix of filler and genuine narrative: the filler
    fields are cleaned and the story field is preserved."""
    db = _db()
    try:
        logline_canon = (
            "Korri enters the coffee shop, orders a latte, tastes it, and "
            "reacts with surprise at the flavor."
        )
        mixed_summary = {
            "logline": logline_canon,  # story_canon → preserve
            "shortSummary": "Please call me friend",  # user_preference → clean
            "longSummary": "ok thanks will do",  # meta_conversation → clean
        }
        pid = _make_project(db, story_summary=mixed_summary)
        result = clean_persisted_wiki_filler(pid, db)

        assert set(result["cleaned_fields"]) == {
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }
        assert "storySummary.logline" in result["preserved_fields"]

        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == logline_canon, "canon logline must be preserved"
        assert story["shortSummary"] == "", "filler shortSummary must be blanked"
        assert story["longSummary"] == "", "filler longSummary must be blanked"
    finally:
        db.close()


# ── Test 4: already-blank → idempotent no-op ───────────────────────────────


def test_already_blank_is_noop() -> None:
    """A project with already-blank Story fields must be a no-op: nothing
    is cleaned, nothing changes, and the persisted state is untouched."""
    db = _db()
    try:
        blank_summary = {
            "logline": "",
            "shortSummary": "",
            "longSummary": "",
        }
        pid = _make_project(db, story_summary=blank_summary)
        before = _load_intelligence(db, pid)

        result = clean_persisted_wiki_filler(pid, db)

        assert result["cleaned_fields"] == [], "already-blank fields must not be 'cleaned'"
        # Preserved fields are reported (the audit records the decision),
        # but nothing is written.
        assert set(result["preserved_fields"]) == {
            "storySummary.logline",
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }

        after = _load_intelligence(db, pid)
        assert before == after, "already-blank project must be unchanged"

        # Idempotency: run again, still nothing changes.
        result2 = clean_persisted_wiki_filler(pid, db)
        assert result2["cleaned_fields"] == []
        after2 = _load_intelligence(db, pid)
        assert after == after2, "second run on blank project must not mutate state"
    finally:
        db.close()


def test_idempotent_on_cleaned_project() -> None:
    """Running the migration twice on a project that needed cleaning: the
    second run finds blank fields and is a no-op (running twice == once)."""
    db = _db()
    try:
        filler_summary = {
            "logline": "Please call me friend",
            "shortSummary": "ok thanks will do",
            "longSummary": "Use Balanced mode",
        }
        pid = _make_project(db, story_summary=filler_summary)

        first = clean_persisted_wiki_filler(pid, db)
        assert len(first["cleaned_fields"]) == 3

        second = clean_persisted_wiki_filler(pid, db)
        assert second["cleaned_fields"] == [], "second run must not re-clean blank fields"

        # State after second run == state after first run.
        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == ""
        assert story["shortSummary"] == ""
        assert story["longSummary"] == ""
    finally:
        db.close()


# ── Test 5: audit records both cleaned and preserved ──────────────────────


def test_audit_records_cleaned_and_preserved() -> None:
    """The audit log must contain an entry for every field decision, with
    the field name, original snippet, classification, and action."""
    db = _db()
    try:
        logline_canon = (
            "Korri enters the coffee shop, orders a latte, tastes it, and "
            "reacts with surprise at the flavor."
        )
        mixed_summary = {
            "logline": logline_canon,  # preserved
            "shortSummary": "Please call me friend",  # cleaned
            "longSummary": "",  # preserved (already blank)
        }
        pid = _make_project(db, story_summary=mixed_summary)
        result = clean_persisted_wiki_filler(pid, db)

        audit = result["audit"]
        # One audit entry per storySummary field.
        fields_audited = {entry["field"] for entry in audit}
        assert fields_audited == {
            "storySummary.logline",
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }

        # Each audit entry must have the required shape.
        for entry in audit:
            assert "project_id" in entry and entry["project_id"] == pid
            assert "field" in entry
            assert "original_snippet" in entry and isinstance(entry["original_snippet"], str)
            assert "classification" in entry
            assert "action" in entry and entry["action"] in {"cleaned", "preserved"}

        # The cleaned entry must record the filler snippet + classification.
        cleaned_entries = [e for e in audit if e["action"] == "cleaned"]
        assert len(cleaned_entries) == 1
        assert cleaned_entries[0]["field"] == "storySummary.shortSummary"
        assert "call me friend" in cleaned_entries[0]["original_snippet"]
        assert cleaned_entries[0]["classification"] == "user_preference"

        # The preserved canon entry must record the canon classification.
        preserved_canon = [
            e for e in audit if e["field"] == "storySummary.logline"
        ]
        assert len(preserved_canon) == 1
        assert preserved_canon[0]["action"] == "preserved"
        assert preserved_canon[0]["classification"] == "story_canon"
    finally:
        db.close()


# ── Bonus: knowledgeEntries story-section filler is cleaned ───────────────


def test_knowledge_entries_story_filler_cleaned() -> None:
    """A knowledgeEntry in a story-shaped section whose text is filler is
    cleaned; entries in non-story sections are left untouched."""
    db = _db()
    try:
        knowledge_entries = [
            {
                "id": "ke-1",
                "text": "Please call me friend",  # user_preference → clean
                "state": "confirmed",
                "section": "storyAndEpisodes",
            },
            {
                "id": "ke-2",
                "text": "Maya is a detective who works the night shift.",  # canon → preserve
                "state": "confirmed",
                "section": "characters",  # non-story section → untouched
            },
        ]
        pid = _make_project(db, knowledge_entries=knowledge_entries)
        result = clean_persisted_wiki_filler(pid, db)

        # Only the story-section filler entry should be cleaned.
        assert any(
            f.startswith("knowledgeEntries[0]") for f in result["cleaned_fields"]
        ), f"story-section filler should be cleaned, got: {result['cleaned_fields']}"
        # The character-section entry must NOT be cleaned.
        assert not any(
            f.startswith("knowledgeEntries[1]") for f in result["cleaned_fields"]
        ), "non-story-section entry must not be touched"

        intelligence = _load_intelligence(db, pid)
        entries = intelligence["knowledgeEntries"]
        assert entries[0]["text"] == "", "story-section filler must be blanked"
        assert (
            entries[1]["text"] == "Maya is a detective who works the night shift."
        ), "character entry must be untouched"
    finally:
        db.close()


# ── Bonus: unknown is preserved (conservative) ───────────────────────────


def test_unknown_classification_preserved() -> None:
    """Text that classifies as `unknown` must be PRESERVED — the heuristics
    may simply fail to recognize legitimate story, and the migration must
    be conservative."""
    db = _db()
    try:
        # A snippet the regex heuristics don't recognize as canon, but that
        # could be legitimate user-authored story. classify_conversation_turn
        # returns `unknown` for this.
        unknown_text = "A quiet western town at the edge of the desert."
        summary = {
            "logline": unknown_text,
            "shortSummary": "",
            "longSummary": "",
        }
        pid = _make_project(db, story_summary=summary)

        # Sanity: the classifier returns unknown for this text.
        from app.codirector.wiki_intelligence.classification import (
            classify_conversation_turn,
        )

        assert classify_conversation_turn(unknown_text) == "unknown"

        result = clean_persisted_wiki_filler(pid, db)
        assert result["cleaned_fields"] == [], "unknown must NOT be cleaned"
        assert "storySummary.logline" in result["preserved_fields"]

        intelligence = _load_intelligence(db, pid)
        assert intelligence["compiledWiki"]["storySummary"]["logline"] == unknown_text
    finally:
        db.close()


# ── Bonus: run_cleanup_for_all_projects ────────────────────────────────────


def test_run_cleanup_for_all_projects_handles_multiple() -> None:
    """run_cleanup_for_all_projects iterates every project and returns one
    result per project, even when some need cleaning and some don't."""
    db = _db()
    try:
        filler_pid = _make_project(
            db,
            story_summary={
                "logline": "Please call me friend",
                "shortSummary": "",
                "longSummary": "",
            },
        )
        canon_pid = _make_project(
            db,
            story_summary={
                "logline": (
                    "Korri enters the coffee shop, orders a latte, tastes it, "
                    "and reacts with surprise at the flavor."
                ),
                "shortSummary": "",
                "longSummary": "",
            },
        )

        results = run_cleanup_for_all_projects(db)
        by_pid = {r["project_id"]: r for r in results}
        assert filler_pid in by_pid
        assert canon_pid in by_pid

        assert any(
            f == "storySummary.logline" for f in by_pid[filler_pid]["cleaned_fields"]
        ), "filler project must be cleaned"
        assert by_pid[canon_pid]["cleaned_fields"] == [], "canon project must not be cleaned"
    finally:
        db.close()


# ── clean_polluted_wiki_story: known-string contamination cleanup ──────────


def _seed_story_entry(db, project_id: str, *, logline: str = "", short: str = "", long_summary: str = "") -> None:
    """Seed an authoritative StoryEntry row via the existing store."""
    from app.story_entries.models import StoryEntryCreate
    from app.story_entries.store import create_entry, ensure_story_entries_tables

    ensure_story_entries_tables()
    create_entry(
        db,
        project_id,
        StoryEntryCreate(
            title="Story",
            entryType="project_story",
            logline=logline,
            shortSummary=short,
            longSummary=long_summary,
        ),
    )


def test_polluted_wiki_story_cleans_known_contamination_strings() -> None:
    """Story fields containing known contamination strings are blanked and
    then rebuilt from the authoritative Story record."""
    db = _db()
    try:
        polluted_summary = {
            "logline": "Please call me friend",  # known marker
            "shortSummary": "I've filled in how I'd like us to work together",  # known marker
            "longSummary": "Audit Schnick Coffee — Follow-up Test",  # known markers
        }
        pid = _make_project(db, story_summary=polluted_summary)
        # Authoritative Story record has clean content.
        _seed_story_entry(
            db,
            pid,
            logline="Korri enters the coffee shop and reacts with surprise at the latte.",
            short="Korri orders a latte and reacts with surprise.",
            long_summary="Korri enters the coffee shop, orders a latte, tastes it, and reacts with surprise.",
        )

        result = clean_polluted_wiki_story(db, pid)

        assert set(result["cleaned_fields"]) == {
            "storySummary.logline",
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }, f"all three polluted fields should be cleaned, got: {result['cleaned_fields']}"
        assert result["rebuilt_from_story_record"] is True

        # Read back: Story fields now mirror the authoritative Story record.
        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == "Korri enters the coffee shop and reacts with surprise at the latte."
        assert story["shortSummary"] == "Korri orders a latte and reacts with surprise."
        assert story["longSummary"] == "Korri enters the coffee shop, orders a latte, tastes it, and reacts with surprise."
        # No pollution markers survive.
        for field in ("logline", "shortSummary", "longSummary"):
            assert "call me friend" not in story[field].lower()
            assert "schnick" not in story[field].lower()
            assert "follow-up test" not in story[field].lower()
    finally:
        db.close()


def test_polluted_wiki_story_preserves_legitimate_content() -> None:
    """Story fields with no pollution markers are preserved untouched."""
    db = _db()
    try:
        logline = "Korri enters the coffee shop, orders a latte, tastes it, and reacts with surprise at the flavor."
        short = "Korri orders a latte and reacts with surprise, deciding to investigate the barista."
        long_summary = "Korri enters the coffee shop, orders a latte, tastes it, and reacts with surprise at the flavor. She decides to investigate the mysterious barista."
        clean_summary = {"logline": logline, "shortSummary": short, "longSummary": long_summary}
        pid = _make_project(db, story_summary=clean_summary)

        result = clean_polluted_wiki_story(db, pid)

        assert result["cleaned_fields"] == [], "legitimate content must not be cleaned"
        assert result["rebuilt_from_story_record"] is False, "no rebuild when nothing cleaned"
        assert set(result["preserved_fields"]) == {
            "storySummary.logline",
            "storySummary.shortSummary",
            "storySummary.longSummary",
        }

        # Read back: content byte-for-byte preserved.
        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == logline
        assert story["shortSummary"] == short
        assert story["longSummary"] == long_summary
    finally:
        db.close()


def test_polluted_wiki_story_idempotent() -> None:
    """Running twice == running once. The second run finds clean content and
    is a no-op."""
    db = _db()
    try:
        polluted_summary = {
            "logline": "Please call me friend",
            "shortSummary": "Persistence verification — Follow-up Test",
            "longSummary": "Audit Schnick Coffee",
        }
        pid = _make_project(db, story_summary=polluted_summary)
        _seed_story_entry(db, pid, logline="Korri tastes a surprising latte.")

        first = clean_polluted_wiki_story(db, pid)
        assert len(first["cleaned_fields"]) == 3

        second = clean_polluted_wiki_story(db, pid)
        assert second["cleaned_fields"] == [], "second run must not re-clean clean content"
        assert second["rebuilt_from_story_record"] is False

        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == "Korri tastes a surprising latte."
    finally:
        db.close()


def test_polluted_wiki_story_blank_when_no_story_record() -> None:
    """When pollution is cleaned but no Story record exists, Story fields
    remain genuinely blank (no filler, no rebuild)."""
    db = _db()
    try:
        polluted_summary = {
            "logline": "Please call me friend",
            "shortSummary": "",
            "longSummary": "",
        }
        pid = _make_project(db, story_summary=polluted_summary)
        # No StoryEntry seeded.

        result = clean_polluted_wiki_story(db, pid)

        assert result["cleaned_fields"] == ["storySummary.logline"]
        assert result["rebuilt_from_story_record"] is False, "no rebuild without a Story record"

        intelligence = _load_intelligence(db, pid)
        story = intelligence["compiledWiki"]["storySummary"]
        assert story["logline"] == "", "polluted logline must be blanked with no Story record to rebuild from"
    finally:
        db.close()


def test_polluted_wiki_story_audit_records_decisions() -> None:
    """The audit log records a per-field decision for cleaned and preserved
    fields, with the matching pollution marker."""
    db = _db()
    try:
        mixed_summary = {
            "logline": "Please call me friend",  # cleaned
            "shortSummary": "Korri orders a latte and reacts with surprise.",  # preserved
            "longSummary": "",  # preserved (already blank)
        }
        pid = _make_project(db, story_summary=mixed_summary)
        _seed_story_entry(db, pid, logline="Korri tastes a surprising latte.")

        result = clean_polluted_wiki_story(db, pid)
        audit = result["audit"]
        fields_audited = {entry["field"] for entry in audit if entry["field"].startswith("storySummary.")}
        assert "storySummary.logline" in fields_audited
        assert "storySummary.shortSummary" in fields_audited
        assert "storySummary.longSummary" in fields_audited

        cleaned_entries = [e for e in audit if e["action"] == "cleaned"]
        assert len(cleaned_entries) == 1
        assert cleaned_entries[0]["field"] == "storySummary.logline"
        assert cleaned_entries[0]["pollution_marker"] == "Please call me friend"

        preserved_entries = [e for e in audit if e["action"] == "preserved"]
        assert any(e["field"] == "storySummary.shortSummary" for e in preserved_entries)
    finally:
        db.close()