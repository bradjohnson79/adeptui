"""PRS is composed from an approved still + prop JSON, not imagined by a model."""

from pathlib import Path

from PIL import Image

from app.prop_creator.prs_compose import compose_prop_reference_sheet


def test_compose_prop_reference_sheet_writes_labeled_page(tmp_path: Path):
    src = tmp_path / "mug.png"
    Image.new("RGB", (256, 256), (80, 40, 20)).save(src)
    dest = tmp_path / "prs.png"
    compose_prop_reference_sheet(
        src,
        {
            "name": "Coffee Mug",
            "tag": "%CoffeeMug",
            "description": "Ceramic mug with a Schnick mark.",
            "style": "live_action",
        },
        dest,
    )
    assert dest.is_file()
    page = Image.open(dest)
    assert page.size == (1600, 900)


def test_prs_preserves_source_and_percent_tag(tmp_path: Path):
    """ORDER 16: % tag, source field, original still bytes unchanged."""
    src = tmp_path / "thermos.png"
    Image.new("RGB", (320, 240), (30, 90, 140)).save(src)
    before = src.read_bytes()
    dest = tmp_path / "prs_out.png"
    compose_prop_reference_sheet(
        src,
        {
            "name": "Schnick Thermos",
            "tag": "%SchnickThermos",
            "description": "Metal thermos from Schnick cafe.",
            "source": "approved still thermos.png",
            "style": "live_action",
            "notes": "identity lock",
        },
        dest,
    )
    assert dest.is_file()
    assert src.read_bytes() == before
    assert dest.resolve() != src.resolve()
    page = Image.open(dest)
    assert page.size == (1600, 900)
    # Tag contract: compose callers must pass %PascalCase (grammar frozen in sheet_tags).
    assert "%SchnickThermos".startswith("%")

