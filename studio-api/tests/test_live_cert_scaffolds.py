"""CDX-093 — LIVE certification layer scaffolds (opt-in via ADEPT_LIVE_CERT=1).

The default conftest `client` fixture mocks `api.job_queue.enqueue` with an
AsyncMock, so no API test proves the REAL enqueue path. This module provides
one live-path scaffold per generation subsystem (character, prop, scene, ERS).

Every test here:
- requests the `live_cert` gate fixture -> SKIPPED by default;
- uses `live_cert_client` -> the REAL `job_queue.enqueue` (no mock);
- drives the subsystem's real job-submission path;
- asserts the job row was durably persisted AND the job id reached the real
  job queue (queue receipt), i.e. the exact behavior the conftest mock used to
  hide.

The provider RESOLUTION layer is pinned via the standard mock-provider env
(STUDIO_E2E=1 / ADEPT_CODIRECTOR_PROVIDER=mock, same as every other codirector
test); only the ENQUEUE is exercised for real. No default test is turned into
live generation — these tests never run unless the operator sets the flag.

TESTS ONLY. No app/ source is modified here.
"""

from __future__ import annotations

import json
import uuid

import pytest


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


@pytest.fixture()
def db():
    from app.db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(client, name: str = "Live Cert Project") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _seed_image_asset(db, project_id: str) -> str:
    """Insert a real image Asset row (no network upload; the character-sheet
    route only requires an image-kind asset in the project)."""
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="ref",
            kind="image",
            filename="ref.png",
            path="ref.png",
        )
    )
    db.commit()
    return asset_id


def _real_queue_contains(job_queue, job_id: str) -> bool:
    """True when the job id was actually put on the real asyncio queue.

    The AsyncMock used by the default client fixture never puts anything on the
    queue, so a receipt here is direct evidence the REAL enqueue path ran.
    """
    q = job_queue._q
    try:
        return job_id in list(q._queue)
    except Exception:  # noqa: BLE001 - queue internals may differ across versions
        return q.qsize() >= 1


def _assert_real_enqueue(db, job_id: str) -> None:
    """Prove the REAL enqueue path: durable Job row + real queue receipt."""
    from app.db import Job
    from app.queue_worker import job_queue

    row = db.get(Job, job_id)
    assert row is not None, f"job {job_id} was not durably created by the real path"
    assert row.status == "queued", f"job {job_id} expected queued, got {row.status}"
    assert _real_queue_contains(job_queue, job_id), (
        f"job {job_id} never reached the real job queue — enqueue was mocked"
    )


# ==========================================================================
# Character subsystem — POST /api/projects/{pid}/tools/character-sheet
# ==========================================================================


def test_character_subsystem_real_enqueue(live_cert_client, mock_provider_env) -> None:
    """The character-sheet route durably creates a character_sheet job and
    enqueues it through the REAL job_queue when the live-cert flag is set."""
    project_id = _create_project(live_cert_client)
    db = _session()
    try:
        asset_id = _seed_image_asset(db, project_id)
        res = live_cert_client.post(
            f"/api/projects/{project_id}/tools/character-sheet",
            json={"source_asset_id": asset_id, "character_name": "Ava"},
        )
        assert res.status_code == 200, res.text
        job_id = res.json()["id"]
        assert job_id
        from app.db import Job

        _assert_real_enqueue(db, job_id)
        row = db.get(Job, job_id)
        assert row.kind == "character_sheet"
    finally:
        db.close()


# ==========================================================================
# Prop subsystem — POST /api/prop-creator/projects/{pid}/props/{id}/generate
# ==========================================================================


def test_prop_subsystem_real_enqueue(live_cert_client, mock_provider_env, monkeypatch) -> None:
    """Prop Candidate generation funnels through the real image-product enqueue
    (enqueue_imagegen_job -> generate_images -> schedule_job_queue_enqueue)."""
    from app.prop_creator import generation as prop_gen

    # Runtime probe only (list_local_generator_families); the ENQUEUE stays real.
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )

    project_id = _create_project(live_cert_client)
    created = live_cert_client.post(
        f"/api/prop-creator/projects/{project_id}/props",
        json={"name": "Coffee Mug", "visual_style": "live_action", "description": "White ceramic mug with a chip."},
    )
    assert created.status_code == 200, created.text
    prop_id = created.json()["prop"]["id"]

    gen = live_cert_client.post(
        f"/api/prop-creator/projects/{project_id}/props/{prop_id}/generate",
        json={"local_enabled": True, "api_enabled": False, "candidate_count": 1},
    )
    assert gen.status_code == 200, gen.text
    candidates = gen.json()["prop"]["candidates"]
    queued = [c for c in candidates if c["status"] == "queued"]
    assert queued, f"no queued prop candidates produced: {candidates}"

    db = _session()
    try:
        from app.db import Job

        for cand in queued:
            _assert_real_enqueue(db, cand["job_id"])
            row = db.get(Job, cand["job_id"])
            assert row.kind == "imagegen"
    finally:
        db.close()


# ==========================================================================
# Scene subsystem — POST /api/projects/{pid}/timeline/apply (enqueue_render)
# ==========================================================================


def test_scene_subsystem_real_enqueue(live_cert_client, mock_provider_env) -> None:
    """Timeline apply with enqueue_render=true durably creates a render_timeline
    job and enqueues it through the REAL job_queue."""
    project_id = _create_project(live_cert_client)
    res = live_cert_client.post(
        f"/api/projects/{project_id}/timeline/apply",
        json={
            "scenes": [
                {
                    "name": "Opening",
                    "prompt": "Wide establishing shot of the flooded city.",
                    "duration_sec": 5.0,
                    "engine": "ltx",
                    "camera_note": "",
                }
            ],
            "replace_existing": True,
            "enqueue_render": True,
        },
    )
    assert res.status_code == 200, res.text
    job_id = res.json().get("job_id")
    assert job_id, res.text
    db = _session()
    try:
        from app.db import Job

        _assert_real_enqueue(db, job_id)
        row = db.get(Job, job_id)
        assert row.kind == "render_timeline"
    finally:
        db.close()


# ==========================================================================
# ERS subsystem — real ERS image-product enqueue (mirrors the handler's
# _enqueue_ers_image_product: storyboard_jobs.enqueue_imagegen_job with
# purpose=environment_reference_sheet)
# ==========================================================================


def test_ers_subsystem_real_enqueue(live_cert_client, mock_provider_env) -> None:
    """The ERS enqueue funnel durably creates an imagegen job carrying
    purpose=environment_reference_sheet and puts it on the REAL job queue."""
    project_id = _create_project(live_cert_client)
    db = _session()
    try:
        from app.storyboard_jobs import enqueue_imagegen_job

        job = enqueue_imagegen_job(
            db,
            project_id,
            {
                "prompt": "Environment reference sheet of one locked environment.",
                "purpose": "environment_reference_sheet",
                "source": "local",
                "model": "qwen2512",
                "modelFamilyPreference": "qwen2512",
                "lockModelFamily": True,
                "sourceAssetId": "atlas-live-cert-1",
                "source_asset_id": "atlas-live-cert-1",
                "width": 1280,
                "height": 720,
            },
        )
        params = json.loads(job.params_json or "{}")
        assert params.get("purpose") == "environment_reference_sheet"
        _assert_real_enqueue(db, job.id)
        assert job.kind == "imagegen"
    finally:
        db.close()
