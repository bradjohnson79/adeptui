"""Character Creator final-closure regressions — no live GPU, no Schnick writes."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.character_identity import models as _ci_models  # noqa: F401
from app.codirector.execution.cancel import dismiss_leftover_execution
from app.codirector.execution.contracts import ChildJobStatus, ChildJobView, ExecutionPlan, ExecutionStatus
from app.codirector.execution.pack_store import load_pack, save_pack
from app.db import Base, Project
from app.imagegen_workflows import build_local_generator_models
from app.workflows.qwen_image_edit_2509 import discover_qwen_edit_2509


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
                conn.execute(text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-cc-close", name="CC Closure Fixture"))
    session.commit()
    yield session
    session.close()


def test_character_roster_hides_non_executable_and_auto_stays():
    roster = build_local_generator_models(surface="character")
    ids = [row["id"] for row in roster]
    assert ids[0] == "auto"
    assert "sd15" not in ids
    disc = discover_qwen_edit_2509()
    if disc.get("runtimeReady"):
        assert "qwen_edit_2509" in ids
    else:
        assert "qwen_edit_2509" not in ids
    for row in roster:
        if row["id"] == "auto":
            continue
        assert row.get("executable") is True, row
        assert row.get("readinessLabel") == "Ready"


def test_auto_family_is_executable_certified_only():
    from app.character_identity.visual_sheet import (
        CRS_AUTO_FALLBACK_FAMILY,
        CRS_AUTO_PRIMARY_FAMILY,
        _candidate_family_executable,
        _resolve_crs_auto_family,
    )

    family = _resolve_crs_auto_family()
    assert family in {CRS_AUTO_PRIMARY_FAMILY, CRS_AUTO_FALLBACK_FAMILY}
    if _candidate_family_executable(CRS_AUTO_PRIMARY_FAMILY):
        assert family == CRS_AUTO_PRIMARY_FAMILY
    else:
        assert family == CRS_AUTO_FALLBACK_FAMILY
    assert family != "qwen2512.ref"
    assert not family.endswith(".ref_edit")


def test_dismiss_leftover_missing_job_does_not_retry(db):
    execution_id = str(uuid.uuid4())
    save_pack(
        db,
        "proj-cc-close",
        ExecutionPlan(
            execution_id=execution_id,
            capability="character.generate",
            project_id="proj-cc-close",
            status=ExecutionStatus.FAILED,
            error=None,
            child_jobs=[
                ChildJobView(
                    job_id="missing-job",
                    label="Candidate",
                    status=ChildJobStatus.FAILED,
                    error="JOB_NOT_FOUND",
                )
            ],
            surface_type="image_generation",
        ),
    )
    plan = dismiss_leftover_execution(db, "proj-cc-close", execution_id)
    assert plan is not None
    assert plan.status == ExecutionStatus.CANCELLED
    assert plan.error == "DISMISSED"
    assert plan.child_jobs[0].status == ChildJobStatus.CANCELLED
    assert plan.child_jobs[0].error == "DISMISSED"
    reloaded = load_pack(db, "proj-cc-close", execution_id)
    assert reloaded is not None
    assert reloaded.status == ExecutionStatus.CANCELLED
    assert reloaded.error == "DISMISSED"


def test_approve_stamps_revision_and_previous_approved(db, tmp_path):
    from app.character_identity import service
    from app.character_identity.models import CharacterReferenceAssetRow
    from app.character_identity.visual_sheet import _load_pack_raw, _save_pack
    from app.db import Asset

    profile = service.seed_korri_from_canon(db, "proj-cc-close")
    old = tmp_path / "old.png"
    new = tmp_path / "character_sheet_new.png"
    old.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    new.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    old_id = "11111111-1111-4111-8111-111111111111"
    new_id = "22222222-2222-4222-8222-222222222222"
    db.add(Asset(id=old_id, project_id="proj-cc-close", tag="character_sheet", kind="image", filename="old.png", path=str(old), labels_json=json.dumps(["character_sheet"])))
    db.add(Asset(id=new_id, project_id="proj-cc-close", tag="character_sheet", kind="image", filename="character_sheet_new.png", path=str(new), labels_json=json.dumps(["character_sheet", "composed"])))
    db.add(
        CharacterReferenceAssetRow(
            id="33333333-3333-4333-8333-333333333333",
            character_profile_id=profile.id,
            asset_id=old_id,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    _save_pack(
        db,
        "proj-cc-close",
        profile.id,
        {
            "candidates": [{"sheetAssetId": new_id, "assetId": new_id, "status": "done"}],
            "previousCandidates": [],
            "approvedHeroIdentity": old_id,
            "roleAssets": {"hero_identity": old_id},
            "crsRevision": 3,
        },
    )
    db.commit()
    from app.character_identity.crs_service import load_persisted_crs

    before_rev = int((load_persisted_crs(db, profile.id) or {}).get("crs_revision") or 0)
    result = service.approve_character_candidate(
        db,
        "proj-cc-close",
        profile.id,
        asset_id=new_id,
        reference_role="hero_identity",
        source_type="generated",
        notes="final-closure",
        owner_confirmed=True,
    )
    assert int(result["crsRevision"]) == before_rev + 1
    assert result["approvedSheetAssetId"] == new_id
    pack = _load_pack_raw(db, profile.id)
    assert pack["approvedHeroIdentity"] == new_id
    assert int(pack["crsRevision"]) == before_rev + 1
    history_ids = {str(item.get("sheetAssetId") or item.get("assetId") or "") for item in (pack.get("previousCandidates") or [])}
    assert old_id in history_ids
    assert all(
        item.get("approved") is True or str(item.get("status") or "").lower() == "approved"
        for item in (pack.get("previousCandidates") or [])
        if old_id in {str(item.get("sheetAssetId") or ""), str(item.get("assetId") or "")}
    )
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") == new_id
