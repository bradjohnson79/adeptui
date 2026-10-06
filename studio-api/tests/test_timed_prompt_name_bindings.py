"""Timed Prompt name bindings persist and compile without rewriting creator prose."""

from __future__ import annotations

from app.director_timeline import PromptSegment, parse_director_timeline
from app.director_timeline_bindings import (
    binding_ids_from_name_bindings,
    dump_prompt_name_bindings,
    name_binding_index,
    parse_prompt_name_bindings,
)
from app.director_timeline_w46.generation.r2v import R2VSlot, map_canonical_r2v


PROSE = (
    "Korri and Anadriya walk through the Venture corridor while Korri carries the mug."
)


def test_parse_roundtrip_keeps_prompt_names_and_ids():
    raw = {
        "media_mode": "video",
        "duration_sec": 5,
        "prompt_segments": [
            {
                "id": "ps1",
                "start": 0,
                "length": 5,
                "text": PROSE,
                "reference_binding_ids": ["bind-k", "bind-a", "bind-ers"],
                "reference_name_bindings": [
                    {
                        "bindingId": "bind-k",
                        "promptName": "Korri",
                        "type": "character",
                        "tag": "@Korri",
                    },
                    {
                        "binding_id": "bind-a",
                        "prompt_name": "Anadriya",
                        "type": "character",
                        "tag": "@Anadriya",
                    },
                    {
                        "binding_id": "bind-ers",
                        "prompt_name": "Venture corridor",
                        "type": "environment",
                        "tag": "#VentureCorridorScene",
                    },
                ],
            }
        ],
    }
    import json

    tl = parse_director_timeline(json.dumps(raw))
    seg = tl.prompt_segments[0]
    assert [row.prompt_name for row in seg.reference_name_bindings] == [
        "Korri",
        "Anadriya",
        "Venture corridor",
    ]
    assert binding_ids_from_name_bindings(seg.reference_name_bindings) == [
        "bind-k",
        "bind-a",
        "bind-ers",
    ]
    dumped = dump_prompt_name_bindings(seg.reference_name_bindings)
    assert dumped[0]["tag"] == "@Korri"
    assert dumped[2]["type"] == "environment"


def test_name_index_is_structural_not_text_replace():
    rows = parse_prompt_name_bindings(
        [{"binding_id": "bind-k", "prompt_name": "Korri", "type": "character", "tag": "@Korri"}]
    )
    index = name_binding_index(rows)
    assert index["bind-k"]["prompt_name"] == "Korri"
    assert "@Korri" not in PROSE
    assert "Korri" in PROSE


def test_same_bindings_recompile_per_generator_without_changing_prose():
    slots = [
        R2VSlot(role="character", assetId="crs-k", label="Korri", identityId="char-k"),
        R2VSlot(role="character", assetId="crs-a", label="Anadriya", identityId="char-a"),
        R2VSlot(role="place", assetId="ers-1", label="Venture corridor"),
    ]
    h3 = map_canonical_r2v(
        slots=slots,
        generator_id="minimax-h3",
        mapped_start=None,
        authored_prompt=PROSE,
    )
    ltx = map_canonical_r2v(
        slots=slots,
        generator_id="ltx-2.5-distilled",
        mapped_start="ers-1",
        authored_prompt=PROSE,
    )
    seedance = map_canonical_r2v(
        slots=slots,
        generator_id="seedance-api",
        mapped_start=None,
        authored_prompt=PROSE,
    )
    # Phase N: H3 diagnostics prefix is the Timed Prompt verbatim.
    assert h3.promptPrefix == PROSE
    assert "walk through the Venture corridor" in h3.promptPrefix
    assert "carries the mug" in h3.promptPrefix
    assert PROSE in ltx.promptPrefix
    assert PROSE in seedance.promptPrefix
    assert "@Korri" not in h3.promptPrefix
    assert "@Korri" not in ltx.promptPrefix
    assert "@Korri" not in seedance.promptPrefix
    assert "<Picture" not in h3.promptPrefix
    assert "Korri" in h3.promptPrefix
    assert "<Picture" not in ltx.promptPrefix
    assert h3.mechanism != ltx.mechanism
    assert seedance.mechanism == "seedance_r2v"
    assert "@Image" not in seedance.promptPrefix
    assert any("image_url" in note for note in seedance.disclosures)
    assert h3.promptPrefix != ltx.promptPrefix


def test_prompt_segment_model_accepts_name_bindings():
    seg = PromptSegment(
        id="p1",
        text=PROSE,
        reference_binding_ids=["bind-k"],
        reference_name_bindings=[
            {
                "binding_id": "bind-k",
                "prompt_name": "Korri",
                "type": "character",
                "tag": "@Korri",
            }
        ],
    )
    assert seg.reference_name_bindings[0].prompt_name == "Korri"
    assert seg.reference_binding_ids == ["bind-k"]
