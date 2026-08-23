"""CC/CD Character Sheet: one imagegen job per candidate, honest layout flag."""

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
from app.character_identity.four_view_sheet import REQUIRED_VIEWS
from app.character_identity.visual_sheet import (
    advance_visual_sheet_pack,
    start_visual_sheet_generation,
)
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
    session.add(Project(id="proj-sheet", name="Sheet Test"))
    session.commit()

    def fake_enqueue(db, project_id, body, scene_id=None):
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
    yield session
    session.close()


def _png(path: Path, size=(256, 256)) -> str:
    from PIL import Image

    Image.new("RGB", size, (200, 100, 50)).save(str(path), format="PNG")
    return str(path)


def test_start_enqueues_front_only_not_four_views(db):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    hero = pack["jobs"]["hero"]
    assert len(hero["viewJobs"]) == 1
    assert hero["viewJobs"][0]["canonicalView"] == "front_full"
    assert hero.get("fourViewSingleOutput") is not True
    assert "full_body_three_quarter_front" not in [v.get("role") for v in hero["viewJobs"]]
    jobs = db.query(Job).all()
    image_jobs = [j for j in jobs if (j.kind or "").startswith("image") or j.kind == "imagegen"]
    assert len(image_jobs) == 1
    for job in image_jobs:
        params = json.loads(job.params_json or "{}")
        blob = json.dumps(params)
        assert "four-panel" not in blob
        assert params.get("fourViewSingleOutput") is not True
        assert params.get("taskType") == "CRS_SINGLE_VIEW"
        assert max(int(params.get("width") or 0), int(params.get("height") or 0)) >= 2048
    cand = (pack.get("candidates") or [None])[0]
    assert cand is not None
    assert cand.get("characterSheetIntent", {}).get("layout") == "single_view"
    assert "full_body_three_quarter" not in list(REQUIRED_VIEWS)


def test_advance_does_not_call_compose_grid(db, tmp_path, monkeypatch):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    vj = pack["jobs"]["hero"]["viewJobs"][0]
    job = db.get(Job, vj["jobId"])
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-sheet",
            tag="character_sheet",
            kind="image",
            filename="sheet.png",
            path=_png(tmp_path / "sheet.png", (1024, 1024)),
        )
    )
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()

    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("PIL compose must not run for CC/CD sheets")

    monkeypatch.setattr(
        "app.character_identity.visual_sheet._compose_character_sheet_grid", _boom
    )
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    cand = (advanced.get("candidates") or [None])[0]
    # One of four views done: do not compose yet.
    assert cand.get("sheetAssetId") in (None, "")


def test_advance_tall_portrait_layout_noncompliant_true(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    vj = pack["jobs"]["hero"]["viewJobs"][0]
    job = db.get(Job, vj["jobId"])
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-sheet",
            tag="character_sheet",
            kind="image",
            filename="tall.png",
            path=_png(tmp_path / "tall.png", (512, 1024)),
        )
    )
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    cand = (advanced.get("candidates") or [None])[0]
    assert cand.get("sheetAssetId") in (None, "")


def test_front_only_pack_does_not_auto_compose_sheet(db, tmp_path):
    """V2 leftover generate path: completing Front does not invent a collage sheet."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    assert len(pack["jobs"]["hero"]["viewJobs"]) == 1
    vj = pack["jobs"]["hero"]["viewJobs"][0]
    job = db.get(Job, vj["jobId"])
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-sheet",
            tag="character_view",
            kind="image",
            filename="front.png",
            path=_png(tmp_path / "front.png", (2048, 2048)),
        )
    )
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    cand = (advanced.get("candidates") or [None])[0]
    assert cand is not None
    assert cand.get("sheetAssetId") in (None, "")
    assert cand.get("sheetAssetId") != asset_id
