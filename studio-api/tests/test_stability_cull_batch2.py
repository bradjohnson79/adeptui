"""Stability Cull Batch 2 — readiness, bind-or-fail, SenseNova honesty."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.image_runtime.workflow_execute import legacy_comfy_workflow_key
from app.workflows.readiness import WORKFLOW_MODEL_COMPONENTS, workflow_readiness
from app.workflows.sensenova_u15 import inspect_weights
from app.image_runtime.certified_registry import get_workflow
from app.queue_worker import JobQueue
from app.db import Job, Project, SessionLocal


def test_foreign_families_do_not_alias_to_zimage():
    assert legacy_comfy_workflow_key("zimage.txt2img") == "zimage.txt2img"
    assert legacy_comfy_workflow_key("flux.txt2img") == "flux.txt2img"
    assert legacy_comfy_workflow_key("qwen2512.txt2img") == "qwen2512.txt2img"
    assert legacy_comfy_workflow_key("illustrious.txt2img") == "illustrious.txt2img"
    assert legacy_comfy_workflow_key("sensenova.crs") == "sensenova.crs"
    assert "zimage_models" not in WORKFLOW_MODEL_COMPONENTS["flux.txt2img"]
    assert "zimage_models" not in WORKFLOW_MODEL_COMPONENTS["qwen2512.txt2img"]


def test_flux_readiness_does_not_use_zimage_components():
    report = workflow_readiness(
        "flux.txt2img",
        node_types={"UNETLoader", "CLIPTextEncode"},
        model_states={"flux1_kontext_dev_local": False, "flux1_dev_local": False, "zimage_models": True},
    )
    assert report["status"] == "blocked"
    assert report["reasonCode"] == "WORKFLOW_MISSING_MODELS"


def test_flux_ready_when_either_flux_component_present():
    report = workflow_readiness(
        "flux.txt2img",
        node_types=set(),
        model_states={"flux1_kontext_dev_local": False, "flux1_dev_local": True},
    )
    assert report["status"] in {"ready", "unknown"}
    assert report["reasonCode"] != "WORKFLOW_MISSING_MODELS"


def test_illustrious_null_hash_is_not_a_silent_zimage_alias():
    leaf = get_workflow("illustrious.txt2img")
    assert leaf is not None
    assert legacy_comfy_workflow_key("illustrious.txt2img") != "image.txt2img"
    # Null graphHash is an accepted fingerprint gap — do not treat as Z-Image ready.
    if not (leaf.fingerprints or {}).get("graphHash"):
        assert "illustrious" in (leaf.workflow_key or "illustrious.txt2img")


def test_sensenova_disk_is_not_runtime_ready():
    probe = inspect_weights()
    assert probe.get("runtimeReady") is False


def test_bind_prompt_rejects_empty():
    q = JobQueue()
    try:
        q.bind_prompt("job-x", "")
        raise AssertionError("empty prompt_id must fail")
    except RuntimeError as exc:
        assert "empty" in str(exc).lower()


def test_fail_unbound_running_claimed():
    from app.db import init_db

    init_db()
    db = SessionLocal()
    try:
        db.merge(Project(id="p-cull-1", name="Cull"))
        job = Job(
            id="j-unbound",
            project_id="p-cull-1",
            kind="imagegen",
            status="running",
            stage="claimed",
            message="claimed",
            comfy_prompt_id=None,
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(job)
        db.commit()
    finally:
        db.close()

    q = JobQueue()
    failed = q.fail_unbound_running(older_than_sec=1)
    assert "j-unbound" in failed
