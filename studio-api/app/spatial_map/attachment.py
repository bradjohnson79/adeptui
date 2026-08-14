"""Frozen Spatial Map character-prop attachment contract.

Field names and enums are identical in Python and TypeScript.
See studio-api/.runtime/spatial-map-attachment-contract.md.

Slot mapping (do not mix):
- attachedCharacterSlot is 1-4 (product Character 1-4).
- Existing Spatial Map CHARACTER_SLOTS / slotIndex are 0-3.
- attachedCharacterSlot = slotIndex + 1
- slotIndex = attachedCharacterSlot - 1
Never store a 0-based value in attachedCharacterSlot.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, MutableMapping

PlacementMode = Literal["independent", "attached"]
PropRelationship = Literal[
    "held",
    "carried",
    "worn",
    "using",
    "interacting",
    "associated",
]
AttachmentPoint = Literal[
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
]
AttachedCharacterSlot = Literal[1, 2, 3, 4]

PLACEMENT_MODES: tuple[str, ...] = ("independent", "attached")
PROP_RELATIONSHIPS: tuple[str, ...] = (
    "held",
    "carried",
    "worn",
    "using",
    "interacting",
    "associated",
)
ATTACHMENT_POINTS: tuple[str, ...] = (
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
ATTACHED_CHARACTER_SLOTS: tuple[int, ...] = (1, 2, 3, 4)

# Existing Spatial Map slotIndex is 0-3. Product attachedCharacterSlot is 1-4.
_SLOT_INDEX_TO_ATTACHED = {0: 1, 1: 2, 2: 3, 3: 4}
_ATTACHED_TO_SLOT_INDEX = {1: 0, 2: 1, 3: 2, 4: 3}

_ATTACHMENT_FIELD_DEFAULTS: dict[str, Any] = {
    "attachedCharacterSlot": None,
    "attachedCharacterId": None,
    "relationship": None,
    "attachmentPoint": None,
}


class PropAttachmentError(ValueError):
    """Illegal character-prop attachment state."""


def attached_slot_from_slot_index(slot_index: int | None) -> int | None:
    """Map existing 0-based slotIndex to product attachedCharacterSlot (1-4)."""
    if slot_index is None:
        return None
    try:
        return _SLOT_INDEX_TO_ATTACHED[int(slot_index)]
    except (KeyError, TypeError, ValueError):
        return None


def slot_index_from_attached_slot(attached_character_slot: int | None) -> int | None:
    """Map product attachedCharacterSlot (1-4) to existing 0-based slotIndex."""
    if attached_character_slot is None:
        return None
    try:
        return _ATTACHED_TO_SLOT_INDEX[int(attached_character_slot)]
    except (KeyError, TypeError, ValueError):
        return None


def _get(prop: Any, key: str, default: Any = None) -> Any:
    if isinstance(prop, Mapping):
        return prop.get(key, default)
    return getattr(prop, key, default)


def _set(prop: Any, key: str, value: Any) -> None:
    if isinstance(prop, MutableMapping):
        prop[key] = value
        return
    setattr(prop, key, value)


def _clear_attachment_fields(prop: Any) -> None:
    for key, value in _ATTACHMENT_FIELD_DEFAULTS.items():
        _set(prop, key, value)


def _blank_id(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def normalize_prop_attachment(prop: Any) -> Any:
    """Default missing placementMode to independent and enforce XOR.

    Independent is authoritative: attachment fields are cleared so they
    cannot remain set as a second source of truth. Physical x/y/normalized
    coordinates are never moved.
    """
    mode = _get(prop, "placementMode")
    if mode not in PLACEMENT_MODES:
        mode = "independent"
    if mode != "attached":
        _set(prop, "placementMode", "independent")
        _clear_attachment_fields(prop)
        return prop
    _set(prop, "placementMode", "attached")
    character_id = _get(prop, "attachedCharacterId")
    if _blank_id(character_id):
        _set(prop, "attachedCharacterId", None)
    return prop


def validate_prop_attachment(prop: Any) -> Any:
    """Validate the frozen XOR attachment law.

    - Missing / unknown placementMode loads as independent (backward compatible).
    - independent: attachment fields are cleared (not kept as authoritative).
    - attached: requires attachedCharacterId or attachedCharacterSlot in 1-4,
      AND relationship. attachmentPoint is optional (unspecified allowed).
    - attachedCharacterSlot must be 1-4, never a 0-based slotIndex.
    """
    normalize_prop_attachment(prop)
    if _get(prop, "placementMode") != "attached":
        return prop

    character_id = _get(prop, "attachedCharacterId")
    slot = _get(prop, "attachedCharacterSlot")
    relationship = _get(prop, "relationship")
    point = _get(prop, "attachmentPoint")

    slot_ok = False
    if slot is not None:
        try:
            slot_ok = int(slot) in ATTACHED_CHARACTER_SLOTS
        except (TypeError, ValueError):
            slot_ok = False
        if not slot_ok:
            raise PropAttachmentError(
                "attachedCharacterSlot must be 1-4 (Character 1-4); "
                "do not use slotIndex 0-3 here "
                "(mapping: attachedCharacterSlot = slotIndex + 1)"
            )

    has_character = (not _blank_id(character_id)) or slot_ok
    if not has_character:
        raise PropAttachmentError(
            "attached prop requires attachedCharacterId or attachedCharacterSlot (1-4)"
        )
    if relationship not in PROP_RELATIONSHIPS:
        raise PropAttachmentError(
            "attached prop requires relationship "
            "(held|carried|worn|using|interacting|associated)"
        )
    if point is not None and point not in ATTACHMENT_POINTS:
        raise PropAttachmentError(f"invalid attachmentPoint: {point}")
    return prop


def has_independent_grid_position(prop: Any) -> bool:
    """True when normalized or non-negative grid cells are set (Reset uses -1/None)."""
    nx = _get(prop, "normalizedX")
    ny = _get(prop, "normalizedY")
    if nx is not None and ny is not None:
        return True
    try:
        row = int(_get(prop, "gridRow", -1))
        col = int(_get(prop, "gridColumn", -1))
    except (TypeError, ValueError):
        return False
    return row >= 0 and col >= 0


def clear_independent_grid_position(prop: Any) -> None:
    """Inactivate independent grid placement (existing Reset / unplaced style).

    XOR: attached / unplaced props must not keep leftover independent world
    coords. normalizedX/Y are already nulled; x/y/z are cleared too.
    """
    _set(prop, "normalizedX", None)
    _set(prop, "normalizedY", None)
    _set(prop, "gridRow", -1)
    _set(prop, "gridColumn", -1)
    _set(prop, "x", None)
    _set(prop, "y", None)
    _set(prop, "z", None)


def apply_attach(
    prop: Any,
    *,
    attached_character_id: Any = None,
    attached_character_slot: Any = None,
    relationship: Any,
    attachment_point: Any = None,
) -> Any:
    """Mark a prop attached and clear independent grid position."""
    _set(prop, "placementMode", "attached")
    _set(prop, "attachedCharacterId", None if _blank_id(attached_character_id) else attached_character_id)
    _set(prop, "attachedCharacterSlot", attached_character_slot)
    _set(prop, "relationship", relationship)
    _set(prop, "attachmentPoint", attachment_point)
    clear_independent_grid_position(prop)
    return validate_prop_attachment(prop)


def apply_detach(prop: Any) -> Any:
    """Clear attachment and leave the prop independent-unplaced."""
    _set(prop, "placementMode", "independent")
    _clear_attachment_fields(prop)
    clear_independent_grid_position(prop)
    return validate_prop_attachment(prop)


def apply_relationship_update(
    prop: Any,
    *,
    relationship: Any,
    attachment_point: Any = None,
    update_attachment_point: bool = False,
) -> Any:
    """Update relationship (and optional attachmentPoint) on an already-attached prop."""
    if _get(prop, "placementMode") != "attached":
        raise PropAttachmentError("update_prop_relationship requires an attached prop")
    _set(prop, "relationship", relationship)
    if update_attachment_point:
        _set(prop, "attachmentPoint", attachment_point)
    return validate_prop_attachment(prop)


def props_attached_to_character(props: list[Any], character: Any) -> list[Any]:
    """Props attached to THIS character placement, not leftover same-characterId rows.

    attachedCharacterSlot maps from this placement's slotIndex (0 -> 1).
    attachedCharacterId is only an owner key when this placement is a canonical
    slot (slotIndex 0-3). slotIndex -1 leftovers must not 409 just because
    another row with the same characterId has an attached prop.
    """
    character_ids: set[str] = set()
    cid = _get(character, "characterId")
    pid = _get(character, "id")
    if not _blank_id(cid):
        character_ids.add(str(cid).strip())
    if not _blank_id(pid):
        character_ids.add(str(pid).strip())
    expected_slot = attached_slot_from_slot_index(_get(character, "slotIndex"))
    matched: list[Any] = []
    for prop in props:
        if _get(prop, "placementMode") != "attached":
            continue
        slot = _get(prop, "attachedCharacterSlot")
        try:
            slot_int = int(slot) if slot is not None else None
        except (TypeError, ValueError):
            slot_int = None
        if expected_slot is not None and slot_int == expected_slot:
            matched.append(prop)
            continue
        # Canonical slots only (0-3). Leftover slotIndex -1 is not an owner.
        if expected_slot is None:
            continue
        prop_cid = _get(prop, "attachedCharacterId")
        if not _blank_id(prop_cid) and str(prop_cid).strip() in character_ids:
            matched.append(prop)
    return matched
