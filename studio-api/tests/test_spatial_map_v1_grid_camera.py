"""Cartesian Spatial Map: Placement Precision, assignment, cameras, migration."""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.db import Project, init_db
from app.spatial_map.grid import (
    GRID_DENSITY,
    PLACEMENT_GRID_CARTESIAN,
    clamp_grid_scale,
    density_for_scale,
    is_valid_cell,
    legacy_polar_to_normalized,
    migrate_document,
)
from app.spatial_map.limits import CAMERA_LIMIT
from app.spatial_map.schemas import (
    SpatialCameraCreateBody,
    SpatialCameraUpdateBody,
    SpatialCharacterPlacementBody,
    SpatialCharacterPlacementUpdateBody,
    SpatialMapCreateBody,
    SpatialMapDocument,
    SpatialMapUpdateBody,
    SpatialPropPlacementBody,
    SpatialPropPlacementUpdateBody,
)
from app.spatial_map.service import (
    create_camera,
    create_document,
    get_document,
    list_documents,
    place_character,
    place_prop,
    remove_camera,
    remove_character,
    remove_prop,
    update_camera,
    update_character,
    update_document,
    update_prop,
)


def _session():
    from app.db import SessionLocal

    init_db()
    return SessionLocal()


def _create_project(name: str = "Spatial Map Cartesian Test") -> str:
    db = _session()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _seed_entities(db, project_id: str) -> None:
    """CDX-013: placements must reference project-owned canonical entities."""
    from app.character_identity.models import CharacterProfileRow
    from app.spatial_map.ers_contracts import PropEntity
    from app.spatial_map.ers_persistence import save_prop_entity

    existing = db.get(CharacterProfileRow, "korri-123")
    if existing is not None:
        db.delete(existing)
        db.commit()
    db.add(CharacterProfileRow(id="korri-123", project_id=project_id, name="Korri"))
    db.commit()
    for prop_id in ("prop-lightsaber", "prop-9"):
        save_prop_entity(
            db,
            project_id,
            PropEntity(
                id=prop_id,
                project_id=project_id,
                tag=prop_id,
                display_label=prop_id,
                approved_asset_id=f"approved-{prop_id}",
            ),
        )


def test_camera_limit_is_four():
    assert CAMERA_LIMIT == 4


def test_neutral_density_is_10():
    assert density_for_scale(0) == 10
    assert GRID_DENSITY[0] == 10


def test_grid_scale_range_and_clamp():
    assert clamp_grid_scale(-5) == -5
    assert clamp_grid_scale(5) == 5
    assert clamp_grid_scale(-10) == -5
    assert clamp_grid_scale(99) == 5
    assert density_for_scale(-5) == 5
    assert density_for_scale(5) == 20


def test_grid_scale_persistence_and_clamping():
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Scale Test"))
        assert doc.gridScale == 0
        assert doc.placementGrid == PLACEMENT_GRID_CARTESIAN
        updated = update_document(db, project_id, doc.id, SpatialMapUpdateBody(gridScale=2))
        assert updated.gridScale == 2
        updated2 = update_document(db, project_id, doc.id, SpatialMapUpdateBody(gridScale=10))
        assert updated2.gridScale == 5
        updated3 = update_document(db, project_id, doc.id, SpatialMapUpdateBody(gridScale=-10))
        assert updated3.gridScale == -5
        reloaded = get_document(db, project_id, doc.id)
        assert reloaded.gridScale == -5
    finally:
        db.close()


def test_character_assignment_requires_character_id_and_does_not_auto_place():
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        with pytest.raises(ValidationError):
            SpatialCharacterPlacementBody(characterId="", label="Korri")
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Char"))
        updated = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(
                characterId="korri-123",
                label="Korri",
                slotIndex=0,
                colorKey="red",
                tag="@Korri",
            ),
        )
        placement = updated.characters[0]
        assert placement.characterId == "korri-123"
        assert placement.gridRow == -1
        assert placement.gridColumn == -1
        assert placement.normalizedX is None
        placed = update_character(
            db,
            project_id,
            updated.id,
            placement.id,
            SpatialCharacterPlacementUpdateBody(gridRow=4, gridColumn=4),
        )
        entity = placed.characters[0]
        assert entity.gridRow == 4
        assert entity.gridColumn == 4
        assert entity.normalizedX is not None
        assert entity.normalizedY is not None
        assert is_valid_cell(entity.gridColumn, entity.gridRow, 10)
    finally:
        db.close()



def test_normalized_only_create_persists_coords():
    """Create-body default gridRow/Column=-1 must not wipe provided normalized coords."""
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Norm Persist"))
        doc = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(
                characterId="korri-123",
                label="Korri",
                normalizedX=0.1,
                normalizedY=-0.2,
            ),
        )
        char = doc.characters[0]
        assert char.normalizedX == 0.1
        assert char.normalizedY == -0.2
        assert char.gridRow >= 0
        assert char.gridColumn >= 0
        doc = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(
                label="Coffee Cup",
                assetId="asset-library-99",
                propId=None,
                normalizedX=-0.3,
                normalizedY=0.25,
            ),
        )
        prop = doc.props[0]
        assert prop.assetId == "asset-library-99"
        assert prop.propId is None
        assert prop.normalizedX == -0.3
        assert prop.normalizedY == 0.25
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(
                label="C1",
                cameraSlot=0,
                orientation="N",
                fovPreset="medium",
                normalizedX=0.0,
                normalizedY=0.6,
            ),
        )
        cam = doc.cameras[0]
        assert cam.normalizedX == 0.0
        assert cam.normalizedY == 0.6
        assert cam.cameraSlot == 0
        reloaded = get_document(db, project_id, doc.id)
        assert reloaded.characters[0].normalizedX == 0.1
        assert reloaded.props[0].normalizedX == -0.3
        assert reloaded.cameras[0].normalizedY == 0.6
    finally:
        db.close()


def test_prop_assignment_binds_prop_id():
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Prop"))
        updated = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(
                label="Lightsaber",
                propId="prop-lightsaber",
                slotIndex=0,
                colorKey="purple",
                tag="#lightsaber",
            ),
        )
        prop = updated.props[0]
        assert prop.propId == "prop-lightsaber"
        assert prop.gridRow == -1
    finally:
        db.close()


def test_normalized_position_survives_precision_change():
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Stable"))
        doc = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(
                characterId="korri-123",
                label="Korri",
                gridRow=4,
                gridColumn=4,
                slotIndex=0,
                colorKey="red",
            ),
        )
        nx = doc.characters[0].normalizedX
        ny = doc.characters[0].normalizedY
        plus = update_document(db, project_id, doc.id, SpatialMapUpdateBody(gridScale=5))
        assert plus.characters[0].normalizedX == nx
        assert plus.characters[0].normalizedY == ny
        minus = update_document(db, project_id, plus.id, SpatialMapUpdateBody(gridScale=-5))
        assert minus.characters[0].normalizedX == nx
        assert minus.characters[0].normalizedY == ny
        back = update_document(db, project_id, minus.id, SpatialMapUpdateBody(gridScale=0))
        assert back.characters[0].normalizedX == nx
        assert back.characters[0].normalizedY == ny
        assert back.characters[0].gridColumn == 4
        assert back.characters[0].gridRow == 4
    finally:
        db.close()


def test_create_and_update_camera_orientation_fov_and_placement():
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Camera"))
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, orientation="N", fovPreset="medium"),
        )
        camera = doc.cameras[0]
        assert camera.cameraSlot == 0
        assert camera.gridRow == -1
        placed = update_camera(
            db,
            project_id,
            doc.id,
            camera.id,
            SpatialCameraUpdateBody(gridRow=4, gridColumn=5, orientation="NE", fovPreset="wide"),
        )
        cam = placed.cameras[0]
        assert cam.orientation == "NE"
        assert cam.fovPreset == "wide"
        assert cam.yawDegrees == 45
        assert cam.gridColumn == 5
        assert cam.normalizedX is not None
    finally:
        db.close()


def test_camera_limit_enforced_at_four():
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Camera Limit"))
        for i in range(4):
            doc = create_camera(db, project_id, doc.id, SpatialCameraCreateBody(label=f"C{i+1}", cameraSlot=i))
        assert len(doc.cameras) == 4
        from app.spatial_map.errors import SpatialMapErrorCode

        try:
            create_camera(db, project_id, doc.id, SpatialCameraCreateBody(label="C5", cameraSlot=4))
            assert False, "expected camera limit error"
        except Exception as exc:
            assert SpatialMapErrorCode.CAMERA_LIMIT_REACHED in str(exc)
    finally:
        db.close()


def test_legacy_polar_migration_preserves_entities():
    doc = SpatialMapDocument(projectId="p1", placementGrid="", gridScale=0)
    from app.spatial_map.schemas import SpatialCharacterPlacement, SpatialCamera

    nx, ny = legacy_polar_to_normalized(2, 0)
    doc.characters.append(
        SpatialCharacterPlacement(
            characterId="korri-123",
            label="Korri",
            gridRow=2,
            gridColumn=0,
            slotIndex=0,
            colorKey="red",
        )
    )
    doc.cameras.append(SpatialCamera(label="C1", cameraSlot=0, gridRow=3, gridColumn=2, orientation="E", fovPreset="wide"))
    changed = migrate_document(doc)
    assert changed is True
    assert doc.placementGrid == PLACEMENT_GRID_CARTESIAN
    char = doc.characters[0]
    assert char.characterId == "korri-123"
    assert char.normalizedX is not None
    assert abs(char.normalizedX - nx) < 0.2 or char.gridColumn >= 0
    cam = doc.cameras[0]
    assert cam.orientation == "E"
    assert cam.fovPreset == "wide"
    assert cam.normalizedX is not None

def test_library_tagged_prop_uses_asset_id_without_fabricating_prop_id():
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Library Prop"))
        updated = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(
                label="Coffee Cup",
                assetId="asset-library-99",
                propId=None,
                slotIndex=0,
                colorKey="purple",
                tag="#coffee-cup",
            ),
        )
        prop = updated.props[0]
        assert prop.assetId == "asset-library-99"
        assert prop.propId is None
        reloaded = get_document(db, project_id, doc.id)
        assert reloaded.props[0].assetId == "asset-library-99"
        assert reloaded.props[0].propId is None
    finally:
        db.close()


def test_reset_returns_neutral_and_clears_coords_keeps_assignments():
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Reset Neutral"))
        doc = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(
                characterId="korri-123",
                label="Korri",
                gridRow=4,
                gridColumn=4,
                slotIndex=0,
                colorKey="red",
                miniPrompt="@Korri at the bar.",
            ),
        )
        doc = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(label="Lightsaber", propId="prop-lightsaber", gridRow=3, gridColumn=3),
        )
        doc = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(label="Coffee Cup", assetId="asset-library-99", propId=None, gridRow=2, gridColumn=2),
        )
        for spec in (
            ("C1", 0, 5, 5, "N", "medium"),
            ("C2", 1, 5, 4, "NE", "wide"),
            ("C3", 2, 4, 5, "E", "narrow"),
            ("C4", 3, 3, 4, "S", "medium"),
        ):
            label, slot, row, col, orientation, fov = spec
            doc = create_camera(
                db,
                project_id,
                doc.id,
                SpatialCameraCreateBody(
                    label=label,
                    cameraSlot=slot,
                    gridRow=row,
                    gridColumn=col,
                    orientation=orientation,
                    fovPreset=fov,
                ),
            )
        doc = update_document(db, project_id, doc.id, SpatialMapUpdateBody(gridScale=3))
        assert doc.gridScale == 3
        assert density_for_scale(doc.gridScale) == 16

        char_id = doc.characters[0].id
        doc = update_character(
            db,
            project_id,
            doc.id,
            char_id,
            SpatialCharacterPlacementUpdateBody(gridRow=-1, gridColumn=-1, miniPrompt=""),
        )
        for prop in list(doc.props):
            doc = update_prop(
                db,
                project_id,
                doc.id,
                prop.id,
                SpatialPropPlacementUpdateBody(gridRow=-1, gridColumn=-1, miniPrompt=""),
            )
        for camera in list(doc.cameras):
            doc = update_camera(
                db,
                project_id,
                doc.id,
                camera.id,
                SpatialCameraUpdateBody(gridRow=-1, gridColumn=-1, normalizedX=None, normalizedY=None),
            )
        doc = update_document(db, project_id, doc.id, SpatialMapUpdateBody(gridScale=0))

        assert doc.gridScale == 0
        assert density_for_scale(doc.gridScale) == 10
        assert doc.placementGrid == PLACEMENT_GRID_CARTESIAN
        assert len(doc.characters) == 1
        assert doc.characters[0].characterId == "korri-123"
        assert doc.characters[0].gridRow == -1
        assert doc.characters[0].gridColumn == -1
        assert doc.characters[0].normalizedX is None
        assert doc.characters[0].normalizedY is None
        assert len(doc.props) == 2
        assert doc.props[0].propId == "prop-lightsaber"
        assert doc.props[1].assetId == "asset-library-99"
        assert doc.props[1].propId is None
        assert doc.props[0].gridRow == -1
        assert len(doc.cameras) == 4
        by_label = {cam.label: cam for cam in doc.cameras}
        assert set(by_label) == {"C1", "C2", "C3", "C4"}
        assert by_label["C1"].cameraSlot == 0
        assert by_label["C1"].orientation == "N"
        assert by_label["C1"].fovPreset == "medium"
        assert by_label["C2"].cameraSlot == 1
        assert by_label["C2"].orientation == "NE"
        assert by_label["C2"].fovPreset == "wide"
        assert by_label["C3"].cameraSlot == 2
        assert by_label["C3"].orientation == "E"
        assert by_label["C3"].fovPreset == "narrow"
        assert by_label["C4"].cameraSlot == 3
        assert by_label["C4"].orientation == "S"
        assert by_label["C4"].fovPreset == "medium"
        for cam in doc.cameras:
            assert cam.gridRow == -1
            assert cam.gridColumn == -1
            assert cam.normalizedX is None
            assert cam.normalizedY is None
        reloaded = get_document(db, project_id, doc.id)
        assert len(reloaded.cameras) == 4
        assert {cam.label for cam in reloaded.cameras} == {"C1", "C2", "C3", "C4"}
        for cam in reloaded.cameras:
            assert cam.gridRow == -1
            assert cam.gridColumn == -1
            assert cam.normalizedX is None
            assert cam.normalizedY is None
        assert {cam.label: (cam.orientation, cam.fovPreset, cam.cameraSlot) for cam in reloaded.cameras} == {
            "C1": ("N", "medium", 0),
            "C2": ("NE", "wide", 1),
            "C3": ("E", "narrow", 2),
            "C4": ("S", "medium", 3),
        }
    finally:
        db.close()


def test_legacy_document_get_does_not_stamp_cartesian_until_write():
    import json
    from datetime import datetime

    from app.spatial_map.models import SpatialMapDocumentRow

    project_id = _create_project()
    db = _session()
    try:
        doc_id = str(uuid.uuid4())
        legacy = {
            "id": doc_id,
            "projectId": project_id,
            "title": "Legacy Polar",
            "gridScale": 0,
            "placementGrid": "",
            "characters": [
                {
                    "characterId": "korri-123",
                    "label": "Korri",
                    "gridRow": 2,
                    "gridColumn": 0,
                    "slotIndex": 0,
                    "colorKey": "red",
                }
            ],
            "props": [
                {
                    "label": "Cup",
                    "assetId": "asset-library-1",
                    "gridRow": 1,
                    "gridColumn": 3,
                }
            ],
            "cameras": [
                {
                    "label": "C1",
                    "cameraSlot": 0,
                    "gridRow": 3,
                    "gridColumn": 2,
                    "orientation": "E",
                    "fovPreset": "wide",
                }
            ],
        }
        db.add(
            SpatialMapDocumentRow(
                id=doc_id,
                project_id=project_id,
                title="Legacy Polar",
                document_json=json.dumps(legacy),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        db.commit()
        loaded = get_document(db, project_id, doc_id)
        assert loaded.placementGrid == PLACEMENT_GRID_CARTESIAN
        assert len(loaded.characters) == 1
        assert loaded.characters[0].characterId == "korri-123"
        assert loaded.characters[0].normalizedX is not None
        assert loaded.characters[0].normalizedY is not None
        assert loaded.characters[0].gridRow >= 0
        assert loaded.characters[0].gridColumn >= 0
        assert len(loaded.props) == 1
        assert loaded.props[0].assetId == "asset-library-1"
        assert loaded.props[0].propId is None
        assert loaded.props[0].normalizedX is not None
        assert len(loaded.cameras) == 1
        assert loaded.cameras[0].orientation == "E"
        assert loaded.cameras[0].fovPreset == "wide"
        assert loaded.cameras[0].normalizedX is not None
        listed = list_documents(db, project_id)
        assert any(item.id == doc_id for item in listed)
        raw = json.loads(db.get(SpatialMapDocumentRow, doc_id).document_json)
        assert raw["placementGrid"] == ""
        assert raw["characters"][0]["characterId"] == "korri-123"
        assert "normalizedX" not in raw["characters"][0]
        assert raw["props"][0]["assetId"] == "asset-library-1"
        assert raw["props"][0].get("propId") in (None, "")
        assert len(raw["cameras"]) == 1
        written = update_document(db, project_id, doc_id, SpatialMapUpdateBody(notes="stamp-on-write"))
        assert written.placementGrid == PLACEMENT_GRID_CARTESIAN
        raw = json.loads(db.get(SpatialMapDocumentRow, doc_id).document_json)
        assert raw["placementGrid"] == PLACEMENT_GRID_CARTESIAN
        assert raw["characters"][0]["characterId"] == "korri-123"
        assert raw["characters"][0]["normalizedX"] is not None
        assert raw["props"][0]["assetId"] == "asset-library-1"
        assert raw["props"][0].get("propId") in (None, "")
        assert len(raw["cameras"]) == 1
    finally:
        db.close()

def test_visible_default_true_and_false_persists_assignment_and_coords():
    """Missing visible defaults true. visible=false persists and keeps assignment/coords."""
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Visible"))
        doc = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(
                characterId="korri-123",
                label="Korri",
                slotIndex=0,
                colorKey="red",
                gridRow=4,
                gridColumn=4,
            ),
        )
        char = doc.characters[0]
        assert char.visible is True
        assert char.characterId == "korri-123"
        assert char.normalizedX is not None
        nx, ny = char.normalizedX, char.normalizedY
        hidden = update_character(
            db,
            project_id,
            doc.id,
            char.id,
            SpatialCharacterPlacementUpdateBody(visible=False),
        )
        entity = hidden.characters[0]
        assert entity.visible is False
        assert entity.characterId == "korri-123"
        assert entity.slotIndex == 0
        assert entity.normalizedX == nx
        assert entity.normalizedY == ny
        assert entity.gridRow == 4
        assert entity.gridColumn == 4
        doc = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(label="Cup", assetId="asset-1", visible=False, gridRow=3, gridColumn=3),
        )
        prop = doc.props[0]
        assert prop.visible is False
        assert prop.assetId == "asset-1"
        assert prop.normalizedX is not None
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, orientation="NE", fovPreset="wide", visible=False),
        )
        cam = doc.cameras[0]
        assert cam.visible is False
        assert cam.cameraSlot == 0
        reloaded = get_document(db, project_id, doc.id)
        assert reloaded.characters[0].visible is False
        assert reloaded.characters[0].characterId == "korri-123"
        assert reloaded.characters[0].normalizedX == nx
        assert reloaded.characters[0].normalizedY == ny
        assert reloaded.props[0].visible is False
        assert reloaded.props[0].assetId == "asset-1"
        assert reloaded.cameras[0].visible is False
        assert reloaded.cameras[0].cameraSlot == 0
        assert reloaded.cameras[0].orientation == "NE"
        assert reloaded.cameras[0].fovPreset == "wide"
        from app.spatial_map.schemas import SpatialCharacterPlacement

        legacy = SpatialCharacterPlacement.model_validate(
            {"characterId": "hero-1", "label": "Hero", "normalizedX": 0.1, "normalizedY": -0.2}
        )
        assert legacy.visible is True
        assert legacy.characterId == "hero-1"
        assert legacy.normalizedX == 0.1
    finally:
        db.close()


def test_add_unplaced_then_place_move_same_placement_id():
    """ADD creates unplaced (grid -1, normalized null). PLACE/MOVE write cell center on the same id."""
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Unplaced Place Move"))
        doc = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(characterId="korri-123", label="Korri", slotIndex=1, colorKey="blue"),
        )
        placement = doc.characters[0]
        placement_id = placement.id
        assert placement.gridRow == -1
        assert placement.gridColumn == -1
        assert placement.normalizedX is None
        assert placement.normalizedY is None
        placed = update_character(
            db,
            project_id,
            doc.id,
            placement_id,
            SpatialCharacterPlacementUpdateBody(gridRow=4, gridColumn=5),
        )
        entity = placed.characters[0]
        assert entity.id == placement_id
        assert entity.characterId == "korri-123"
        assert entity.gridRow == 4
        assert entity.gridColumn == 5
        assert entity.normalizedX is not None
        assert entity.normalizedY is not None
        first_nx, first_ny = entity.normalizedX, entity.normalizedY
        moved = update_character(
            db,
            project_id,
            doc.id,
            placement_id,
            SpatialCharacterPlacementUpdateBody(gridRow=2, gridColumn=3),
        )
        moved_entity = moved.characters[0]
        assert moved_entity.id == placement_id
        assert moved_entity.characterId == "korri-123"
        assert moved_entity.gridRow == 2
        assert moved_entity.gridColumn == 3
        assert moved_entity.normalizedX != first_nx or moved_entity.normalizedY != first_ny
        assert len(moved.characters) == 1
    finally:
        db.close()


def test_camera_coords_only_does_not_reset_orientation_fov():
    """Set orientation/FOV/visible first; coords-only update must not reset them (exclude_unset)."""
    project_id = _create_project()
    db = _session()
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Camera Coords Only"))
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, orientation="N", fovPreset="medium"),
        )
        camera = doc.cameras[0]
        assert camera.visible is True
        assert camera.gridRow == -1
        # Set orientation/FOV/visible first (no coords).
        doc = update_camera(
            db,
            project_id,
            doc.id,
            camera.id,
            SpatialCameraUpdateBody(orientation="NE", fovPreset="wide", visible=False),
        )
        camera = doc.cameras[0]
        assert camera.orientation == "NE"
        assert camera.fovPreset == "wide"
        assert camera.yawDegrees == 45
        assert camera.visible is False
        assert camera.gridRow == -1
        assert camera.gridColumn == -1
        # Then coords only — must not reset orientation/FOV/visible.
        updated = update_camera(
            db,
            project_id,
            doc.id,
            camera.id,
            SpatialCameraUpdateBody(gridRow=5, gridColumn=6),
        )
        cam = updated.cameras[0]
        assert cam.id == camera.id
        assert cam.orientation == "NE"
        assert cam.fovPreset == "wide"
        assert cam.yawDegrees == 45
        assert cam.visible is False
        assert cam.gridRow == 5
        assert cam.gridColumn == 6
        assert cam.normalizedX is not None
        reloaded = get_document(db, project_id, doc.id)
        assert reloaded.cameras[0].orientation == "NE"
        assert reloaded.cameras[0].fovPreset == "wide"
        assert reloaded.cameras[0].yawDegrees == 45
        assert reloaded.cameras[0].visible is False
        assert reloaded.cameras[0].gridRow == 5
        assert reloaded.cameras[0].gridColumn == 6
    finally:
        db.close()


def test_hide_is_not_delete_hidden_entity_remains_in_document():
    """visible=false hides the marker only. The entity stays in the document; remove_* deletes it."""
    project_id = _create_project()
    db = _session()
    _seed_entities(db, project_id)
    try:
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Hide Ne Delete"))
        doc = place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(
                characterId="korri-123",
                label="Korri",
                slotIndex=0,
                colorKey="red",
                gridRow=4,
                gridColumn=4,
            ),
        )
        doc = place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(label="Cup", assetId="asset-1", propId="prop-9", gridRow=3, gridColumn=3),
        )
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, orientation="NE", fovPreset="wide"),
        )
        char_id = doc.characters[0].id
        prop_id = doc.props[0].id
        cam_id = doc.cameras[0].id
        char_nx, char_ny = doc.characters[0].normalizedX, doc.characters[0].normalizedY
        prop_nx, prop_ny = doc.props[0].normalizedX, doc.props[0].normalizedY
        assert doc.characters[0].visible is True
        assert doc.props[0].visible is True
        assert doc.cameras[0].visible is True

        hidden = update_character(
            db, project_id, doc.id, char_id, SpatialCharacterPlacementUpdateBody(visible=False)
        )
        hidden = update_prop(
            db, project_id, doc.id, prop_id, SpatialPropPlacementUpdateBody(visible=False)
        )
        hidden = update_camera(
            db, project_id, doc.id, cam_id, SpatialCameraUpdateBody(visible=False)
        )

        assert len(hidden.characters) == 1
        assert len(hidden.props) == 1
        assert len(hidden.cameras) == 1
        assert hidden.characters[0].id == char_id
        assert hidden.props[0].id == prop_id
        assert hidden.cameras[0].id == cam_id
        assert hidden.characters[0].visible is False
        assert hidden.props[0].visible is False
        assert hidden.cameras[0].visible is False
        assert hidden.characters[0].characterId == "korri-123"
        assert hidden.characters[0].slotIndex == 0
        assert hidden.characters[0].normalizedX == char_nx
        assert hidden.characters[0].normalizedY == char_ny
        assert hidden.props[0].assetId == "asset-1"
        assert hidden.props[0].propId == "prop-9"
        assert hidden.props[0].normalizedX == prop_nx
        assert hidden.props[0].normalizedY == prop_ny
        assert hidden.cameras[0].cameraSlot == 0
        assert hidden.cameras[0].orientation == "NE"
        assert hidden.cameras[0].fovPreset == "wide"

        reloaded = get_document(db, project_id, doc.id)
        assert len(reloaded.characters) == 1
        assert len(reloaded.props) == 1
        assert len(reloaded.cameras) == 1
        assert reloaded.characters[0].id == char_id
        assert reloaded.props[0].id == prop_id
        assert reloaded.cameras[0].id == cam_id
        assert reloaded.characters[0].visible is False
        assert reloaded.props[0].visible is False
        assert reloaded.cameras[0].visible is False
        assert reloaded.characters[0].characterId == "korri-123"
        assert reloaded.characters[0].normalizedX == char_nx
        assert reloaded.props[0].assetId == "asset-1"
        assert reloaded.cameras[0].orientation == "NE"

        deleted = remove_character(db, project_id, doc.id, char_id)
        assert all(item.id != char_id for item in deleted.characters)
        assert len(deleted.characters) == 0
        assert len(deleted.props) == 1
        assert deleted.props[0].id == prop_id
        assert deleted.props[0].visible is False
        assert len(deleted.cameras) == 1
        assert deleted.cameras[0].id == cam_id
        assert deleted.cameras[0].visible is False

        after_delete = get_document(db, project_id, doc.id)
        assert len(after_delete.characters) == 0
        assert len(after_delete.props) == 1
        assert after_delete.props[0].id == prop_id
        assert after_delete.props[0].visible is False
        assert len(after_delete.cameras) == 1
        assert after_delete.cameras[0].id == cam_id
        assert after_delete.cameras[0].visible is False

        deleted = remove_prop(db, project_id, doc.id, prop_id)
        deleted = remove_camera(db, project_id, doc.id, cam_id)
        assert deleted.props == []
        assert deleted.cameras == []
        gone = get_document(db, project_id, doc.id)
        assert gone.characters == []
        assert gone.props == []
        assert gone.cameras == []
    finally:
        db.close()
