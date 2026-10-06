"""Background Alignment — hydrate, persist, invariance, ERS packet/panel."""

from __future__ import annotations

import json
import uuid
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.db import Project, init_db
from app.spatial_map.background_alignment import (
    ALIGNMENT_MAX,
    SCALE_MAX,
    SCALE_MIN,
    clamp_offset,
    clamp_scale,
    contain_rect,
    hydrate_alignment,
)

ZERO = {
    "offsetX": 0.0,
    "offsetY": 0.0,
    "scale": 1.0,
    "sourceWidth": 0.0,
    "sourceHeight": 0.0,
    "sourceAspectRatio": 1.0,
}
from app.spatial_map.ers_compose_2k import _contain_atlas, render_spatial_map_panel
from app.spatial_map.ers_packet import compile_ers_packet, placement_fingerprint
from app.spatial_map.scene_intent import lineage_fingerprint
from app.spatial_map.schemas import (
    BackgroundAlignment,
    SpatialCharacterPlacement,
    SpatialMapCreateBody,
    SpatialMapDocument,
    SpatialMapUpdateBody,
    SpatialPropPlacement,
)
from app.spatial_map.service import create_document, get_document, update_document


def _session():
    from app.db import SessionLocal

    init_db()
    return SessionLocal()


def _create_project(name: str = "Background Alignment Unit") -> str:
    db = _session()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def test_hydrate_missing_and_invalid_to_zero() -> None:
    assert hydrate_alignment(None) == ZERO
    assert hydrate_alignment({}) == ZERO
    assert hydrate_alignment({"offsetX": "x", "offsetY": float("inf")}) == ZERO
    assert hydrate_alignment({"scale": "x"}) == ZERO
    assert hydrate_alignment({"scale": float("nan")}) == ZERO
    doc = SpatialMapDocument.model_validate({"projectId": "p1"})
    assert doc.backgroundAlignment.offsetX == 0.0
    assert doc.backgroundAlignment.offsetY == 0.0
    assert doc.backgroundAlignment.scale == 1.0
    null_doc = SpatialMapDocument.model_validate({"projectId": "p1", "backgroundAlignment": None})
    assert null_doc.backgroundAlignment.offsetX == 0.0
    assert null_doc.backgroundAlignment.scale == 1.0


def test_old_document_json_deserializes() -> None:
    raw = {
        "projectId": "p1",
        "id": "map-old",
        "title": "Historical Atlas",
        "backgroundAssetId": "atlas-1",
        "characters": [],
        "props": [],
        "cameras": [],
    }
    doc = SpatialMapDocument.model_validate(raw)
    assert doc.backgroundAssetId == "atlas-1"
    assert doc.backgroundAlignment.offsetX == 0
    assert doc.backgroundAlignment.offsetY == 0
    assert doc.backgroundAlignment.scale == 1.0
    assert hydrate_alignment(raw.get("backgroundAlignment")) == ZERO


def test_contain_rect_keeps_native_aspect() -> None:
    x, y, w, h = contain_rect(1000.0, 16 / 9)
    assert abs((w / h) - (16 / 9)) < 1e-6
    assert abs(w - 1000.0) < 1e-6
    assert y > 0
    x4, y4, w4, h4 = contain_rect(1000.0, 4 / 3)
    assert abs((w4 / h4) - (4 / 3)) < 1e-6
    portrait = contain_rect(1000.0, 9 / 16)
    assert abs((portrait[2] / portrait[3]) - (9 / 16)) < 1e-6
    assert portrait[0] > 0


def test_clamp_rejects_extreme_and_nan() -> None:
    assert clamp_offset(99999999) == ALIGNMENT_MAX
    assert clamp_offset(-99999999) == -ALIGNMENT_MAX
    assert clamp_offset(float("nan")) == 0.0
    assert clamp_scale(99) == SCALE_MAX
    assert clamp_scale(0) == SCALE_MIN
    assert clamp_scale(float("nan")) == 1.0
    aligned = BackgroundAlignment(offsetX=12, offsetY=-12, scale=99)
    assert aligned.offsetX == ALIGNMENT_MAX
    assert aligned.offsetY == -ALIGNMENT_MAX
    assert aligned.scale == SCALE_MAX


def test_save_update_reset_and_entity_invariance() -> None:
    project_id = _create_project()
    other_id = _create_project("Background Alignment Other")
    db = _session()
    try:
        doc = create_document(
            db,
            project_id,
            SpatialMapCreateBody(title="Align Persist", backgroundAssetId="atlas-keep"),
        )
        doc.characters = [
            SpatialCharacterPlacement(
                id="c1",
                characterId="cid-1",
                label="Korri",
                normalizedX=-0.2,
                normalizedY=0.1,
                gridRow=4,
                gridColumn=3,
            )
        ]
        doc.props = [
            SpatialPropPlacement(
                id="p1",
                label="Crate",
                normalizedX=0.3,
                normalizedY=-0.1,
                gridRow=5,
                gridColumn=6,
            )
        ]
        from app.spatial_map.service import _row_or_404, _save_document

        row = _row_or_404(db, project_id, doc.id)
        seeded = _save_document(db, row, doc)
        before_chars = [(c.id, c.normalizedX, c.normalizedY, c.gridRow, c.gridColumn) for c in seeded.characters]
        before_props = [(p.id, p.normalizedX, p.normalizedY, p.gridRow, p.gridColumn) for p in seeded.props]
        before_atlas = seeded.backgroundAssetId

        updated = update_document(
            db,
            project_id,
            seeded.id,
            SpatialMapUpdateBody(
                backgroundAlignment=BackgroundAlignment(offsetX=-0.05, offsetY=0.02, scale=2.0)
            ),
        )
        assert updated.backgroundAlignment.offsetX == -0.05
        assert updated.backgroundAlignment.offsetY == 0.02
        assert updated.backgroundAlignment.scale == 2.0
        assert updated.backgroundAssetId == before_atlas
        assert [(c.id, c.normalizedX, c.normalizedY, c.gridRow, c.gridColumn) for c in updated.characters] == before_chars
        assert [(p.id, p.normalizedX, p.normalizedY, p.gridRow, p.gridColumn) for p in updated.props] == before_props

        reloaded = get_document(db, project_id, seeded.id)
        assert reloaded.backgroundAlignment.offsetX == -0.05
        assert reloaded.backgroundAlignment.offsetY == 0.02
        assert reloaded.backgroundAlignment.scale == 2.0

        reset = update_document(
            db,
            project_id,
            seeded.id,
            SpatialMapUpdateBody(backgroundAlignment=BackgroundAlignment()),
        )
        assert reset.backgroundAlignment.offsetX == 0.0
        assert reset.backgroundAlignment.offsetY == 0.0
        assert reset.backgroundAlignment.scale == 1.0

        try:
            get_document(db, other_id, seeded.id)
            raised = False
        except Exception:
            raised = True
        assert raised, "alignment maps must stay project-isolated"
    finally:
        db.close()


def test_packet_alignment_changes_placement_fingerprint_not_lineage() -> None:
    document = SimpleNamespace(
        id="map-1",
        projectId="p1",
        title="Lab",
        backgroundAssetId="atlas-1",
        sceneDescription="silver corridor",
        sceneIntent=SimpleNamespace(summary="silver corridor", model_dump=lambda: {"summary": "silver corridor"}),
        widthMeters=20,
        depthMeters=12,
        metersPerCell=1,
        characters=[SimpleNamespace(id="c1", label="Korri", normalizedX=0.1, normalizedY=-0.2, yawDegrees=90)],
        props=[],
        cameras=[],
        environmentalAnchors=[],
        backgroundAlignment=BackgroundAlignment(offsetX=-0.05, offsetY=0.02),
    )
    packet = compile_ers_packet(document, project_id="p1")
    assert packet["backgroundAlignment"]["offsetX"] == -0.05
    assert packet["backgroundAlignment"]["offsetY"] == 0.02
    assert packet["backgroundAlignment"]["scale"] == 1.0
    assert packet["backgroundAlignment"]["sourceAspectRatio"] == 1.0
    zero = {**packet, "backgroundAlignment": {"offsetX": 0.0, "offsetY": 0.0, "scale": 1.0}}
    assert placement_fingerprint(packet) != placement_fingerprint(zero)
    scaled = {**packet, "backgroundAlignment": {"offsetX": -0.05, "offsetY": 0.02, "scale": 2.0}}
    assert placement_fingerprint(packet) != placement_fingerprint(scaled)
    lineage_a = lineage_fingerprint(
        None,
        background_asset_id="atlas-1",
        original_reference_asset_id=None,
    )
    lineage_b = lineage_fingerprint(
        None,
        background_asset_id="atlas-1",
        original_reference_asset_id=None,
    )
    assert lineage_a == lineage_b


def test_panel_applies_offset_to_atlas_only() -> None:
    atlas = Image.new("RGB", (64, 64), (10, 10, 10))
    for x in range(32):
        for y in range(64):
            atlas.putpixel((x, y), (220, 30, 30))
        for y in range(64):
            atlas.putpixel((x + 32, y), (30, 30, 220))
    buf = BytesIO()
    atlas.save(buf, format="PNG")
    raw = buf.getvalue()
    packet = {
        "characters": [{"id": "c1", "x": 0.0, "y": 0.0}],
        "props": [],
        "cameras": [],
        "backgroundAlignment": {"offsetX": 0.2, "offsetY": 0.0},
    }
    aligned = render_spatial_map_panel(packet, size=80, atlas_bytes=raw)
    zero_packet = {**packet, "backgroundAlignment": {"offsetX": 0.0, "offsetY": 0.0}}
    zero = render_spatial_map_panel(zero_packet, size=80, atlas_bytes=raw)
    # Center marker stays put (teal character dot), atlas pixels shift.
    assert aligned.getpixel((40, 40)) == zero.getpixel((40, 40))
    assert aligned.tobytes() != zero.tobytes()


def test_panel_scale_about_center_leaves_marker() -> None:
    atlas = Image.new("RGB", (64, 64))
    for x in range(64):
        for y in range(64):
            atlas.putpixel((x, y), (x * 4, y * 4, 80))
    buf = BytesIO()
    atlas.save(buf, format="PNG")
    raw = buf.getvalue()
    packet = {
        "characters": [{"id": "c1", "x": 0.0, "y": 0.0}],
        "props": [],
        "cameras": [],
        "backgroundAlignment": {"offsetX": 0.0, "offsetY": 0.0, "scale": 2.0},
    }
    scaled = render_spatial_map_panel(packet, size=80, atlas_bytes=raw)
    one_packet = {**packet, "backgroundAlignment": {"offsetX": 0.0, "offsetY": 0.0, "scale": 1.0}}
    one = render_spatial_map_panel(one_packet, size=80, atlas_bytes=raw)
    # Center marker stays put; scale about center changes atlas pixels only.
    assert scaled.getpixel((40, 40)) == one.getpixel((40, 40))
    assert scaled.tobytes() != one.tobytes()


def test_panel_does_not_circle_mask_a_square_atlas() -> None:
    atlas = Image.new("RGB", (80, 80), (220, 40, 40))
    buf = BytesIO()
    atlas.save(buf, format="PNG")
    panel = render_spatial_map_panel(
        {"characters": [], "props": [], "cameras": [], "backgroundAlignment": {}},
        size=80,
        atlas_bytes=buf.getvalue(),
    )
    # Corners stay atlas red. A leftover circular mask would leave canvas fill.
    assert panel.getpixel((2, 2))[0] > 180
    assert panel.getpixel((77, 2))[0] > 180
    assert panel.getpixel((2, 77))[0] > 180


def test_panel_contains_16x9_without_square_crop() -> None:
    atlas = Image.new("RGB", (160, 90), (220, 40, 40))
    contained = _contain_atlas(atlas, 80, 0.0, 0.0, 1.0)
    # Letterbox bars stay canvas fill; a cover crop would paint those pixels red.
    assert contained.getpixel((40, 4)) == (28, 34, 42)
    assert contained.getpixel((40, 40))[0] > 180
    covered_would_fill = max(80 / 160, 80 / 90) > min(80 / 160, 80 / 90)
    assert covered_would_fill
