"""Story → Wiki Manual Save contract tests (Amendment: Story → Wiki Manual Save).

The Wiki Story section must update ONLY when the creator explicitly clicks
"Save to Wiki" (which calls POST /wiki/compile → compile_wiki_bundle
force_full). Editing the Story (autosave) must NOT trigger a Wiki recompile,
so the Wiki retains the previously-published version until an explicit
publish.

These tests verify the invalidation contract that underpins the manual model:
Story save (`story_entries.store._invalidate_wiki`) marks ONLY the
`production_state` cache section stale and never touches the compiled-wiki
cache (`snapshot.compiledWiki`). Therefore `get_compiled_wiki` keeps serving
the previously-published Story values until an explicit compile.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_story_save_invalidates_only_production_state_not_compiled_wiki() -> None:
    """`_invalidate_wiki` (called on every Story create/update/delete/reorder)
    must only mark the `production_state` cache section stale — it must NOT
    invalidate the compiled-wiki cache. This is what lets the Wiki retain the
    published Story version while the creator edits the Story."""
    from app.story_entries.store import _invalidate_wiki

    captured: dict[str, object] = {}

    def fake_invalidate_cache_sections(db, project_id, sections):
        captured["sections"] = list(sections)
        return None

    with patch(
        "app.codirector.production_state.invalidation.invalidate_cache_sections",
        side_effect=fake_invalidate_cache_sections,
    ):
        _invalidate_wiki(db=None, project_id="proj-1")

    sections = captured.get("sections") or []
    assert sections == ["production_state"], (
        f"Story save must only invalidate 'production_state', got: {sections!r}"
    )
    # The compiled-wiki cache section must NOT be invalidated by Story save.
    assert "compiledWiki" not in sections
    assert "wiki" not in sections
    assert "compiled_wiki" not in sections


def test_get_compiled_wiki_serves_cached_until_explicit_compile() -> None:
    """get_compiled_wiki returns the cached compiledWiki (published version)
    when it has pages + projection=compiled_bible_v1. Story edits do not
    invalidate that cache, so the Wiki keeps serving the published version
    until compile_wiki_bundle(force_full=True) is invoked by Save to Wiki."""
    from app.codirector.wiki_intelligence.compiled import page_compiler

    class _FakeSnapshot:
        compiledWiki = {
            "projection": "compiled_bible_v1",
            "pages": [{"id": "story", "title": "Story"}],
            "storySummary": {"logline": "published-logline"},
        }

    fake = _FakeSnapshot()
    with patch.object(page_compiler, "load_snapshot", return_value=fake):
        result = page_compiler.get_compiled_wiki(db=None, project_id="proj-1")
    # The cached published version is served as-is (no recompile).
    assert result is fake.compiledWiki
    assert result["storySummary"]["logline"] == "published-logline"


def test_compile_wiki_bundle_force_full_picks_up_new_story_values() -> None:
    """The Save to Wiki path (compile_wiki_bundle force_full) is the ONLY path
    that picks up the latest StoryEntry values and overwrites the cached
    compiledWiki. This is the explicit-publish write gate."""
    from app.codirector.wiki_intelligence.compiled import page_compiler

    class _FakeSnapshot:
        compiledWiki = None

    fake = _FakeSnapshot()

    def fake_compile(db, project_id, *, force_full=False):
        assert force_full is True, "Save to Wiki must force a full recompile"
        return {
            "projection": "compiled_bible_v1",
            "pages": [{"id": "story"}],
            "storySummary": {"logline": "new-logline"},
        }

    with patch.object(page_compiler, "load_snapshot", return_value=fake), \
         patch.object(page_compiler, "compile_wiki_bundle", side_effect=fake_compile):
        result = page_compiler.get_compiled_wiki(db=None, project_id="proj-1")
    assert result["storySummary"]["logline"] == "new-logline"


def test_blank_story_field_maps_to_blank_wiki_field() -> None:
    """Blank Story Logline → blank Wiki Logline (no invented content). The
    compiler reads the Story record directly; a blank field stays blank."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    class _FakeStoryRecord:
        logline = ""
        short_summary = ""
        long_summary = ""
        entry_type = "project_story"

    result = compile_story_summary(
        story_texts=["some unrelated conversation text"],
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
        story_record=_FakeStoryRecord(),
    )
    assert result.logline in (None, "")
    assert result.shortSummary in (None, "")
    assert result.longSummary in (None, "")


def test_conversation_text_does_not_affect_wiki_story_fields() -> None:
    """Unrelated conversation content must never populate Story Logline /
    Short Summary / Long Summary — the Story record is the only source."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    class _FakeStoryRecord:
        logline = "real-logline"
        short_summary = "real-short"
        long_summary = "real-long"
        entry_type = "project_story"

    result = compile_story_summary(
        story_texts=[
            "Please call me friend",
            "ok thanks will do",
            "Create a storyboard for the opening scene.",
        ],
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
        story_record=_FakeStoryRecord(),
    )
    assert result.logline == "real-logline"
    assert result.shortSummary == "real-short"
    assert result.longSummary == "real-long"
    blob = " ".join(s for s in (result.logline, result.shortSummary, result.longSummary) if s)
    assert "call me friend" not in blob.lower()
    assert "storyboard" not in blob.lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
