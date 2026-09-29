"""H3 uploads a one-figure crop from an approved CRS, not the labeled bible."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from PIL import Image, ImageDraw

from app.character_identity.h3_identity_still import (
    classify_sheet_layout,
    looks_like_reference_sheet,
    resolve_h3_character_source,
    write_identity_still,
)
from app.character_identity.character_sheet_compose import plan_v3_character_sheet
from app.video_runtime.comfy_asset_stage import stage_h3_visual_asset, stage_library_asset


def _sheet_asset(path: Path, asset_id: str = "sheet-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=asset_id,
        path=str(path),
        filename="Hero.jpeg",
        tag="Hero",
        kind="image",
        labels_json='["character_sheet", "crs", "character_reference_sheet"]',
        prompt_meta_json="{}",
        comfy_name="",
    )


def _write_type_a_sheet(path: Path) -> Path:
    im = Image.new("RGB", (1536, 864), (230, 230, 232))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1536, 90), fill=(20, 40, 80))
    colors = ((200, 40, 40), (40, 180, 40), (40, 40, 200), (200, 180, 40))
    for idx, color in enumerate(colors):
        x0 = 28 + idx * 155
        draw.rectangle((x0, 150, x0 + 118, 500), fill=color)
    draw.rectangle((690, 120, 1024, 490), fill=(90, 90, 200))
    draw.rectangle((40, 560, 1496, 840), fill=(248, 248, 248))
    im.save(path, format="JPEG", quality=92)
    return path


def _write_portrait(path: Path) -> Path:
    im = Image.new("RGB", (512, 768), (18, 18, 22))
    draw = ImageDraw.Draw(im)
    draw.ellipse((160, 80, 350, 300), fill=(200, 160, 120))
    draw.rectangle((200, 320, 310, 700), fill=(40, 80, 160))
    im.save(path)
    return path


def _write_four_panel(path: Path) -> Path:
    im = Image.new("RGB", (256, 256), (8, 8, 8))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 120, 120), fill=(200, 40, 40))
    draw.rectangle((136, 0, 255, 120), fill=(40, 180, 40))
    draw.rectangle((0, 136, 120, 255), fill=(40, 40, 200))
    draw.rectangle((136, 136, 255, 255), fill=(200, 180, 40))
    draw.rectangle((124, 0, 132, 255), fill=(255, 255, 255))
    draw.rectangle((0, 124, 255, 132), fill=(255, 255, 255))
    im.save(path)
    return path


def test_landscape_labeled_sheet_is_detected(tmp_path: Path) -> None:
    path = _write_type_a_sheet(tmp_path / "sheet.jpg")
    asset = _sheet_asset(path)
    assert looks_like_reference_sheet(path, asset) is True


def test_single_portrait_is_not_a_sheet(tmp_path: Path) -> None:
    path = _write_portrait(tmp_path / "hero.png")
    asset = SimpleNamespace(
        id="hero-1",
        path=str(path),
        filename="hero.png",
        tag="hero",
        kind="image",
        labels_json="[]",
        prompt_meta_json="{}",
    )
    assert looks_like_reference_sheet(path, asset) is False
    source, ledger = resolve_h3_character_source(asset, cache_dir=tmp_path / "cache")
    assert source == path
    assert ledger["uploaded"] == "library_file"


def test_type_a_still_is_one_figure_not_the_bible(tmp_path: Path) -> None:
    path = _write_type_a_sheet(tmp_path / "sheet.jpg")
    dest = tmp_path / "still.png"
    assert write_identity_still(path, dest, asset=_sheet_asset(path)) is True
    still = Image.open(dest)
    sheet = Image.open(path)
    assert still.size != sheet.size
    assert still.size[0] / max(1, still.size[1]) < 0.7
    # First turnaround figure is red-dominant.
    px = list(still.resize((1, 1)).getdata())[0]
    assert px[0] > px[1] and px[0] > px[2]


def _write_adept_v3_sheet(path: Path) -> Path:
    im = Image.new("RGB", (2560, 1080), (18, 18, 20))
    draw = ImageDraw.Draw(im)
    plan = plan_v3_character_sheet(2560, 1080)
    colors = {
        "full_body_front": (200, 40, 40),
        "full_body_side_left": (40, 180, 40),
        "full_body_three_quarter_front": (40, 40, 200),
        "full_body_back": (200, 180, 40),
    }
    for cell in plan["views"]:
        x0, y0, x1, y1 = cell["identityBbox"]
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=colors[cell["role"]])
    nx0, ny0, nx1, ny1 = plan["notes"]["bbox"]
    draw.rectangle((nx0, ny0, nx1 - 1, ny1 - 1), fill=(40, 40, 48))
    im.save(path)
    return path


def test_adept_cc_sheet_uses_front_tile_not_notes(tmp_path: Path) -> None:
    path = _write_adept_v3_sheet(tmp_path / "cc.png")
    asset = _sheet_asset(path)
    asset.prompt_meta_json = '{"layout": "v3_21x9_express", "composer": "adept", "objective": "character_sheet_composed"}'
    assert classify_sheet_layout(path, asset) == "adept_v3"
    dest = tmp_path / "still.png"
    assert write_identity_still(path, dest, asset=asset) is True
    still = Image.open(dest)
    assert still.size != Image.open(path).size
    px = list(still.resize((1, 1)).getdata())[0]
    assert px[0] > 140 and px[1] < 80


def test_four_panel_still_uses_front_tile(tmp_path: Path) -> None:
    path = _write_four_panel(tmp_path / "grid.png")
    dest = tmp_path / "still.png"
    asset = _sheet_asset(path)
    assert looks_like_reference_sheet(path, asset) is True
    assert write_identity_still(path, dest, asset=asset) is True
    px = list(Image.open(dest).resize((1, 1)).getdata())[0]
    assert px[0] > 140 and px[1] < 80


def test_character_slot_stages_plain_copy_not_h3id(tmp_path: Path) -> None:
    """Timeline H3 LoadImage must receive creator CRS bytes (no crop/re-encode)."""
    path = _write_type_a_sheet(tmp_path / "sheet.jpg")
    asset = _sheet_asset(path, "crs-korri")
    staged = stage_h3_visual_asset(
        asset,
        role="character",
        input_dir=tmp_path / "input",
        cache_dir=tmp_path / "cache",
    )
    assert staged.comfy_name == "studio/crs-korri.jpg" or staged.comfy_name.endswith(".jpeg")
    assert "_h3id" not in staged.comfy_name
    assert staged.ledger.get("uploaded") == "library_file"
    assert staged.ledger.get("plainCopy") is True
    assert staged.ledger.get("h3IdentityStill") == "bypassed"
    assert staged.ledger.get("identityAuthority") == "reference_image"
    assert Path(staged.staged_path).stat().st_size == path.stat().st_size
    assert Path(staged.staged_path).read_bytes() == path.read_bytes()


def test_character_slot_opt_in_derived_identity_still(tmp_path: Path) -> None:
    """Legacy crop path remains available only via derive_identity_still=True."""
    path = _write_type_a_sheet(tmp_path / "sheet.jpg")
    asset = _sheet_asset(path, "crs-korri")
    staged = stage_h3_visual_asset(
        asset,
        role="character",
        input_dir=tmp_path / "input",
        cache_dir=tmp_path / "cache",
        derive_identity_still=True,
    )
    assert staged.comfy_name == "studio/crs-korri_h3id.png"
    assert staged.ledger.get("uploaded") == "derived_identity_still"
    assert staged.ledger.get("identityAuthority") == "reference_image"
    assert (tmp_path / "input" / "studio" / "crs-korri_h3id.png").is_file()
    still = Image.open(staged.staged_path)
    assert still.size != Image.open(path).size
    assert still.size[0] / max(1, still.size[1]) < 0.7


def test_place_slot_keeps_full_library_file(tmp_path: Path) -> None:
    path = _write_type_a_sheet(tmp_path / "place.jpg")
    asset = _sheet_asset(path, "place-1")
    staged = stage_h3_visual_asset(
        asset,
        role="place",
        input_dir=tmp_path / "input",
        cache_dir=tmp_path / "cache",
    )
    assert staged.comfy_name == "studio/place-1.jpg" or staged.comfy_name.endswith(".jpeg")
    assert "_h3id" not in staged.comfy_name
    assert staged.ledger.get("uploaded") == "library_file"
    assert Path(staged.staged_path).stat().st_size == path.stat().st_size


def test_live_approved_sheets_become_one_figure_stills(tmp_path: Path) -> None:
    import pytest

    root = Path(__file__).resolve().parents[2] / "data" / "assets" / "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
    korri = root / "a42e77e0-dfe3-4ac9-85af-ab98dfc510e5.jpeg"
    addex = root / "91b82df6-6c5a-410a-bdb8-6cd3f79753c7.jpeg"
    if not korri.is_file() or not addex.is_file():
        pytest.skip("approved Korri/Addex CRS files are not in this checkout")
    for path, asset_id, name in (
        (korri, "a42e77e0-dfe3-4ac9-85af-ab98dfc510e5", "Korri 40 years old.jpeg"),
        (addex, "91b82df6-6c5a-410a-bdb8-6cd3f79753c7", "Addex.jpeg"),
    ):
        asset = _sheet_asset(path, asset_id)
        asset.filename = name
        source, ledger = resolve_h3_character_source(asset, cache_dir=tmp_path / "cache")
        assert ledger["uploaded"] == "derived_identity_still"
        assert ledger["identityAuthority"] == "reference_image"
        still = Image.open(source)
        sheet = Image.open(path)
        assert still.size[0] >= 150
        assert still.size[1] >= 300
        assert still.size != sheet.size
        assert still.size[0] / max(1, still.size[1]) < 0.7


def test_live_adept_cc_sheet_front_is_one_figure(tmp_path: Path) -> None:
    import pytest

    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "projects"
        / "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
        / "assets"
        / "character_sheet_4a2e9cbe_c1_1c986575.png"
    )
    if not path.is_file():
        pytest.skip("Adept Character Creator Korri sheet is not in this checkout")
    asset = _sheet_asset(path, "eb99dae4-ca9d-41bd-8a57-997106957227")
    asset.filename = path.name
    asset.prompt_meta_json = '{"layout": "v3_21x9_express", "composer": "adept", "objective": "character_sheet_composed"}'
    assert classify_sheet_layout(path, asset) == "adept_v3"
    source, ledger = resolve_h3_character_source(asset, cache_dir=tmp_path / "cache")
    assert ledger["uploaded"] == "derived_identity_still"
    still = Image.open(source)
    sheet = Image.open(path)
    assert still.size != sheet.size
    assert still.size[0] / max(1, still.size[1]) < 0.85


def test_plain_stage_still_copies_library_bytes(tmp_path: Path) -> None:
    path = _write_portrait(tmp_path / "face.png")
    asset = SimpleNamespace(id="face-1", path=str(path), filename="face.png", comfy_name="", kind="image")
    staged = stage_library_asset(asset, input_dir=tmp_path / "input")
    assert staged.comfy_name == "studio/face-1.png"
    assert staged.bytes == path.stat().st_size
