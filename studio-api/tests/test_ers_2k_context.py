"""ERS 2K size lock + placement-derived contextual subjects."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.capabilities.handlers.ers_generate import (
    _ers_sheet_prompt,
    _force_ers_honest_t2i,
    _resolve_ers_grounding,
    build_ers_image_body,
    ers_2k_pixels,
)
from app.codirector.knowledgebase.ers_compiler import compile_environment_reference_sheet_prompt
from app.spatial_map.schemas import (
    SpatialCharacterPlacement,
    SpatialMapDocument,
    SpatialPropPlacement,
)


def test_ers_2k_pixels_locks_native_16_9_probe() -> None:
    assert ers_2k_pixels("16:9") == (2560, 1440)
    w, h = ers_2k_pixels("9:16")
    assert w % 8 == 0 and h % 8 == 0
    assert (w, h) != (2560, 1440)
    assert w < h


def test_build_ers_image_body_is_native_2k_t2i() -> None:
    body = build_ers_image_body(
        prompt="Environment reference sheet",
        direction="sheet",
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        sheet_id="sheet-1",
        spatial_map_id="map-1",
        selected={"referenceImage": "must-not-survive", "sourceAssetId": "nope"},
    )
    assert body["width"] == 2560
    assert body["height"] == 1440
    assert body["operation"] == "image.generate"
    assert "referenceImage" not in body
    assert "sourceAssetId" not in body
    stripped = _force_ers_honest_t2i(dict(body), reference_id="atlas-1")
    assert stripped["operation"] == "image.generate"
    assert "referenceImage" not in stripped


def test_grounding_uses_visible_placements_only() -> None:
    document = SpatialMapDocument(
        projectId="proj-generic",
        characters=[
            SpatialCharacterPlacement(
                characterId="char-visible",
                label="Mira",
                tag="@Mira",
                slotIndex=0,
                visible=True,
            ),
            SpatialCharacterPlacement(
                characterId="char-hidden",
                label="Hidden",
                visible=False,
            ),
        ],
        props=[
            SpatialPropPlacement(
                propId="prop-visible",
                label="Lantern",
                tag="#lantern",
                visible=True,
            ),
        ],
    )
    grounding = _resolve_ers_grounding(None, "proj-generic", document)
    assert grounding["character_ids"] == ["char-visible"]
    assert grounding["prop_ids"] == ["prop-visible"]
    assert "Mira" in grounding["characters"]
    assert "Hidden" not in grounding["characters"]
    blob = " ".join(grounding["contextual_subjects"])
    assert "Mira" in blob
    assert "Lantern" in blob
    assert "Hidden" not in blob


def test_sheet_prompt_confines_subjects_to_contextual_panel() -> None:
    document = SpatialMapDocument(
        projectId="proj-generic",
        masterEnvironmentPrompt="Cold warehouse with high windows.",
        characters=[
            SpatialCharacterPlacement(characterId="char-1", label="Mira", slotIndex=0),
        ],
        props=[
            SpatialPropPlacement(propId="prop-1", label="Lantern"),
        ],
    )
    grounding = _resolve_ers_grounding(None, "proj-generic", document)
    sheet = SimpleNamespace(
        name="Harbor Warehouse",
        description="A cold industrial warehouse interior with high windows.",
        spatialMap=SimpleNamespace(northLockDirection="north", mapId=document.id),
    )
    prompt = _ers_sheet_prompt(sheet, document, grounding).lower()
    assert "contextual production — occupied scale" in prompt
    assert "mira" in prompt
    assert "lantern" in prompt
    assert "characters (scale / occupancy" not in prompt
    hero = prompt[prompt.index("1. hero environment") : prompt.index("4. directional")]
    assert "environment-only" in hero
    assert "mira" not in hero


def test_compiler_does_not_need_schnick_named_branch() -> None:
    src = compile_environment_reference_sheet_prompt.__code__.co_consts
    joined = " ".join(str(item) for item in src if isinstance(item, str)).lower()
    assert "schnick" not in joined
    assert "if schnick" not in joined
