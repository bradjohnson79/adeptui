"""One-pass GPT Image 2 full-sheet ERS: pipeline, prompt, persist, repair."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.codirector.knowledgebase.ers_compiler import (
    ERS_TEMPLATE_ID,
    compile_environment_reference_sheet_prompt,
)
from app.spatial_map.ers_collage_templates import ORIGINAL_ERS_V1, lookup_collage_template
from app.spatial_map.ers_component_pipeline import resolve_pipeline_mode
from app.spatial_map.ers_full_sheet import (
    FAIL_EXTRA_BOARD,
    FAIL_NESTED_OCCUPIED_FRAME,
    assess_extra_board_below_canonical,
    assess_full_sheet_layout,
    assess_panel9_nested_frame,
    crop_panel_bytes,
    persist_repair_lineage,
    validate_full_sheet,
)
from app.spatial_map.ers_packet import compile_ers_packet


def test_gpt_default_is_one_pass_full_sheet() -> None:
    assert resolve_pipeline_mode("", gpt_selected=True) == "full_sheet"
    assert resolve_pipeline_mode("full_sheet_api") == "full_sheet"
    assert resolve_pipeline_mode("", gpt_selected=True, retry_component="occupied") == "components"
    assert resolve_pipeline_mode("", gpt_selected=False) == "collage"


def test_full_sheet_prompt_has_nine_panels_and_dynamic_identity() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Observatory Control Room",
        environment_description="A locked circular observatory with instrument rings.",
        characters=[
            {
                "displayName": "Special Agent Jacob Barnes",
                "characterId": "10303eba-ed95-49fe-a86b-e5493b7a1c75",
                "identityFacts": ["species: human", "wardrobe: black suit, red tie"],
                "wardrobe": "black suit, white shirt, red tie",
            }
        ],
        spatial_map={"id": "map-1", "northLockDirection": "north"},
    )
    prompt = compiled["prompt"]
    lowered = prompt.lower()
    assert compiled["templateId"] == ERS_TEMPLATE_ID
    for needle in (
        "panel 1 — hero environment",
        "panel 2 — spatial / top-down",
        "panel 3 — structural / 3d",
        "panel 4 — directional / orthographic views",
        "panel 5 — materials",
        "panel 6 — lighting",
        "panel 7 — environment dna",
        "panel 8 — continuity rules",
        "panel 9 — contextual production",
        "north",
        "east",
        "south",
        "west",
    ):
        assert needle in lowered, needle
    assert "approved saved character special agent jacob barnes" in lowered
    assert "do not substitute a generic person" in lowered
    assert "do not convert this into a loose dashboard" in lowered
    assert "do not redesign the ers layout" in lowered
    assert "jacob" in lowered
    assert "generic person" in lowered


def test_full_sheet_prompt_does_not_hardcode_jacob_without_canon() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Harbor",
        environment_description="Cold warehouse.",
        characters=[{"displayName": "Mira", "identityFacts": ["species: human"]}],
    )
    prompt = compiled["prompt"]
    assert "Special Agent Jacob Barnes" not in prompt
    assert "approved saved character Mira" in prompt


def test_original_template_alias_and_scaled_panel9() -> None:
    contract = lookup_collage_template(template_id=ORIGINAL_ERS_V1)
    assert contract is not None
    assert contract.allow_scaled is True
    assert contract.panel_content("occupied") is not None
    assert contract.panel_content("hero") is not None
    image = Image.new("RGB", (2560, 1440), (20, 30, 40))
    image.paste(Image.new("RGB", (400, 200), (200, 10, 10)), (1600, 760))
    buf = BytesIO()
    image.save(buf, format="PNG")
    cropped = crop_panel_bytes(buf.getvalue(), "occupied", template_id=ORIGINAL_ERS_V1)
    out = Image.open(BytesIO(cropped))
    assert out.size[0] > 10 and out.size[1] > 10


def test_repair_lineage_stamps_original_full_sheet() -> None:
    package = SimpleNamespace(metadata={})
    persist_repair_lineage(
        package,
        original_full_sheet_asset_id="full-1",
        replacement_component="occupied",
        replacement_asset_id="occ-1",
        restitch_composite_asset_id="stitch-1",
    )
    assert package.metadata["originalFullSheetAssetId"] == "full-1"
    assert package.metadata["replacementComponent"] == "occupied"
    assert package.metadata["replacementAssetId"] == "occ-1"
    assert package.metadata["restitchCompositeAssetId"] == "stitch-1"
    assert package.metadata["repairRevision"] == 1


def test_stamp_repair_on_sheet_updates_identity_and_lineage() -> None:
    from app.spatial_map.ers_full_sheet import stamp_repair_on_sheet

    sheet = SimpleNamespace(provenance=SimpleNamespace(details={"identityGate": {"verdict": "FAIL_CHARACTER_IDENTITY"}}))
    stamp_repair_on_sheet(
        sheet,
        identity={"verdict": "PASS", "reason": "Jacob matches the approved reference."},
        original_full_sheet_asset_id="full-1",
        replacement_component="occupied",
        replacement_asset_id="occ-1",
        restitch_composite_asset_id="stitch-1",
        repair_revision=1,
    )
    details = sheet.provenance.details
    assert details["identityGate"]["verdict"] == "PASS"
    assert details["originalFullSheetAssetId"] == "full-1"
    assert details["replacementComponent"] == "occupied"
    assert details["replacementAssetId"] == "occ-1"
    assert details["restitchCompositeAssetId"] == "stitch-1"
    assert details["visualSheetAssetId"] == "stitch-1"
    assert details["repairRevision"] == 1


def test_machine_packet_is_not_parsed_from_gpt_text() -> None:
    document = SimpleNamespace(
        id="map-1",
        projectId="p1",
        title="Lab",
        backgroundAssetId="atlas-1",
        sceneDescription="silver corridor",
        sceneIntent=SimpleNamespace(summary="silver corridor"),
        characters=[
            SimpleNamespace(
                id="c1",
                characterId="10303eba-ed95-49fe-a86b-e5493b7a1c75",
                label="Special Agent Jacob Barnes",
                visible=True,
                normalizedX=0.1,
                normalizedY=-0.2,
                yawDegrees=90,
            )
        ],
        props=[],
        cameras=[],
        environmentalAnchors=[],
    )
    packet = compile_ers_packet(document, project_id="p1")
    assert packet["spatialMapAssetId"] == "atlas-1"
    assert packet["characters"][0]["characterId"] == "10303eba-ed95-49fe-a86b-e5493b7a1c75"



def test_original_template_has_no_m1_m2_m3_region() -> None:
    contract = lookup_collage_template(template_id=ORIGINAL_ERS_V1)
    assert contract is not None
    pixels = dict(contract.panel_pixels or {})
    keys = {str(k).strip().lower() for k in pixels}
    assert "m1" not in keys
    assert "m2" not in keys
    assert "m3" not in keys
    for needle in ("m1", "m2", "m3"):
        assert contract.panel_content(needle) is None
        assert contract.panel_content(needle.upper()) is None


def test_compiled_prompt_forbids_appended_planning_boards() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Harbor Warehouse",
        environment_description="Cold warehouse interior.",
        characters=[{"displayName": "Mira", "identityFacts": ["species: human"]}],
    )
    prompt = compiled["prompt"]
    lowered = prompt.lower()
    assert compiled["templateId"] == ERS_TEMPLATE_ID == ORIGINAL_ERS_V1
    assert "one complete" in lowered
    assert "9-panel" in lowered or "9 panel" in lowered
    assert "exactly 9 sections only" in lowered
    assert "not a storyboard" in lowered
    assert "m1/m2/m3" in lowered
    assert "do not append a planning board" in lowered
    assert "purple board" in lowered
    assert "nested occupied" in lowered
    assert "do not add extra rows" in lowered
    assert "shot-planning" in lowered
    assert "Special Agent Jacob Barnes" not in prompt
    assert "Jacob" not in prompt


def _png(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_extra_board_validation_fails_2560x2220_strip() -> None:
    """Committed 2560x2220 after a ~780px planning strip on a 16:9 sheet MUST fail."""
    sheet = Image.new("RGB", (2560, 1440), (36, 40, 48))
    strip = Image.new("RGB", (2560, 780), (112, 48, 168))  # purple planning board
    fake = Image.new("RGB", (2560, 2220), (0, 0, 0))
    fake.paste(sheet, (0, 0))
    fake.paste(strip, (0, 1440))
    png = _png(fake)
    extra = assess_extra_board_below_canonical(2560, 2220)
    assert extra["ok"] is False
    assert extra["code"] == FAIL_EXTRA_BOARD
    assert extra["extraHeightPx"] > 700
    layout = assess_full_sheet_layout(png)
    assert layout["ok"] is False
    assert layout["code"] == FAIL_EXTRA_BOARD
    result = validate_full_sheet(_DummyDb(), "proj", asset_id="sheet-1", packet={}, png=png)
    assert result["blockingFailure"] == FAIL_EXTRA_BOARD
    assert result["layout"]["ok"] is False
    # Canonical 16:9 and native template sizes must not fail.
    assert assess_extra_board_below_canonical(2560, 1440)["ok"] is True
    assert assess_extra_board_below_canonical(1672, 941)["ok"] is True
    assert assess_extra_board_below_canonical(1672, 1000)["ok"] is True


def test_panel9_nested_frame_is_layout_fail() -> None:
    from PIL import ImageDraw

    image = Image.new("RGB", (1672, 941), (42, 46, 52))
    occupied = (1048, 496, 1660, 632)
    # Varied occupied content, no inner frame — must not brittle-fail.
    occ = Image.new("RGB", (occupied[2] - occupied[0], occupied[3] - occupied[1]), (74, 96, 84))
    draw = ImageDraw.Draw(occ)
    for i in range(0, occ.size[0], 18):
        draw.rectangle((i, 0, i + 8, occ.size[1]), fill=(62 + (i % 20), 88, 70))
    image.paste(occ, (occupied[0], occupied[1]))
    clean = assess_panel9_nested_frame(_png(image))
    assert clean["ok"] is True
    assert clean["code"] is None

    # Obvious inset occupied overlay: second framed scene inside Panel 9.
    ix0, iy0 = 48, 18
    ix1, iy1 = occ.size[0] - 48, occ.size[1] - 18
    draw.rectangle((ix0, iy0, ix1 - 1, iy1 - 1), fill=(210, 190, 160), outline=(0, 0, 0), width=8)
    image.paste(occ, (occupied[0], occupied[1]))
    png = _png(image)
    nested = assess_panel9_nested_frame(png)
    assert nested["ok"] is False, nested
    assert nested["code"] == FAIL_NESTED_OCCUPIED_FRAME
    layout = assess_full_sheet_layout(png)
    assert layout["ok"] is False
    assert layout["code"] == FAIL_NESTED_OCCUPIED_FRAME
    result = validate_full_sheet(_DummyDb(), "proj", asset_id="sheet-2", packet={}, png=png)
    assert result["blockingFailure"] == FAIL_NESTED_OCCUPIED_FRAME
    assert result["layout"]["code"] == FAIL_NESTED_OCCUPIED_FRAME


def test_reference_order_remains_character_then_environment() -> None:
    from app.codirector.capabilities.handlers.ers_generate import order_occupied_reference_assets

    ordered = order_occupied_reference_assets(["char-ref-1"], "env-atlas", ["env-atlas", "layout-ex"])
    assert ordered[0] == "char-ref-1"
    assert ordered[1] == "env-atlas"
    assert "layout-ex" in ordered[1:]


class _DummyDb:
    def get(self, *_a, **_k):
        return None

    def add(self, *_a, **_k):
        return None

    def flush(self):
        return None
