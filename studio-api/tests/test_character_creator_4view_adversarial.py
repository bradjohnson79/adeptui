"""Adversarial Character Creator 4-view cases — in-memory only, no Schnick writes."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity.crs_service import load_persisted_crs
from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.visual_sheet import (
    reject_visual_sheet_candidate,
    start_visual_sheet_generation,
)
from app.config import settings
from app.db import Asset, Base, Job, Project


@pytest.fixture()
def db(tmp_path, monkeypatch):
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
    session = Session()
    session.add(Project(id="proj-adv", name="4-View Adversarial"))
    session.commit()
    yield session
    session.close()


def _disposable(db, name: str):
    return service.create_profile(
        db,
        "proj-adv",
        CharacterProfileCreate(name=name, slug=name.lower().replace(" ", "-"), role="fixture"),
    )


def _png(db, tag: str) -> str:
    aid = str(uuid.uuid4())
    path = settings.data_dir + f"/{tag}.png"
    from pathlib import Path

    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    db.add(
        Asset(
            id=aid,
            project_id="proj-adv",
            tag=tag,
            kind="image",
            filename=f"{tag}.png",
            path=path,
            labels_json=json.dumps(["character_sheet", "candidate_draft"]),
        )
    )
    db.commit()
    return aid


def _enqueue_spy(monkeypatch):
    captured: list[dict] = []

    def fake_enqueue(db, project_id, body, scene_id=None):
        captured.append(dict(body or {}))
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(body or {}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    return captured


def test_approve_while_generating_unknown_asset_leaves_no_canon(db, monkeypatch):
    _enqueue_spy(monkeypatch)
    profile = _disposable(db, "Approve Running")
    start_visual_sheet_generation(
        db,
        "proj-adv",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    with pytest.raises(HTTPException):
        service.approve_character_candidate(
            db,
            "proj-adv",
            profile.id,
            asset_id=str(uuid.uuid4()),
            source_type="generation",
        )
    assert load_persisted_crs(db, profile.id) == {}


def test_rejected_draft_does_not_resurrect_as_canon(db, monkeypatch):
    _enqueue_spy(monkeypatch)
    profile = _disposable(db, "No Resurrection")
    sheet = _png(db, "doomed-draft")
    start_visual_sheet_generation(
        db,
        "proj-adv",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    reject_visual_sheet_candidate(db, "proj-adv", profile.id, asset_id=sheet)
    again = reject_visual_sheet_candidate(db, "proj-adv", profile.id, asset_id=sheet)
    assert again["alreadyGone"] is True
    assert load_persisted_crs(db, profile.id) == {}
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") is None


def test_existing_canon_refuses_api_approve_without_owner_confirmed(db):
    profile = _disposable(db, "Existing Fixture Canon")
    canon = _png(db, "fixture-canon")
    service.approve_character_candidate(
        db, "proj-adv", profile.id, asset_id=canon, source_type="generation"
    )
    replacement = _png(db, "fixture-replace")
    with pytest.raises(HTTPException) as exc:
        service.approve_character_candidate(
            db,
            "proj-adv",
            profile.id,
            asset_id=replacement,
            source_type="generation",
            owner_confirmed=False,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PRODUCTION_CANON_PROTECTED"
    assert load_persisted_crs(db, profile.id)["approved_sheet_asset_id"] == canon
