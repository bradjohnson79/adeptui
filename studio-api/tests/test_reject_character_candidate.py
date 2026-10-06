"""Reject deletes candidate-owned draft pixels only. Korri rev 3 / canon stay put."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity.models import CharacterReferenceAssetRow
from app.character_identity.visual_sheet import _save_pack, reject_visual_sheet_candidate
from app.db import Asset, Base, Project


CANON_ID = "b6ab91dd-0000-4000-8000-approved03"
DRAFT_ID = "c0ffeeee-0000-4000-8000-draft0001"
VIEW_ID = "c0ffeeee-0000-4000-8000-view00001"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.config import settings

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
    session.add(Project(id="proj-sheet", name="Reject CRS"))
    session.commit()
    yield session
    session.close()


def _png(path: Path) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)


def test_reject_deletes_candidate_owned_only_korri_rev3_untouched(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    approved = tmp_path / "approved.png"
    draft = tmp_path / "character_sheet_korri_c2_draft.png"
    view = tmp_path / "character_sheet_korri_c2_view.png"
    _png(approved)
    _png(draft)
    _png(view)

    db.add(Asset(id=CANON_ID, project_id="proj-sheet", tag="korri_approved_sheet", kind="image", filename="approved.png", path=str(approved)))
    db.add(Asset(
        id=DRAFT_ID,
        project_id="proj-sheet",
        tag="character_sheet",
        kind="image",
        filename="character_sheet_korri_c2_draft.png",
        path=str(draft),
        labels_json=json.dumps(["character_sheet", "composed", "candidate_2"]),
    ))
    db.add(Asset(
        id=VIEW_ID,
        project_id="proj-sheet",
        tag="character_sheet",
        kind="image",
        filename="character_sheet_korri_c2_view.png",
        path=str(view),
        labels_json=json.dumps(["character_sheet", "candidate_2"]),
    ))
    db.add(
        CharacterReferenceAssetRow(
            id="c49371ed-0000-4000-8000-ref00001",
            character_profile_id=profile.id,
            asset_id=CANON_ID,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()

    pack = {
        "schema_version": 2,
        "status": "READY_FOR_OWNER",
        "characterId": profile.id,
        "projectId": "proj-sheet",
        "candidates": [
            {
                "id": "cand-draft",
                "sheetAssetId": DRAFT_ID,
                "assetId": DRAFT_ID,
                "status": "done",
                "viewJobs": [{"assetId": VIEW_ID}],
            }
        ],
        "previousCandidates": [],
        "roleAssets": {"hero_identity": CANON_ID},
        "approvedHeroIdentity": CANON_ID,
        "crsRevision": 3,
    }
    _save_pack(db, "proj-sheet", profile.id, pack)
    db.commit()

    approved_before = service.resolve_approved_reference(db, profile.id, "hero_identity")
    assert approved_before == CANON_ID

    result = reject_visual_sheet_candidate(db, "proj-sheet", profile.id, asset_id=DRAFT_ID)

    assert result["ok"] is True
    leftover = {row.id for row in db.query(Asset).all()}
    assert CANON_ID in leftover
    assert DRAFT_ID not in leftover
    assert VIEW_ID not in leftover
    assert not draft.exists()
    assert approved.exists()

    pack_after = result["pack"]
    assert pack_after.get("approvedHeroIdentity") == CANON_ID
    assert pack_after.get("crsRevision") == 3
    assert pack_after.get("candidates") == []
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") == CANON_ID
    canon = db.get(Asset, CANON_ID)
    assert canon is not None
    assert canon.id == CANON_ID
    leftover_ids = {str(item.get("sheetAssetId") or item.get("assetId") or "") for item in (pack_after.get("previousCandidates") or [])}
    assert DRAFT_ID not in leftover_ids
    assert VIEW_ID not in leftover_ids


def test_reject_deletes_pack_listed_imagegen_candidate(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    approved = tmp_path / "approved.png"
    draft = tmp_path / "imagegen_edit_flux_draft.png"
    _png(approved)
    _png(draft)
    flux_id = "e0a9d984-0000-4000-8000-flux0001"
    db.add(Asset(id=CANON_ID, project_id="proj-sheet", tag="korri_approved_sheet", kind="image", filename="approved.png", path=str(approved)))
    db.add(Asset(
        id=flux_id,
        project_id="proj-sheet",
        tag="imagegen",
        kind="image",
        filename="imagegen_edit_flux_draft.png",
        path=str(draft),
        labels_json=json.dumps(["imagegen"]),
    ))
    db.add(
        CharacterReferenceAssetRow(
            id="c49371ed-0000-4000-8000-ref00004",
            character_profile_id=profile.id,
            asset_id=CANON_ID,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()
    _save_pack(db, "proj-sheet", profile.id, {
        "candidates": [{"sheetAssetId": flux_id, "assetId": flux_id, "status": "done", "workflowKey": "flux.txt2img"}],
        "previousCandidates": [],
        "approvedHeroIdentity": CANON_ID,
        "roleAssets": {"hero_identity": CANON_ID},
        "crsRevision": 3,
    })
    result = reject_visual_sheet_candidate(db, "proj-sheet", profile.id, asset_id=flux_id)
    assert result["ok"] is True
    assert flux_id in result["rejectedAssetIds"]
    assert db.get(Asset, flux_id) is None
    assert db.get(Asset, CANON_ID) is not None
    assert not draft.exists()
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") == CANON_ID


def test_reject_dismisses_execution_and_keeps_canon(db, tmp_path):
    from app.codirector.execution.contracts import ChildJobStatus, ChildJobView, ExecutionPlan, ExecutionStatus
    from app.codirector.execution.pack_store import load_pack, save_pack

    profile = service.seed_korri_from_canon(db, "proj-sheet")
    approved = tmp_path / "approved.png"
    draft = tmp_path / "character_sheet_korri_c2_draft.png"
    _png(approved)
    _png(draft)
    db.add(Asset(id=CANON_ID, project_id="proj-sheet", tag="korri_approved_sheet", kind="image", filename="approved.png", path=str(approved)))
    db.add(Asset(
        id=DRAFT_ID,
        project_id="proj-sheet",
        tag="character_sheet",
        kind="image",
        filename="character_sheet_korri_c2_draft.png",
        path=str(draft),
        labels_json=json.dumps(["character_sheet", "composed", "candidate_2"]),
    ))
    db.add(
        CharacterReferenceAssetRow(
            id="c49371ed-0000-4000-8000-ref00003",
            character_profile_id=profile.id,
            asset_id=CANON_ID,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()
    _save_pack(db, "proj-sheet", profile.id, {
        "candidates": [{"sheetAssetId": DRAFT_ID, "assetId": DRAFT_ID, "status": "done", "jobId": "job-draft"}],
        "previousCandidates": [{"sheetAssetId": DRAFT_ID, "assetId": DRAFT_ID, "status": "done"}],
        "approvedHeroIdentity": CANON_ID,
        "roleAssets": {"hero_identity": CANON_ID},
        "crsRevision": 3,
    })
    save_pack(
        db,
        "proj-sheet",
        ExecutionPlan(
            execution_id="exec-draft",
            capability="character.generate",
            project_id="proj-sheet",
            status=ExecutionStatus.FAILED,
            result_asset_ids=[DRAFT_ID],
            child_jobs=[ChildJobView(job_id="job-draft", label="Candidate", status=ChildJobStatus.FAILED, asset_id=DRAFT_ID, error="JOB_NOT_FOUND")],
            surface_type="image_generation",
        ),
    )
    db.commit()

    result = reject_visual_sheet_candidate(db, "proj-sheet", profile.id, asset_id=DRAFT_ID)
    assert result["ok"] is True
    assert DRAFT_ID in result["rejectedAssetIds"]
    assert "exec-draft" in result["dismissedExecutionIds"]
    assert db.get(Asset, DRAFT_ID) is None
    assert db.get(Asset, CANON_ID) is not None
    dismissed = load_pack(db, "proj-sheet", "exec-draft")
    assert dismissed is not None
    assert dismissed.status == ExecutionStatus.CANCELLED
    assert dismissed.error == "DISMISSED"
    pack_after = result["pack"]
    assert pack_after.get("approvedHeroIdentity") == CANON_ID
    assert pack_after.get("crsRevision") == 3
    leftover_ids = {
        str(item.get("sheetAssetId") or item.get("assetId") or "")
        for item in list(pack_after.get("candidates") or []) + list(pack_after.get("previousCandidates") or [])
    }
    assert DRAFT_ID not in leftover_ids


def test_reject_refuses_approved_hero_and_keeps_candidate(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    approved = tmp_path / "approved.png"
    _png(approved)
    db.add(Asset(id=CANON_ID, project_id="proj-sheet", tag="korri_approved_sheet", kind="image", filename="approved.png", path=str(approved)))
    db.add(
        CharacterReferenceAssetRow(
            id="c49371ed-0000-4000-8000-ref00002",
            character_profile_id=profile.id,
            asset_id=CANON_ID,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()
    pack = {
        "candidates": [{"sheetAssetId": CANON_ID, "assetId": CANON_ID, "status": "done"}],
        "previousCandidates": [],
        "approvedHeroIdentity": CANON_ID,
        "roleAssets": {"hero_identity": CANON_ID},
        "crsRevision": 3,
    }
    _save_pack(db, "proj-sheet", profile.id, pack)
    db.commit()

    with pytest.raises(ValueError, match="approved or canonical"):
        reject_visual_sheet_candidate(db, "proj-sheet", profile.id, asset_id=CANON_ID)

    from app.character_identity.visual_sheet import _load_pack_raw

    kept = _load_pack_raw(db, profile.id)
    assert kept.get("candidates")
    assert kept["candidates"][0]["sheetAssetId"] == CANON_ID
    assert db.get(Asset, CANON_ID) is not None
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") == CANON_ID
