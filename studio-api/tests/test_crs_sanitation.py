"""Sanitation Phase 1 — CRS resolve and pixel-review dimensions."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.service import approve_character_candidate, create_profile
from app.codirector.entity_resolver import resolve_character
from app.codirector.vision.pixel_review import (
    PIXEL_REVIEW_DIMENSIONS,
    all_dimensions_present,
    pixel_review_instructions,
)
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
def db(monkeypatch: pytest.MonkeyPatch) -> Session:
    _apply_flags(monkeypatch)
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


def test_pixel_review_requires_all_five_dimensions() -> None:
    assert PIXEL_REVIEW_DIMENSIONS == (
        "IDENTITY",
        "PLACEMENT",
        "ENVIRONMENT",
        "PERFORMANCE",
        "CAMERA",
    )
    text = pixel_review_instructions(character_name="Korri", scene_name="Schnick Coffee")
    for dim in PIXEL_REVIEW_DIMENSIONS:
        assert dim in text
    assert all_dimensions_present(
        {
            "identity": "pass",
            "placement": "pass",
            "environment": "pass",
            "performance": "pass",
            "camera": "pass",
        }
    )
    assert not all_dimensions_present({"identity": "pass", "placement": "pass"})


def test_resolve_character_prefers_approved_asset_not_prose(db: Session) -> None:
    project_id = f"crs-san-{uuid.uuid4().hex[:8]}"
    db.merge(Project(id=project_id, name="CRS Sanitation"))
    db.commit()
    profile = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name="Korri", slug="korri", role="lead"),
    )
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="korri-crs",
            kind="image",
            filename="korri-crs.png",
            path="korri-crs.png",
        )
    )
    db.commit()
    approve_character_candidate(db, project_id, profile.id, asset_id=asset_id)
    resolved = resolve_character(db, project_id, "Korri")
    assert resolved is not None
    assert resolved["character_id"] == profile.id
    assert resolved["approved_casting_asset_id"] == asset_id
    assert resolved.get("approved_sheet_asset_id") == asset_id

def test_regenerate_does_not_destroy_approved_rev_3(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regenerate must keep approved CRS revision 3 and its asset."""
    from app.character_identity.crs_service import load_persisted_crs
    from app.character_identity.service import resolve_approved_reference
    from app.character_identity.visual_sheet import (
        _load_pack_raw,
        _save_pack,
        start_visual_sheet_generation,
    )

    project_id = f"crs-rev3-{uuid.uuid4().hex[:8]}"
    db.merge(Project(id=project_id, name="CRS Rev3 Disposable"))
    db.commit()
    profile = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name="Mira", slug="mira-rev3", role="lead"),
    )
    assets: list[str] = []
    for tag in ("rev1", "rev2", "rev3"):
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
        assets.append(aid)
        approve_character_candidate(
            db,
            project_id,
            profile.id,
            asset_id=aid,
            reference_role="hero_identity",
            owner_confirmed=True,
        )

    approved = assets[-1]
    persisted = load_persisted_crs(db, profile.id)
    assert persisted["crs_revision"] == 3
    assert persisted["approved_sheet_asset_id"] == approved
    assert resolve_approved_reference(db, profile.id, "hero_identity") == approved

    _save_pack(
        db,
        project_id,
        profile.id,
        {
            "schema_version": 2,
            "status": "OWNER_APPROVED",
            "characterId": profile.id,
            "projectId": project_id,
            "candidates": [
                {
                    "sheetAssetId": approved,
                    "assetId": approved,
                    "status": "done",
                    "revision": 3,
                    "label": "Approved",
                }
            ],
            "previousCandidates": [],
            "candidateCount": 1,
            "nextCandidateRevision": 4,
            "approvedHeroIdentity": approved,
            "crsRevision": 3,
            "roleAssets": {"hero_identity": approved},
            "jobs": {},
        },
    )

    class FakeJob:
        id = "job-crs-rev3-draft"
        status = "queued"
        message = ""

    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda *_args, **_kwargs: FakeJob(),
    )

    pack = start_visual_sheet_generation(
        db,
        project_id,
        profile.id,
        include_details=False,
        include_performance=False,
    )
    assert pack["approvedHeroIdentity"] == approved
    assert pack["roleAssets"]["hero_identity"] == approved
    history_ids = {
        str(c.get("sheetAssetId") or c.get("assetId") or "")
        for c in (pack.get("previousCandidates") or [])
    }
    assert approved in history_ids
    draft_ids = {
        str(c.get("sheetAssetId") or c.get("assetId") or "")
        for c in (pack.get("candidates") or [])
    }
    assert approved not in draft_ids or pack.get("status") == "GENERATING"

    after = load_persisted_crs(db, profile.id)
    assert after["crs_revision"] == 3
    assert after["approved_sheet_asset_id"] == approved
    assert resolve_approved_reference(db, profile.id, "hero_identity") == approved

    raw = _load_pack_raw(db, profile.id) or {}
    assert raw.get("approvedHeroIdentity") == approved
    assert resolve_character(db, project_id, "Mira")["approved_sheet_asset_id"] == approved


def test_crs_is_project_isolated(db: Session) -> None:
    """Approved CRS on project A must not resolve on project B."""
    project_a = f"crs-iso-a-{uuid.uuid4().hex[:8]}"
    project_b = f"crs-iso-b-{uuid.uuid4().hex[:8]}"
    db.merge(Project(id=project_a, name="CRS Iso A"))
    db.merge(Project(id=project_b, name="CRS Iso B"))
    db.commit()
    profile_a = create_profile(
        db, project_a, CharacterProfileCreate(name="Korri", slug="korri-iso-a", role="lead")
    )
    create_profile(
        db, project_b, CharacterProfileCreate(name="Mira", slug="mira-iso-b", role="lead")
    )
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_a,
            tag="crs-a",
            kind="image",
            filename="a.png",
            path="a.png",
        )
    )
    db.commit()
    approve_character_candidate(db, project_a, profile_a.id, asset_id=asset_id)
    resolved_a = resolve_character(db, project_a, "Korri")
    resolved_b_name = resolve_character(db, project_b, "Korri")
    resolved_b_own = resolve_character(db, project_b, "Mira")
    assert resolved_a is not None
    assert resolved_a["character_id"] == profile_a.id
    assert resolved_a["approved_sheet_asset_id"] == asset_id
    if resolved_b_name is not None:
        assert resolved_b_name["character_id"] != profile_a.id
        assert resolved_b_name.get("approved_sheet_asset_id") != asset_id
    assert resolved_b_own is None or not resolved_b_own.get("approved_sheet_asset_id")

