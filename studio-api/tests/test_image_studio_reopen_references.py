"""Journey 1 — reopen (reload) restores the full reference set + provenance.

Persistence law: saved references must survive reload. ``reopen_from_asset``
rebuilds the creator's setup from the persisted job/asset — the reference
authority ids (Characters / Props / Environment / ~GenericImage) must all
round-trip.
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

from app.db import Asset, Base, Job, Project


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.config import settings
    from app.image_studio import provenance as reopen_module

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-reopen", name="Reopen References Pin"))
    session.commit()
    # reopen_from_asset opens its own SessionLocal() — point it at this engine
    # so the in-memory tables are shared, not a fresh empty DB.
    monkeypatch.setattr(reopen_module, "SessionLocal", Session)
    yield session
    session.close()


def _persisted_generation(db, *, ref_ids):
    """Persist an imagegen job + its committed asset the way the worker does."""
    crs_id, ers_id, generic_id = ref_ids
    job_id = str(uuid.uuid4())
    params = {
        "prompt": "korri in the corridor",
        "negative": "",
        "reference_ids": [crs_id, ers_id, generic_id],
        "imageIntent": {
            "prompt": "korri in the corridor",
            "referenceIds": [crs_id, ers_id, generic_id],
            "enginePreference": "zimage",
            "metadata": {"aspect": "16:9"},
        },
        "output_asset_id": None,
    }
    job = Job(
        id=job_id,
        project_id="proj-reopen",
        kind="imagegen",
        status="done",
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()

    asset_id = str(uuid.uuid4())
    meta = {
        "jobId": job_id,
        "provenance": {"references": [crs_id, ers_id, generic_id]},
        "imageIntent": params["imageIntent"],
    }
    asset = Asset(
        id=asset_id,
        project_id="proj-reopen",
        tag="imagegen",
        kind="image",
        filename=f"{asset_id}.png",
        path=f"/tmp/{asset_id}.png",
        prompt_meta_json=json.dumps(meta),
    )
    db.add(asset)
    db.commit()
    return asset_id


def test_reopen_restores_all_reference_authority_ids(db):
    from app.image_studio.provenance import reopen_from_asset

    crs_id = str(uuid.uuid4())
    ers_id = str(uuid.uuid4())
    generic_id = str(uuid.uuid4())
    asset_id = _persisted_generation(db, ref_ids=(crs_id, ers_id, generic_id))

    reopened = reopen_from_asset("proj-reopen", asset_id)
    assert reopened is not None, "reopen payload must exist for a persisted generation"

    refs = reopened.get("referenceAssetIds") or []
    assert crs_id in refs, "Character (CRS) reference must survive reload"
    assert ers_id in refs, "Environment (ERS) reference must survive reload"
    assert generic_id in refs, "~GenericImage reference must survive reload"
    assert reopened.get("prompt") == "korri in the corridor"


def test_reopen_rejects_cross_project_asset(db):
    from app.image_studio.provenance import reopen_from_asset

    crs_id, ers_id, generic_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    asset_id = _persisted_generation(db, ref_ids=(crs_id, ers_id, generic_id))

    reopened = reopen_from_asset("proj-other", asset_id)
    assert reopened is None, "reopen must not leak assets across project boundaries"
