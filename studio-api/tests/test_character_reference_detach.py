"""Character reference detach endpoint + service.detach_reference tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import service
from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow
from app.character_identity.schemas import CharacterProfileCreate, ReferenceAttach
from app.db import Asset, Base, Project


@pytest.fixture()
def db():
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
                conn.execute(
                    text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}")
                )
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-detach", name="Detach Test"))
    session.add(
        Asset(
            id="asset-hero",
            project_id="proj-detach",
            tag="korri_sheet",
            kind="image",
            filename="korri.png",
            path="korri.png",
        )
    )
    session.add(
        Asset(
            id="asset-extra",
            project_id="proj-detach",
            tag="reference",
            kind="image",
            filename="ref.png",
            path="ref.png",
        )
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def profile_id(db):
    profile = service.create_profile(
        db,
        "proj-detach",
        CharacterProfileCreate(name="Korri", slug="korri", role="Sass Queen"),
    )
    return profile.id


def _attach(db, project_id, character_id, *, asset_id, role):
    return service.attach_reference(
        db,
        project_id,
        character_id,
        ReferenceAttach(asset_id=asset_id, reference_role=role, canonical=True),
    )


def test_detach_reference_removes_row(db, profile_id):
    _attach(db, "proj-detach", profile_id, asset_id="asset-hero", role="hero_identity")
    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == profile_id,
            CharacterReferenceAssetRow.asset_id == "asset-hero",
        )
        .all()
    )
    assert len(rows) == 1

    result = service.detach_reference(db, "proj-detach", profile_id, "asset-hero")
    assert result["ok"] is True
    assert result["detached"] == "asset-hero"

    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == profile_id,
            CharacterReferenceAssetRow.asset_id == "asset-hero",
        )
        .all()
    )
    assert rows == []


def test_detach_reference_idempotent_on_missing(db, profile_id):
    result = service.detach_reference(db, "proj-detach", profile_id, "asset-never-attached")
    assert result == {"ok": True, "detached": None}


def test_detach_reference_preserves_library_asset(db, profile_id):
    _attach(db, "proj-detach", profile_id, asset_id="asset-hero", role="hero_identity")
    service.detach_reference(db, "proj-detach", profile_id, "asset-hero")
    asset = db.get(Asset, "asset-hero")
    assert asset is not None
    assert asset.id == "asset-hero"
    assert asset.project_id == "proj-detach"


def test_detach_reference_recomputes_coverage(db, profile_id):
    role = "full_body_front"
    _attach(db, "proj-detach", profile_id, asset_id="asset-hero", role=role)

    cov_before = service.coverage(db, "proj-detach", profile_id)
    assert role in cov_before.present_roles

    service.detach_reference(db, "proj-detach", profile_id, "asset-hero")

    cov_after = service.coverage(db, "proj-detach", profile_id)
    assert role not in cov_after.present_roles


def test_detach_reference_blocks_locked_profile(db, profile_id):
    _attach(db, "proj-detach", profile_id, asset_id="asset-hero", role="hero_identity")
    row = db.get(CharacterProfileRow, profile_id)
    row.status = "LOCKED"
    db.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        service.detach_reference(db, "proj-detach", profile_id, "asset-hero")
    assert exc.value.status_code == 409


def test_detach_reference_project_isolation(db, profile_id):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        service.detach_reference(db, "proj-wrong", profile_id, "asset-hero")
    assert exc.value.status_code == 404
