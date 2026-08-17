"""CDX-001: non-hero sheet phases honor the creator's Local/Cloud source.

Covers the pack pipeline after the hero candidate completes: coverage x6 (and
details x6 / performance x2 when enabled) must be enqueued on the SAME source
the creator selected for the hero. Cloud-only selections must never silently
enqueue local qwen2512 jobs; an unavailable selected source must fail honestly
with a typed error instead of falling back to the default local model.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.character_identity import service
from app.character_identity.visual_sheet import (
    VisualSheetSourceUnavailableError,
    advance_visual_sheet_pack,
    start_visual_sheet_generation,
)
from app.db import Asset, Base, Job, Project

# Cloud-only source using a fal dock: the fal pin path needs no API key, so the
# test proves the routing truthfully without external credentials.
CLOUD_ONLY_SOURCES = {
    "local": None,
    "api": [
        {
            "model": "krea2-turbo-fal",
            "providerId": "fal",
            "modelId": "krea-2-turbo",
            "enabled": True,
            "batchCount": 1,
        }
    ],
}


@pytest.fixture()
def db(monkeypatch):
    from app.config import settings

    # Sandbox quirk: tempfile.mkdtemp dirs get deny-ACLs. Create a writable
    # scratch dir under TMP with plain mkdir instead (junk left for outside
    # cleanup, same as the Phase-1 gate note).
    scratch_root = Path(os.environ.get("TMP") or os.environ.get("TEMP") or ".")
    scratch = scratch_root / f"phase-source-{uuid.uuid4().hex[:10]}"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "data_dir", str(scratch), raising=False)
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
    session.add(Project(id="proj-sheet", name="Sheet Source Test"))
    session.commit()
    yield session
    session.close()


def _scratch_dir() -> Path:
    root = Path(os.environ.get("TMP") or os.environ.get("TEMP") or ".")
    d = root / f"phase-src-png-{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _png(path: Path, size=(256, 256)) -> str:
    from PIL import Image

    Image.new("RGB", size, (200, 100, 50)).save(str(path), format="PNG")
    return str(path)


def _complete_hero(db, pack) -> None:
    """Mark the single four-view hero job done with a real asset."""
    hero = pack["jobs"]["hero"]
    vj = hero["viewJobs"][0]
    job = db.get(Job, vj["jobId"])
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-sheet",
            tag="character_sheet",
            kind="image",
            filename="sheet.png",
            path=_png(_scratch_dir() / "sheet.png", (1024, 1024)),
        )
    )
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()


def _complete_phase_jobs(db, pack, phase: str) -> None:
    """Complete every job of one pack phase with a real asset."""
    for item in pack["jobs"][phase]:
        job = db.get(Job, item["jobId"])
        if not job or job.status == "done":
            continue
        asset_id = str(uuid.uuid4())
        db.add(
            Asset(
                id=asset_id,
                project_id="proj-sheet",
                tag=f"character_{phase}",
                kind="image",
                filename=f"{phase}_{item['role']}.png",
                path=_png(_scratch_dir() / f"{phase}_{item['role']}.png", (1024, 1024)),
            )
        )
        job.status = "done"
        job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()


def _params(db, job_id) -> dict:
    job = db.get(Job, job_id)
    assert job is not None, f"job {job_id} missing"
    return json.loads(job.params_json or "{}")


def _phase_jobs(db, pack, phase: str) -> list[tuple[str, dict]]:
    out = []
    for item in pack["jobs"][phase]:
        out.append((item["role"], _params(db, item["jobId"])))
    return out


def _assert_cloud_job(role: str, params: dict, *, expect_selected_source: bool = False) -> None:
    """A hosted job must carry provider/cloud fields and never a local model."""
    assert params.get("providerPreference") == "cloud", f"{role} must prefer cloud"
    assert params.get("cloudPaid") is True, f"{role} must be a paid hosted job"
    assert params.get("hostedModelId") == "krea2-turbo-fal", f"{role} must pin the selected model"
    assert params.get("falImageModelId") == "fal-ai/krea-2/turbo", f"{role} must resolve the fal model"
    runtime = params.get("imageRuntime") or {}
    assert str(runtime.get("workflowKey") or "").startswith("fal:"), f"{role} must use the hosted adapter"
    assert str(runtime.get("provider") or "").lower() == "fal"
    creative = params.get("creativeContext") or {}
    assert creative.get("providerKind") == "api", f"{role} creativeContext must record api source"
    if expect_selected_source:
        assert creative.get("selectedSource") == "krea2-turbo-fal", f"{role} must record the selected source"
    assert params.get("model") != "qwen2512", f"{role} must not fall back to local qwen2512"
    assert params.get("model") not in ("qwen-image-2512", "illustrious", "zimage")


def test_advance_cloud_only_enqueues_coverage_on_hosted_model(db):
    """Cloud-only: coverage jobs carry hosted/provider fields, zero local enqueue."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        include_performance=False,
        generator_sources=dict(CLOUD_ONLY_SOURCES),
    )
    _assert_cloud_job("hero", _params(db, pack["jobs"]["hero"]["jobId"]))

    _complete_hero(db, pack)
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)

    coverage = _phase_jobs(db, advanced, "coverage")
    assert len(coverage) >= 4, "coverage phase must enqueue real jobs"
    for role, params in coverage:
        _assert_cloud_job(role, params, expect_selected_source=True)
    assert "qwen2512.txt2img" not in (advanced.get("workflows") or [])


def test_advance_cloud_only_honors_all_phases(db):
    """Cloud-only applies to coverage AND details AND performance phases."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=True,
        include_performance=True,
        generator_sources=dict(CLOUD_ONLY_SOURCES),
    )
    _complete_hero(db, pack)
    pack = advance_visual_sheet_pack(db, "proj-sheet", profile.id)

    # coverage -> details -> performance, advancing as each phase completes
    for phase in ("coverage", "details", "performance"):
        jobs = pack["jobs"].get(phase)
        assert isinstance(jobs, list) and jobs, f"{phase} must be enqueued"
        for role, params in _phase_jobs(db, pack, phase):
            _assert_cloud_job(role, params, expect_selected_source=True)
        _complete_phase_jobs(db, pack, phase)
        pack = advance_visual_sheet_pack(db, "proj-sheet", profile.id)

    workflows = pack.get("workflows") or []
    assert "qwen2512.txt2img" not in workflows, "no phase may run local qwen2512 under Cloud-only"
    assert any(w.startswith("krea2") for w in workflows) or any(
        "turbo" in w for w in workflows
    ), "phase workflows must reflect the hosted source"


def test_advance_cloud_only_with_no_api_model_fails_honestly(db):
    """Cloud-only with no API model selected: typed error, no local fallback."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-sheet",
            tag="character_sheet",
            kind="image",
            filename="hero.png",
            path=_png(_scratch_dir() / "hero.png", (1024, 1024)),
        )
    )
    db.commit()
    # hero_asset_id skips candidate routing, so the broken Cloud-only source
    # survives start and must be caught honestly at phase enqueue time.
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        include_performance=False,
        hero_asset_id=asset_id,
        generator_sources={"local": None, "api": {"enabled": True}},
    )
    assert pack.get("generatorSources") == {"local": None, "api": {"enabled": True}}
    with pytest.raises(VisualSheetSourceUnavailableError) as excinfo:
        advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert "no api model" in str(excinfo.value).lower()
    assert isinstance(excinfo.value, ValueError), "typed error must stay API-mappable (400)"
    assert db.query(Job).count() == 0, "no job may be enqueued for the broken source"


def test_advance_default_sources_preserve_local_qwen2512(db):
    """Legacy packs without generatorSources keep the default local qwen2512."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db, "proj-sheet", profile.id, include_details=False, include_performance=False
    )
    _complete_hero(db, pack)
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)

    coverage = _phase_jobs(db, advanced, "coverage")
    assert coverage, "coverage phase must enqueue real jobs"
    for role, params in coverage:
        assert params.get("providerPreference") != "cloud", f"{role} must stay local"
        runtime = params.get("imageRuntime") or {}
        assert runtime.get("workflowKey") == "qwen2512.txt2img", f"{role} must keep the default local model"
        creative = params.get("creativeContext") or {}
        assert creative.get("providerKind") == "local"
        assert creative.get("workflowKey") == "qwen2512.txt2img"
    assert "qwen2512.txt2img" in (advanced.get("workflows") or [])


def test_advance_explicit_local_family_routes_every_phase(db):
    """Explicit local family applies to all generated stages, not just hero."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        include_performance=False,
        generator_sources={"local": [{"family": "illustrious", "enabled": True, "batchCount": 1}], "api": None},
    )
    _complete_hero(db, pack)
    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)

    coverage = _phase_jobs(db, advanced, "coverage")
    assert coverage
    for role, params in coverage:
        assert params.get("providerPreference") != "cloud"
        intent = params.get("imageIntent") or {}
        assert intent.get("enginePreference") == "illustrious", f"{role} must use the selected local family"
        runtime = params.get("imageRuntime") or {}
        assert runtime.get("workflowKey") == "illustrious.txt2img", f"{role} must pin the family workflow"
        creative = params.get("creativeContext") or {}
        assert creative.get("workflowKey") == "illustrious.txt2img"
        assert creative.get("providerKind") == "local"
    assert "illustrious.txt2img" in (advanced.get("workflows") or [])
    assert "qwen2512.txt2img" not in (advanced.get("workflows") or [])
