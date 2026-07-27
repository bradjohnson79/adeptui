"""Co-Director M2.5 vision validation vertical-slice tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.orm import Session

from app.codirector.intelligence.schemas import ProductionPlan
from app.codirector.intelligence.store import IntelligenceStore
from app.codirector.vision.engine import VisionEngine, run_validation
from app.codirector.vision.reports import band_for_score, compute_report
from app.codirector.vision.schemas import ValidateRequest, ValidatorFinding
from app.codirector.vision.store import VisionStore
from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M006


@pytest.fixture(autouse=True)
def _allow_mock_vision_provider(monkeypatch: pytest.MonkeyPatch):
    """The mock vision provider is E2E-only in production code; these tests opt in."""
    monkeypatch.setenv("STUDIO_E2E", "1")


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    session.merge(Project(id="proj-vision-1", name="Vision Test Project"))
    session.merge(
        Asset(
            id="asset-vision-1",
            project_id="proj-vision-1",
            tag="storyboard",
            kind="image",
            filename="mock.png",
            path="missing-on-purpose.png",
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_feature_flag_defaults_off():
    flags = FeatureFlags.from_env({})
    assert flags.vision_validation_v1 is False


def test_m006_registered_and_m010_untouched():
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M006" in revs
    assert "M010" in revs
    assert M006.revision == "M006"
    assert revs.index("M006") < revs.index("M010")


def test_scoring_bands_and_blocking_cannot_average_away():
    assert band_for_score(96) == "approve"
    assert band_for_score(92) == "review"
    assert band_for_score(85) == "corrections_required"
    assert band_for_score(70) == "reject"

    findings = [
        ValidatorFinding(validatorId="technical", status="fail", score=40, blocking=True, summary="bad tech"),
        ValidatorFinding(validatorId="identity", status="pass", score=100, summary="ok id"),
        ValidatorFinding(validatorId="continuity", status="pass", score=100, summary="ok cont"),
        ValidatorFinding(validatorId="lighting", status="pass", score=100, summary="ok"),
        ValidatorFinding(validatorId="camera", status="pass", score=100, summary="ok"),
        ValidatorFinding(validatorId="composition", status="pass", score=100, summary="ok"),
        ValidatorFinding(validatorId="color", status="pass", score=100, summary="ok"),
    ]
    report = compute_report(
        session_id="s1",
        project_id="p1",
        findings=findings,
        provider="mock",
    )
    assert "technical" in report.blockingFailures
    assert report.band == "reject"
    assert report.passed is False
    assert report.overallScore < 80


def test_mock_validate_clears_visual_validation_pending(db: Session):
    plan = ProductionPlan(
        planId="plan-vision-1",
        projectId="proj-vision-1",
        title="Storyboard plan",
        visualValidationPending=True,
        requestId="req-1",
    )
    IntelligenceStore.save_plan(db, plan=plan, status="draft")
    row = db.get(__import__("app.db", fromlist=["CoDirectorProductionPlan"]).CoDirectorProductionPlan, "plan-vision-1")
    assert row is not None
    assert row.visual_validation_pending == 1

    result = run_validation(
        db,
        ValidateRequest(
            projectId="proj-vision-1",
            assetId="asset-vision-1",
            planId="plan-vision-1",
            provider="mock",
            fixtureProfile="pass",
        ),
    )
    assert result["session"]["status"] == "completed"
    assert result["report"]["band"] in {"approve", "review", "corrections_required"}
    db.refresh(row)
    assert row.visual_validation_pending == 0
    reloaded = IntelligenceStore.load_plan(db, "plan-vision-1")
    assert reloaded is not None
    assert reloaded.visualValidationPending is False

    asset = db.get(Asset, "asset-vision-1")
    assert asset is not None
    assert asset.validation_lifecycle == "completed"
    assert asset.validation_result in {"passed", "warnings", "failed"}
    assert asset.production_approval == "none"


def test_blocking_fixture_fails_and_correction_proposal(db: Session):
    from app.codirector.vision.corrections import create_correction_proposal
    from app.codirector.vision.schemas import ValidationReport

    result = run_validation(
        db,
        ValidateRequest(
            projectId="proj-vision-1",
            assetId="asset-vision-1",
            provider="mock",
            fixtureProfile="fail_technical",
        ),
    )
    report = ValidationReport.model_validate(result["report"])
    assert report.passed is False
    assert "technical" in report.blockingFailures

    created = create_correction_proposal(
        db,
        project_id="proj-vision-1",
        report=report,
        notes="fix blur",
    )
    assert created["proposalId"]
    links = VisionStore.list_correction_links(db, result["session"]["sessionId"])
    assert any(link.proposalId == created["proposalId"] for link in links)


def test_approve_creates_bible_link_proposal_only(db: Session):
    from app.codirector.vision.approval import record_decision

    result = run_validation(
        db,
        ValidateRequest(
            projectId="proj-vision-1",
            assetId="asset-vision-1",
            provider="mock",
            fixtureProfile="pass",
        ),
    )
    session_id = result["session"]["sessionId"]
    out = record_decision(
        db,
        project_id="proj-vision-1",
        session_id=session_id,
        decision="approved",
        link_to_bible=True,
    )
    assert out["status"] == "approved"
    assert out["bibleLinkProposal"]["proposalId"]
    asset = db.get(Asset, "asset-vision-1")
    assert asset is not None
    assert asset.production_approval == "approved"


def test_local_provider_ml_stubs_inconclusive(db: Session):
    engine = VisionEngine()
    result = engine.run(
        db,
        ValidateRequest(
            projectId="proj-vision-1",
            assetId="asset-vision-1",
            provider="local",
        ),
    )
    findings = result["report"]["findings"]
    by_id = {f["validatorId"]: f for f in findings}
    # Missing file -> technical fail; ML validators must not fake pass.
    assert by_id["technical"]["status"] == "fail"
    assert by_id["identity"]["status"] == "inconclusive"
    assert by_id["camera"]["status"] == "inconclusive"


def test_api_flag_off_returns_404(client):
    os.environ.pop("STUDIO_FEATURE_VISION_VALIDATION_V1", None)
    # Reload feature flags module singleton used by API.
    from app import feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    res = client.post(
        "/api/codirector/vision/validate",
        json={"projectId": "proj-vision-1", "provider": "mock"},
    )
    assert res.status_code == 404


def test_api_flag_on_validate_and_session(client, db: Session):
    os.environ["STUDIO_FEATURE_VISION_VALIDATION_V1"] = "1"
    from app import feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    try:
        res = client.post(
            "/api/codirector/vision/validate",
            json={
                "projectId": "proj-vision-1",
                "assetId": "asset-vision-1",
                "provider": "mock",
                "fixtureProfile": "corrections",
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        session_id = body["session"]["sessionId"]
        report_id = body["report"]["reportId"]
        get_session = client.get(f"/api/codirector/vision/session/{session_id}", params={"projectId": "proj-vision-1"})
        assert get_session.status_code == 200
        get_report = client.get(f"/api/codirector/vision/report/{report_id}", params={"projectId": "proj-vision-1"})
        assert get_report.status_code == 200
        assert get_report.json()["band"] in {"corrections_required", "review", "reject", "approve"}
    finally:
        os.environ.pop("STUDIO_FEATURE_VISION_VALIDATION_V1", None)
        ff.feature_flags = FeatureFlags.from_env(os.environ)


def test_specialist_validation_status_not_overloaded():
    """Asset visual review must not reuse CoDirectorSpecialistFinding.validation_status."""
    from app.db import CoDirectorSpecialistFinding, CoDirectorValidationFinding

    assert CoDirectorSpecialistFinding.__tablename__ == "codirector_specialist_findings"
    assert CoDirectorValidationFinding.__tablename__ == "codirector_validation_findings"
    assert "validation_status" in CoDirectorSpecialistFinding.__table__.c
    assert "validation_status" not in CoDirectorValidationFinding.__table__.c
