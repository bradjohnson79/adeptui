"""G11 — Adept deterministic labeled CRS compositor.

Asserts the compositor API layout contract (regions + drawn strings).
Does not OCR pixels. Does not generate live. Does not start uvicorn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.character_sheet_compose import (
    CRS_SHEET_LONG_EDGE,
    CRS_SHEET_MIN_LONG_EDGE,
    EMPTY_PLACEHOLDER,
    LAW_VIEW_DISPLAY_LABELS,
    compose_labeled_character_sheet,
    plan_labeled_character_sheet,
    sheet_texts_from_profile,
)
from app.character_identity.visual_sheet import (
    CHARACTER_SHEET_GRID_COLS,
    CHARACTER_SHEET_GRID_ROWS,
    CHARACTER_SHEET_TILE_SIZE,
    _compose_character_sheet_grid,
)


def _tile(path: Path, color: tuple[int, int, int]) -> str:
    from PIL import Image

    Image.new("RGB", (512, 768), color).save(str(path), format="PNG")
    return str(path)


def _five_tiles(tmp_path: Path) -> list[str]:
    colors = (
        (200, 40, 40),
        (40, 180, 40),
        (40, 40, 200),
        (200, 180, 40),
        (180, 40, 180),
    )
    return [_tile(tmp_path / f"view_{i}.png", color) for i, color in enumerate(colors)]


PROFILE = {
    "name": "Korri Test",
    "role": "Scout",
    "description": "Keeps the ridge watch.",
    "height_description": "5'1\"",
    "body_type": "petite athletic",
    "wardrobe": {
        "name": "Handmade cloth",
        "description": "Uneven black wraps",
        "footwear": "brown sandals",
    },
}


def test_sheet_texts_use_profile_fields_only():
    texts = sheet_texts_from_profile(PROFILE)
    assert texts["name"] == "Korri Test"
    assert texts["role"] == "Scout"
    assert texts["notes"] == "Keeps the ridge watch."
    assert "Handmade cloth" in texts["wardrobe"]
    assert "brown sandals" in texts["wardrobe"]
    assert "5'1\"" in texts["height"]
    empty = sheet_texts_from_profile({})
    assert empty["name"] == ""
    assert empty["notes"] == ""
    assert empty["wardrobe"] == ""
    assert empty["specs"] == ""
    assert empty["height"] == ""


def test_plan_labeled_character_sheet_exposes_labels_and_regions():
    layout = plan_labeled_character_sheet(5, profile=PROFILE)
    assert layout["layout"] == "law_views_labeled"
    assert layout["composer"] == "adept"
    assert layout["labels"] == list(LAW_VIEW_DISPLAY_LABELS)
    assert layout["labels"] == ["Front", "3/4", "Side", "Back", "Close-Up"]
    assert layout["longEdge"] >= CRS_SHEET_MIN_LONG_EDGE
    assert layout["longEdge"] == CRS_SHEET_LONG_EDGE
    assert layout["grid"]["cols"] == 3
    assert layout["grid"]["rows"] == 2
    assert len(layout["views"]) == 5
    for cell, expected in zip(layout["views"], LAW_VIEW_DISPLAY_LABELS):
        x0, y0, x1, y1 = cell["bbox"]
        assert x1 > x0 and y1 > y0
        lx0, ly0, lx1, ly1 = cell["labelBbox"]
        assert ly1 == y1
        assert cell["label"] == expected
        assert expected in layout["drawnStrings"]
    titles = {p["title"] for p in layout["panels"]}
    assert titles == {"Character Notes", "Wardrobe / Gear", "Technical Specs"}
    assert "Korri Test" in layout["drawnStrings"]
    assert "Scout" in layout["drawnStrings"]
    assert "Keeps the ridge watch." in layout["drawnStrings"]
    assert any("Handmade cloth" in s for s in layout["drawnStrings"])
    assert any("5'1\"" in s for s in layout["drawnStrings"])


def test_missing_profile_fields_still_draw_section_headers():
    layout = plan_labeled_character_sheet(5, profile={})
    assert layout["header"]["name"] == ""
    assert layout["header"]["role"] == ""
    for panel in layout["panels"]:
        assert panel["title"] in layout["drawnStrings"]
        assert panel["placeholder"] is True
        assert panel["text"] == ""
        assert EMPTY_PLACEHOLDER in layout["drawnStrings"]
    # Do not invent biography when profile fields are empty.
    joined = " ".join(layout["drawnStrings"])
    assert "was born" not in joined.lower()
    assert "biography" not in joined.lower()


def test_compose_five_labeled_tiles_returns_layout_and_2k_png(tmp_path):
    from PIL import Image

    paths = _five_tiles(tmp_path)
    out = tmp_path / "sheet.png"
    layout_out: dict = {}
    result = _compose_character_sheet_grid(
        paths,
        str(out),
        profile=PROFILE,
        layout_out=layout_out,
    )
    assert result == str(out)
    assert out.is_file()
    im = Image.open(out)
    assert max(im.size) >= CRS_SHEET_MIN_LONG_EDGE
    assert max(im.size) == CRS_SHEET_LONG_EDGE
    assert layout_out["labels"] == list(LAW_VIEW_DISPLAY_LABELS)
    assert layout_out["path"] == str(out)
    assert layout_out["width"] == im.size[0]
    assert layout_out["height"] == im.size[1]
    # Label bars are Adept-drawn dark strips: not a single tile fill color.
    for cell in layout_out["views"]:
        lx0, ly0, lx1, ly1 = cell["labelBbox"]
        crop = im.crop((lx0, ly0, lx1, ly1))
        colors = crop.getcolors(maxcolors=crop.size[0] * crop.size[1])
        assert colors is not None
        assert len(colors) > 1


def test_compose_labeled_api_matches_grid_wrapper(tmp_path):
    paths = _five_tiles(tmp_path)
    direct = compose_labeled_character_sheet(
        paths, str(tmp_path / "direct.png"), profile=PROFILE
    )
    assert direct["labels"] == list(LAW_VIEW_DISPLAY_LABELS)
    assert Path(direct["path"]).is_file()


def test_unlabeled_four_view_grid_still_2x2(tmp_path):
    from PIL import Image

    paths = [_tile(tmp_path / f"v{i}.png", (80, 80, 80)) for i in range(4)]
    out = tmp_path / "four.png"
    result = _compose_character_sheet_grid(paths, str(out))
    im = Image.open(result)
    tile = CHARACTER_SHEET_TILE_SIZE
    assert im.size == (tile * CHARACTER_SHEET_GRID_COLS, tile * CHARACTER_SHEET_GRID_ROWS)


def test_compose_rejects_wrong_view_count(tmp_path):
    with pytest.raises(ValueError):
        _compose_character_sheet_grid(
            [_tile(tmp_path / "one.png", (10, 10, 10))],
            str(tmp_path / "bad.png"),
        )
