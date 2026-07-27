"""M2.12 Adaptive Learning unit/API tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M014, M015, MigrationRunner

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
EXPECTED_MANIFEST_SHA = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
FLAG_ENV = "STUDIO_FEATURE_CODIRECTOR_ADAPTIVE_LEARNING_V1"
M211_FLAG = "STUDIO_FEATURE_CODIRECTOR_PRODUCTION_INTELLIGENCE_V1"


@pytest.fixture()
def enable_m212(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(FLAG_ENV, "1")
    monkeypatch.setenv(M211_FLAG, "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    yield
    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def db(enable_m212):
    init_db()
    from app.codirector.m212.db import ensure_m212_tables
    from app.codirector.m211.db import ensure_m211_tables

    ensure_m211_tables()
    ensure_m212_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m212", name="M212 Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(enable_m212):
    from app.main import app

    init_db()
    from app.codirector.m212.db import ensure_m212_tables
    from app.codirector.m211.db import ensure_m211_tables

    ensure_m211_tables()
    ensure_m212_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m212", name="M212 Test"))
    session.commit()
    session.close()
    return TestClient(app)


def test_flag_default_off():
    flags = FeatureFlags.from_env({})
    assert flags.codirector_adaptive_learning_v1 is False


def test_m015_registered_after_m014():
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M015" in revs
    assert M015.revision == "M015"
    assert M014.revision == "M014"
    assert revs.index("M014") < revs.index("M015")


def test_m015_creates_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm015.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M015" in result.applied
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "m212_lessons" in tables
    assert "m212_lesson_versions" in tables
    assert "m212_retrospectives" in tables
    assert "m212_confidence_calibration" in tables
    assert "m212_strategy_packs" in tables


def test_flags_off_api_404(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "0")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    from app.main import app

    client = TestClient(app)
    res = client.get("/api/codirector/m212/status")
    assert res.status_code == 404


def test_layer_isolation(db):
    from app.codirector.m212.lessons import LessonStore

    a = LessonStore.create_candidate(
        db,
        layer="project",
        text_body="Project lesson A",
        project_id="proj-m212",
        confidence=0.7,
        evidence_score=0.7,
        mistake_class="continuity",
    )
    b = LessonStore.create_candidate(
        db,
        layer="session",
        text_body="Session lesson B",
        project_id="proj-m212",
        session_id="sess-1",
        confidence=0.7,
        evidence_score=0.7,
        mistake_class="camera",
    )
    assert a["layer"] == "project"
    assert b["layer"] == "session"
    listed = LessonStore.list_lessons(db, project_id="proj-m212", layer="project")
    assert all(x["layer"] == "project" for x in listed)
    assert any(x["id"] == a["id"] for x in listed)
    assert all(x["id"] != b["id"] for x in listed)


def test_system_no_auto_promote(db):
    from app.codirector.m212.lessons import LessonStore
    from app.codirector.m212.promote import promote_lesson
    from app.codirector.m212.safety import AdaptiveLearningSafetyError, assert_no_system_auto_activate

    with pytest.raises(AdaptiveLearningSafetyError):
        assert_no_system_auto_activate("system", auto=True)

    lesson = LessonStore.create_candidate(
        db,
        layer="system",
        text_body="Global continuity policy",
        confidence=0.9,
        evidence_score=0.9,
        mistake_class="continuity",
    )
    assert lesson["status"] == "candidate"
    with pytest.raises(AdaptiveLearningSafetyError):
        promote_lesson(db, lesson["id"], actor="bot", role="user", note="auto")


def test_regression_required_before_activate(db):
    from app.codirector.m212.lessons import LessonStore
    from app.codirector.m212.promote import promote_lesson
    from app.codirector.m212.safety import AdaptiveLearningSafetyError

    lesson = LessonStore.create_candidate(
        db,
        layer="project",
        text_body="Keep artifact orientation",
        project_id="proj-m212",
        confidence=0.8,
        evidence_score=0.8,
        mistake_class="continuity",
    )
    # Force missing regression by clearing fields and calling require path
    LessonStore.update_fields(
        db,
        lesson["id"],
        fields={"regressionSuiteId": None, "regressionPassed": False},
        actor="test",
        action="clear_reg",
    )
    with pytest.raises(AdaptiveLearningSafetyError):
        promote_lesson(
            db,
            lesson["id"],
            actor="user",
            role="user",
            run_regression=False,
            into_learning_py=False,
        )


def test_rollback_keeps_audit(db):
    from app.codirector.m212.lessons import LessonStore
    from app.codirector.m212.promote import promote_lesson, rollback_lesson

    lesson = LessonStore.create_candidate(
        db,
        layer="project",
        text_body="Do not flip scanner hand",
        project_id="proj-m212",
        confidence=0.85,
        evidence_score=0.85,
        mistake_class="continuity",
    )
    promoted = promote_lesson(
        db, lesson["id"], actor="user", role="user", into_learning_py=False
    )
    assert promoted["lesson"]["status"] == "active"
    rolled = rollback_lesson(db, lesson["id"], actor="user", note="bad lesson")
    assert rolled["lesson"]["status"] == "rolled_back"
    versions = LessonStore.versions(db, lesson["id"])
    actions = {v["action"] for v in versions}
    assert "promote" in actions
    assert "rollback" in actions
    # row still exists (no silent delete)
    assert LessonStore.get(db, lesson["id"]) is not None


def test_unverified_outputs_blocked(db):
    from app.codirector.m212.critique import critique_action
    from app.codirector.m212.safety import AdaptiveLearningSafetyError

    with pytest.raises(AdaptiveLearningSafetyError):
        critique_action(
            db,
            project_id="proj-m212",
            action={"summary": "attempt"},
            outcome={"status": "failed", "verified": False},
        )


def test_manifest_sha_unchanged():
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert digest == EXPECTED_MANIFEST_SHA


def test_learning_cannot_mutate_manifest_or_locks(client):
    res = client.post(
        "/api/codirector/m212/safety/probe-forbidden-write",
        json={"path": "config/capabilities/adept-ui-v1.0-provider-manifest.json"},
    )
    assert res.status_code == 200
    assert res.json()["allowed"] is False
    res2 = client.post(
        "/api/codirector/m212/safety/probe-forbidden-write",
        json={"path": "studio-api/app/codirector/m210b/execution_lock.py"},
    )
    assert res2.status_code == 200
    assert res2.json()["allowed"] is False


def test_smoke_reject_critique_promote_retrieve_rollback(client, db):
    # 1-3: rejected recommendation -> critique -> candidate
    critique = client.post(
        "/api/codirector/m212/critique",
        json={
            "projectId": "proj-m212",
            "layer": "project",
            "action": {
                "summary": "Recommend wardrobe unlock across scenes",
                "recommendation": "Unlock wardrobe",
                "confidence": 0.9,
            },
            "outcome": {
                "status": "rejected",
                "verified": True,
                "humanRejected": True,
                "rejected": True,
                "classified": True,
                "mistakeClass": "continuity",
                "message": "User rejected wardrobe unlock",
                "lessonText": "Keep wardrobe locked across S2-S4 for this project.",
                "confidence": 0.8,
            },
            "traces": [{"id": "t1", "status": "completed", "failures": []}],
        },
    )
    assert critique.status_code == 200, critique.text
    body = critique.json()
    assert body["mistakeClass"] == "continuity"
    lesson = body["candidateLesson"]
    assert lesson and lesson["status"] == "candidate"
    lid = lesson["id"]

    # 4: regression
    reg = client.post(f"/api/codirector/m212/lessons/{lid}/regression")
    assert reg.status_code == 200, reg.text
    assert reg.json()["passed"] is True

    # 5: human approve project promote
    promo = client.post(
        f"/api/codirector/m212/lessons/{lid}/promote",
        json={"actor": "user", "role": "user", "note": "smoke approve", "intoLearningPy": True},
    )
    assert promo.status_code == 200, promo.text
    assert promo.json()["lesson"]["status"] == "active"

    # 6: subsequent orchestration retrieves lesson
    orch = client.post(
        "/api/codirector/m211/orchestrate",
        json={
            "projectId": "proj-m212",
            "brief": "Create a suspenseful laboratory scene where two scientists discover an alien artifact.",
        },
    )
    assert orch.status_code == 200, orch.text
    orch_body = orch.json()
    active = orch_body.get("activeLessons") or []
    assert any(x.get("id") == lid for x in active), active
    pack = orch_body.get("contextPack") or {}
    assert any(x.get("id") == lid for x in (pack.get("activeLessons") or [])), pack.get("activeLessons")

    # 7: rollback
    rb = client.post(
        f"/api/codirector/m212/lessons/{lid}/rollback",
        json={"actor": "user", "note": "smoke rollback"},
    )
    assert rb.status_code == 200, rb.text
    assert rb.json()["lesson"]["status"] == "rolled_back"

    # 8: manifest unchanged
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert digest == EXPECTED_MANIFEST_SHA


def test_status_safety_contract(client):
    res = client.get("/api/codirector/m212/status")
    assert res.status_code == 200
    body = res.json()
    assert body["fineTuning"] is False
    assert body["autonomousSourceRewrite"] is False
    assert body["manifestSha256"] == EXPECTED_MANIFEST_SHA
    assert "system" in body["layers"]
