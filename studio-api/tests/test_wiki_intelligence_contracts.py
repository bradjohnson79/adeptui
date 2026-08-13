"""Professional Wiki Intelligence — classification, assignment, projection."""

from __future__ import annotations

from app.codirector.conversation.schemas import WikiCandidate
from app.codirector.wiki_intelligence.assignment import assign_specialists_for_domains
from app.codirector.wiki_intelligence.classification import (
    classify_entity_type,
    is_false_character_name,
    is_user_preference_not_canon,
    names_are_aliases,
)
from app.codirector.wiki_intelligence.contracts import WIKI_WRITE_SPECIALIST_IDS
from app.codirector.wiki_intelligence.projection import project_professional_toc
from app.codirector.wiki_intelligence.reorganize import _detect_problems


def test_false_characters_rejected():
    assert is_false_character_name("She")
    assert is_false_character_name("Research")
    assert is_false_character_name("Series Synopsis")
    assert is_false_character_name("Agent Gold")
    assert not is_false_character_name("Kyung Leong")


def test_preference_filter():
    assert is_user_preference_not_canon("Please call me Brad and use Agent Gold.")
    assert not is_user_preference_not_canon("Kyung enters the anteroom wearing a dark coat.")


def test_alias_merge_detection():
    assert names_are_aliases("Kyung", "Kyung Leong")
    assert names_are_aliases("Dr. Kyung Leong", "Kyung Leong")


def test_entity_classification_routes():
    assert classify_entity_type("Gakona research station in Alaska") == "location"
    assert classify_entity_type("Continuum Guild oversees clerks") == "organization"
    assert classify_entity_type("Kyung wears a dark wool coat") == "wardrobe"
    assert classify_entity_type("Barnes carries a government recorder") == "prop"


def test_specialist_assignment_not_all():
    assignment = assign_specialists_for_domains(
        project_id="p1",
        domains=["characters", "wardrobe"],
        max_specialists=6,
    )
    assert assignment.selectedSpecialists
    assert len(assignment.selectedSpecialists) <= 6
    assert "character-creator" in assignment.selectedSpecialists or "costume-designer" in assignment.selectedSpecialists


def test_wiki_write_specialists_curated():
    assert "character-creator" in WIKI_WRITE_SPECIALIST_IDS
    assert "costume-designer" in WIKI_WRITE_SPECIALIST_IDS
    assert "code-director" not in WIKI_WRITE_SPECIALIST_IDS


def test_professional_toc_hides_empty_and_filters_fragments():
    sections = {
        "characters": {
            "entries": [
                {"id": "1", "text": "She: pronoun leak", "state": "proposed"},
                {"id": "2", "text": "Kyung Leong: lead researcher", "state": "confirmed"},
            ]
        },
        "worldAndSetting": {"entries": [{"id": "3", "text": "Gakona: research station", "state": "proposed"}]},
        "knownDetails": {"entries": []},
    }
    toc = project_professional_toc(sections)
    keys = {n["key"] for n in toc}
    assert "characters" in keys
    assert "projectOverview" not in keys  # empty hidden
    char = next(n for n in toc if n["key"] == "characters")
    assert char["count"] == 1  # false character excluded


def test_detect_problems_finds_duplicates_and_prefs():
    entries = [
        WikiCandidate(id="a", text="Kyung: scientist", state="proposed", section="characters"),
        WikiCandidate(id="b", text="Kyung Leong: scientist", state="proposed", section="characters"),
        WikiCandidate(id="c", text="She: walks in", state="proposed", section="characters"),
        WikiCandidate(id="d", text="Call me Agent Gold", state="proposed", section="knownDetails"),
    ]
    problems = _detect_problems(entries)
    types = {p.problemType for p in problems}
    assert "duplicate_character" in types
    assert "false_character" in types
    assert "preference_leak" in types


# ---------------------------------------------------------------------------
# Wiki User-Authority Law regression tests
# ---------------------------------------------------------------------------


def test_false_character_scaffolding_tokens():
    """Assistant scaffolding tokens must never become character names."""
    assert is_false_character_name("Current")
    assert is_false_character_name("Tell")
    assert is_false_character_name("Narrative")
    assert is_false_character_name("Onboarding")
    assert is_false_character_name("Director")
    assert is_false_character_name("Assistant")
    assert is_false_character_name("Suggestion")


def test_false_character_name_extraction_filter():
    """Remaining scaffolding words must be caught by is_false_character_name."""
    assert is_false_character_name("Default")
    assert is_false_character_name("Creator")
    assert is_false_character_name("Sample")
    assert is_false_character_name("Skip")
    assert is_false_character_name("Understanding")
    assert is_false_character_name("Collaboration")
    assert is_false_character_name("Preference")
    assert not is_false_character_name("Maya")
    assert not is_false_character_name("Kyung Leong")


def test_is_junk_name_expanded():
    """character_compiler._is_junk_name must match assistant scaffolding words."""
    from app.codirector.wiki_intelligence.compiled.character_compiler import _is_junk_name

    assert _is_junk_name("Current")
    assert _is_junk_name("Tell")
    assert _is_junk_name("Narrative")
    assert _is_junk_name("Onboarding")
    assert _is_junk_name("Director")
    assert _is_junk_name("Assistant")
    assert _is_junk_name("Default")
    assert not _is_junk_name("Maya")
    assert not _is_junk_name("Kyung Leong")


def test_page_compiler_excludes_non_characters_from_char_resolution():
    """page_compiler must not pass non-characters-section entries to resolve_characters."""
    from app.codirector.wiki_intelligence.compiled.page_compiler import _entry_texts
    from app.codirector.conversation.schemas import ProjectIntelligenceSnapshot

    snapshot = ProjectIntelligenceSnapshot(projectId="test-p1", knowledgeEntries=[
        WikiCandidate(id="a", text="Current Co-Director understanding.", state="confirmed", section="storyAndEpisodes"),
        WikiCandidate(id="b", text="Maya Chen is a detective.", state="confirmed", section="characters"),
    ])
    entries = _entry_texts(snapshot)
    char_texts = [t for _, t, s in entries if s == "characters"]
    assert len(char_texts) == 1, f"Expected 1 character text, got {len(char_texts)}: {char_texts}"
    assert "Maya" in char_texts[0]
    assert all("Current" not in t for t in char_texts), "Non-characters entry leaked"


def test_resolve_characters_still_accepts_legitimate_names():
    """resolve_characters must still accept legitimate character names."""
    from app.codirector.wiki_intelligence.compiled.character_compiler import resolve_characters

    chars = resolve_characters(["Maya Chen", "Kyung Leong"])
    titles = [c["title"] for c in chars]
    assert "Maya Chen" in titles
    assert "Kyung Leong" in titles


def test_story_compiler_no_hardcoded_narrative_frame():
    """narrativeFrame must not contain hardcoded 'Current Co-Director' text.

    Workstream B: narrativeFrame derives from the saved Story record (when
    any of Logline/Short/Long is populated), not from conversation.
    """
    from app.codirector.wiki_intelligence.compiled.story_compiler import compile_story_summary

    result = compile_story_summary(
        story_texts=[],
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
    )
    assert "Current" not in result.narrativeFrame, f"narrativeFrame contains hardcoded text: {result.narrativeFrame}"
    assert result.narrativeFrame == "", f"Expected empty narrativeFrame, got: {result.narrativeFrame}"

    # With a populated Story record, narrativeFrame should be non-empty but
    # reasonable (conversation-only input no longer drives it).
    class _Record:
        logline = "Maya Chen is a detective in Neo-Tokyo who discovers a conspiracy."
        short_summary = ""
        long_summary = ""
        entry_type = "project_story"

    result2 = compile_story_summary(
        story_texts=[],
        open_questions=[],
        episode_summaries=[],
        source_ids=["test-1"],
        story_record=_Record(),
    )
    assert "Current" not in result2.narrativeFrame
    assert result2.narrativeFrame, "Expected non-empty narrativeFrame with Story record content"
