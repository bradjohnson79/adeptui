"""Character Reference `reference_image` role tests (Workstream A).

Verifies that the new `reference_image` role is a first-class member of the
reference-role taxonomy and round-trips through attach/detach without
colliding with `hero_identity`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import service
from app.character_identity.models import CharacterReferenceAssetRow
from app.character_identity.roles import ALL_REFERENCE_ROLES
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
    session.add(Project(id="proj-refrole", name="Reference Role Test"))
    session.add(
        Asset(
            id="asset-ref",
            project_id="proj-refrole",
            tag="reference",
            kind="image",
            filename="ref.png",
            path="ref.png",
        )
    )
    session.add(
        Asset(
            id="asset-hero",
            project_id="proj-refrole",
            tag="hero",
            kind="image",
            filename="hero.png",
            path="hero.png",
        )
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def profile_id(db):
    profile = service.create_profile(
        db,
        "proj-refrole",
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


def test_reference_image_in_all_reference_roles():
    assert "reference_image" in ALL_REFERENCE_ROLES


def test_reference_image_distinct_from_hero_identity():
    assert "reference_image" != "hero_identity"
    assert "hero_identity" in ALL_REFERENCE_ROLES
    assert "reference_image" in ALL_REFERENCE_ROLES


def test_attach_reference_image_persists(db, profile_id):
    result = _attach(
        db, "proj-refrole", profile_id, asset_id="asset-ref", role="reference_image"
    )
    assert result["reference_role"] == "reference_image"
    assert result["asset_id"] == "asset-ref"

    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == profile_id,
            CharacterReferenceAssetRow.asset_id == "asset-ref",
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].reference_role == "reference_image"


def test_detach_removes_reference_image_row(db, profile_id):
    _attach(
        db, "proj-refrole", profile_id, asset_id="asset-ref", role="reference_image"
    )
    result = service.detach_reference(db, "proj-refrole", profile_id, "asset-ref")
    assert result["ok"] is True
    assert result["detached"] == "asset-ref"

    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == profile_id,
            CharacterReferenceAssetRow.asset_id == "asset-ref",
        )
        .all()
    )
    assert rows == []


def test_reference_image_and_hero_identity_are_separate_rows(db, profile_id):
    """Attaching both `reference_image` and `hero_identity` for the same asset
    produces two distinct rows with different roles (no aliasing / overwrite)."""
    _attach(
        db, "proj-refrole", profile_id, asset_id="asset-ref", role="reference_image"
    )
    _attach(
        db, "proj-refrole", profile_id, asset_id="asset-hero", role="hero_identity"
    )

    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == profile_id)
        .all()
    )
    assert len(rows) == 2

    by_role = {r.reference_role: r.asset_id for r in rows}
    assert by_role.get("reference_image") == "asset-ref"
    assert by_role.get("hero_identity") == "asset-hero"

    # Detaching the hero_identity row must NOT remove the reference_image row.
    service.detach_reference(db, "proj-refrole", profile_id, "asset-hero")
    remaining = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == profile_id)
        .all()
    )
    assert len(remaining) == 1
    assert remaining[0].reference_role == "reference_image"
    assert remaining[0].asset_id == "asset-ref"
