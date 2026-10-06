"""Preview Monitor Approve as — Character / Environment / Prop / Scene Frame."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.character_identity import models as _ci_models  # noqa: F401
from app.character_identity.crs_service import load_persisted_crs
from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.service import create_profile
from app.db import Asset, Base, Project, Scene
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import service as ref_service
from app.scene_references.approve_as import approve_library_image_as
from app.scene_references.sheet_tags import classify_asset


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-approve", name="Approve As Test"))
    session.add(
        Asset(
            id="asset-addex",
            project_id="proj-approve",
            tag="Addex",
            kind="image",
            filename="addex.png",
            path="addex.png",
        )
    )
    session.add(
        Asset(
            id="asset-korri",
            project_id="proj-approve",
            tag="Korri40YearsOld",
            kind="image",
            filename="korri.png",
            path="korri.png",
        )
    )
    session.add(
        Asset(
            id="asset-place",
            project_id="proj-approve",
            tag="VentureCorridor",
            kind="image",
            filename="place.png",
            path="place.png",
        )
    )
    session.add(
        Asset(
            id="asset-prop",
            project_id="proj-approve",
            tag="Lantern",
            kind="image",
            filename="lantern.png",
            path="lantern.png",
        )
    )
    session.add(
        Asset(
            id="asset-audio",
            project_id="proj-approve",
            tag="Footsteps",
            kind="audio",
            filename="steps.wav",
            path="steps.wav",
        )
    )
    session.add(
        Scene(
            id="scene-4",
            project_id="proj-approve",
            index=3,
            name="Scene 4",
            prompt="High quality anime characters",
            duration_sec=12.0,
        )
    )
    session.commit()
    yield session
    session.close()


def _attach_image(db, asset_id: str, alias: str):
    return ref_service.attach(
        db,
        "proj-approve",
        {
            "asset_id": asset_id,
            "scope_type": "project",
            "scope_id": "proj-approve",
            "reference_type": "image",
            "media_kind": "image",
            "alias": alias,
            "usage_modes": ["appearance"],
        },
        actor="user",
    )


def test_approve_as_character_retags_image_and_persists_sheet(db):
    create_profile(db, "proj-approve", CharacterProfileCreate(name="Addex", role="character"))
    first = _attach_image(db, "asset-addex", "Addex")
    assert first["reference_type"] == "image"
    assert str(first.get("display_token") or "").startswith("#")

    out = approve_library_image_as(
        db,
        "proj-approve",
        asset_id="asset-addex",
        kind="character",
    )
    assert out["ok"] is True
    assert out["kind"] == "character"
    assert out["character"]["name"] == "Addex"
    assert out["character"]["created"] is False
    assert out["character"]["approvedSheetAssetId"] == "asset-addex"
    assert out["binding"]["reference_type"] == "character"
    assert str(out["binding"].get("display_token") or "").startswith("@")
    assert out["binding"]["identity_id"] == out["character"]["characterId"]

    asset = db.get(Asset, "asset-addex")
    labels = json.loads(asset.labels_json or "[]")
    assert "character_sheet" in labels
    assert classify_asset(asset).kind == "crs"
    persisted = load_persisted_crs(db, out["character"]["characterId"])
    assert persisted.get("approved_sheet_asset_id") == "asset-addex"


def test_approve_as_character_matches_prefixed_library_name(db):
    created = create_profile(db, "proj-approve", CharacterProfileCreate(name="Korri", role="character"))
    _attach_image(db, "asset-korri", "Korri40YearsOld")
    out = approve_library_image_as(
        db,
        "proj-approve",
        asset_id="asset-korri",
        kind="character",
    )
    assert out["character"]["characterId"] == created.id
    assert out["character"]["created"] is False
    persisted = load_persisted_crs(db, created.id)
    assert persisted.get("approved_sheet_asset_id") == "asset-korri"


def test_approve_as_environment_and_prop(db):
    env = approve_library_image_as(db, "proj-approve", asset_id="asset-place", kind="environment")
    assert env["binding"]["reference_type"] == "environment"
    assert str(env["binding"].get("display_token") or "").startswith("#")
    place = db.get(Asset, "asset-place")
    assert "environment_reference_sheet" in json.loads(place.labels_json or "[]")
    assert classify_asset(place).kind == "ers"

    prop = approve_library_image_as(db, "proj-approve", asset_id="asset-prop", kind="prop")
    assert prop["binding"]["reference_type"] == "prop"
    assert str(prop["binding"].get("display_token") or "").startswith("%")
    lantern = db.get(Asset, "asset-prop")
    assert "prop_reference_sheet" in json.loads(lantern.labels_json or "[]")
    assert classify_asset(lantern).kind == "prs"


def test_approve_as_scene_frame_sets_opening_picture(db):
    out = approve_library_image_as(
        db,
        "proj-approve",
        asset_id="asset-place",
        kind="scene_frame",
        scene_id="scene-4",
    )
    assert out["sceneFrameSet"] is True
    scene = db.get(Scene, "scene-4")
    assert scene.start_asset_id == "asset-place"
    frames = ref_service.list_for_scope(db, "proj-approve", "start_frame", "scene-4")
    assert any(item.get("asset_id") == "asset-place" for item in frames)


def test_approve_as_rejects_audio(db):
    with pytest.raises(HTTPException) as exc:
        approve_library_image_as(db, "proj-approve", asset_id="asset-audio", kind="character")
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "NOT_AN_IMAGE"


def test_approve_as_rejects_unknown_kind(db):
    with pytest.raises(HTTPException) as exc:
        approve_library_image_as(db, "proj-approve", asset_id="asset-addex", kind="wardrobe")
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "INVALID_KIND"


def test_approve_as_atTag_uses_asset_tag_not_profile_name(db):
    """Canonical law: the @ tag comes from the Library asset tag, not the
    character profile name. @Korri40YearsOld (asset tag), not @Korri (profile name)."""
    create_profile(db, "proj-approve", CharacterProfileCreate(name="Korri", role="character"))
    _attach_image(db, "asset-korri", "Korri40YearsOld")
    out = approve_library_image_as(
        db,
        "proj-approve",
        asset_id="asset-korri",
        kind="character",
    )
    # atTag must be @Korri40YearsOld (from asset tag), not @Korri (from profile name)
    assert out["character"]["atTag"] == "@Korri40YearsOld"
    # Binding alias and display_token must also match the asset tag
    assert out["binding"]["alias"] == "Korri40YearsOld"


def test_approve_as_enriches_binding_with_crs_approval(db):
    """After approving a character, list_for_scope returns approval_status=approved + sheet id."""
    from app.scene_references.service import list_for_scope

    create_profile(db, "proj-approve", CharacterProfileCreate(name="Addex", role="character"))
    _attach_image(db, "asset-addex", "Addex")
    approve_library_image_as(db, "proj-approve", asset_id="asset-addex", kind="character")

    bindings = list_for_scope(db, "proj-approve", "project", "proj-approve")
    character_bindings = [b for b in bindings if b.get("reference_type") == "character"]
    assert len(character_bindings) == 1
    b = character_bindings[0]
    assert b["approval_status"] == "approved"
    assert b["approved_sheet_asset_id"] == "asset-addex"
    assert b["identity_id"] is not None
    assert b["broken"] is False


def test_approve_as_is_idempotent(db):
    """Repeated OK clicks must not create duplicate characters, CRS records, or bindings."""
    from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow
    from app.scene_references.repository import list_bindings

    create_profile(db, "proj-approve", CharacterProfileCreate(name="Addex", role="character"))
    _attach_image(db, "asset-addex", "Addex")

    # Approve three times
    for _ in range(3):
        approve_library_image_as(db, "proj-approve", asset_id="asset-addex", kind="character")

    # One character profile (the pre-existing one, not a duplicate)
    profiles = db.query(CharacterProfileRow).filter(CharacterProfileRow.project_id == "proj-approve").all()
    assert len(profiles) == 1

    # One canonical hero_identity reference asset row
    hero_rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == profiles[0].id)
        .filter(CharacterReferenceAssetRow.reference_role == "hero_identity")
        .filter(CharacterReferenceAssetRow.canonical.is_(True))
        .all()
    )
    assert len(hero_rows) == 1

    # One project-scope character binding
    bindings = list_bindings(db, "proj-approve", scope_type="project", scope_id="proj-approve")
    character_bindings = [b for b in bindings if b.reference_type == "character"]
    assert len(character_bindings) == 1
