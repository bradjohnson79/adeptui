"""M2.8 Capability Intelligence unit/API tests (fixture mode)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M012, MigrationRunner


@pytest.fixture()
def enable_m28(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_M28_FIXTURE_MODE", "1")
    monkeypatch.setenv("STUDIO_FEATURE_MODEL_RADAR_V1", "1")
    monkeypatch.setenv("STUDIO_FEATURE_SANDBOX_RUNTIME_V1", "1")
    monkeypatch.setenv("STUDIO_FEATURE_VIRTUAL_STAGE_V1", "1")
    monkeypatch.setenv("STUDIO_FEATURE_SHOT_PROFILES_V1", "1")
    monkeypatch.setenv("STUDIO_FEATURE_PRODUCTION_RECIPE_V1", "1")
    monkeypatch.setenv("STUDIO_FEATURE_LOCATION_SPIN_V1", "1")
    monkeypatch.setenv("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    yield
    for k in list(os.environ):
        if k.startswith("STUDIO_FEATURE_") or k == "ADEPT_M28_FIXTURE_MODE":
            pass
    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def db(enable_m28):
    init_db()
    from app.codirector.m28.db import ensure_m28_tables

    ensure_m28_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m28", name="M28 Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_m28_flags_default_off():
    flags = FeatureFlags.from_env({})
    assert flags.model_radar_v1 is False
    assert flags.sandbox_runtime_v1 is False
    assert flags.virtual_stage_v1 is False
    assert flags.shot_profiles_v1 is False
    assert flags.production_recipe_v1 is False
    assert flags.location_spin_v1 is False


def test_m012_registered_after_m011():
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M012" in revs
    assert M012.revision == "M012"
    assert revs.index("M011") < revs.index("M012")


def test_m012_creates_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm012.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M012" in result.applied
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "m28_model_entries" in tables
    assert "m28_sandbox_plans" in tables
    assert "m28_recipes" in tables


def test_radar_discover_and_dedupe(db):
    from app.codirector.m28.radar.service import RadarService

    first = RadarService.discover(db, source="huggingface")
    assert first["created"] >= 1
    second = RadarService.discover(db, source="huggingface")
    assert second["duplicatesSuppressed"] >= 1
    entries = RadarService.registry(db)
    assert any(e["classification"] == "announcement_only" for e in entries)
    ann = next(e for e in entries if e["classification"] == "announcement_only")
    assert ann["installAction"] is None


def test_sandbox_approval_boundary(db):
    from app.codirector.m28.radar.service import RadarService
    from app.codirector.m28.sandbox.service import SandboxService

    RadarService.discover(db, source="huggingface")
    entry = next(
        e
        for e in RadarService.registry(db)
        if e["classification"] == "official"
    )
    sb = SandboxService.create(db, name="s1")
    plan = SandboxService.create_plan(db, sandbox_id=sb["id"], entry_id=entry["id"])
    assert plan["status"] == "pending"
    with pytest.raises(PermissionError):
        SandboxService.execute_approved_install(db, plan_id=plan["id"])
    rejected = SandboxService.reject_plan(db, plan["id"])
    assert rejected["status"] == "rejected"
    assert rejected["environmentChanged"] is False

    plan2 = SandboxService.create_plan(db, sandbox_id=sb["id"], entry_id=entry["id"])
    approved = SandboxService.approve_plan(
        db, plan_id=plan2["id"], project_id="proj-m28"
    )
    assert approved["status"] == "approved"
    assert approved["job"]["type"] == "sandbox_install"


def test_promote_reject_no_mutation(db):
    from app.codirector.m28.promote.service import PromoteService
    from app.codirector.m28.sandbox.service import SandboxService

    sb = SandboxService.create(db, name="promo")
    SandboxService.validate(db, sb["id"])
    prop = PromoteService.create_proposal(db, sandbox_id=sb["id"])
    rejected = PromoteService.reject(db, prop["id"])
    assert rejected["mutated"] is False
    assert rejected["productionInstallOccurred"] is False


def test_recipe_resume_no_duplicate(db):
    from app.codirector.m28.recipes.service import RecipeService

    recipe = RecipeService.create(db, project_id="proj-m28", name="r1")
    RecipeService.complete_stage(
        db, recipe_id=recipe["id"], stage_id=recipe["stages"][0]["id"], failed=False
    )
    again = RecipeService.run(db, recipe_id=recipe["id"])
    completed = [s for s in again["stages"] if s["status"] == "completed"]
    queued = [s for s in again["stages"] if s["status"] in {"queued", "pending"}]
    assert len(completed) == 1
    assert len(queued) >= 1


def test_recipe_stage_refuses_mock_completion_outside_fixture(db, monkeypatch):
    """M28-08 / EXEC-04: a recipe cannot report a stage completed with a mock result."""
    from app.codirector.m28.recipes.service import RecipeService

    recipe = RecipeService.create(db, project_id="proj-m28", name="r-prod")
    monkeypatch.delenv("ADEPT_M28_FIXTURE_MODE", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    with pytest.raises(PermissionError) as exc:
        RecipeService.complete_stage(
            db, recipe_id=recipe["id"], stage_id=recipe["stages"][0]["id"], failed=False
        )
    assert "no real" in str(exc.value).lower()
    unchanged = RecipeService.get(db, recipe["id"])
    assert all(s["status"] != "completed" for s in unchanged["stages"])


def test_recipe_stage_handler_reports_blocked_outside_fixture(db, monkeypatch):
    from app.codirector.executive.handlers import execute_job
    from app.codirector.executive.models import JobType
    from app.codirector.executive.schemas import JobOut
    from app.codirector.m28.recipes.service import RecipeService

    recipe = RecipeService.create(db, project_id="proj-m28", name="r-blocked")
    monkeypatch.delenv("ADEPT_M28_FIXTURE_MODE", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)

    job = JobOut(
        id="job-recipe-blocked",
        type=JobType.RECIPE_STAGE.value,
        owner="tester",
        projectId="proj-m28",
        priority=5,
        status="running",
        payload={"recipeId": recipe["id"], "stageId": recipe["stages"][0]["id"]},
        createdAt="2026-07-26T00:00:00Z",
        updatedAt="2026-07-26T00:00:00Z",
    )
    result = execute_job(job, db)
    assert result.ok is False
    assert result.status == "Blocked"


def test_location_spin_refuses_synthetic_coverage_outside_fixture(db, monkeypatch):
    """M28-06: fixture-spin coverage packs are CI-only."""
    from app.codirector.m28.location_spin.service import LocationSpinService

    spin = LocationSpinService.plan(db, project_id="proj-m28", location_name="Alley")
    monkeypatch.delenv("ADEPT_M28_FIXTURE_MODE", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    with pytest.raises(PermissionError):
        LocationSpinService.spin_camera(db, spin_id=spin["id"])
    unchanged = LocationSpinService.get(db, spin["id"])
    assert unchanged["coverage"] is None


def test_flags_off_api_404(monkeypatch):
    monkeypatch.delenv("STUDIO_FEATURE_MODEL_RADAR_V1", raising=False)
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env({})
    from app.main import app

    client = TestClient(app)
    res = client.post("/api/codirector/m28/radar/discover", json={"source": "huggingface"})
    assert res.status_code == 404


def test_api_radar_happy_path(enable_m28):
    init_db()
    from app.codirector.m28.db import ensure_m28_tables
    from app.main import app

    ensure_m28_tables()
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    op = health.json().get("operator") or {}
    assert op.get("modelRadarEnabled") is True
    d = client.post("/api/codirector/m28/radar/discover", json={"source": "huggingface"})
    assert d.status_code == 200
    reg = client.get("/api/codirector/m28/radar/registry")
    assert reg.status_code == 200
    assert len(reg.json()["entries"]) >= 1
