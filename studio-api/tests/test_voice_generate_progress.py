"""Honest Voice Creator generation progress (no decorative 100%)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.service import create_profile, ensure_character_identity_tables
from app.character_identity.voice_generate_job import (
    derive_percent,
    load_job,
    phase_label,
    start_job,
    update_job,
)
from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def _apply_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def db(monkeypatch: pytest.MonkeyPatch) -> Session:
    _apply_flags(monkeypatch)
    init_db()
    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


def _project(db: Session, name: str) -> str:
    pid = f"voice-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def test_derive_percent_never_100_until_complete():
    assert derive_percent(phase="preparing", sample_count=3, completed_samples=0) == 6
    assert derive_percent(phase="analyzing_voice", sample_count=3, completed_samples=0) == 12
    assert derive_percent(phase="preparing_model", sample_count=3, completed_samples=0) == 18
    first = derive_percent(phase="generating_sample", sample_count=3, completed_samples=0)
    second = derive_percent(phase="generating_sample", sample_count=3, completed_samples=1)
    third = derive_percent(phase="generating_sample", sample_count=3, completed_samples=2)
    assert 18 <= first < second < third < 100
    four = derive_percent(phase="generating_sample", sample_count=4, completed_samples=1)
    assert four < 50
    assert derive_percent(phase="saving", sample_count=3, completed_samples=3) == 96
    assert derive_percent(phase="failed", sample_count=3, completed_samples=1) < 100
    assert derive_percent(phase="complete", sample_count=3, completed_samples=3) == 100
    assert "sample 2 of 3" in phase_label("generating_sample", sample_index=2, sample_count=3).lower()


def test_start_job_reuses_live_job(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.character_identity.voice_generate_job._run_job",
        lambda *args, **kwargs: None,
    )
    project_id = _project(db, "Voice")
    profile = create_profile(db, project_id, CharacterProfileCreate(name="Cade", slug="cade-voice"))
    first = start_job(
        db,
        project_id,
        profile.id,
        mode="clone",
        payload={"name": "Cade Clone", "sampleCount": 1, "consent": {"consent_confirmed": True}},
        sample_count=1,
    )
    assert first["status"] in {"queued", "running"}
    assert first["percent"] < 100
    second = start_job(
        db,
        project_id,
        profile.id,
        mode="clone",
        payload={"name": "Cade Clone", "sampleCount": 1, "consent": {"consent_confirmed": True}},
        sample_count=1,
    )
    assert second["jobId"] == first["jobId"]
    failed = update_job(db, profile.id, first["jobId"], status="failed", phase="failed", error="GPU busy")
    assert failed["phase"] == "failed"
    assert failed["percent"] < 100
    assert failed["status"] == "failed"
    stored = load_job(db, profile.id)
    assert stored["error"] == "GPU busy"
    assert stored["percent"] < 100
