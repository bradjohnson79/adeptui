"""M2.6.1 closed-loop acceptance — flows A-I + flag matrix smoke."""

from __future__ import annotations

import asyncio
import inspect
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.codirector.intelligence.schemas import ProductionPlan
from app.codirector.intelligence.store import IntelligenceStore
from app.codirector.vision.engine import run_validation
from app.codirector.vision.schemas import ReferenceSetBindingSpec, ReferenceSetSpec, ValidateRequest
from app.codirector.vision.store import VisionStore
from app.db import Asset, CoDirectorProductionPlan, SessionLocal, init_db
from app.director_references.errors import TimelineItemNotFound
from app.director_references.package import ReferencePackageBuilder
from app.director_references.roles import ROLE_TO_VALIDATOR
from app.director_references.service import TimelineReferenceService
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, MigrationRunner

from closed_loop_fixture import ClosedLoopFixture, seed_closed_loop_project
from flag_matrix import FLAG_MATRIX, FlagCombo, apply_flag_combo


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fixture(db: Session, monkeypatch: pytest.MonkeyPatch) -> ClosedLoopFixture:
    apply_flag_combo(
        monkeypatch,
        FlagCombo("full_loop", vision=True, references=True, intelligence=True),
    )
    return seed_closed_loop_project(db)


def _populate_image2_refs(db: Session, fx: ClosedLoopFixture) -> dict:
    svc = TimelineReferenceService(db)
    for asset_id, role, influence in (
        (fx.asset_identity, "character_identity", "strong"),
        (fx.asset_wardrobe, "costume", "moderate"),
        (fx.asset_environment, "environment", "moderate"),
        (fx.asset_lighting, "lighting", "loose"),
        (fx.asset_continuity, "continuity", "strong"),
    ):
        svc.add_binding(
            fx.project_id,
            fx.scene_id,
            fx.image2_id,
            reference_asset_id=asset_id,
            role=role,
            influence=influence,
        )
    return svc.get_references(fx.project_id, fx.scene_id, fx.image2_id)


@pytest.mark.parametrize("combo", FLAG_MATRIX, ids=lambda c: c.name)
def test_flag_matrix_health_honest(client: TestClient, monkeypatch: pytest.MonkeyPatch, combo: FlagCombo):
    apply_flag_combo(monkeypatch, combo)
    # Health reads app.feature_flags.feature_flags at call time via import.
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    op = body.get("operator") or {}
    assert bool(op.get("visionValidationEnabled")) is combo.vision
    assert bool(op.get("timelineReferencesEnabled")) is combo.references


def test_flow_a_primary_without_references(db: Session, fixture: ClosedLoopFixture):
    fx = fixture
    pkg = ReferencePackageBuilder(db).build(fx.project_id, fx.scene_id, fx.image1_id)
    assert pkg["primaryFrame"]["timelineItemId"] == fx.image1_id
    assert pkg["primaryFrame"]["displayTag"] == "@Image1"
    assert pkg["referenceSet"] is None
    check = ReferencePackageBuilder(db).validate_package(fx.project_id, fx.scene_id, fx.image1_id)
    assert check["blocksRun"] is False

    result = run_validation(
        db,
        ValidateRequest(
            projectId=fx.project_id,
            assetId=fx.asset_draft,
            sceneId=fx.scene_id,
            provider="mock",
            fixtureProfile="pass",
        ),
    )
    findings = result["report"]["findings"]
    assert not any(f.get("bindingId") for f in findings)


def test_flow_b_primary_with_reference_set(db: Session, fixture: ClosedLoopFixture):
    fx = fixture
    refs = _populate_image2_refs(db, fx)
    assert refs["activeVersion"] >= 1
    assert refs["count"] == 5
    pkg = ReferencePackageBuilder(db).build(fx.project_id, fx.scene_id, fx.image2_id)
    assert pkg["primaryFrame"]["role"] == "primary_frame"
    assert pkg["primaryFrame"]["assetId"] == fx.asset_primary_2
    assert pkg["referenceSet"] is not None
    assert pkg["referenceSet"]["version"] == refs["activeVersion"]
    binding_assets = {b["referenceAssetId"] for b in pkg["referenceSet"]["bindings"]}
    assert fx.asset_primary_2 not in binding_assets
    assert fx.asset_identity in binding_assets


def test_flow_c_cow_history_retains_versions(db: Session, fixture: ClosedLoopFixture):
    fx = fixture
    svc = TimelineReferenceService(db)
    v1 = svc.add_binding(
        fx.project_id,
        fx.scene_id,
        fx.image2_id,
        reference_asset_id=fx.asset_identity,
        role="character_identity",
        influence="strong",
    )
    assert v1["activeVersion"] == 1
    pkg_v1 = ReferencePackageBuilder(db).build(fx.project_id, fx.scene_id, fx.image2_id)
    assert pkg_v1["referenceSet"]["version"] == 1
    binding_id = v1["bindings"][0]["bindingId"]

    v2 = svc.patch_binding(
        fx.project_id,
        fx.scene_id,
        fx.image2_id,
        binding_id,
        influence="loose",
        expected_version=1,
    )
    assert v2["activeVersion"] == 2
    pkg_v2 = ReferencePackageBuilder(db).build(fx.project_id, fx.scene_id, fx.image2_id)
    assert pkg_v2["referenceSet"]["version"] == 2

    restored = svc.restore_version(fx.project_id, fx.scene_id, fx.image2_id, 1)
    assert restored["activeVersion"] == 3
    assert restored["bindings"][0]["influence"] == "strong"

    with pytest.raises(Exception) as exc:
        svc.patch_binding(
            fx.project_id,
            fx.scene_id,
            fx.image2_id,
            restored["bindings"][0]["bindingId"],
            influence="moderate",
            expected_version=1,
        )
    msg = str(exc.value).lower()
    code = getattr(exc.value, "code", "")
    assert code in {"version_conflict", "expected_version_mismatch", "conflict"} or "version" in msg


def test_flow_d_package_to_validate_binding_annotations(db: Session, fixture: ClosedLoopFixture):
    fx = fixture
    _populate_image2_refs(db, fx)
    pkg = ReferencePackageBuilder(db).build(fx.project_id, fx.scene_id, fx.image2_id)
    rs = pkg["referenceSet"]
    assert rs
    for b in rs["bindings"]:
        if b["role"] in ROLE_TO_VALIDATOR:
            assert ROLE_TO_VALIDATOR[b["role"]]

    ref_spec = ReferenceSetSpec(
        id=rs["id"],
        version=rs["version"],
        bindings=[
            ReferenceSetBindingSpec(
                bindingId=b["bindingId"],
                role=b["role"],
                influence=b.get("influence") or "moderate",
                assetId=b["referenceAssetId"],
            )
            for b in rs["bindings"]
        ],
    )
    result = run_validation(
        db,
        ValidateRequest(
            projectId=fx.project_id,
            assetId=fx.asset_draft,
            sceneId=fx.scene_id,
            referenceSet=ref_spec,
            provider="mock",
            fixtureProfile="warnings",
        ),
    )
    findings = result["report"]["findings"]
    annotated = [f for f in findings if f.get("bindingId")]
    assert annotated, "expected at least one finding annotated with bindingId"
    assert any(f.get("role") for f in annotated)


def test_flow_e_pending_cleared_only_by_vision(db: Session, fixture: ClosedLoopFixture):
    fx = fixture
    plan_id = f"plan-cl-{uuid.uuid4().hex[:8]}"
    plan = ProductionPlan(
        planId=plan_id,
        projectId=fx.project_id,
        title="Storyboard plan",
        visualValidationPending=True,
        requestId="req-cl-1",
    )
    IntelligenceStore.save_plan(db, plan=plan, status="draft")
    row = db.get(CoDirectorProductionPlan, plan_id)
    assert row is not None
    assert row.visual_validation_pending == 1

    TimelineReferenceService(db).add_binding(
        fx.project_id,
        fx.scene_id,
        fx.image1_id,
        reference_asset_id=fx.asset_identity,
        role="style",
    )
    db.refresh(row)
    assert row.visual_validation_pending == 1

    import app.director_references.package as pkg_mod
    import app.director_references.service as svc_mod

    assert "clear_visual_validation_pending" not in inspect.getsource(svc_mod)
    assert "clear_visual_validation_pending" not in inspect.getsource(pkg_mod)
    engine_mod = __import__("app.codirector.vision.engine", fromlist=["VisionEngine"])
    assert "clear_visual_validation_pending" in inspect.getsource(engine_mod.VisionEngine.run)
    assert "visual_validation_pending" in inspect.getsource(VisionStore.clear_visual_validation_pending)

    result = run_validation(
        db,
        ValidateRequest(
            projectId=fx.project_id,
            assetId=fx.asset_draft,
            planId=plan_id,
            provider="mock",
            fixtureProfile="pass",
        ),
    )
    assert result["session"]["status"] == "completed"
    db.refresh(row)
    assert row.visual_validation_pending == 0


def test_flow_f_codirector_tag_resolution(db: Session, fixture: ClosedLoopFixture):
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import timeline_references as tr

    fx = fixture
    _populate_image2_refs(db, fx)
    ctx = ToolContext(db=db, project_id=fx.project_id)

    listed = asyncio.run(tr.list_timeline_images(ctx, {"sceneId": fx.scene_id}))
    assert listed["count"] == 2
    by_tag = {i["displayTag"]: i for i in listed["images"]}
    assert by_tag["@Image1"]["referenceCount"] == 0
    assert by_tag["@Image2"]["referenceCount"] == 5

    resolved = asyncio.run(tr.get_timeline_image(ctx, {"sceneId": fx.scene_id, "displayTag": "@Image2"}))
    assert resolved["timelineItemId"] == fx.image2_id
    assert resolved["referenceSet"] is not None

    with pytest.raises(TimelineItemNotFound):
        asyncio.run(tr.get_timeline_image(ctx, {"sceneId": fx.scene_id, "displayTag": "@Image999"}))


def test_flow_g_proposal_only_reference_mutation(
    client: TestClient, db: Session, fixture: ClosedLoopFixture, monkeypatch: pytest.MonkeyPatch
):
    fx = fixture
    apply_flag_combo(
        monkeypatch,
        FlagCombo("full_loop", vision=True, references=True, intelligence=True),
    )
    before = TimelineReferenceService(db).get_references(fx.project_id, fx.scene_id, fx.image2_id)
    assert before["count"] == 0

    res = client.post(
        f"/api/codirector/projects/{fx.project_id}/tools/proposals",
        json={
            "toolId": "propose_add_reference_binding",
            "arguments": {
                "sceneId": fx.scene_id,
                "timelineItemId": fx.image2_id,
                "referenceAssetId": fx.asset_environment,
                "role": "environment",
                "influence": "moderate",
            },
        },
    )
    assert res.status_code == 200, res.text
    proposal = res.json()
    assert proposal["status"] == "pending"
    assert proposal["toolCall"]["toolId"] == "propose_add_reference_binding"

    mid = TimelineReferenceService(db).get_references(fx.project_id, fx.scene_id, fx.image2_id)
    assert mid["count"] == 0

    approve = client.post(
        f"/api/codirector/projects/{fx.project_id}/proposals/{proposal['id']}/approve",
        json={},
    )
    assert approve.status_code == 200, approve.text
    after = TimelineReferenceService(db).get_references(fx.project_id, fx.scene_id, fx.image2_id)
    assert after["count"] == 1
    assert after["activeVersion"] == 1
    assert after["bindings"][0]["role"] == "environment"


def test_flow_h_i_correction_approval_bible_boundary(db: Session, fixture: ClosedLoopFixture):
    from app.codirector.vision.approval import record_decision
    from app.codirector.vision.corrections import create_correction_proposal
    from app.codirector.vision.schemas import ValidationReport

    fx = fixture
    _populate_image2_refs(db, fx)
    pkg = ReferencePackageBuilder(db).build(fx.project_id, fx.scene_id, fx.image2_id)
    rs = pkg["referenceSet"]
    ref_spec = ReferenceSetSpec(
        id=rs["id"],
        version=rs["version"],
        bindings=[
            ReferenceSetBindingSpec(
                bindingId=b["bindingId"],
                role=b["role"],
                influence=b.get("influence") or "moderate",
                assetId=b["referenceAssetId"],
            )
            for b in rs["bindings"]
        ],
    )
    result = run_validation(
        db,
        ValidateRequest(
            projectId=fx.project_id,
            assetId=fx.asset_draft,
            sceneId=fx.scene_id,
            referenceSet=ref_spec,
            provider="mock",
            fixtureProfile="fail_technical",
        ),
    )
    report = ValidationReport.model_validate(result["report"])
    assert report.passed is False
    created = create_correction_proposal(db, project_id=fx.project_id, report=report, notes="fix loop")
    assert created["proposalId"]

    asset = db.get(Asset, fx.asset_draft)
    assert asset is not None
    assert asset.production_approval == "none"

    ok = run_validation(
        db,
        ValidateRequest(
            projectId=fx.project_id,
            assetId=fx.asset_draft,
            sceneId=fx.scene_id,
            provider="mock",
            fixtureProfile="pass",
        ),
    )
    session_id = ok["session"]["sessionId"]
    out = record_decision(
        db,
        project_id=fx.project_id,
        session_id=session_id,
        decision="approved",
        link_to_bible=True,
    )
    assert out["status"] == "approved"
    assert out["bibleLinkProposal"]["proposalId"]
    db.refresh(asset)
    assert asset.production_approval == "approved"


def test_migration_clean_install_has_m006_m007(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.db'}")
    runner = MigrationRunner(engine, DEFAULT_REGISTRY)
    result = runner.apply_pending()
    assert result.applied == ("M001", "M002", "M003", "M004", "M005", "M006", "M007", "M008", "M010")
    with engine.connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        }
    assert "codirector_validation_sessions" in tables
    assert "timeline_reference_sets" in tables
    assert "timeline_reference_bindings" in tables


def test_migration_upgrade_from_pre_m25(tmp_path):
    from app.migrations import M001, M002, M003, M004, M005, M010
    from app.migrations.registry import MigrationRegistry

    engine = create_engine(f"sqlite:///{tmp_path / 'upgrade.db'}")
    pre = MigrationRegistry((M001, M002, M003, M004, M005, M010))
    MigrationRunner(engine, pre).apply_pending()
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS scenes ("
                "id TEXT PRIMARY KEY, project_id TEXT, name TEXT, director_json TEXT, summary TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO scenes (id, project_id, name, director_json, summary) "
                "VALUES ('s1', 'p1', 'Keep Me', '{\"image_clips\":[]}', 'hello')"
            )
        )

    applied = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M006" in applied.applied
    assert "M007" in applied.applied
    with engine.connect() as conn:
        row = conn.execute(text("SELECT name, summary FROM scenes WHERE id='s1'")).fetchone()
        assert row is not None
        assert row[0] == "Keep Me"
        assert row[1] == "hello"
        tables = {
            r[0]
            for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        }
    assert "timeline_reference_sets" in tables
    assert "codirector_validation_sessions" in tables


def test_capability_bridge_maps_references_and_vision():
    from app.codirector.tools.capability_bridge import psr_ids_for_tool_key

    ref_ids = psr_ids_for_tool_key("references")
    assert "references.timeline_bindings" in ref_ids
    # IC-LoRA must not gate timeline reference tool readiness (honest probe lives in package builder).
    assert "references.ic_lora.ready" not in ref_ids
    vision_ids = psr_ids_for_tool_key("vision")
    assert "codirector.vision.validate" in vision_ids


def test_disabled_flags_are_not_operationally_ready():
    flags = FeatureFlags.from_env({})
    assert flags.vision_validation_v1 is False
    assert flags.timeline_references_v1 is False
    assert flags.codirector_intelligence_v2 is False
