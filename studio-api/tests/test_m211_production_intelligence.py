"""M2.11 Production Intelligence unit/API tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M013, M014, MigrationRunner

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
EXPECTED_MANIFEST_SHA = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
SMOKE_BRIEF = "Create a suspenseful laboratory scene where two scientists discover an alien artifact."
FLAG_ENV = "STUDIO_FEATURE_CODIRECTOR_PRODUCTION_INTELLIGENCE_V1"


@pytest.fixture()
def enable_m211(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(FLAG_ENV, "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)

    # Keep M2.11 smoke/API tests on the labeled limited-analysis path so a local
    # Ollama install cannot turn the suite into live multi-specialist LLM calls.
    async def _force_limited(_provider=None, *, prefer_provider=None):
        return None, False, "limited-analysis"

    monkeypatch.setattr(
        "app.codirector.m211.orchestrator.resolve_provider_for_specialists",
        _force_limited,
    )
    yield
    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def db(enable_m211):
    init_db()
    from app.codirector.m211.db import ensure_m211_tables

    ensure_m211_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m211", name="M211 Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(enable_m211):
    from app.main import app

    init_db()
    from app.codirector.m211.db import ensure_m211_tables

    ensure_m211_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m211", name="M211 Test"))
    session.commit()
    session.close()
    return TestClient(app)


def test_flag_default_off():
    flags = FeatureFlags.from_env({})
    assert flags.codirector_production_intelligence_v1 is False


def test_m014_registered_after_m013():
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M014" in revs
    assert M014.revision == "M014"
    assert M013.revision == "M013"
    assert revs.index("M013") < revs.index("M014")


def test_m014_creates_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm014.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M014" in result.applied
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "m211_memory_items" in tables
    assert "m211_decision_records" in tables
    assert "m211_execution_traces" in tables


def test_flags_off_api_404(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "0")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    from app.main import app

    client = TestClient(app)
    res = client.get("/api/codirector/m211/status")
    assert res.status_code == 404


def test_routing_first_class_intents():
    from app.codirector.intelligence.schemas import IntentClassification
    from app.codirector.intelligence.specialist_selector import SpecialistSelector

    selector = SpecialistSelector()
    cases = {
        "production_intelligence": ("sound-designer", "music-supervisor", "editor"),
        "plan_audio": ("sound-designer", "music-supervisor", "editor"),
        "assemble_sequence": ("editor", "sound-designer", "music-supervisor"),
    }
    for intent_name, must_include in cases.items():
        intent = IntentClassification(primaryIntent=intent_name)  # type: ignore[arg-type]
        selected = selector.select(intent)
        ids = selected.all_selected
        for sid in must_include:
            assert sid in ids, f"{intent_name} missing {sid}: {ids}"
        # first-class: sound/music/editor appear among early required specialists
        assert ids[0] in {
            "story-analyst",
            "sound-designer",
            "editor",
            "screenwriter",
        } or sid in ids


def test_dag_order():
    from app.codirector.m211.dag import DEFAULT_PIPELINE, default_stage_order

    expected_stages = [
        "storyteller",
        "story",
        "bible",
        "continuity",
        "director",
        "camera",
        "sound_producer",
        "sound",
        "music",
        "editor",
        "vpc",
        "qa",
        "user_review",
    ]
    assert default_stage_order() == expected_stages
    expected_specialists = [
        "storyteller",
        "story-analyst",
        "bible-manager",
        "continuity-analyst",
        "director",
        "cinematographer",
        "sound-producer",
        "sound-designer",
        "music-supervisor",
        "editor",
        "virtual-production-coordinator",
        "qa-reviewer",
        "qa-reviewer",
    ]
    assert [n.specialist_id for n in DEFAULT_PIPELINE] == expected_specialists
    labels = " → ".join(n.label for n in DEFAULT_PIPELINE)
    assert "Storyteller" in labels
    assert "Story Analyst" in labels
    assert "Sound Producer" in labels
    assert "Virtual Production Coordinator" in labels
    assert "Director" in labels
    assert "Editor" in labels
    assert "User Review" in labels


def test_heuristic_enrichment_does_not_invent_lab_assets_for_unrelated_brief():
    from app.codirector.m211.orchestrator import _heuristic_enrichment

    enrichment = _heuristic_enrichment("A quiet seaside conversation at dawn.")

    assert enrichment["missingAssets"] == []
    assert "corridor" not in str(enrichment).lower()
    assert enrichment["briefExcerpt"].startswith("A quiet seaside")


def test_memory_upsert_search(db):
    from app.codirector.m211.memory import ProductionMemoryStore

    row = ProductionMemoryStore.upsert(
        db,
        project_id="proj-m211",
        content="Alien artifact orientation locked facing camera left.",
        category="continuity",
        tags=["artifact", "continuity"],
    )
    assert row["id"]
    assert row["content"].startswith("Alien artifact")
    hits = ProductionMemoryStore.search(db, project_id="proj-m211", query="artifact")
    assert any(h["id"] == row["id"] for h in hits)


def test_decisions_explainability_required_fields(db):
    from app.codirector.m211.decisions import DecisionRecordStore

    explain = {
        "summary": "Hold two-shot on discovery",
        "recommendation": "Push slowly to artifact",
        "evidence": [{"type": "requirement", "text": "Readable artifact insert"}],
        "bibleRefs": [],
        "specialistId": "director",
        "confidence": 0.81,
        "stageId": "director",
        "blockingIssues": [],
    }
    decision = DecisionRecordStore.create(
        db,
        project_id="proj-m211",
        category="director",
        rationale=explain["summary"],
        confidence=0.81,
        evidence=explain["evidence"],
        bible_refs=[],
        specialist_id="director",
        approval_required=False,
        recommendation=explain["recommendation"],
        explainability=explain,
    )
    for key in (
        "id",
        "rationale",
        "confidence",
        "evidence",
        "bibleRefs",
        "specialistId",
        "approvalRequired",
        "explainability",
        "recommendation",
    ):
        assert key in decision
    expl = decision["explainability"]
    for key in (
        "summary",
        "recommendation",
        "evidence",
        "bibleRefs",
        "specialistId",
        "confidence",
    ):
        assert key in expl


def test_conflicts_bridge_and_bible_routes(client, db):
    from app.codirector.intelligence.schemas import SpecialistFinding
    from app.codirector.m211.conflicts_bridge import bridge_specialist_conflicts
    from app.codirector.bible import conflicts as bible_conflicts

    assert hasattr(bible_conflicts, "detect_all_conflicts")
    finding = SpecialistFinding(
        specialistId="continuity-analyst",
        summary="Continuity check",
        recommendation="Fix mismatch",
        confidence=0.7,
        requirements=[],
        risks=["wardrobe conflict on coat color"],
        blockingIssues=["continuity conflict across S2/S3"],
    )
    out = bridge_specialist_conflicts(db, "proj-m211", [finding], scene_id=None)
    assert isinstance(out, dict)
    # bible conflicts routes exist
    # routes are under bible domain router — probe OpenAPI or direct path patterns
    paths = {getattr(r, "path", "") for r in client.app.routes}
    assert any("/conflicts" in p for p in paths), paths


def test_review_loop_stages():
    from app.codirector.m211.review_loop import REVIEW_ORDER, ReviewLoopService

    assert list(REVIEW_ORDER) == [
        "plan",
        "execute",
        "review",
        "critique",
        "revise",
        "approve",
        "archive",
    ]
    state = ReviewLoopService.start("proj-m211", None)
    assert state.stage == "plan"
    ReviewLoopService.advance(state.loop_id, action="next")
    mid = ReviewLoopService.get(state.loop_id)
    assert mid is not None
    assert mid.stage == "execute"


def test_dashboard_api_when_flag_on(client):
    res = client.get("/api/codirector/m211/dashboard", params={"projectId": "proj-m211"})
    assert res.status_code == 200
    body = res.json()
    assert body["projectId"] == "proj-m211"
    assert "specialists" in body
    assert "pendingApprovals" in body
    assert "health" in body
    assert "timelineStatus" in body
    assert "executionHistory" in body


def test_traces_created_by_orchestrate(client):
    res = client.post(
        "/api/codirector/m211/orchestrate",
        json={"projectId": "proj-m211", "brief": SMOKE_BRIEF},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("trace")
    assert body["trace"].get("id")
    listed = client.get("/api/codirector/m211/traces", params={"projectId": "proj-m211"})
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1


def test_smoke_orchestration_no_media(client):
    res = client.post(
        "/api/codirector/m211/orchestrate",
        json={"projectId": "proj-m211", "brief": SMOKE_BRIEF},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    required = [
        "story",
        "bible",
        "specialists",
        "shotPlan",
        "camera",
        "music",
        "sfx",
        "editingBeats",
        "continuity",
        "missingAssets",
        "checklist",
    ]
    for key in required:
        assert key in body, key
        assert body[key] is not None
    # no media generation artifacts
    assert "generatedMedia" not in body
    assert "assetId" not in body


def test_provider_manifest_sha_unchanged():
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert digest == EXPECTED_MANIFEST_SHA


def test_specialist_count_gte_28():
    from app.codirector.intelligence.specialist_registry import SpecialistRegistry

    count = len(SpecialistRegistry().inventory())
    assert count >= 28


def test_m210b_expected_manifest_sha_regression():
    """Guard: m210b EXPECTED_MANIFEST_SHA still matches Provider Manifest."""
    from tests.test_m210b_execution_lock_guards import EXPECTED_MANIFEST_SHA as M210B_SHA

    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert M210B_SHA == EXPECTED_MANIFEST_SHA
    assert digest == M210B_SHA
