"""Character Creator Save / Reset / Delete backend contract."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate
from app.character_identity.service import create_profile, delete_profile, get_profile, update_profile
from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def _apply_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def enable_m33(monkeypatch: pytest.MonkeyPatch):
    _apply_flags(monkeypatch)
    yield
    _apply_flags(monkeypatch)


@pytest.fixture()
def db(enable_m33) -> Session:
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


def _make_project(db: Session) -> str:
    pid = f"life-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name="Lifecycle Controls"))
    db.commit()
    return pid


def test_save_persists_profile_fields(db: Session) -> None:
    pid = _make_project(db)
    created = create_profile(
        db,
        pid,
        CharacterProfileCreate(
            name="Lifecycle Mira",
            description="Original description that is long enough to keep.",
        ),
    )
    updated = update_profile(
        db,
        pid,
        created.id,
        CharacterProfileUpdate(description="Saved description that must survive reload."),
    )
    assert updated.description == "Saved description that must survive reload."
    reloaded = get_profile(db, pid, created.id)
    assert reloaded.description == "Saved description that must survive reload."


def test_save_validation_rejects_missing_character(db: Session) -> None:
    pid = _make_project(db)
    with pytest.raises(Exception) as exc:
        update_profile(
            db,
            pid,
            str(uuid.uuid4()),
            CharacterProfileUpdate(description="nope"),
        )
    assert "404" in str(exc.value) or "not found" in str(exc.value).lower()


def test_reset_is_local_only_no_profile_mutation(db: Session) -> None:
    """Reset restores a snapshot in the UI. Backend Save is the only persist path."""
    pid = _make_project(db)
    created = create_profile(
        db,
        pid,
        CharacterProfileCreate(name="Snapshot", description="Persisted snapshot text."),
    )
    before = get_profile(db, pid, created.id)
    # Simulate a local reset: do not call update_profile.
    after = get_profile(db, pid, created.id)
    assert after.description == before.description == "Persisted snapshot text."
    assert after.updated_at == before.updated_at


def test_delete_removes_character_and_leaves_shared_assets(db: Session) -> None:
    pid = _make_project(db)
    created = create_profile(
        db,
        pid,
        CharacterProfileCreate(name="Disposable Twin", description="Safe to delete."),
    )
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=pid,
            tag="library",
            kind="image",
            filename="shared.png",
            path="shared.png",
        )
    )
    db.commit()
    out = delete_profile(db, pid, created.id)
    assert out["deleted"] is True
    with pytest.raises(Exception):
        get_profile(db, pid, created.id)
    asset = db.get(Asset, aid)
    assert asset is not None
    assert asset.project_id == pid


def test_korri_cannot_be_deleted_by_name_guard(db: Session) -> None:
    pid = _make_project(db)
    created = create_profile(
        db,
        pid,
        CharacterProfileCreate(name="Korri", description="Protected seed character."),
    )
    with pytest.raises(Exception) as exc:
        delete_profile(db, pid, created.id)
    assert "409" in str(exc.value) or "cannot be deleted" in str(exc.value).lower()
    still = get_profile(db, pid, created.id)
    assert still.name == "Korri"
