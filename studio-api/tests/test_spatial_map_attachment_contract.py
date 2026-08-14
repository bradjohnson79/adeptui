"""Frozen Spatial Map character-prop attachment contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.spatial_map.attachment import (
    ATTACHED_CHARACTER_SLOTS,
    ATTACHMENT_POINTS,
    PLACEMENT_MODES,
    PROP_RELATIONSHIPS,
    PropAttachmentError,
    attached_slot_from_slot_index,
    slot_index_from_attached_slot,
    validate_prop_attachment,
)
from app.spatial_map.schemas import SpatialPropPlacement, SpatialPropPlacementBody


def test_contract_field_names_and_enums_are_frozen() -> None:
    assert PLACEMENT_MODES == ("independent", "attached")
    assert PROP_RELATIONSHIPS == (
        "held",
        "carried",
        "worn",
        "using",
        "interacting",
        "associated",
    )
    assert ATTACHMENT_POINTS == (
        "left_hand",
        "right_hand",
        "both_hands",
        "head",
        "upper_body",
        "lower_body",
        "back",
        "waist",
        "wrist",
        "shoulder",
        "unspecified",
    )
    assert ATTACHED_CHARACTER_SLOTS == (1, 2, 3, 4)
    fields = SpatialPropPlacement.model_fields
    for name in (
        "placementMode",
        "attachedCharacterSlot",
        "attachedCharacterId",
        "relationship",
        "attachmentPoint",
    ):
        assert name in fields


def test_missing_fields_default_to_independent() -> None:
    prop = SpatialPropPlacement(label="Coffee", propId="coffee-1")
    assert prop.placementMode == "independent"
    assert prop.attachedCharacterSlot is None
    assert prop.attachedCharacterId is None
    assert prop.relationship is None
    assert prop.attachmentPoint is None
    assert prop.propId == "coffee-1"


def test_attach_korri_coffee_held_right_hand() -> None:
    prop = SpatialPropPlacement(
        label="Coffee",
        propId="coffee-1",
        tag="#coffee",
        placementMode="attached",
        attachedCharacterId="korri",
        attachedCharacterSlot=1,
        relationship="held",
        attachmentPoint="right_hand",
    )
    assert prop.propId == "coffee-1"
    assert prop.placementMode == "attached"
    assert prop.attachedCharacterId == "korri"
    assert prop.attachedCharacterSlot == 1
    assert prop.relationship == "held"
    assert prop.attachmentPoint == "right_hand"
    assert prop.normalizedX is None
    assert prop.normalizedY is None


def test_xor_independent_clears_attachment_fields() -> None:
    prop = SpatialPropPlacement(
        label="Coffee",
        propId="coffee-1",
        placementMode="independent",
        attachedCharacterId="korri",
        attachedCharacterSlot=1,
        relationship="held",
        attachmentPoint="right_hand",
    )
    assert prop.placementMode == "independent"
    assert prop.attachedCharacterId is None
    assert prop.attachedCharacterSlot is None
    assert prop.relationship is None
    assert prop.attachmentPoint is None


def test_xor_attached_requires_character_and_relationship() -> None:
    with pytest.raises(ValidationError):
        SpatialPropPlacement(label="Coffee", placementMode="attached")
    with pytest.raises(ValidationError):
        SpatialPropPlacement(
            label="Coffee",
            placementMode="attached",
            relationship="held",
        )
    with pytest.raises(ValidationError):
        SpatialPropPlacement(
            label="Coffee",
            placementMode="attached",
            attachedCharacterId="korri",
        )
    with pytest.raises(PropAttachmentError):
        validate_prop_attachment(
            {
                "placementMode": "attached",
                "attachedCharacterSlot": 0,
                "relationship": "held",
            }
        )


def test_attached_allows_slot_binding_without_id() -> None:
    prop = SpatialPropPlacement(
        label="Coffee",
        propId="coffee-1",
        placementMode="attached",
        attachedCharacterSlot=2,
        relationship="carried",
        attachmentPoint="unspecified",
    )
    assert prop.attachedCharacterId is None
    assert prop.attachedCharacterSlot == 2
    assert prop.relationship == "carried"


def test_backward_compat_legacy_json_does_not_move_positions() -> None:
    legacy = {
        "propId": "coffee-1",
        "label": "Coffee",
        "x": 1.5,
        "y": 0.0,
        "z": -2.0,
        "normalizedX": 0.25,
        "normalizedY": -0.4,
        "gridRow": 3,
        "gridColumn": 6,
        "slotIndex": 0,
        "tag": "#coffee",
    }
    prop = SpatialPropPlacement.model_validate(legacy)
    assert prop.placementMode == "independent"
    assert prop.attachedCharacterId is None
    assert prop.relationship is None
    assert prop.x == 1.5
    assert prop.z == -2.0
    assert prop.normalizedX == 0.25
    assert prop.normalizedY == -0.4
    assert prop.gridRow == 3
    assert prop.gridColumn == 6
    assert prop.slotIndex == 0
    assert prop.propId == "coffee-1"


def test_slot_mapping_0_based_index_to_1_based_product_slot() -> None:
    assert attached_slot_from_slot_index(0) == 1
    assert attached_slot_from_slot_index(1) == 2
    assert attached_slot_from_slot_index(2) == 3
    assert attached_slot_from_slot_index(3) == 4
    assert attached_slot_from_slot_index(-1) is None
    assert attached_slot_from_slot_index(4) is None
    assert slot_index_from_attached_slot(1) == 0
    assert slot_index_from_attached_slot(4) == 3
    assert slot_index_from_attached_slot(0) is None


def test_create_body_defaults_independent() -> None:
    body = SpatialPropPlacementBody(label="Coffee", propId="coffee-1")
    assert body.placementMode == "independent"
    assert body.attachedCharacterId is None
