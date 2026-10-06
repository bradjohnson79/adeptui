"""G10 + G13/G25: scene identity is a VIEW, never the composed CRS sheet.

Narrow fixture tests only. Does not generate. Does not touch live Korri rev 3.
Does not start uvicorn. Does not steal qwen2512.ref. Does not create CRS2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity.crs_identity_views import (
    FOUR_PANEL_ROLES,
    extract_crs_identity_views,
    persist_derived_identity_views,
    plan_crs_view_regions,
    scene_identity_source_asset_id,
)
from app.character_identity.crs_service import load_persisted_crs, persist_crs_in_session
from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow
from app.character_identity.schemas import CharacterProfileCreate, ReferenceAttach
from app.character_identity.service import attach_reference, create_profile
from app.character_identity.visual_context import (
    resolve_character_visual_context,
    resolve_scene_identity_view,
)
from app.config import settings
from app.db import Asset, Base, Project


SHEET_ID = "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"
# Distinct quadrant colors so crops are reproducible and checkable.
FRONT = (200, 40, 40)
SIDE = (40, 180, 40)
BACK = (40, 40, 200)
CLOSEUP = (200, 180, 40)
TILE = 64


def _session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Project(id="proj-g10", name="G10 Identity View"))
    db.commit()
    return db


def _four_panel_fixture(path: Path) -> Path:
    img = Image.new("RGB", (TILE * 2, TILE * 2), (8, 8, 8))
    quads = (FRONT, SIDE, BACK, CLOSEUP)
    for idx, color in enumerate(quads):
        tile = Image.new("RGB", (TILE, TILE), color)
        img.paste(tile, ((idx % 2) * TILE, (idx // 2) * TILE))
    img.save(path, format="PNG")
    return path


def _sample(im: Image.Image) -> tuple[int, int, int]:
    cx, cy = im.size[0] // 2, im.size[1] // 2
    return im.getpixel((cx, cy))[:3]


def _seed_korri_sheet(db, tmp_path, *, revision_target: int = 3) -> tuple[str, str]:
    """Approved CRS authority only. Does not write derived views yet."""
    profile = create_profile(
        db,
        "proj-g10",
        CharacterProfileCreate(
            name="Korri",
            slug="korri",
            role="lead",
            visual_description="Test fixture ? not live Korri.",
        ),
    )
    # Use a stable-looking character id only inside this isolated sqlite.
    # Do not collide with live c49371ed.
    sheet_path = _four_panel_fixture(tmp_path / "korri_rev3_sheet.png")
    db.add(
        Asset(
            id=SHEET_ID,
            project_id="proj-g10",
            tag="crs_sheet",
            kind="image",
            filename=sheet_path.name,
            path=str(sheet_path),
        )
    )
    db.commit()
    attach_reference(
        db,
        "proj-g10",
        profile.id,
        ReferenceAttach(
            asset_id=SHEET_ID,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="generation",
        ),
    )
    row = db.get(CharacterProfileRow, profile.id)
    persist_crs_in_session(db, row, asset_id=SHEET_ID)
    # Force revision 3 without touching a live PNG / approve path.
    persisted = load_persisted_crs(db, profile.id)
    persisted["crs_revision"] = revision_target
    persisted["approved_sheet_revision"] = revision_target
    from app.character_identity.models import CharacterTraitRow
    from app.character_identity.crs_service import CRS_CANON_TRAIT_KEY

    for trait in (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == profile.id,
            CharacterTraitRow.key == CRS_CANON_TRAIT_KEY,
        )
        .all()
    ):
        trait.value = json.dumps(persisted)
    db.commit()
    return profile.id, SHEET_ID


def test_extract_four_panel_fixture_regions(tmp_path):
    path = _four_panel_fixture(tmp_path / "sheet.png")
    regions = plan_crs_view_regions(TILE * 2, TILE * 2)
    assert [r["role"] for r in regions] == list(FOUR_PANEL_ROLES)
    assert "full_body_three_quarter_front" not in [r["role"] for r in regions]

    views = extract_crs_identity_views(path)
    assert [v.role for v in views] == list(FOUR_PANEL_ROLES)
    colors = [_sample(v.image) for v in views]
    assert colors == [FRONT, SIDE, BACK, CLOSEUP]


def test_scene_identity_resolver_never_returns_sheet_as_source(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    character_id, sheet_id = _seed_korri_sheet(db, tmp_path)

    before = resolve_scene_identity_view(db, "proj-g10", character_id, camera="front")
    assert before is not None
    assert before.source == "derived_crop_request"
    assert before.sourceAssetId is None
    assert before.asset_id is None
    assert before.crs_sheet_asset_id == sheet_id
    assert before.derived_crop_request["useComposedSheet"] is False
    assert scene_identity_source_asset_id(view_asset_id=sheet_id, sheet_asset_id=sheet_id) is None

    written = persist_derived_identity_views(
        db,
        "proj-g10",
        character_id,
        sheet_asset_id=sheet_id,
        crs_revision=3,
    )
    roles = {row["referenceRole"] for row in written}
    assert roles == set(FOUR_PANEL_ROLES)

    view = resolve_scene_identity_view(db, "proj-g10", character_id, camera="front")
    assert view is not None
    assert view.source == "identity_view"
    assert view.sourceAssetId != sheet_id
    assert view.asset_id != sheet_id
    assert view.asset_id == view.sourceAssetId
    assert view.reference_role == "full_body_front"
    assert view.crs_sheet_asset_id == sheet_id


def test_camera_side_selects_side_role(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    character_id, sheet_id = _seed_korri_sheet(db, tmp_path)
    persist_derived_identity_views(
        db, "proj-g10", character_id, sheet_asset_id=sheet_id, crs_revision=3
    )
    view = resolve_scene_identity_view(db, "proj-g10", character_id, camera="profile")
    assert view is not None
    assert view.camera_role == "side"
    assert view.reference_role == "full_body_side_left"
    assert view.sourceAssetId != sheet_id

    back = resolve_scene_identity_view(db, "proj-g10", character_id, camera="back")
    assert back.reference_role == "full_body_back"
    assert back.sourceAssetId != sheet_id


def test_lineage_points_at_original_crs(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    character_id, sheet_id = _seed_korri_sheet(db, tmp_path)
    written = persist_derived_identity_views(
        db, "proj-g10", character_id, sheet_asset_id=sheet_id, crs_revision=3
    )
    assert written
    side = next(row for row in written if row["referenceRole"] == "full_body_side_left")
    ref = db.get(CharacterReferenceAssetRow, side["referenceId"])
    lineage = json.loads(ref.generation_lineage_json)
    assert lineage["sourceCrsAssetId"] == sheet_id
    assert lineage["sourceCrsRevision"] == 3
    assert lineage["newCanon"] is False
    assert lineage["kind"] == "crs_derived_crop"
    assert ref.canonical is False
    assert ref.source_type == "crs_derived_crop"

    view = resolve_scene_identity_view(db, "proj-g10", character_id, camera="side")
    assert view.lineage["sourceCrsAssetId"] == sheet_id
    assert view.crs_revision == 3


def test_persist_is_additive_and_does_not_change_crs_or_hero(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    character_id, sheet_id = _seed_korri_sheet(db, tmp_path)
    persisted_before = load_persisted_crs(db, character_id)
    assert persisted_before["crs_revision"] == 3
    assert persisted_before["approved_sheet_asset_id"] == sheet_id

    hero = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == character_id,
            CharacterReferenceAssetRow.reference_role == "hero_identity",
        )
        .one()
    )
    hero_id = hero.id
    hero_asset = hero.asset_id

    written = persist_derived_identity_views(
        db, "proj-g10", character_id, sheet_asset_id=sheet_id, crs_revision=3
    )
    assert written

    persisted_after = load_persisted_crs(db, character_id)
    assert persisted_after["crs_revision"] == 3
    assert persisted_after["approved_sheet_asset_id"] == sheet_id

    hero_after = db.get(CharacterReferenceAssetRow, hero_id)
    assert hero_after.asset_id == hero_asset == sheet_id
    assert hero_after.canonical is True

    again = persist_derived_identity_views(
        db, "proj-g10", character_id, sheet_asset_id=sheet_id, crs_revision=3
    )
    assert again == []


def test_visual_context_scene_purpose_never_returns_sheet(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    character_id, sheet_id = _seed_korri_sheet(db, tmp_path)

    inspection = resolve_character_visual_context(db, "proj-g10", character_id)
    assert inspection is not None
    assert inspection.source == "crs_sheet"
    assert inspection.asset_id == sheet_id

    scene = resolve_character_visual_context(
        db, "proj-g10", character_id, purpose="scene", camera="front"
    )
    assert scene is not None
    assert scene.source == "derived_crop_request"
    assert scene.asset_id != sheet_id
    assert not scene.asset_id

    persist_derived_identity_views(
        db, "proj-g10", character_id, sheet_asset_id=sheet_id, crs_revision=3
    )
    scene2 = resolve_character_visual_context(
        db, "proj-g10", character_id, purpose="scene", camera="side"
    )
    assert scene2.source == "identity_view"
    assert scene2.asset_id != sheet_id
    assert scene2.reference_type == "full_body_side_left"
    assert scene2.lineage.get("sourceCrsAssetId") == sheet_id
