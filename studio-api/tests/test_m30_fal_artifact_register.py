"""M3.0 Completion Phase 6: registering the already-paid-for fal artifact as an Asset.

The M3.0a live render cost real money once and must not be re-submitted. The script under
test turns that existing file into a project Asset carrying its fal provenance, and refuses
to do so if the bytes no longer match the digest recorded with the request id.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "m30_register_fal_artifact.py"


def load_script():
    spec = importlib.util.spec_from_file_location("m30_register_fal_artifact", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def script():
    return load_script()


@pytest.fixture()
def fake_artifact(tmp_path, script, monkeypatch: pytest.MonkeyPatch):
    """A stand-in for artifacts/m30a-fal/ so the test never depends on the real render."""
    video = tmp_path / "seedance_t2v_4s_480p.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"pretend-video-bytes" * 64)
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    summary = {
        "outcome": "verified",
        "engine": "fal_seedance",
        "model_id": "bytedance/seedance-2.0/text-to-video",
        "request_id": "019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc",
        "duration_sec": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "seed": 42,
        "artifact_path": "artifacts/m30a-fal/seedance_t2v_4s_480p.mp4",
        "file_size_bytes": video.stat().st_size,
        "sha256": digest,
        "completed_utc": "2026-07-27T05:15:50.453279Z",
    }
    summary_path = tmp_path / "live_proof_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(script, "VIDEO_PATH", video)
    monkeypatch.setattr(script, "SUMMARY_PATH", summary_path)
    return {"video": video, "summary": summary, "digest": digest}


@pytest.fixture()
def project():
    from app.db import Project, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        row = Project(id=str(uuid.uuid4()), name="M3.0 fal artifact test")
        db.add(row)
        db.commit()
        project_id = row.id
    finally:
        db.close()
    return project_id


def run(script, project_id: str, *extra: str) -> int:
    import sys

    argv = ["m30_register_fal_artifact.py", "--project-id", project_id, *extra]
    old = sys.argv
    sys.argv = argv
    try:
        return script.main()
    finally:
        sys.argv = old


def registered_assets(project_id: str):
    from app.db import Asset, SessionLocal

    db = SessionLocal()
    try:
        return db.query(Asset).filter(Asset.project_id == project_id).all()
    finally:
        db.close()


def test_registers_the_artifact_with_fal_provenance(script, fake_artifact, project) -> None:
    assert run(script, project) == 0

    assets = registered_assets(project)
    assert len(assets) == 1
    asset = assets[0]
    assert asset.kind == "video"
    assert asset.tag == "m30a-fal-live-proof"
    assert Path(asset.path).exists()
    assert Path(asset.path).read_bytes() == fake_artifact["video"].read_bytes()

    meta = json.loads(asset.prompt_meta_json)
    assert meta["request_id"] == fake_artifact["summary"]["request_id"]
    assert meta["model_id"] == "bytedance/seedance-2.0/text-to-video"
    assert meta["sha256"] == fake_artifact["digest"]
    assert meta["resubmitted"] is False
    assert meta["reused_existing_artifact"] is True


def test_second_run_is_a_no_op(script, fake_artifact, project) -> None:
    assert run(script, project) == 0
    assert run(script, project) == 0
    assert len(registered_assets(project)) == 1


def test_force_registers_another_copy(script, fake_artifact, project) -> None:
    assert run(script, project) == 0
    assert run(script, project, "--force") == 0
    assert len(registered_assets(project)) == 2


def test_digest_mismatch_is_refused(script, fake_artifact, project) -> None:
    fake_artifact["video"].write_bytes(b"different bytes entirely")

    assert run(script, project) == 3
    assert registered_assets(project) == []


def test_unknown_project_is_refused(script, fake_artifact) -> None:
    assert run(script, "not-a-project-id") == 2


def test_unverified_summary_is_refused(script, fake_artifact, project) -> None:
    summary = dict(fake_artifact["summary"], outcome="aborted")
    script.SUMMARY_PATH.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(SystemExit):
        run(script, project)
    assert registered_assets(project) == []


def test_the_real_artifact_still_matches_its_recorded_digest() -> None:
    """Guards the file the docs point at; skipped when the artifact is not checked out."""
    video = REPO_ROOT / "artifacts" / "m30a-fal" / "seedance_t2v_4s_480p.mp4"
    summary_path = REPO_ROOT / "artifacts" / "m30a-fal" / "live_proof_summary.json"
    if not video.exists() or not summary_path.exists():
        pytest.skip("M3.0a fal artifact not present")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(video.read_bytes()).hexdigest() == summary["sha256"]
    assert summary["outcome"] == "verified"
    assert summary["request_id"]
