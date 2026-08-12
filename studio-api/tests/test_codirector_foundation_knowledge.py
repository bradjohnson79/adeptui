"""Tests for the Co-Director Creative Knowledge Framework."""

from __future__ import annotations

from app.codirector.foundation.knowledge import get_knowledge_pack, list_pack_ids, query_knowledge


def test_get_knowledge_pack_returns_three_act():
    pack = get_knowledge_pack("three_act")
    assert pack is not None
    assert pack.packId == "three_act"
    assert pack.frames


def test_query_knowledge_by_structure_tag_returns_frames():
    hits = query_knowledge(tags=["structure"], limit=12)
    assert hits
    assert any("structure" in hit.frame.tags for hit in hits)


def test_story_and_structure_topics_resolve_to_same_pack_source():
    structure_hit = next(hit for hit in query_knowledge(tags=["structure"], intent="story beats", limit=20) if hit.packId == "three_act")
    story_hit = next(hit for hit in query_knowledge(tags=["story"], intent="structure arc", limit=20) if hit.packId == "three_act")

    assert structure_hit.packId == story_hit.packId == "three_act"
    assert structure_hit.frame.frameId == story_hit.frame.frameId


def test_catalog_lists_expected_packs():
    catalog = set(list_pack_ids())
    expected = {
        "three_act",
        "five_act",
        "heros_journey",
        "save_the_cat",
        "kishotenketsu",
        "story_circle",
        "pixar_principles",
        "documentary_narrative",
        "television_acts",
        "anime_pacing",
        "cinematography_principles",
        "lens_characteristics",
        "visual_composition",
        "blocking_theory",
        "lighting_theory",
        "color_psychology",
        "editing_rhythm",
        "sound_design_principles",
        "performance_direction",
        "production_workflows",
    }
    assert expected.issubset(catalog)
