"""Co-Director M2.7 Production Executive orchestration tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.orm import Session

from app.codirector.bible.proposals import ProposalService
from app.codirector.bible.schemas import BibleMutationSet, EntityMutation
from app.codirector.executive.contracts import validate_job_input
from app.codirector.executive.models import JobStatus, JobType
from app.codirector.executive.schemas import MarkApprovalRequest
from app.codirector.executive.service import ProductionExecutiveService
from app.codirector.executive.store import JobStore
from app.codirector.executive.worker import ProductionJobWorker
from app.db import Asset, CoDirectorExecutionReceipt, Job, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M008, M011, MigrationRunner
from sqlalchemy import create_engine


_TRUE = frozenset({"1", "true", "TRUE", "yes", "YES", "on", "ON"})


def _real_imagegen_stack_available() -> bool:
    """Honest probe for full closed-loop image path.

    Requires ADEPT_REQUIRE_REAL_IMAGEGEN=1 (opt-in) and live Comfy /system_stats.
    In-process pytest does not start the studio job_queue worker; do not claim pass
    without an explicit real-provider run. Never treat ADEPT_MOCK_IMAGEGEN as success.
    """
    if os.environ.get("ADEPT_REQUIRE_REAL_IMAGEGEN", "").strip() not in _TRUE:
        return False
    try:
        from app.codirector.executive.imagegen_adapter import comfy_available, should_use_mock_imagegen

        if should_use_mock_imagegen():
            return False
        return bool(comfy_available())
    except Exception:  # noqa: BLE001
        return False


requires_real_imagegen = pytest.mark.skipif(
    not _real_imagegen_stack_available(),
    reason=(
        "ComfyUI/vision stack unavailable or ADEPT_REQUIRE_REAL_IMAGEGEN not set — "
        "closed-loop/image tests require real providers (no mock)"
    ),
)


@pytest.fixture(autouse=True)
def _executive_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable vision validation for executive tests. Do not enable mock ImageGen."""
    monkeypatch.delenv("ADEPT_MOCK_IMAGEGEN", raising=False)
    monkeypatch.setenv("STUDIO_FEATURE_VISION_VALIDATION_V1", "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    session.merge(Project(id="proj-exec-1", name="Executive Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def worker(monkeypatch: pytest.MonkeyPatch) -> ProductionJobWorker:
    from app.codirector.executive import worker as worker_mod

    monkeypatch.setattr(worker_mod.production_worker, "start", lambda: None)
    worker_mod.production_worker.stop()
    w = ProductionJobWorker(poll_interval=0.05, max_concurrent=2)
    yield w
    w.stop()
    worker_mod.production_worker.stop()


def _closed_loop_jobs(db: Session, loop: dict) -> dict[str, object]:
    return {
        j["type"]: JobStore.get_job(db, j["id"])
        for j in loop["jobs"]
    }


def _proposal_id_from_loop(db: Session, loop: dict) -> str:
    jobs = _closed_loop_jobs(db, loop)
    prop_job = jobs[JobType.CREATE_PROPOSAL.value]
    assert prop_job is not None
    assert prop_job.result is not None
    proposal_id = prop_job.result.get("proposalId")
    assert proposal_id
    return str(proposal_id)


def test_feature_flag_defaults_off() -> None:
    flags = FeatureFlags.from_env({})
    assert flags.production_executive_v1 is False


def test_m008_registered_before_m010() -> None:
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M008" in revs
    assert M008.revision == "M008"
    assert revs.index("M007") < revs.index("M008") < revs.index("M010")
    assert "M011" in revs
    assert M011.revision == "M011"
    assert revs.index("M010") < revs.index("M011")


def test_production_context_immutable_and_sparse() -> None:
    from app.codirector.executive.production_context import ProductionContext

    ctx = ProductionContext(
        id="ctx-1",
        projectId="proj-1",
        sceneId="scene-1",
        createdAt="2026-07-25T00:00:00Z",
        initiatedBy="user",
    )
    d = ctx.to_dict()
    assert "shotId" not in d
    assert d["projectId"] == "proj-1"
    assert d["initiatedBy"] == "user"
    with pytest.raises(Exception):
        ctx.projectId = "other"  # type: ignore[misc]


def test_m011_migration_creates_context_tables(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'm011.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M011" in result.applied
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(production_jobs)").fetchall()
        }
    assert "production_contexts" in tables
    assert "production_context_extensions" in tables
    assert "production_context_id" in cols


def test_m008_migration_creates_tables(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'm008.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M008" in result.applied
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "production_jobs" in tables
    assert "production_job_attempts" in tables
    assert "production_job_dependencies" in tables
    assert "production_job_events" in tables
    assert "production_notifications" in tables
    assert "production_job_audit" in tables


def test_queue_order_by_priority(db: Session, worker: ProductionJobWorker) -> None:
    low = JobStore.create_job(
        db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", priority=200, payload={"n": 2}
    )
    high = JobStore.create_job(
        db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", priority=10, payload={"n": 1}
    )
    first = worker.tick_once(db)
    assert first == high.id
    second = worker.tick_once(db)
    assert second == low.id


def test_dependencies_block_until_complete(db: Session, worker: ProductionJobWorker) -> None:
    a = JobStore.create_job(
        db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", priority=10, payload={"step": "a"}
    )
    b = JobStore.create_job(
        db,
        job_type=JobType.GENERIC.value,
        project_id="proj-exec-1",
        priority=10,
        payload={"step": "b"},
        depends_on_job_ids=[a.id],
    )
    assert b.status == JobStatus.WAITING.value
    worker.tick_once(db)
    b2 = JobStore.get_job(db, b.id)
    assert b2 is not None
    assert b2.status in (JobStatus.WAITING.value, JobStatus.QUEUED.value, JobStatus.COMPLETED.value)
    worker.drain(max_steps=10)
    assert JobStore.get_job(db, a.id).status == JobStatus.COMPLETED.value
    assert JobStore.get_job(db, b.id).status == JobStatus.COMPLETED.value


def test_pause_resume_retry_cancel(db: Session, worker: ProductionJobWorker) -> None:
    job = JobStore.create_job(
        db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", payload={"x": 1}
    )
    paused = ProductionExecutiveService.pause(db, job.id, reason="hold")
    assert paused.status == JobStatus.PAUSED.value
    assert worker.tick_once(db) is None
    resumed = ProductionExecutiveService.resume(db, job.id)
    assert resumed.status == JobStatus.QUEUED.value
    worker.tick_once(db)
    assert JobStore.get_job(db, job.id).status == JobStatus.COMPLETED.value

    fail = JobStore.create_job(
        db,
        job_type=JobType.GENERIC.value,
        project_id="proj-exec-1",
        max_attempts=1,
        payload={"forceFail": True},
    )
    worker.tick_once(db)
    assert JobStore.get_job(db, fail.id).status == JobStatus.FAILED.value
    retried = ProductionExecutiveService.retry(db, fail.id)
    assert retried.status == JobStatus.RETRYING.value

    c = JobStore.create_job(
        db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", payload={"y": 1}
    )
    cancelled = ProductionExecutiveService.cancel(db, c.id)
    assert cancelled.status == JobStatus.CANCELLED.value


def test_crash_restart_recovery_no_duplicate_attempts(db: Session, worker: ProductionJobWorker) -> None:
    job = JobStore.create_job(
        db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", payload={"z": 1}
    )
    JobStore.transition(db, job.id, JobStatus.RUNNING.value, actor="test", reason="simulate")
    attempt = JobStore.begin_attempt(db, job.id, provider="local", capability_snapshot={})
    recovered = JobStore.recover_running_jobs(db)
    assert any(r.id == job.id for r in recovered)
    db.expire_all()
    job2 = JobStore.get_job(db, job.id)
    assert job2 is not None
    assert job2.status == JobStatus.RETRYING.value
    attempts = JobStore.list_attempts(db, job.id)
    assert len(attempts) == 1
    assert attempts[0].id == attempt.id
    assert attempts[0].outcome == "interrupted"
    steps = worker.drain(max_steps=5)
    assert steps >= 1
    attempts2 = JobStore.list_attempts(db, job.id)
    assert len(attempts2) == 2
    assert attempts2[0].outcome == "interrupted"
    assert attempts2[1].attemptN == 2
    assert JobStore.get_job(db, job.id).status == JobStatus.COMPLETED.value


def test_provider_unavailable_blocks(db: Session, worker: ProductionJobWorker) -> None:
    job = JobStore.create_job(
        db,
        job_type=JobType.IMAGE_GENERATE.value,
        project_id="proj-exec-1",
        capability_requirements=["comfyui.health"],
        payload={"mockUnavailableCapabilities": ["comfyui.health"]},
    )
    db.expire_all()
    assert worker.drain(max_steps=3) >= 1
    out = JobStore.get_job(db, job.id)
    assert out is not None
    assert out.status == JobStatus.BLOCKED.value
    assert out.blockedReason and "comfyui.health" in out.blockedReason


@requires_real_imagegen
def test_closed_loop_real_wiring_no_auto_approve(db: Session, worker: ProductionJobWorker) -> None:
    loop = ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="scene-1", provider="local"
    )
    assert len(loop["jobs"]) == 6
    worker.drain(max_steps=20)
    jobs = _closed_loop_jobs(db, loop)
    assert jobs[JobType.STORYBOARD_GENERATE.value].status == JobStatus.COMPLETED.value
    assert jobs[JobType.IMAGE_GENERATE.value].status == JobStatus.COMPLETED.value
    assert jobs[JobType.VALIDATE.value].status == JobStatus.COMPLETED.value
    assert jobs[JobType.CREATE_PROPOSAL.value].status == JobStatus.COMPLETED.value
    await_job = jobs[JobType.AWAIT_APPROVAL.value]
    assert await_job.status == JobStatus.NEEDS_REVIEW.value
    apply_job = jobs[JobType.APPLY_CANON.value]
    assert apply_job.status in (JobStatus.WAITING.value, JobStatus.QUEUED.value, JobStatus.BLOCKED.value)

    proposal_id = _proposal_id_from_loop(db, loop)
    prop_before = ProposalService.get(db, "proj-exec-1", proposal_id)
    assert prop_before.status == "pending"
    receipts_before = (
        db.query(CoDirectorExecutionReceipt)
        .filter(CoDirectorExecutionReceipt.proposal_id == proposal_id)
        .count()
    )
    assert receipts_before == 0
    assert apply_job.status != JobStatus.COMPLETED.value

    marked = ProductionExecutiveService.mark_approval(
        db,
        await_job.id,
        MarkApprovalRequest(proposalId=proposal_id, approved=True, actor="reviewer"),
    )
    assert marked.status == JobStatus.QUEUED.value
    worker.drain(max_steps=20)
    assert JobStore.get_job(db, await_job.id).status == JobStatus.COMPLETED.value
    apply_done = JobStore.get_job(db, apply_job.id)
    assert apply_done.status == JobStatus.COMPLETED.value
    assert apply_done.result is not None
    assert apply_done.result.get("applied") is True
    assert apply_done.result.get("receiptId")
    prop_after = ProposalService.get(db, "proj-exec-1", proposal_id)
    assert prop_after.status == "completed"


def test_contracts_validate_closed_loop_inputs() -> None:
    project_id = "proj-exec-1"
    cases = {
        JobType.STORYBOARD_GENERATE.value: {"sceneId": "scene-1", "provider": "local"},
        JobType.IMAGE_GENERATE.value: {"sceneId": "scene-1", "provider": "local"},
        JobType.VALIDATE.value: {"assetId": "asset-1", "provider": "local"},
        JobType.CREATE_PROPOSAL.value: {"sceneId": "scene-1", "assetId": "asset-1", "sessionId": "sess-1"},
        JobType.AWAIT_APPROVAL.value: {"proposalId": "prop-1", "proposalApproved": False},
        JobType.APPLY_CANON.value: {"proposalId": "prop-1", "proposalApproved": False},
    }
    for job_type, payload in cases.items():
        model = validate_job_input(job_type, payload, project_id=project_id)
        assert model is not None


@requires_real_imagegen
def test_image_generate_uses_job_asset_lifecycle(db: Session, worker: ProductionJobWorker) -> None:
    job = JobStore.create_job(
        db,
        job_type=JobType.IMAGE_GENERATE.value,
        project_id="proj-exec-1",
        scene_id="scene-img-1",
        provider="local",
        payload={"projectId": "proj-exec-1", "sceneId": "scene-img-1", "provider": "local"},
    )
    worker.drain(max_steps=10)
    done = JobStore.get_job(db, job.id)
    assert done is not None
    assert done.status == JobStatus.COMPLETED.value
    assert done.result is not None
    asset_id = done.result.get("assetId")
    assert asset_id
    asset = db.get(Asset, asset_id)
    assert asset is not None
    assert asset.project_id == "proj-exec-1"
    image_job_id = done.result.get("imageJobId")
    assert image_job_id
    studio_job = db.get(Job, image_job_id)
    assert studio_job is not None
    assert studio_job.status == "done"


@requires_real_imagegen
def test_await_approval_stays_needs_review_without_signal(
    db: Session, worker: ProductionJobWorker
) -> None:
    loop = ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="scene-await", provider="local"
    )
    worker.drain(max_steps=20)
    jobs = _closed_loop_jobs(db, loop)
    await_job = jobs[JobType.AWAIT_APPROVAL.value]
    apply_job = jobs[JobType.APPLY_CANON.value]
    assert await_job.status == JobStatus.NEEDS_REVIEW.value
    assert apply_job.status != JobStatus.COMPLETED.value
    proposal_id = _proposal_id_from_loop(db, loop)
    prop = ProposalService.get(db, "proj-exec-1", proposal_id)
    assert prop.status == "pending"


def test_apply_canon_blocked_without_approval(db: Session, worker: ProductionJobWorker) -> None:
    prop = ProposalService.create_proposal(
        db,
        project_id="proj-exec-1",
        proposal_type="entity_create",
        title="t",
        summary="s",
        payload=BibleMutationSet(
            entityMutations=[
                EntityMutation(
                    entityType="production_decision",
                    entityKey="k",
                    displayName="d",
                    data={"decision": "hold", "rationale": "test"},
                )
            ]
        ),
    )
    job = JobStore.create_job(
        db,
        job_type=JobType.APPLY_CANON.value,
        project_id="proj-exec-1",
        payload={
            "proposalId": prop.id,
            "proposalApproved": False,
            "projectId": "proj-exec-1",
        },
    )
    worker.tick_once(db)
    assert JobStore.get_job(db, job.id).status == JobStatus.BLOCKED.value


@requires_real_imagegen
def test_mark_approval_auto_approved_false_api(client, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.executive import worker as worker_mod

    monkeypatch.setattr(worker_mod.production_worker, "start", lambda: None)
    os.environ["STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1"] = "1"
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    try:
        loop = client.post(
            "/api/codirector/jobs/closed-loop",
            json={
                "projectId": "proj-exec-1",
                "sceneId": "scene-api-1",
                "provider": "local",
            },
        )
        assert loop.status_code == 200, loop.text
        loop_body = loop.json()
        await_job = next(j for j in loop_body["jobs"] if j["type"] == JobType.AWAIT_APPROVAL.value)
        drain = client.post("/api/codirector/jobs/worker/drain", json={"maxSteps": 40})
        assert drain.status_code == 200
        prop_job = next(j for j in loop_body["jobs"] if j["type"] == JobType.CREATE_PROPOSAL.value)
        prop_inspect = client.get(f"/api/codirector/jobs/{prop_job['id']}")
        assert prop_inspect.status_code == 200
        proposal_id = prop_inspect.json()["job"]["result"]["proposalId"]
        approve = client.post(
            f"/api/codirector/jobs/{await_job['id']}/mark-approval",
            json={"proposalId": proposal_id, "approved": True, "actor": "pytest"},
        )
        assert approve.status_code == 200
        body = approve.json()
        assert body.get("autoApproved") is False
    finally:
        os.environ.pop("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", None)
        ff.feature_flags = FeatureFlags.from_env(os.environ)


def test_worker_poll_interval_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_PRODUCTION_EXECUTIVE_POLL_INTERVAL", "0.5")
    w = ProductionJobWorker()
    assert w.poll_interval == 0.5


@requires_real_imagegen
def test_chain_propagates_asset_and_proposal_ids(db: Session, worker: ProductionJobWorker) -> None:
    loop = ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="scene-chain", provider="local"
    )
    worker.drain(max_steps=20)
    jobs = _closed_loop_jobs(db, loop)
    image = jobs[JobType.IMAGE_GENERATE.value]
    validate = jobs[JobType.VALIDATE.value]
    prop = jobs[JobType.CREATE_PROPOSAL.value]
    await_job = jobs[JobType.AWAIT_APPROVAL.value]

    assert image.result is not None
    asset_id = image.result.get("assetId")
    assert asset_id

    assert validate.payload.get("assetId") == asset_id or validate.result.get("assetId") == asset_id
    assert prop.result is not None
    proposal_id = prop.result.get("proposalId")
    assert proposal_id
    assert await_job.payload.get("proposalId") == proposal_id


def test_idempotency_duplicate_create(db: Session) -> None:
    a = JobStore.create_job(
        db,
        job_type=JobType.GENERIC.value,
        project_id="proj-exec-1",
        idempotency_key="idem-1",
        payload={"v": 1},
    )
    b = JobStore.create_job(
        db,
        job_type=JobType.GENERIC.value,
        project_id="proj-exec-1",
        idempotency_key="idem-1",
        payload={"v": 2},
    )
    assert a.id == b.id


def test_concurrent_jobs_drain(db: Session, worker: ProductionJobWorker) -> None:
    ids = [
        JobStore.create_job(
            db, job_type=JobType.GENERIC.value, project_id="proj-exec-1", priority=i, payload={"i": i}
        ).id
        for i in range(5)
    ]
    worker.drain(max_steps=20)
    for job_id in ids:
        assert JobStore.get_job(db, job_id).status == JobStatus.COMPLETED.value


def test_api_flag_off_404(client) -> None:
    os.environ.pop("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", None)
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    res = client.get("/api/codirector/jobs?projectId=proj-exec-1")
    assert res.status_code == 404


def test_api_flag_on_create_and_inspect(client, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.executive import worker as worker_mod

    monkeypatch.setattr(worker_mod.production_worker, "start", lambda: None)
    os.environ["STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1"] = "1"
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    try:
        res = client.post(
            "/api/codirector/jobs",
            json={
                "type": "generic",
                "projectId": "proj-exec-1",
                "priority": 5,
                "payload": {"hello": True},
            },
        )
        assert res.status_code == 200, res.text
        job_id = res.json()["job"]["id"]
        got = client.get(f"/api/codirector/jobs/{job_id}?projectId=proj-exec-1")
        assert got.status_code == 200
        drain = client.post("/api/codirector/jobs/worker/drain", json={"maxSteps": 10})
        assert drain.status_code == 200
        hist = client.get(f"/api/codirector/jobs/{job_id}/history")
        assert hist.status_code == 200
        assert len(hist.json()["attempts"]) >= 1
        audit = hist.json()["audit"]
        assert any(a["toStatus"] == "Completed" for a in audit)
    finally:
        os.environ.pop("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", None)
        ff.feature_flags = FeatureFlags.from_env(os.environ)


def test_scene_progress_derived(db: Session, worker: ProductionJobWorker) -> None:
    JobStore.create_job(
        db,
        job_type=JobType.GENERIC.value,
        project_id="proj-exec-1",
        scene_id="sc-1",
        payload={},
    )
    JobStore.create_job(
        db,
        job_type=JobType.GENERIC.value,
        project_id="proj-exec-1",
        scene_id="sc-1",
        payload={"forceFail": True},
        max_attempts=1,
    )
    worker.drain(max_steps=10)
    progress = JobStore.scene_progress(db, "proj-exec-1", "sc-1")
    assert progress.derivedFromJobs is True
    assert progress.totalJobs == 2
    assert progress.completed == 1
    assert progress.failed == 1

def test_closed_loop_creates_production_context(db: Session) -> None:
    loop = ProductionExecutiveService.create_closed_loop(
        db, project_id="proj-exec-1", scene_id="scene-ctx", provider="local", owner="tester"
    )
    assert loop.get("productionContext")
    assert loop["productionContext"]["projectId"] == "proj-exec-1"
    assert loop["productionContext"]["sceneId"] == "scene-ctx"
    assert loop["productionContext"]["initiatedBy"] == "tester"
    assert "shotId" not in loop["productionContext"]
    jobs = loop["jobs"]
    assert len(jobs) == 6
    ctx_id = loop["productionContext"]["id"]
    for j in jobs:
        assert j.get("productionContextId") == ctx_id
        assert j["payload"].get("productionContext", {}).get("id") == ctx_id
    # Immutability: frozen dataclass round-trip
    from app.codirector.executive.production_context import (
        append_context_extension,
        load_production_context,
    )

    loaded = load_production_context(db, ctx_id)
    assert loaded is not None
    snap_before = loaded.to_dict()
    append_context_extension(
        db, ctx_id, extension_type="fact", payload={"k": "v"}, actor="tester"
    )
    loaded2 = load_production_context(db, ctx_id)
    assert loaded2 is not None
    assert loaded2.to_dict() == snap_before

