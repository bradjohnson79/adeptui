"""Phase 2.1 spatial-metric-v1 — meters, migration, camera lock."""

from __future__ import annotations

from app.spatial_map.metric import (
    METRIC_SCHEMA,
    apply_extent,
    bearing_degrees,
    compile_metric_lines,
    grid_cell_label,
    halfway_point,
    look_at,
    migrate_metric_document,
    orbit_camera,
    parse_grid_cell,
    planar_distance_meters,
    raise_camera,
    sync_document,
)
from app.spatial_map.schemas import (
    SpatialAnchor,
    SpatialCamera,
    SpatialCharacterPlacement,
    SpatialMapDocument,
    Vec3Meters,
)


def _doc(**overrides) -> SpatialMapDocument:
    data = {
        "projectId": "2347bf46-3762-4763-86c5-4a6032522278",
        "title": "Metric cert",
        "characters": [
            SpatialCharacterPlacement(
                id="char-a",
                characterId="char-a",
                label="Red",
                x=-6.0,
                y=0.0,
                z=0.0,
            ),
            SpatialCharacterPlacement(
                id="char-b",
                characterId="char-b",
                label="Blue",
                x=6.0,
                y=0.0,
                z=0.0,
            ),
        ],
        "cameras": [
            SpatialCamera(id="cam-1", label="Hero", x=0.0, y=1.6, z=8.0, heightMeters=1.6),
        ],
    }
    data.update(overrides)
    return SpatialMapDocument.model_validate(data)


def test_grid_cell_e8() -> None:
    assert grid_cell_label(4, 7) == "E8"
    assert parse_grid_cell("E8") == (4, 7)


def test_legacy_get_fills_meters_without_moving_schnick_style_coords() -> None:
    doc = SpatialMapDocument.model_validate(
        {
            "projectId": "2347bf46-3762-4763-86c5-4a6032522278",
            "title": "Schnick",
            "characters": [
                SpatialCharacterPlacement(
                    id="korri",
                    characterId="korri",
                    label="Korri",
                    x=1.25,
                    y=0.0,
                    z=-0.5,
                )
            ],
        }
    )
    assert doc.metricSchema is None
    changed = migrate_metric_document(doc)
    assert changed is True
    assert doc.metricSchema == METRIC_SCHEMA
    assert doc.metersPerCell == 1.0
    assert doc.widthMeters == 10.0
    assert doc.characters[0].x == 1.25
    assert doc.characters[0].z == -0.5
    assert doc.characters[0].positionMeters == Vec3Meters(x=1.25, y=0.0, z=-0.5)


def test_martial_arts_12m_spacing() -> None:
    doc = _doc()
    apply_extent(doc, 20.0, 20.0)
    sync_document(doc)
    a = doc.characters[0].positionMeters
    b = doc.characters[1].positionMeters
    assert a is not None and b is not None
    assert abs(planar_distance_meters(a.x, a.z, b.x, b.z) - 12.0) < 1e-6
    assert doc.widthMeters == 20.0
    lines = compile_metric_lines(doc)
    assert any("12.0 m" in line for line in lines)


def test_camera_orbit_does_not_move_characters() -> None:
    doc = _doc()
    sync_document(doc)
    before = [(c.id, c.x, c.z, c.positionMeters.model_dump() if c.positionMeters else None) for c in doc.characters]
    cam = doc.cameras[0]
    look_at(cam, 0.0, 0.0, 0.0)
    raise_camera(cam, 2.0)
    orbit_camera(cam, 45.0, (0.0, 0.0, 0.0))
    sync_document(doc)
    after = [(c.id, c.x, c.z, c.positionMeters.model_dump() if c.positionMeters else None) for c in doc.characters]
    assert after == before
    assert cam.heightMeters == 3.6
    assert cam.positionMeters is not None
    assert (cam.x, cam.z) != (0.0, 8.0)


def test_look_at_faces_north_zero() -> None:
    cam = SpatialCamera(id="c", label="C", x=0.0, y=1.6, z=4.0, heightMeters=1.6)
    look_at(cam, 0.0, 1.6, 0.0)
    assert abs(cam.yawDegrees) < 1e-6
    look_at(cam, 4.0, 1.6, 4.0)
    assert abs(cam.yawDegrees - 90.0) < 1e-6


def test_halfway_and_bearing() -> None:
    mid = halfway_point((-6.0, 0.0, 0.0), (6.0, 0.0, 0.0))
    assert mid == (0.0, 0.0, 0.0)
    assert abs(bearing_degrees(0.0, 0.0, 1.0, 0.0) - 90.0) < 1e-6


def test_no_zones_field() -> None:
    doc = _doc()
    dumped = doc.model_dump()
    assert "zones" not in dumped


def test_legacy_anchors_do_not_break_metric_sync() -> None:
    doc = SpatialMapDocument.model_validate(
        {
            "projectId": "2347bf46-3762-4763-86c5-4a6032522278",
            "title": "Anchors",
            "anchors": [SpatialAnchor(label="Bar", x=1.0, y=0.0, z=-2.0)],
        }
    )
    migrate_metric_document(doc)
    assert doc.anchors[0].x == 1.0
    assert doc.anchors[0].positionMeters == Vec3Meters(x=1.0, y=0.0, z=-2.0)
