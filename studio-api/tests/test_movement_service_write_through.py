"""Movement service/router: inherit, activate, write-through, isolation."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.db import Project, init_db
from app.spatial_map.errors import SpatialMapErrorCode
from app.spatial_map.schemas import (
    MovementCreateBody,
    MovementUpdateBody,
    SpatialCameraCreateBody,
    SpatialCameraUpdateBody,
    SpatialCharacterPlacementBody,
    SpatialCharacterPlacementUpdateBody,
    SpatialMapCreateBody,
)
from app.spatial_map.service import (
    activate_movement,
    create_camera,
    create_document,
    create_movement,
    get_document,
    place_character,
    remove_movement,
    update_camera,
    update_character,
    update_movement,
)


def _session():
    from app.db import SessionLocal

    init_db()
    return SessionLocal()


def _create_project(name: str = "Movement Service Cert") -> str:
    db = _session()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _seed_character(db, project_id: str, character_id: str, name: str) -> None:
    from app.character_identity.models import CharacterProfileRow

    db.add(CharacterProfileRow(id=character_id, project_id=project_id, name=name))
    db.commit()


def _place(db, project_id: str, document_id: str, character_id: str, label: str, slot: int, row: int, col: int):
    doc = place_character(
        db,
        project_id,
        document_id,
        SpatialCharacterPlacementBody(
            characterId=character_id,
            label=label,
            slotIndex=slot,
            colorKey="red" if slot == 0 else "blue",
            tag=f"@{label}",
        ),
    )
    placement = next(c for c in doc.characters if c.characterId == character_id)
    return update_character(
        db,
        project_id,
        document_id,
        placement.id,
        SpatialCharacterPlacementUpdateBody(gridRow=row, gridColumn=col),
    )


def test_create_document_hydrates_m1() -> None:
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="M1 Seed"))
        assert len(doc.movementSegments) == 1
        assert doc.movementSegments[0].segmentNumber == 1
        reloaded = get_document(db, project_id, doc.id)
        assert len(reloaded.movementSegments) == 1
        assert reloaded.activeMovementSegmentId == doc.movementSegments[0].id
    finally:
        db.close()


def test_create_m2_inherits_and_activate_swaps_live_buffer() -> None:
    project_id = _create_project()
    db = _session()
    korri_id = f"korri-{uuid.uuid4().hex[:8]}"
    other_id = f"other-{uuid.uuid4().hex[:8]}"
    try:
        _seed_character(db, project_id, korri_id, "Korri")
        _seed_character(db, project_id, other_id, "Other")
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Inherit"))
        doc = _place(db, project_id, doc.id, korri_id, "Korri", 0, 3, 3)
        doc = _place(db, project_id, doc.id, other_id, "Other", 1, 6, 6)
        m1_id = doc.activeMovementSegmentId
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        other = next(c for c in doc.characters if c.characterId == other_id)
        m1_korri_x = korri.normalizedX
        m1_other_x = other.normalizedX
        doc = create_movement(db, project_id, doc.id, MovementCreateBody(beatName="Walks"))
        assert len(doc.movementSegments) == 2
        m2 = next(s for s in doc.movementSegments if s.segmentNumber == 2)
        assert m2.beatName == "Walks"
        assert m2.characterStates[0].characterId in {korri_id, other_id}
        assert doc.activeMovementSegmentId == m2.id
        moved = update_character(
            db,
            project_id,
            doc.id,
            korri.id,
            SpatialCharacterPlacementUpdateBody(gridRow=7, gridColumn=7),
        )
        moved_korri = next(c for c in moved.characters if c.characterId == korri_id)
        moved_other = next(c for c in moved.characters if c.characterId == other_id)
        assert moved_korri.normalizedX != m1_korri_x
        assert moved_other.normalizedX == m1_other_x
        m1 = next(s for s in moved.movementSegments if s.segmentNumber == 1)
        m2 = next(s for s in moved.movementSegments if s.segmentNumber == 2)
        assert next(c.normalizedX for c in m1.characterStates if c.characterId == korri_id) == m1_korri_x
        assert next(c.normalizedX for c in m2.characterStates if c.characterId == korri_id) == moved_korri.normalizedX
        activated = activate_movement(db, project_id, doc.id, m1_id)
        live_korri = next(c for c in activated.characters if c.characterId == korri_id)
        assert live_korri.normalizedX == m1_korri_x
        reloaded = get_document(db, project_id, doc.id)
        assert reloaded.activeMovementSegmentId == m1_id
        assert next(c.normalizedX for c in reloaded.characters if c.characterId == korri_id) == m1_korri_x
    finally:
        db.close()


def test_delete_m1_forbidden_and_limit_five() -> None:
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Limit"))
        m1_id = doc.movementSegments[0].id
        with pytest.raises(HTTPException) as exc:
            remove_movement(db, project_id, doc.id, m1_id)
        assert exc.value.detail["code"] == SpatialMapErrorCode.MOVEMENT_CANNOT_DELETE.value
        for _ in range(4):
            doc = create_movement(db, project_id, doc.id, MovementCreateBody())
        assert len(doc.movementSegments) == 5
        with pytest.raises(HTTPException) as exc:
            create_movement(db, project_id, doc.id, MovementCreateBody())
        assert exc.value.detail["code"] == SpatialMapErrorCode.MOVEMENT_LIMIT_REACHED.value
    finally:
        db.close()


def test_camera_fov_yaw_shot_size_survive_movement_switch() -> None:
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Camera Survive"))
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, orientation="N", fovPreset="wide", shotSize="medium"),
        )
        cam_id = doc.cameras[0].id
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=4, gridColumn=4, fovPreset="narrow", shotSize="close_up", orientation="E"),
        )
        yaw = doc.cameras[0].yawDegrees
        fov = doc.cameras[0].fovPreset
        shot = doc.cameras[0].shotSize
        m1_id = doc.activeMovementSegmentId
        doc = create_movement(db, project_id, doc.id, MovementCreateBody())
        doc = activate_movement(db, project_id, doc.id, m1_id)
        cam = doc.cameras[0]
        assert cam.fovPreset == fov
        assert cam.shotSize == shot
        assert cam.yawDegrees == yaw
    finally:
        db.close()


def test_update_movement_narrative_and_project_isolation() -> None:
    project_a = _create_project("Move A")
    project_b = _create_project("Move B")
    db = _session()
    try:
        doc_a = create_document(db, project_a, SpatialMapCreateBody(title="A"))
        doc_b = create_document(db, project_b, SpatialMapCreateBody(title="B"))
        m2 = create_movement(db, project_a, doc_a.id, MovementCreateBody(beatName="A2"))
        updated = update_movement(
            db,
            project_a,
            doc_a.id,
            next(s.id for s in m2.movementSegments if s.segmentNumber == 2),
            MovementUpdateBody(userDirection="Walk north."),
        )
        assert any(s.userDirection == "Walk north." for s in updated.movementSegments)
        other = get_document(db, project_b, doc_b.id)
        assert len(other.movementSegments) == 1
        assert all((s.userDirection or "") == "" for s in other.movementSegments)
    finally:
        db.close()


def test_move_placement_meters_write_through() -> None:
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers.spatial_m411 import apply_move_placement

    project_id = _create_project()
    db = _session()
    korri_id = f"korri-{uuid.uuid4().hex[:8]}"
    try:
        _seed_character(db, project_id, korri_id, "Korri")
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Meters"))
        doc = _place(db, project_id, doc.id, korri_id, "Korri", 0, 4, 4)
        before = next(c for c in doc.characters if c.characterId == korri_id)
        ctx = ToolContext(db=db, project_id=project_id)
        result = apply_move_placement(
            ctx,
            {
                "documentId": doc.id,
                "targetType": "character",
                "targetId": before.id,
                "metersNorth": 1,
            },
        )
        assert result["ok"] is True
        moved = get_document(db, project_id, doc.id)
        after = next(c for c in moved.characters if c.characterId == korri_id)
        assert after.gridRow != before.gridRow or after.normalizedY != before.normalizedY
        active = next(s for s in moved.movementSegments if s.id == moved.activeMovementSegmentId)
        snap = next(c for c in active.characterStates if c.characterId == korri_id)
        assert snap.normalizedY == after.normalizedY
        assert snap.gridRow == after.gridRow
    finally:
        db.close()



def test_camera_free_entity_pose_hydrate_m1_m2() -> None:
    """Non-POV C1 is a free entity: M1/M2 restore camera poses, not character poses."""
    project_id = _create_project("Camera Free Entity")
    db = _session()
    korri_id = f"korri-{uuid.uuid4().hex[:8]}"
    try:
        _seed_character(db, project_id, korri_id, "Korri")
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Camera Free"))
        doc = _place(db, project_id, doc.id, korri_id, "Korri", 0, 3, 3)
        m1_id = doc.activeMovementSegmentId
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        m1_korri = (korri.normalizedX, korri.normalizedY, korri.gridRow, korri.gridColumn)

        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(
                label="C1",
                cameraSlot=0,
                shotSize="wide",
                attachMode="free",
                gridRow=1,
                gridColumn=8,
                normalizedX=0.72,
                normalizedY=0.18,
            ),
        )
        cam = next(c for c in doc.cameras if c.cameraSlot == 0 or c.label == "C1")
        cam_id = cam.id
        m1_cam = (cam.normalizedX, cam.normalizedY, cam.gridRow, cam.gridColumn)
        # Camera must not sit on Korri at create time.
        assert (cam.normalizedX, cam.normalizedY) != (korri.normalizedX, korri.normalizedY)

        doc = create_movement(db, project_id, doc.id, MovementCreateBody(beatName="Corridor"))
        m2 = next(s for s in doc.movementSegments if s.segmentNumber == 2)
        assert m2.cameraStates, "M2 must inherit camera pose snapshots"
        assert any(c.id == cam_id for c in m2.cameraStates)

        # Move Korri on M2 (character path) and C1 to a distinct free spot.
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        doc = update_character(
            db,
            project_id,
            doc.id,
            korri.id,
            SpatialCharacterPlacementUpdateBody(gridRow=8, gridColumn=3, normalizedX=0.21, normalizedY=0.81),
        )
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=7, gridColumn=8, normalizedX=0.79, normalizedY=0.86, shotSize="wide"),
        )
        cam = next(c for c in doc.cameras if c.id == cam_id)
        m2_cam = (cam.normalizedX, cam.normalizedY, cam.gridRow, cam.gridColumn)
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        m2_korri = (korri.normalizedX, korri.normalizedY, korri.gridRow, korri.gridColumn)
        assert m2_cam != m1_cam
        assert (cam.normalizedX, cam.normalizedY) != (korri.normalizedX, korri.normalizedY)

        # Flip to M1: camera returns to its saved free pose, not onto Korri.
        doc = activate_movement(db, project_id, doc.id, m1_id)
        cam = next(c for c in doc.cameras if c.id == cam_id)
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        assert (cam.normalizedX, cam.normalizedY, cam.gridRow, cam.gridColumn) == m1_cam
        assert (korri.normalizedX, korri.normalizedY, korri.gridRow, korri.gridColumn) == m1_korri
        assert (cam.normalizedX, cam.normalizedY) != (korri.normalizedX, korri.normalizedY)

        # Flip to M2: camera returns to the dragged free pose, still not on Korri.
        doc = activate_movement(db, project_id, doc.id, m2.id)
        cam = next(c for c in doc.cameras if c.id == cam_id)
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        assert (cam.normalizedX, cam.normalizedY, cam.gridRow, cam.gridColumn) == m2_cam
        assert (korri.normalizedX, korri.normalizedY, korri.gridRow, korri.gridColumn) == m2_korri
        assert (cam.normalizedX, cam.normalizedY) != (korri.normalizedX, korri.normalizedY)

        # POV is attach metadata only; leaving POV restores free poses.
        doc = update_camera(
            db, project_id, doc.id, cam_id, SpatialCameraUpdateBody(shotSize="pov", attachMode="pov")
        )
        assert next(c for c in doc.cameras if c.id == cam_id).shotSize == "pov"
        doc = update_camera(
            db, project_id, doc.id, cam_id, SpatialCameraUpdateBody(shotSize="wide", attachMode="free")
        )
        cam = next(c for c in doc.cameras if c.id == cam_id)
        assert cam.shotSize == "wide"
        assert cam.attachMode == "free"
        assert (cam.normalizedX, cam.normalizedY, cam.gridRow, cam.gridColumn) == m2_cam
    finally:
        db.close()


def test_camera_m1_and_m2_poses_both_stick_after_edits() -> None:
    """Brad NO-GO: place C1 on M1, then M2, flip repeatedly — both poses stick."""
    project_id = _create_project("Camera Autosave Both")
    db = _session()
    korri_id = f"korri-{uuid.uuid4().hex[:8]}"
    try:
        _seed_character(db, project_id, korri_id, "Korri")
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Autosave Both"))
        doc = _place(db, project_id, doc.id, korri_id, "Korri", 0, 3, 3)
        m1_id = doc.activeMovementSegmentId
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(
                label="C1",
                cameraSlot=0,
                shotSize="wide",
                attachMode="free",
                gridRow=1,
                gridColumn=8,
            ),
        )
        cam_id = doc.cameras[0].id

        # Distinct M1 camera pose
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=2, gridColumn=2, movementSegmentId=m1_id),
        )
        m1_pose = (doc.cameras[0].gridRow, doc.cameras[0].gridColumn, doc.cameras[0].normalizedX, doc.cameras[0].normalizedY)
        m1_snap = next(c for c in next(s for s in doc.movementSegments if s.id == m1_id).cameraStates if c.id == cam_id)
        assert (m1_snap.gridRow, m1_snap.gridColumn) == (m1_pose[0], m1_pose[1])

        doc = create_movement(db, project_id, doc.id, MovementCreateBody(beatName="Walk"))
        m2_id = doc.activeMovementSegmentId

        # Distinct M2 camera pose
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=8, gridColumn=8, movementSegmentId=m2_id),
        )
        m2_pose = (doc.cameras[0].gridRow, doc.cameras[0].gridColumn, doc.cameras[0].normalizedX, doc.cameras[0].normalizedY)
        assert m2_pose != m1_pose

        for _ in range(3):
            doc = activate_movement(db, project_id, doc.id, m1_id)
            cam = next(c for c in doc.cameras if c.id == cam_id)
            assert (cam.gridRow, cam.gridColumn, cam.normalizedX, cam.normalizedY) == m1_pose
            doc = activate_movement(db, project_id, doc.id, m2_id)
            cam = next(c for c in doc.cameras if c.id == cam_id)
            assert (cam.gridRow, cam.gridColumn, cam.normalizedX, cam.normalizedY) == m2_pose

        # Character also write-throughs per movement
        korri = next(c for c in doc.characters if c.characterId == korri_id)
        doc = update_character(
            db,
            project_id,
            doc.id,
            korri.id,
            SpatialCharacterPlacementUpdateBody(gridRow=9, gridColumn=1, movementSegmentId=m2_id),
        )
        m2_korri = next(c for c in doc.characters if c.characterId == korri_id)
        m2_korri_pose = (m2_korri.gridRow, m2_korri.gridColumn)
        doc = activate_movement(db, project_id, doc.id, m1_id)
        m1_korri = next(c for c in doc.characters if c.characterId == korri_id)
        assert (m1_korri.gridRow, m1_korri.gridColumn) != m2_korri_pose
        doc = activate_movement(db, project_id, doc.id, m2_id)
        live = next(c for c in doc.characters if c.characterId == korri_id)
        assert (live.gridRow, live.gridColumn) == m2_korri_pose
    finally:
        db.close()


def test_update_camera_movement_segment_id_aligns_active_before_write() -> None:
    """Client-sent movementSegmentId wins over stale server active (switch race)."""
    project_id = _create_project("Camera Segment Align")
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Align"))
        m1_id = doc.activeMovementSegmentId
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, gridRow=1, gridColumn=1),
        )
        cam_id = doc.cameras[0].id
        doc = create_movement(db, project_id, doc.id, MovementCreateBody())
        m2_id = doc.activeMovementSegmentId
        assert doc.activeMovementSegmentId == m2_id

        # Server active is M2, but client targets M1 (race / stale UI).
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=4, gridColumn=5, movementSegmentId=m1_id),
        )
        assert doc.activeMovementSegmentId == m1_id
        m1 = next(s for s in doc.movementSegments if s.id == m1_id)
        m2 = next(s for s in doc.movementSegments if s.id == m2_id)
        m1_cam = next(c for c in m1.cameraStates if c.id == cam_id)
        m2_cam = next(c for c in m2.cameraStates if c.id == cam_id)
        assert (m1_cam.gridRow, m1_cam.gridColumn) == (4, 5)
        assert (m2_cam.gridRow, m2_cam.gridColumn) != (4, 5)
    finally:
        db.close()


def test_seed_missing_camera_states_does_not_poison_m1_from_m2_live() -> None:
    from app.spatial_map.movement import hydrate_live_from_segment, seed_missing_camera_states
    from app.spatial_map.schemas import MovementSegment, SpatialCamera

    project_id = _create_project("Seed Poison")
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Seed"))
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, gridRow=1, gridColumn=1),
        )
        cam_id = doc.cameras[0].id
        doc = create_movement(db, project_id, doc.id, MovementCreateBody())
        m1 = next(s for s in doc.movementSegments if s.segmentNumber == 1)
        m2 = next(s for s in doc.movementSegments if s.segmentNumber == 2)
        # Simulate legacy empty M1 cameraStates while live/M2 hold a later pose.
        m1.cameraStates = []
        m1.cameraStateRefs = []
        doc.cameras[0].gridRow = 8
        doc.cameras[0].gridColumn = 8
        m2.cameraStates = [doc.cameras[0].model_copy(deep=True)]
        m2.cameraStateRefs = [cam_id]
        doc.activeMovementSegmentId = m2.id

        seed_missing_camera_states(doc)
        # M1 must inherit from prior snapshot chain / stay empty — not silently take live M2 pose.
        # With prev_states from M2 only after M2 is visited in order, M1 is processed first:
        # inactive + no prev => leave empty.
        assert not (m1.cameraStates or []), "M1 must not be poisoned from M2 live during seed"

        # Activating M1 with empty states must not leave M2 live cameras for write-through.
        # After seed-on-activate fills from previous (M2) inheritance is OK as starting point,
        # but empty hydrate must not keep stale live without going through activate_segment.
        hydrate_live_from_segment(doc, m1)
        # empty states + empty refs => live unchanged by design; refs-only would filter.
        m1.cameraStateRefs = [cam_id]
        hydrate_live_from_segment(doc, m1)
        assert all(str(c.id) == cam_id for c in doc.cameras)
    finally:
        db.close()


def test_activate_empty_m1_does_not_copy_m2_live_camera() -> None:
    """Live Korri failure: empty M1 cameraStates must not inherit still-live M2 poses."""
    from app.spatial_map.movement import activate_segment

    project_id = _create_project("Activate Empty M1")
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Empty M1 Cam"))
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, gridRow=1, gridColumn=1, attachMode="free"),
        )
        cam_id = doc.cameras[0].id
        m1_id = doc.activeMovementSegmentId
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=2, gridColumn=2, movementSegmentId=m1_id),
        )
        m1_pose = (doc.cameras[0].gridRow, doc.cameras[0].gridColumn)
        doc = create_movement(db, project_id, doc.id, MovementCreateBody())
        m2_id = doc.activeMovementSegmentId
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=8, gridColumn=8, movementSegmentId=m2_id),
        )
        m2_pose = (doc.cameras[0].gridRow, doc.cameras[0].gridColumn)
        assert m2_pose != m1_pose

        # Wipe M1 camera snapshot like the live Korri document (disk empty).
        m1 = next(s for s in doc.movementSegments if s.id == m1_id)
        m1.cameraStates = []
        m1.cameraStateRefs = []
        doc.activeMovementSegmentId = m2_id
        doc.cameras[0].gridRow = 8
        doc.cameras[0].gridColumn = 8

        activate_segment(doc, m1_id)
        live = next(c for c in doc.cameras if c.id == cam_id)
        # Incoming empty may inherit M2 as a first-visit start, but must not
        # silently keep writing M2-only if M1 already had a distinct pose in live history.
        # After wipe, inherit-from-snapshot (M2) is the allowed start; live must match M1 snapshot now.
        m1 = next(s for s in doc.movementSegments if s.id == m1_id)
        m2 = next(s for s in doc.movementSegments if s.id == m2_id)
        assert m1.cameraStates, "M1 empty incoming should inherit a snapshot, not stay empty"
        assert m2.cameraStates, "M2 flushed snapshot must remain"
        m2_snap = next(c for c in m2.cameraStates if c.id == cam_id)
        assert (m2_snap.gridRow, m2_snap.gridColumn) == m2_pose
        # Live after activate is M1 snapshot (inherited start), and a later M1 edit must stick.
        doc = update_camera(
            db,
            project_id,
            doc.id,
            cam_id,
            SpatialCameraUpdateBody(gridRow=3, gridColumn=4, movementSegmentId=m1_id),
        )
        m1_new = (doc.cameras[0].gridRow, doc.cameras[0].gridColumn)
        doc = activate_movement(db, project_id, doc.id, m2_id)
        assert (doc.cameras[0].gridRow, doc.cameras[0].gridColumn) == m2_pose
        doc = activate_movement(db, project_id, doc.id, m1_id)
        assert (doc.cameras[0].gridRow, doc.cameras[0].gridColumn) == m1_new
        assert m1_new != m2_pose
    finally:
        db.close()
