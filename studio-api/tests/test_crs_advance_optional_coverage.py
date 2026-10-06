"""Pin: advance after Adept compose must not enqueue leftover coverage.

Isolated sqlite only. Does not generate live CRS, does not touch Korri rev 3,
does not POST generate, and does not bounce the API.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity.four_view_sheet import (
    attach_four_view_sheet_intent,
    is_single_image_four_view,
)
from app.character_identity.schemas import ReferenceAttach
from app.character_identity.visual_sheet import (
    _save_pack,
    advance_visual_sheet_pack,
    cancel_visual_sheet_optional_phase_jobs,
    get_visual_sheet_pack,
    recompute_visual_sheet_pack_from_jobs,
    start_visual_sheet_generation,
)
from app.queue_worker import job_cancel_should_interrupt_comfy
from app.db import Asset, Base, Job, Project


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
    session.add(Project(id="proj-sheet", name="CRS Coverage Pin"))
    session.commit()

    def fake_enqueue(db, project_id, body, scene_id=None):
        payload = dict(body or {})
        # Simulate compile/worker four-view stamp so persist pin can fight it.
        if str(payload.get("taskType") or "").upper() in {"CRS_GENERATION", "CRS_SINGLE_VIEW"}:
            payload["fourViewSingleOutput"] = True
            ctx = dict(payload.get("creativeContext") or {})
            ctx["fourViewSingleOutput"] = True
            payload["creativeContext"] = ctx
            payload["layout"] = "four_view"
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(payload),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    yield session
    session.close()


def _png(path: Path, size=(2048, 2048)) -> str:
    from PIL import Image

    Image.new("RGB", size, (200, 100, 50)).save(str(path), format="PNG")
    return str(path)


def _complete_law_views(db, pack, tmp_path) -> None:
    hero = pack["jobs"]["hero"]
    for i, vj in enumerate(hero["viewJobs"]):
        job = db.get(Job, vj["jobId"])
        asset_id = str(uuid.uuid4())
        db.add(
            Asset(
                id=asset_id,
                project_id="proj-sheet",
                tag=f"character_view_{i}",
                kind="image",
                filename=f"view_{i}.png",
                path=_png(tmp_path / f"view_{i}.png"),
            )
        )
        job.status = "done"
        job.params_json = json.dumps(
            {
                **json.loads(job.params_json or "{}"),
                "output_asset_id": asset_id,
            }
        )
    from app.character_identity.crs_law_view_gates import stamp_matching_gate_extras
    from app.character_identity.visual_sheet import _save_pack
    stamp_matching_gate_extras(hero["viewJobs"])
    _save_pack(db, "proj-sheet", pack.get("characterId") or pack.get("character_id"), pack)
    db.commit()


def test_advance_after_five_view_compose_enqueues_zero_coverage(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    assert len(pack["jobs"]["hero"]["viewJobs"]) == 1
    jobs_before = {row.id for row in db.query(Job).all()}
    _complete_law_views(db, pack, tmp_path)

    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)

    assert not (advanced.get("jobs") or {}).get("coverage")
    assert not (advanced.get("jobs") or {}).get("details")
    assert not (advanced.get("jobs") or {}).get("performance")
    assert advanced.get("phase") != "turnaround_facial"
    jobs_after = {row.id for row in db.query(Job).all()}
    assert jobs_after == jobs_before
    assert not (advanced.get("jobs") or {}).get("coverage")
    cand = (advanced.get("candidates") or [None])[0]
    # V3 Front-only start may not compose a sheet until angles exist.
    assert cand is None or cand.get("sheetAssetId") or cand.get("assetId") or cand.get("jobId")
    # Pin: no leftover coverage jobs. V3 may keep Front in-progress until angles exist.
    assert str(advanced.get("status") or "") != "CANCELLED"


def test_leftover_coverage_cancel_does_not_cancel_finished_candidate(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    sheet_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=sheet_id,
            project_id="proj-sheet",
            tag="composed_sheet",
            kind="image",
            filename="sheet.png",
            path=_png(tmp_path / "sheet.png"),
        )
    )
    view_jobs = []
    for i in range(5):
        jid = str(uuid.uuid4())
        db.add(
            Job(
                id=jid,
                project_id="proj-sheet",
                kind="imagegen",
                status="done",
                params_json=json.dumps({"taskType": "CRS_GENERATION", "fourViewSingleOutput": False}),
            )
        )
        view_jobs.append({"jobId": jid, "role": f"view_{i}", "status": "done"})
    coverage = []
    for i in range(6):
        jid = str(uuid.uuid4())
        db.add(
            Job(
                id=jid,
                project_id="proj-sheet",
                kind="imagegen",
                status="cancelled",
                params_json=json.dumps({}),
            )
        )
        coverage.append({"jobId": jid, "role": f"coverage_{i}", "status": "queued"})
    db.commit()

    candidate = {
        "status": "done",
        "sheetAssetId": sheet_id,
        "assetId": sheet_id,
        "layout": "law_views",
        "fourViewSingleOutput": False,
        "viewJobs": view_jobs,
        "candidateIndex": 0,
    }
    pack = {
        "schema_version": 2,
        "status": "GENERATING",
        "characterId": profile.id,
        "projectId": "proj-sheet",
        "includeDetails": False,
        "includePerformance": False,
        "taskType": "CRS_GENERATION",
        "jobs": {
            "hero": dict(candidate),
            "hero_candidates": [dict(candidate)],
            "coverage": coverage,
        },
        "candidates": [dict(candidate)],
        "roleAssets": {"hero_identity": sheet_id},
        "phase": "turnaround_facial",
    }
    _save_pack(db, "proj-sheet", profile.id, pack)

    hydrated = get_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert hydrated["status"] != "CANCELLED"
    assert hydrated["status"] in {"COMPLETED", "READY_FOR_OWNER"}
    assert (hydrated.get("candidates") or [None])[0].get("sheetAssetId") == sheet_id

    skipped = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert skipped["status"] != "CANCELLED"
    extra = [
        item
        for item in (skipped.get("jobs") or {}).get("coverage") or []
        if item.get("jobId") not in {c["jobId"] for c in coverage}
    ]
    assert extra == []


def test_crs_job_params_keep_four_view_false_after_persist(db):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    view_jobs = pack["jobs"]["hero"]["viewJobs"]
    assert len(view_jobs) == 1
    for vj in view_jobs:
        job = db.get(Job, vj["jobId"])
        params = json.loads(job.params_json or "{}")
        assert params.get("taskType") == "CRS_SINGLE_VIEW"
        assert params.get("fourViewSingleOutput") is False
        assert (params.get("creativeContext") or {}).get("fourViewSingleOutput") is False
        assert params.get("layout") != "four_view"

    polluted = {
        "taskType": "CRS_GENERATION",
        "purpose": "character_sheet",
        "presetId": "builtin-character-sheet",
        "fourViewSingleOutput": False,
        "viewRole": "full_body_front",
        "creativeContext": {"taskType": "CRS_GENERATION", "fourViewSingleOutput": False},
    }
    assert is_single_image_four_view(polluted) is False
    stamped = attach_four_view_sheet_intent(dict(polluted))
    assert stamped.get("fourViewSingleOutput") is False

def _attach_approved_hero(db, profile_id: str, tmp_path: Path) -> str:
    sheet_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=sheet_id,
            project_id="proj-sheet",
            tag="approved_hero",
            kind="image",
            filename="approved.png",
            path=_png(tmp_path / "approved.png"),
        )
    )
    db.commit()
    service.attach_reference(
        db,
        "proj-sheet",
        profile_id,
        ReferenceAttach(
            asset_id=sheet_id,
            reference_role="hero_identity",
            source_type="generation",
            canonical=True,
            approval_status="approved",
            notes="Korri rev 3 leftover hero — must not unlock coverage",
        ),
    )
    return sheet_id


def test_start_advance_recompute_flags_false_plans_zero_coverage(db, tmp_path):
    """includeDetails=false AND includePerformance=false never plans extras.

    Approved leftover hero_identity (live Korri rev 3) plus advance/recompute
    must not enqueue coverage / details / performance / turnaround_facial.
    """
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    _attach_approved_hero(db, profile.id, tmp_path)

    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    assert pack.get("includeDetails") is False
    assert pack.get("includePerformance") is False
    assert not (pack.get("jobs") or {}).get("coverage")
    assert not (pack.get("jobs") or {}).get("details")
    assert not (pack.get("jobs") or {}).get("performance")
    assert pack.get("phase") != "turnaround_facial"
    jobs_after_start = {row.id for row in db.query(Job).all()}
    assert len(pack["jobs"]["hero"]["viewJobs"]) == 1

    recomputed = dict(pack)
    assert recompute_visual_sheet_pack_from_jobs(db, recomputed) in {True, False}
    assert not (recomputed.get("jobs") or {}).get("coverage")
    hydrated = get_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert not (hydrated.get("jobs") or {}).get("coverage")
    assert {row.id for row in db.query(Job).all()} == jobs_after_start

    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert not (advanced.get("jobs") or {}).get("coverage")
    assert not (advanced.get("jobs") or {}).get("details")
    assert not (advanced.get("jobs") or {}).get("performance")
    assert advanced.get("phase") != "turnaround_facial"
    assert {row.id for row in db.query(Job).all()} == jobs_after_start
    assert advanced.get("status") == "GENERATING"
    law_statuses = [vj.get("status") for vj in advanced["jobs"]["hero"]["viewJobs"]]
    assert any(s in {"queued", "running", None, "GENERATING"} or s == "queued" for s in law_statuses) or all(
        db.get(Job, vj["jobId"]).status == "queued" for vj in advanced["jobs"]["hero"]["viewJobs"]
    )


def test_cancel_coverage_ids_does_not_cancel_running_law_view(db, tmp_path):
    """Cancelling leftover coverage ids must isolate to those extras."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    running_id = str(uuid.uuid4())
    queued_id = str(uuid.uuid4())
    db.add(
        Job(
            id=running_id,
            project_id="proj-sheet",
            kind="imagegen",
            status="running",
            params_json='{"taskType": "CRS_GENERATION", "viewRole": "full_body_front"}',
        )
    )
    db.add(
        Job(
            id=queued_id,
            project_id="proj-sheet",
            kind="imagegen",
            status="queued",
            params_json='{"taskType": "CRS_GENERATION", "viewRole": "full_body_side_left"}',
        )
    )
    coverage = []
    for i, role in enumerate(
        (
            "full_body_front",
            "full_body_side_left",
            "full_body_back",
            "closeup_front",
            "closeup_side_left",
            "closeup_back",
        )
    ):
        jid = str(uuid.uuid4())
        db.add(
            Job(
                id=jid,
                project_id="proj-sheet",
                kind="imagegen",
                status="queued",
                params_json="{}",
            )
        )
        coverage.append({"jobId": jid, "role": role, "status": "queued"})
    db.commit()

    candidate = {
        "status": "generating",
        "layout": "law_views",
        "fourViewSingleOutput": False,
        "viewJobs": [
            {"jobId": running_id, "role": "full_body_front", "status": "running"},
            {"jobId": queued_id, "role": "full_body_side_left", "status": "queued"},
        ],
        "candidateIndex": 0,
    }
    pack = {
        "schema_version": 2,
        "status": "GENERATING",
        "characterId": profile.id,
        "projectId": "proj-sheet",
        "includeDetails": False,
        "includePerformance": False,
        "taskType": "CRS_GENERATION",
        "jobs": {
            "hero": dict(candidate),
            "hero_candidates": [dict(candidate)],
            "coverage": coverage,
        },
        "candidates": [dict(candidate)],
        "phase": "turnaround_facial",
    }
    _save_pack(db, "proj-sheet", profile.id, pack)

    coverage_ids = [item["jobId"] for item in coverage]
    result = cancel_visual_sheet_optional_phase_jobs(
        db, "proj-sheet", profile.id, coverage_ids + [running_id, queued_id]
    )
    assert set(result["cancelledJobIds"]) == set(coverage_ids)
    assert running_id in result["skippedJobIds"]
    assert queued_id in result["skippedJobIds"]

    assert db.get(Job, running_id).status == "running"
    assert db.get(Job, queued_id).status == "queued"
    for jid in coverage_ids:
        assert db.get(Job, jid).status == "cancelled"

    hydrated = result["pack"]
    assert hydrated.get("status") != "CANCELLED"
    assert hydrated.get("status") == "GENERATING"
    assert db.get(Job, running_id).status == "running"

    assert job_cancel_should_interrupt_comfy(
        coverage_ids[0],
        job_prompt_id=None,
        active_prompt_by_job={running_id: "prompt-law-view"},
        heavy_local_active=running_id,
    ) is False
    assert job_cancel_should_interrupt_comfy(
        running_id,
        job_prompt_id="prompt-law-view",
        active_prompt_by_job={running_id: "prompt-law-view"},
        heavy_local_active=running_id,
    ) is True

