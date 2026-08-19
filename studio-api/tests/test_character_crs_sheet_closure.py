"""Character Creator CRS sheet closure — persist, @resolve, delete, 2K, regen hero."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.character_identity.crs_service import get_crs_summary, load_persisted_crs
from app.character_identity.models import CharacterProfileRow
from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.service import (
    approve_character_candidate,
    create_profile,
    delete_profile,
    resolve_approved_reference,
)
from app.character_identity.visual_sheet import (
    CHARACTER_SHEET_TILE_SIZE,
    crs_2k_pixels,
)
from app.codirector.entity_resolver import resolve_character
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


def _project(db: Session) -> str:
    pid = f"crs-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name="CRS Closure"))
    db.commit()
    return pid


def _character(db: Session, project_id: str, name: str = "CRS Fixture") -> str:
    profile = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name=name, slug=name.lower().replace(" ", "-"), role="lead"),
    )
    return profile.id


def _image(db: Session, project_id: str, tag: str = "crs-sheet") -> str:
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=f"{tag}.png",
            path=f"{tag}.png",
        )
    )
    db.commit()
    return aid


def test_crs_2k_pixels_are_native_square_not_ers_16_9():
    assert CHARACTER_SHEET_TILE_SIZE == 1280
    assert crs_2k_pixels() == (2560, 2560)


def test_approve_persists_crs_revision_and_production_ready(db: Session):
    project_id = _project(db)
    character_id = _character(db, project_id, "Mira")
    asset_a = _image(db, project_id, "sheet-a")
    first = approve_character_candidate(
        db, project_id, character_id, asset_id=asset_a, reference_role="hero_identity"
    )
    assert first["productionReady"] is True
    assert first["crsRevision"] == 1
    assert first["atTag"] == "@Mira"
    assert resolve_approved_reference(db, character_id, "hero_identity") == asset_a

    persisted = load_persisted_crs(db, character_id)
    assert persisted["approved_sheet_asset_id"] == asset_a
    assert persisted["crs_revision"] == 1

    summary = get_crs_summary(db, project_id, character_id)
    assert summary is not None
    assert summary.crs_revision == 1
    assert summary.approved_reference_asset_id == asset_a

    profile = db.get(CharacterProfileRow, character_id)
    assert profile is not None
    assert profile.approval_status == "approved"
    assert profile.status == "APPROVED"

    asset_b = _image(db, project_id, "sheet-b")
    second = approve_character_candidate(
        db, project_id, character_id, asset_id=asset_b, reference_role="hero_identity"
    )
    assert second["crsRevision"] == 2
    assert resolve_approved_reference(db, character_id, "hero_identity") == asset_b
    assert load_persisted_crs(db, character_id)["crs_revision"] == 2


def test_at_name_resolver_reads_persisted_crs(db: Session):
    project_id = _project(db)
    character_id = _character(db, project_id, "Mira")
    asset_id = _image(db, project_id)
    approve_character_candidate(db, project_id, character_id, asset_id=asset_id)
    resolved = resolve_character(db, project_id, "Mira")
    assert resolved is not None
    assert resolved["character_id"] == character_id
    assert resolved["crs_revision"] == 1
    assert resolved["approved_sheet_asset_id"] == asset_id
    assert resolved["approved_casting_asset_id"] == asset_id
    assert resolved["production_ready"] is True


def test_delete_korri_guard_unregisters_fixture_keeps_library(db: Session):
    project_id = _project(db)
    korri_id = _character(db, project_id, "Korri")
    with pytest.raises(HTTPException) as exc:
        delete_profile(db, project_id, korri_id)
    assert exc.value.status_code == 409
    assert db.get(CharacterProfileRow, korri_id) is not None

    fixture_id = _character(db, project_id, "CRS Fixture")
    asset_id = _image(db, project_id, "keep-me")
    approve_character_candidate(db, project_id, fixture_id, asset_id=asset_id)
    assert resolve_character(db, project_id, "CRS Fixture") is not None
    delete_profile(db, project_id, fixture_id)
    assert resolve_character(db, project_id, "CRS Fixture") is None
    assert db.get(Asset, asset_id) is not None
    assert db.get(CharacterProfileRow, fixture_id) is None


def test_approve_wrong_asset_does_not_change_canon(db: Session):
    project_id = _project(db)
    character_id = _character(db, project_id, "Mira")
    good = _image(db, project_id, "good")
    approve_character_candidate(db, project_id, character_id, asset_id=good)
    with pytest.raises(HTTPException):
        approve_character_candidate(
            db, project_id, character_id, asset_id=str(uuid.uuid4())
        )
    assert resolve_approved_reference(db, character_id, "hero_identity") == good
    assert load_persisted_crs(db, character_id)["crs_revision"] == 1


def test_four_view_enqueue_requests_native_2k_square(db: Session, monkeypatch: pytest.MonkeyPatch):
    from app.character_identity.visual_sheet import _enqueue_txt2img

    captured: dict = {}

    class FakeJob:
        id = "job-crs-2k"
        status = "queued"
        message = ""

    def fake_enqueue(_db, _project_id, body):
        captured.update(body)
        return FakeJob()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    project_id = _project(db)
    job = _enqueue_txt2img(
        db,
        project_id,
        character_id="char-crs",
        prompt="four panel sheet",
        negative_prompt="",
        tag="crs",
        role="hero_identity",
        sheet_layout="four_view",
        model_family_preference="qwen2512",
    )
    assert job.id == "job-crs-2k"
    assert captured["width"] == 2560
    assert captured["height"] == 2560
    assert captured["quality"] == "2K"
    assert captured["resolutionOrigin"] == "native"


def test_character_creator_crs_smoke(db: Session):
    """Named smoke: persist CRS, @Name resolve, Korri guard, disposable delete."""
    test_approve_persists_crs_revision_and_production_ready(db)
    test_at_name_resolver_reads_persisted_crs(db)
    test_delete_korri_guard_unregisters_fixture_keeps_library(db)
    print("PASS — CHARACTER CREATOR CRS SMOKE")


def test_qwen_without_reference_stays_txt2img():
    from app.character_identity.visual_sheet import _build_candidate_routing_plan

    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id=None,
        generator_sources={"local": {"family": "qwen2512"}, "api": None},
    )
    stage1 = plan[0]["stage1"]
    assert stage1["workflowKey"] == "qwen2512.txt2img"
    assert stage1["source_asset_id"] is None

