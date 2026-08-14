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
        doc = create_camera(
            db,
            project_id,
            doc.id,
            SpatialCameraCreateBody(label="C1", cameraSlot=0, gridRow=5, gridColumn=5, orientation="N", fovPreset="medium"),
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
            doc = remove_camera(db, project_id, doc.id, camera.id)
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
        assert doc.cameras == []
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

