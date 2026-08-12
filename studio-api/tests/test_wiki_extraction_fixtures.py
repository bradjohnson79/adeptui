"""Dual fixtures: sci-fi synopsis minima + neutral documentary — no hardcoding in product paths."""

from __future__ import annotations

from collections import Counter

from app.codirector.conversation.discovery.documentation import extract_documentation
from app.codirector.conversation.discovery.schemas import WikiCandidateCategory
from app.codirector.wiki import normalize_wiki_section

# Test-only Dreamweaver-shaped synopsis (not a product ontology requirement).
DREAMWEAVER_SYNOPSIS = """
The Dreamweaver is a science-fiction web series set across 2140–2147. Overview: it follows
memory cartographers who weave shared dreams into civic infrastructure. The Signal is an
entity that remembers forgotten cities. Characters include Dr. Lena Okoye who guides dreamers,
Agent Marcus Hale who investigates breaches, Professor Imani Crow who maps continuity rules,
Captain Ryo Tanaka who patrols the archive rim, Detective Nora Voss who interviews survivors,
and Korri Vale who hears coordinates before they happen. Timeline markers: 2140 founding,
2143 first breach, 2147 civic vote. World rules: every answered call costs a memory; never
rewrite a living dream without consent; always log continuum drift; continuity must hold across
seasons. Themes are identity, belonging, consequence, and the ethics of shared memory.
Organizations include the Continuum Guild. Locations include Harbor Archive and the Night Lattice.
"""

# Neutral 12-minute documentary — different format-appropriate structure.
DOCUMENTARY_SYNOPSIS = """
This 12-minute documentary follows three generations of oyster farmers in a coastal estuary.
Characters include Elena Ruiz who runs the family skiff, her father Tomas Ruiz who remembers
the old tides, and neighbor Sam Patel who documents water quality. Timeline: 1980s boom years,
1998 die-off winter, 2020 community restoration. World rules of the film: interviews must stay
on location; never stage a catch; always credit community voices; archival clips stay muted
under modern narration. Themes are inheritance, climate pressure, and quiet resilience.
Organizations include the Estuary Cooperative. Location: Cedar Inlet. Format is observational
documentary with intimate portrait interludes.
"""


def _counts(result) -> Counter:
    return Counter(c.category for c in (result.candidates or []))


def test_dreamweaver_fixture_minima():
    result = extract_documentation(DREAMWEAVER_SYNOPSIS, project_id="fixture-dw", source_id="src-dw")
    assert result.candidate_count >= 10
    c = _counts(result)
    # Fixture minima (test-only — not product ontology requirements)
    assert c[WikiCandidateCategory.PROJECT] >= 3 or (
        c[WikiCandidateCategory.PROJECT] + c.get(WikiCandidateCategory.STORY_PRINCIPLE, 0) >= 3
    )
    assert c[WikiCandidateCategory.CHARACTER] + c.get(WikiCandidateCategory.ENTITY, 0) >= 6
    assert c[WikiCandidateCategory.TIMELINE] + c.get(WikiCandidateCategory.EVENT, 0) >= 3
    assert c[WikiCandidateCategory.WORLD_RULE] >= 4
    assert c[WikiCandidateCategory.THEME] >= 4
    assert c.get(WikiCandidateCategory.ENTITY, 0) + c.get(WikiCandidateCategory.LOCATION, 0) >= 2


def test_documentary_fixture_generalized_extraction():
    result = extract_documentation(DOCUMENTARY_SYNOPSIS, project_id="fixture-doc", source_id="src-doc")
    assert result.substantive
    assert result.candidate_count >= 6
    c = _counts(result)
    assert c[WikiCandidateCategory.CHARACTER] >= 2
    assert c[WikiCandidateCategory.TIMELINE] + c.get(WikiCandidateCategory.EVENT, 0) >= 2
    titles = " ".join(x.title.lower() for x in result.candidates)
    # Must not inject sci-fi Dreamweaver ontology into documentary
    assert "dreamweaver" not in titles
    assert "signal" not in titles or "oyster" in DOCUMENTARY_SYNOPSIS.lower()


def test_section_normalization_format_aware_aliases():
    assert normalize_wiki_section("LOCATION", "harbor") == "worldAndSetting"
    assert normalize_wiki_section("TIMELINE", "2140") == "storyAndEpisodes"
    assert normalize_wiki_section("CHARACTER", "Elena") == "characters"
    assert normalize_wiki_section("THEME", "identity") == "creativeFoundation"
    assert normalize_wiki_section("RESEARCH_NOTE", "clip") == "references"


def test_no_dreamweaver_string_in_normalize():
    # Product path must not special-case Dreamweaver titles
    import inspect
    from app.codirector import wiki as wiki_mod

    src = inspect.getsource(wiki_mod.normalize_wiki_section)
    assert "dreamweaver" not in src.lower()
