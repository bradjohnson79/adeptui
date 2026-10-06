"""Journey 1 — Image Generator reference provenance contract.

Generate-with-reference jobs must carry the identity reference ids into job
params (``reference_ids``) so ``ImageProvenance.references`` records the
project authority assets (CRS/ERS/PRS/~GenericImage) that conditioned the
generation — not only the single edit-canvas source hash.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, Job, Project


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-refs", name="Reference Provenance Pin"))
    session.commit()
    yield session
    session.close()


def _no_enqueue(monkeypatch):
    """Stop before the queue loop; we only assert on the persisted job."""
    monkeypatch.setattr(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        lambda _job_id: None,
    )


def test_generate_with_references_stamps_reference_ids(db, monkeypatch):
    from app.image_product import service

    _no_enqueue(monkeypatch)
    crs_id = str(uuid.uuid4())
    ers_id = str(uuid.uuid4())
    generic_id = str(uuid.uuid4())

    try:
        service.generate_images(
            db,
            project_id="proj-refs",
            body={
                "prompt": "korri in the corridor",
                "modelFamilyPreference": "qwen2512",
                "referenceAssetIds": [crs_id, ers_id, generic_id],
            },
        )
    except Exception as exc:  # production dock / runtime maps may raise; job row is what matters
        if "never started" in str(exc):
            raise

    job = db.query(Job).filter(Job.project_id == "proj-refs").one()
    params = json.loads(job.params_json or "{}")
    ref_ids = list(params.get("reference_ids") or [])
    assert crs_id in ref_ids, "CRS identity reference must be in job reference_ids"
    assert ers_id in ref_ids, "ERS identity reference must be in job reference_ids"
    assert generic_id in ref_ids, "~GenericImage reference must be in job reference_ids"
    # The intent itself is the source of truth — reference_ids must mirror it.
    intent = params.get("imageIntent") or {}
    assert list(intent.get("referenceIds") or []) == ref_ids


def test_generate_without_references_has_empty_reference_ids(db, monkeypatch):
    from app.image_product import service

    _no_enqueue(monkeypatch)
    try:
        service.generate_images(
            db,
            project_id="proj-refs",
            body={"prompt": "a red cube"},
        )
    except Exception as exc:
        if "never started" in str(exc):
            raise

    job = db.query(Job).filter(Job.project_id == "proj-refs").one()
    params = json.loads(job.params_json or "{}")
    assert params.get("reference_ids") == [], "no references requested → empty reference_ids"
