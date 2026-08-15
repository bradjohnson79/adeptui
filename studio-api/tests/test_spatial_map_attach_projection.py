"""ERS projection + Scene Creator structured attachment state (Workstream E)."""

from __future__ import annotations

from types import SimpleNamespace

from app.spatial_map.ers_contracts import EnvironmentReferencePackage, ShotRequest
from app.spatial_map.ers_projection import (
    compile_structured_blocking,
    grid_cell_label,
    project_ers_placements,
    project_prop_placement,
)
from app.spatial_map.schemas import SpatialCharacterPlacement, SpatialPropPlacement


def test_grid_cell_label_f6() -> None:
    assert grid_cell_label(5, 5) == "F6"
    assert grid_cell_label(-1, 5) == ""
    assert grid_cell_label(None, 5) == ""


def test_ers_attached_prop_projection_includes_fields_and_no_fake_xy() -> None:
    prop = SpatialPropPlacement(
        label="Coffee Cup",
        propId="coffee-1",
        placementMode="attached",
        attachedCharacterId="korri",
        attachedCharacterSlot=1,
        relationship="held",
        attachmentPoint="right_hand",
        x=1.25,
        y=0.4,
        z=2.0,
        gridRow=-1,
        gridColumn=-1,
    )
    out = project_prop_placement(prop)
    assert out["placementMode"] == "attached"
    assert out["attachedCharacterId"] == "korri"
    assert out["attachedCharacterSlot"] == 1
    assert out["relationship"] == "held"
    assert out["attachmentPoint"] == "right_hand"
    assert out["propId"] == "coffee-1"
    assert out["x"] is None
    assert out["y"] is None
    assert out["z"] is None
    assert out["normalizedX"] is None
    assert out["normalizedY"] is None
    assert out["gridRow"] == -1
    assert out["gridColumn"] == -1


def test_ers_independent_prop_keeps_grid() -> None:
    prop = SpatialPropPlacement(
        label="Espresso Machine",
        propId="machine-1",
        placementMode="independent",
        gridRow=3,
        gridColumn=2,
        normalizedX=0.1,
        normalizedY=-0.2,
        x=0.5,
        z=-0.4,
    )
    out = project_prop_placement(prop)
    assert out["placementMode"] == "independent"
    assert out["relationship"] is None
    assert out["attachedCharacterId"] is None
    assert out["gridRow"] == 3
    assert out["gridColumn"] == 2
    assert out["normalizedX"] == 0.1
    assert out["normalizedY"] == -0.2
    assert out["x"] == 0.5


def test_project_ers_placements_korri_coffee() -> None:
    korri = SpatialCharacterPlacement(
        characterId="korri",
        label="Korri",
        slotIndex=0,
        gridColumn=5,
        gridRow=5,
        x=0.2,
        z=-0.1,
    )
    coffee = SpatialPropPlacement(
        label="Coffee Cup",
        propId="coffee-1",
        placementMode="attached",
        attachedCharacterId="korri",
        attachedCharacterSlot=1,
        relationship="held",
        attachmentPoint="right_hand",
        x=0.2,
        z=-0.1,
    )
    placements = project_ers_placements(characters=[korri], props=[coffee])
    assert len(placements) == 2
    character = placements[0]
    prop = placements[1]
    assert character["characterId"] == "korri"
    assert character["label"] == "Korri"
    assert character["gridColumn"] == 5
    assert character["gridRow"] == 5
    assert prop["placementMode"] == "attached"
    assert prop["relationship"] == "held"
    assert prop["attachmentPoint"] == "right_hand"
    assert prop["x"] is None
    assert prop["y"] is None


def test_structured_blocking_korri_coffee_held_right_hand() -> None:
    state = compile_structured_blocking(
        [
            {
                "characterId": "korri",
                "label": "Korri",
                "slotIndex": 0,
                "gridColumn": 5,
                "gridRow": 5,
            },
            {
                "propId": "coffee-1",
                "label": "Coffee Cup",
                "placementMode": "attached",
                "attachedCharacterId": "korri",
                "attachedCharacterSlot": 1,
                "relationship": "held",
                "attachmentPoint": "right_hand",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            },
        ],
        prop_approved={"coffee-1": True},
    )
    assert "Character: Korri, Position: F6" in state["lines"]
    assert "Attached Prop: Coffee Cup, Relationship: Held, Attachment: Right Hand" in state["lines"]
    assert state["conceptual_prose"] == (
        "Korri is holding the approved Coffee Cup prop in the right hand."
    )
    assert state["attachments"][0]["relationship"] == "held"
    assert state["attachments"][0]["attachmentPoint"] == "right_hand"
    assert state["attachments"][0]["attachedCharacterId"] == "korri"


def test_overlapping_cells_do_not_infer_attachment() -> None:
    state = compile_structured_blocking(
        [
            {
                "characterId": "korri",
                "label": "Korri",
                "gridColumn": 5,
                "gridRow": 5,
                "x": 0.0,
                "z": 0.0,
            },
            {
                "propId": "coffee-1",
                "label": "Coffee Cup",
                "placementMode": "independent",
                "gridColumn": 5,
                "gridRow": 5,
                "x": 0.0,
                "z": 0.0,
            },
        ]
    )
    assert "Character: Korri, Position: F6" in state["lines"]
    assert "Prop: Coffee Cup, Position: F6" in state["lines"]
    assert not any(line.startswith("Attached Prop:") for line in state["lines"])
    assert state["attachments"] == []
    assert "holding" not in state["conceptual_prose"]


def test_compile_shot_prompt_emits_structured_attachment_state(monkeypatch) -> None:
    from app.codirector import entity_resolver as er

    monkeypatch.setattr(
        er,
        "_character_metadata",
        lambda db, pid, ids: [
            {
                "character_id": "korri",
                "name": "Korri",
                "description": "",
                "visual_description": "",
                "visual_style": "",
                "approved_casting_asset_id": "cast-korri",
                "reference_asset_ids": [],
            }
        ],
    )
    monkeypatch.setattr(
        er,
        "_prop_metadata",
        lambda db, pid, ids: [
            {
                "id": "coffee-1",
                "prop_id": "coffee-1",
                "tag": "coffee-cup",
                "display_label": "Coffee Cup",
                "approved_asset_id": "prop-asset-1",
                "library_asset_id": "prop-asset-1",
                "description": "",
                "notes": "",
            }
        ],
    )
    monkeypatch.setattr(er, "_project_visual_style", lambda db, pid: "")

    package = EnvironmentReferencePackage(
        project_id="proj-1",
        scene_layout_id="map-1",
        placements=[
            {
                "characterId": "korri",
                "label": "Korri",
                "slotIndex": 0,
                "gridColumn": 5,
                "gridRow": 5,
            },
            {
                "propId": "coffee-1",
                "label": "Coffee Cup",
                "placementMode": "attached",
                "attachedCharacterId": "korri",
                "attachedCharacterSlot": 1,
                "relationship": "held",
                "attachmentPoint": "right_hand",
                "x": 0.0,
                "y": 0.0,
            },
        ],
    )
    shot = ShotRequest(
        index=0,
        raw_text="@Korri #coffee-cup",
        characters=["korri"],
        prop_entities=["coffee-1"],
    )
    body = er.compile_shot_prompt(SimpleNamespace(), "proj-1", shot, ers_package=package)
    prompt = body["prompt"]
    assert "Character: Korri, Position: F6" in prompt
    assert "Attached Prop: Coffee Cup, Relationship: Held, Attachment: Right Hand" in prompt
    assert "Korri is holding the approved Coffee Cup prop in the right hand." in prompt
    ctx = body["creativeContext"]
    blocking = ctx["structured_blocking"]
    assert blocking["attachments"][0]["relationship"] == "held"
    assert blocking["attachments"][0]["attachmentPoint"] == "right_hand"
    assert blocking["attachments"][0]["attachedCharacterId"] == "korri"
    # Identity / approved asset stay separate from the relationship store.
    assert ctx["characters"][0]["approved_casting_asset_id"] == "cast-korri"
    assert ctx["prop_entities"][0]["approved_asset_id"] == "prop-asset-1"
    assert "approved_asset_id" not in blocking["attachments"][0]

def test_compile_shot_prompt_attaches_ers_composite_when_directionals_null(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.codirector import entity_resolver as er
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage, ShotRequest

    monkeypatch.setattr(er, "_character_metadata", lambda db, pid, ids: [])
    monkeypatch.setattr(er, "_prop_metadata", lambda db, pid, ids: [])
    monkeypatch.setattr(er, "_project_visual_style", lambda db, pid: "")

    package = EnvironmentReferencePackage(
        project_id="proj-1",
        scene_layout_id="map-1",
        directional_assets={"north": None, "east": None, "south": None, "west": None},
        ers_composite_asset_id="2f2e871b-efef-4b67-a1fc-26b7bb50aa7b",
        placements=[],
    )
    shot = ShotRequest(index=0, raw_text="Camera 1 medium", characters=[], prop_entities=[])
    body = er.compile_shot_prompt(SimpleNamespace(), "proj-1", shot, ers_package=package)
    ctx = body["creativeContext"]
    assert ctx["ers_composite_asset_id"] == "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b"
    assert "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b" in (ctx.get("reference_image_ids") or [])
    assert body.get("referenceImage") == "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b"
    assert body.get("reference_image") == "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b"


def test_compile_shot_prompt_keeps_directional_over_composite(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.codirector import entity_resolver as er
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage, ShotRequest

    monkeypatch.setattr(er, "_character_metadata", lambda db, pid, ids: [])
    monkeypatch.setattr(er, "_prop_metadata", lambda db, pid, ids: [])
    monkeypatch.setattr(er, "_project_visual_style", lambda db, pid: "")

    package = EnvironmentReferencePackage(
        project_id="proj-1",
        scene_layout_id="map-1",
        directional_assets={"north": "north-asset-1", "east": None, "south": None, "west": None},
        ers_composite_asset_id="2f2e871b-efef-4b67-a1fc-26b7bb50aa7b",
        placements=[],
    )
    shot = ShotRequest(
        index=0, raw_text="north", characters=[], prop_entities=[], orientation="north"
    )
    body = er.compile_shot_prompt(SimpleNamespace(), "proj-1", shot, ers_package=package)
    ctx = body["creativeContext"]
    refs = ctx.get("reference_image_ids") or []
    assert "north-asset-1" in refs
    assert ctx["ers_directional_ref"]["asset_id"] == "north-asset-1"
    assert "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b" not in refs

