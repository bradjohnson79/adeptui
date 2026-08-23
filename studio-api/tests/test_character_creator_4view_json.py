"""Character Creator 4-view + JSON + Production Canon Approval Law."""

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
from app.character_identity.crs_schema import FOUR_VIEW_REQUIRED_VIEWS, LAW_REQUIRED_VIEWS
from app.character_identity.crs_service import get_character_json
from app.character_identity.four_view_sheet import (
    REQUIRED_VIEWS,
    apply_layout_assessment_to_candidate,
    assess_four_view_layout,
)
from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.visual_sheet import (
    CANDIDATE_SHEET_VIEW_ROLES,
    FIVE_VIEW_LAW_ROLES,
    _hydrate_candidate_layout,
    _save_pack,
    heal_pack_references,
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
    session.add(Project(id="proj-4view", name="4-View Fixture"))
    session.commit()
    yield session
    session.close()


def _disposable(db, name: str = "CC 4View Eng"):
    return service.create_profile(
        db,
        "proj-4view",
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
            project_id="proj-4view",
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


def test_four_view_contract_and_isolated_five_view_law(db, monkeypatch):
    captured = _enqueue_spy(monkeypatch)
    profile = _disposable(db)
    pack = start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
        required_views=list(FOUR_VIEW_REQUIRED_VIEWS),
    )
    views = pack["jobs"]["hero"]["viewJobs"]
    assert [v.get("canonicalView") for v in views] == ["front_full"]
    assert "full_body_three_quarter_front" not in [v["role"] for v in views]
    assert pack["identityPacket"]["requiredViews"] == ["front_full"]
    assert "three_quarter_full" in LAW_REQUIRED_VIEWS
    assert "full_body_three_quarter_front" in FIVE_VIEW_LAW_ROLES
    assert "full_body_three_quarter" not in REQUIRED_VIEWS
    assert len(captured) == 1
    assert pack.get("candidates")
    for body in captured:
        ctx = body.get("creativeContext") if isinstance(body.get("creativeContext"), dict) else {}
        assert ctx.get("fourViewPackTile") is not True
        assert body.get("fourViewSingleOutput") is False
    from app.character_identity.crs_service import load_persisted_crs

    assert load_persisted_crs(db, profile.id) == {}


def test_generate_does_not_persist_crs(db, monkeypatch):
    _enqueue_spy(monkeypatch)
    profile = _disposable(db, "Draft Only")
    start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
    )
    from app.character_identity.crs_service import load_persisted_crs

    assert load_persisted_crs(db, profile.id) == {}
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") is None


def test_production_canon_approval_law_refuses_missing_owner_confirmed(db):
    profile = _disposable(db, "Existing Canon")
    first = _png(db, "canon-a")
    service.approve_character_candidate(
        db, "proj-4view", profile.id, asset_id=first, source_type="generation"
    )
    from app.character_identity.crs_service import load_persisted_crs

    assert load_persisted_crs(db, profile.id).get("crs_revision") == 1
    replacement = _png(db, "canon-b")
    with pytest.raises(HTTPException) as exc:
        service.approve_character_candidate(
            db,
            "proj-4view",
            profile.id,
            asset_id=replacement,
            source_type="generation",
            owner_confirmed=False,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PRODUCTION_CANON_PROTECTED"
    assert load_persisted_crs(db, profile.id)["approved_sheet_asset_id"] == first


def test_owner_confirmed_can_replace_persist_on_disposable(db):
    profile = _disposable(db, "Owner Replace")
    first = _png(db, "first-sheet")
    service.approve_character_candidate(
        db, "proj-4view", profile.id, asset_id=first, source_type="generation"
    )
    second = _png(db, "second-sheet")
    result = service.approve_character_candidate(
        db,
        "proj-4view",
        profile.id,
        asset_id=second,
        source_type="generation",
        owner_confirmed=True,
    )
    assert result["crsRevision"] == 2
    assert result["approvedSheetAssetId"] == second


def test_reject_is_idempotent_when_already_gone(db):
    profile = _disposable(db, "Reject Gone")
    first = reject_visual_sheet_candidate(
        db, "proj-4view", profile.id, asset_id="missing-draft"
    )
    assert first["ok"] is True
    assert first["alreadyGone"] is True
    second = reject_visual_sheet_candidate(
        db, "proj-4view", profile.id, asset_id="missing-draft"
    )
    assert second["ok"] is True
    assert second["alreadyGone"] is True


def test_character_json_from_profile_and_approved_sheet(db):
    profile = _disposable(db, "Json Char")
    empty = get_character_json(db, "proj-4view", profile.id)
    assert empty is not None
    assert empty["name"] == "Json Char"
    assert empty["approvedSheetAssetId"] in (None, "")
    assert set(empty["views"]) == {"front", "side", "back", "closeup"}
    sheet = _png(db, "json-sheet")
    service.approve_character_candidate(
        db, "proj-4view", profile.id, asset_id=sheet, source_type="generation", owner_confirmed=True
    )
    payload = get_character_json(db, "proj-4view", profile.id)
    assert payload["approvedSheetAssetId"] == sheet
    assert payload["crsRevision"] == 1
    assert payload["views"]["front"]["label"] == "Front"
    assert payload["views"]["closeup"]["label"] == "Head/Neck Close-Up"
    assert payload["identityPacket"]["requiredViews"] == list(FOUR_VIEW_REQUIRED_VIEWS)
    assert payload["canon"]["name"] == "Json Char"


def test_double_approve_same_sheet_does_not_increment(db):
    profile = _disposable(db, "Double Approve")
    sheet = _png(db, "same-sheet")
    first = service.approve_character_candidate(
        db, "proj-4view", profile.id, asset_id=sheet, source_type="generation"
    )
    second = service.approve_character_candidate(
        db,
        "proj-4view",
        profile.id,
        asset_id=sheet,
        source_type="generation",
        owner_confirmed=True,
    )
    assert first["crsRevision"] == 1
    assert second["crsRevision"] == 1
    from app.character_identity.crs_service import load_persisted_crs

    assert load_persisted_crs(db, profile.id)["crs_revision"] == 1


def test_generate_while_live_returns_existing_pack(db, monkeypatch):
    captured = _enqueue_spy(monkeypatch)
    profile = _disposable(db, "Live Pack")
    first = start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    first_ids = [v["jobId"] for v in first["jobs"]["hero"]["viewJobs"]]
    second = start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    second_ids = [v["jobId"] for v in second["jobs"]["hero"]["viewJobs"]]
    assert second_ids == first_ids
    assert len(captured) == 1
    from app.db import Job

    for jid in first_ids:
        assert db.get(Job, jid).status == "queued"


def test_double_generate_cancels_prior_draft_jobs_and_does_not_persist(db, monkeypatch):
    captured = _enqueue_spy(monkeypatch)
    profile = _disposable(db, "Double Generate")
    first = start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    first_ids = [v["jobId"] for v in first["jobs"]["hero"]["viewJobs"]]
    assert len(first_ids) == 1
    from app.character_identity.visual_sheet import _load_pack_raw, _save_pack
    from app.db import Job

    failed_pack = _load_pack_raw(db, profile.id) or {}
    failed_pack["status"] = "FAILED"
    _save_pack(db, "proj-4view", profile.id, failed_pack)
    second = start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    second_ids = [v["jobId"] for v in second["jobs"]["hero"]["viewJobs"]]
    assert len(captured) == 2
    assert first_ids != second_ids
    from app.db import Job
    from app.character_identity.crs_service import load_persisted_crs

    for jid in first_ids:
        job = db.get(Job, jid)
        assert job is not None
        assert job.status == "cancelled"
        assert "REPLACED_BY_REGENERATE" in (job.message or "")
    assert load_persisted_crs(db, profile.id) == {}


def test_approve_unknown_asset_does_not_create_canon(db):
    profile = _disposable(db, "Stale Candidate")
    with pytest.raises(Exception):
        service.approve_character_candidate(
            db,
            "proj-4view",
            profile.id,
            asset_id=str(uuid.uuid4()),
            source_type="generation",
        )
    from app.character_identity.crs_service import load_persisted_crs

    assert load_persisted_crs(db, profile.id) == {}


def test_reject_does_not_mutate_persist_revision(db):
    profile = _disposable(db, "Reject Protect")
    canon = _png(db, "canon-keep")
    service.approve_character_candidate(
        db, "proj-4view", profile.id, asset_id=canon, source_type="generation"
    )
    from app.character_identity.crs_service import load_persisted_crs

    before = load_persisted_crs(db, profile.id)
    gone = reject_visual_sheet_candidate(
        db, "proj-4view", profile.id, asset_id="missing-draft"
    )
    assert gone["alreadyGone"] is True
    after = load_persisted_crs(db, profile.id)
    assert after["crs_revision"] == before["crs_revision"]
    assert after["approved_sheet_asset_id"] == canon


def test_first_disposable_approve_allowed_without_owner_confirmed(db):
    profile = _disposable(db, "First Approve")
    sheet = _png(db, "first-ok")
    result = service.approve_character_candidate(
        db, "proj-4view", profile.id, asset_id=sheet, source_type="generation"
    )
    assert result["crsRevision"] == 1
    assert result["approvedSheetAssetId"] == sheet


def test_hydrate_preserves_composed_four_view_verdict(db):
    from PIL import Image

    path = settings.data_dir + "/composed-4view.png"
    Image.new("RGB", (2048, 2048), (28, 28, 28)).save(path)
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id="proj-4view",
            tag="composed-4view",
            kind="image",
            filename="composed-4view.png",
            path=path,
            labels_json="[]",
        )
    )
    db.commit()
    item = {
        "sheetAssetId": aid,
        "layout": "four_view",
        "fourViewSingleOutput": False,
        "viewJobs": [{"role": "front"}, {"role": "side"}, {"role": "back"}, {"role": "closeup"}],
        "status": "done",
    }
    apply_layout_assessment_to_candidate(
        item, assess_four_view_layout(path, view_count=4, composed=True)
    )
    assert item["layoutVerified"] is True
    _hydrate_candidate_layout(db, item)
    assert item["layoutVerified"] is True
    assert str(item["layoutAssessment"]["note"]).startswith("verified_composed")


def test_hydrate_skips_tiles_before_compose(db):
    item = {
        "assetId": _png(db, "front-tile"),
        "sheetAssetId": None,
        "viewJobs": [{"role": "a"}, {"role": "b"}, {"role": "c"}, {"role": "d"}],
        "layoutNoncompliant": None,
    }
    assert _hydrate_candidate_layout(db, item) is False
    assert item.get("layoutVerified") in (None, False)


def test_reject_first_draft_when_pack_hero_points_at_draft(db):
    profile = _disposable(db, "Draft Hero Ptr")
    draft = _png(db, "draft-as-hero")
    pack = {
        "schema_version": 2,
        "status": "READY_FOR_OWNER",
        "characterId": profile.id,
        "projectId": "proj-4view",
        "candidates": [
            {
                "id": "cand-draft",
                "sheetAssetId": draft,
                "assetId": draft,
                "status": "done",
                "layout": "four_view",
            }
        ],
        "previousCandidates": [],
        "roleAssets": {"hero_identity": draft},
        "phase": "sheet_ready",
    }
    _save_pack(db, "proj-4view", profile.id, pack)
    result = reject_visual_sheet_candidate(db, "proj-4view", profile.id, asset_id=draft)
    assert result["ok"] is True
    assert result.get("alreadyGone") is not True
    after = result["pack"] or {}
    leftover = {str(c.get("sheetAssetId") or c.get("assetId") or "") for c in (after.get("candidates") or [])}
    assert draft not in leftover
    assert (after.get("roleAssets") or {}).get("hero_identity") != draft
    from app.character_identity.crs_service import load_persisted_crs

    assert load_persisted_crs(db, profile.id) == {}


def test_heal_pack_references_skips_unapproved_draft_hero(db):
    from app.character_identity.models import CharacterReferenceAssetRow

    profile = _disposable(db, "Heal Draft")
    draft = _png(db, "heal-draft-hero")
    _save_pack(
        db,
        "proj-4view",
        profile.id,
        {
            "schema_version": 2,
            "status": "READY_FOR_OWNER",
            "characterId": profile.id,
            "roleAssets": {"hero_identity": draft},
            "candidates": [{"sheetAssetId": draft, "status": "done"}],
        },
    )
    assert heal_pack_references(db, "proj-4view", profile.id) == 0
    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == profile.id)
        .all()
    )
    assert rows == []


def test_generate_does_not_inject_korri_name_lock(db, monkeypatch):
    _enqueue_spy(monkeypatch)
    profile = _disposable(db, "Korri")
    pack = start_visual_sheet_generation(
        db,
        "proj-4view",
        profile.id,
        generator_sources={"local": {"model": "flux"}, "api": None},
        layout="four_view",
    )
    assert pack.get("identityLock") in ("", None)
    assert "LOCKED IDENTITY" not in json.dumps(pack)
