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
    yield session
    session.close()


def _png(path: Path, size=(256, 256)) -> str:
    from PIL import Image

    Image.new("RGB", size, (200, 100, 50)).save(str(path), format="PNG")
    return str(path)


def test_start_enqueues_one_job_per_candidate_not_four_tiles(db):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    hero = pack["jobs"]["hero"]
    assert len(hero["viewJobs"]) == 1
    assert hero.get("fourViewSingleOutput") is True
    jobs = db.query(Job).all()
    image_jobs = [j for j in jobs if (j.kind or "").startswith("image") or j.kind == "imagegen"]
    assert len(image_jobs) == 1
    job = image_jobs[0]
    params = json.loads(job.params_json or "{}")
    intent = params.get("imageIntent") or {}
    meta = intent.get("metadata") or {}
    blob = json.dumps(params)
    assert "four_view" in blob
    assert meta.get("layout") == "four_view" or params.get("layout") == "four_view"
    assert list(params.get("requiredViews") or meta.get("requiredViews") or hero.get("requiredViews")) == list(
        REQUIRED_VIEWS
    )
    cand = (pack.get("candidates") or [None])[0]
    assert cand is not None
    assert "layoutNoncompliant" in cand
    assert cand.get("characterSheetIntent", {}).get("layout") == "four_view"


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
    assert called["n"] == 0
    cand = (advanced.get("candidates") or [None])[0]
    assert cand["assetId"] == asset_id
    assert "layoutNoncompliant" in cand
    assert cand.get("layoutNoncompliant") is False
    assert cand.get("layoutVerified") is False
    assert cand.get("fourViewSingleOutput") is True


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
    assert cand["layoutNoncompliant"] is True
    assert cand.get("layout_noncompliant") is True
    assert cand.get("sheetAssetId") == asset_id
    assert cand.get("assetId") == asset_id
    assert cand["status"] == "done"


def test_get_recomputes_stale_square_layout_flag(db, tmp_path):
    """GET/hydrate must flip a stale square=noncompliant stamp without generate."""
    from app.character_identity.visual_sheet import (
        _save_pack,
        get_visual_sheet_pack,
    )

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
            path=_png(tmp_path / "sheet.png", (2048, 2048)),
        )
    )
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    cand = (advanced.get("candidates") or [None])[0]
    assert cand["layoutNoncompliant"] is False

    for bucket in (
        advanced.get("candidates") or [],
        (advanced.get("jobs") or {}).get("hero_candidates") or [],
    ):
        for item in bucket:
            item["layoutNoncompliant"] = True
            item["layout_noncompliant"] = True
            item["layoutVerified"] = False
    hero = (advanced.get("jobs") or {}).get("hero")
    if isinstance(hero, dict):
        hero["layoutNoncompliant"] = True
        hero["layout_noncompliant"] = True
    _save_pack(db, "proj-sheet", profile.id, advanced)

    hydrated = get_visual_sheet_pack(db, "proj-sheet", profile.id)
    got = (hydrated.get("candidates") or [None])[0]
    assert got is not None
    assert got.get("layoutNoncompliant") is False
    assert got.get("layout_noncompliant") is False
    assert got.get("layoutVerified") is False
    assert got.get("sheetAssetId") == asset_id
