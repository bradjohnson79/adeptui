"""Movement Segment contract — state-based inheritance, isolation, IDs."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.spatial_map.errors import SpatialMapErrorCode
from app.spatial_map.movement import (
    activate_segment,
    compact_segment_json,
    compute_transition,
    create_inherited_movement,
    delete_segment,
    find_segment,
    hydrate_movement_segments,
    inherit_segment,
    movement_alias,
    resolve_movement_ref,
    update_segment_narrative,
    write_through_active,
)
from app.spatial_map.schemas import (
    MovementCreateBody,
    MovementDialogue,
    MovementUpdateBody,
    SpatialCharacterPlacement,
    SpatialMapDocument,
    SpatialPropPlacement,
)


def _doc_with_korri() -> SpatialMapDocument:
    return SpatialMapDocument(
        projectId="proj-1",
        characters=[
            SpatialCharacterPlacement(
                id="char-korri",
                characterId="cid-korri",
                label="Korri",
                tag="@Korri",
                normalizedX=-0.4,
                normalizedY=0.2,
                gridRow=3,
                gridColumn=2,
                slotIndex=0,
            )
        ],
        props=[
            SpatialPropPlacement(
                id="prop-mug",
                propId="pid-mug",
                label="green slime mug",
                tag="#mug",
                placementMode="attached",
                attachedCharacterId="cid-korri",
                attachedCharacterSlot=1,
                relationship="held",
                attachmentPoint="right_hand",
            )
        ],
    )


def test_migrate_creates_m1_from_live_state() -> None:
    doc = _doc_with_korri()
    assert hydrate_movement_segments(doc) is True
    assert len(doc.movementSegments) == 1
    m1 = doc.movementSegments[0]
    assert m1.segmentNumber == 1
    assert movement_alias(m1.segmentNumber) == "M1"
    assert m1.characterStates[0].label == "Korri"
    assert m1.propStates[0].attachmentPoint == "right_hand"
    assert doc.activeMovementSegmentId == m1.id


def test_m1_cannot_delete() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    with pytest.raises(HTTPException) as exc:
        delete_segment(doc, doc.movementSegments[0].id)
    assert exc.value.detail["code"] == SpatialMapErrorCode.MOVEMENT_CANNOT_DELETE.value


def test_inherit_copies_state_not_prose() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    m1 = doc.movementSegments[0]
    m1.userDirection = "Korri recoils at the drink."
    m1.dialogue = [MovementDialogue(speaker="Korri", text="Ever wanted to taste...")]
    m1.beatName = "Green Drink Reaction"
    created = create_inherited_movement(
        doc,
        MovementCreateBody(beatName="Leaves Counter", userDirection="Korri walks to the table."),
    )
    assert created.segmentNumber == 2
    assert created.characterStates[0].label == "Korri"
    assert created.characterStates[0].normalizedX == -0.4
    assert created.propStates[0].attachmentPoint == "right_hand"
    assert created.userDirection == "Korri walks to the table."
    assert created.dialogue == []
    assert m1.userDirection == "Korri recoils at the drink."
    assert m1.dialogue[0].text.startswith("Ever wanted")


def test_position_delta_does_not_mutate_m1() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    m2 = create_inherited_movement(doc, MovementCreateBody(userDirection="Korri walks to the table."))
    doc.characters[0].normalizedX = 0.6
    doc.characters[0].normalizedY = -0.3
    write_through_active(doc)
    m1 = [s for s in doc.movementSegments if s.segmentNumber == 1][0]
    assert m1.characterStates[0].normalizedX == -0.4
    assert m2.characterStates[0].normalizedX == 0.6
    assert m1.propStates[0].attachmentPoint == "right_hand"
    assert m2.propStates[0].attachmentPoint == "right_hand"


def test_activate_hydrates_live_buffer() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    m1_id = doc.movementSegments[0].id
    create_inherited_movement(doc)
    doc.characters[0].normalizedX = 0.5
    write_through_active(doc)
    activate_segment(doc, m1_id)
    assert doc.characters[0].normalizedX == -0.4


def test_max_five_and_stable_ids() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    created = [create_inherited_movement(doc) for _ in range(4)]
    assert [s.segmentNumber for s in doc.movementSegments] == [1, 2, 3, 4, 5]
    m3_id = created[1].id
    delete_segment(doc, m3_id)
    assert [s.segmentNumber for s in doc.movementSegments] == [1, 2, 4, 5]
    nxt = create_inherited_movement(doc)
    assert nxt.segmentNumber == 3
    with pytest.raises(HTTPException) as exc:
        create_inherited_movement(doc)
    assert exc.value.detail["code"] == SpatialMapErrorCode.MOVEMENT_LIMIT_REACHED.value


def test_missing_segment_does_not_fall_back_to_m1() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    with pytest.raises(HTTPException) as exc:
        find_segment(doc, "missing-id")
    assert exc.value.detail["code"] == SpatialMapErrorCode.MOVEMENT_SEGMENT_NOT_FOUND.value


def test_transition_separates_unchanged_and_changed() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    m2 = create_inherited_movement(doc)
    doc.characters[0].normalizedX = 0.7
    write_through_active(doc)
    m1 = doc.movementSegments[0]
    transition = compute_transition(m1, m2)
    assert "Korri moved" in transition["changed"]
    assert any("mug" in item or "identity" in item for item in transition["unchanged"])
    assert "environment" in transition["unchanged"]
    assert transition["startingState"]["characters"][0]["normalizedX"] == -0.4
    assert transition["endingState"]["characters"][0]["normalizedX"] == 0.7


def test_resolve_m2_and_next() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    create_inherited_movement(doc, MovementCreateBody(beatName="Leaves Counter"))
    activate_segment(doc, doc.movementSegments[0].id)
    hit = resolve_movement_ref(doc, "M2")
    assert hit["ambiguous"] is False
    assert hit["matched"][0]["segmentNumber"] == 2
    nxt = resolve_movement_ref(doc, "the next movement")
    assert nxt["matched"][0]["segmentNumber"] == 2
    named = resolve_movement_ref(doc, "Leaves Counter")
    assert named["matched"][0]["beatName"] == "Leaves Counter"


def test_update_direction_does_not_overwrite_inherited_state() -> None:
    doc = _doc_with_korri()
    hydrate_movement_segments(doc)
    m2 = create_inherited_movement(doc)
    update_segment_narrative(
        doc,
        m2.id,
        MovementUpdateBody(userDirection="Korri walks to the table.", productionPrompt="Walks with the mug."),
    )
    assert m2.propStates[0].attachmentPoint == "right_hand"
    assert m2.userDirection.startswith("Korri walks")
    packed = compact_segment_json(m2)
    assert packed["alias"] == "M2"
    assert packed["propStates"][0]["attachmentPoint"] == "right_hand"


def test_inherit_helper_does_not_copy_dialogue() -> None:
    from app.spatial_map.movement import seed_movement_one

    m1 = seed_movement_one(_doc_with_korri())
    m1.dialogue = [MovementDialogue(speaker="Korri", text="Stay at the counter.")]
    m1.userDirection = "Hold the mug."
    inherited = inherit_segment(m1, 2)
    assert inherited.dialogue == []
    assert inherited.userDirection == ""
    assert inherited.characterStates[0].label == "Korri"
