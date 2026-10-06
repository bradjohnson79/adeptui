"""Visual-sheet pack reconcile pin — pack is a projection of Job rows.

Isolated sqlite only. Does not touch live Schnick, does not POST generate,
does not invent Library assets, and does not rewrite approved CRS identity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity.models import CharacterReferenceAssetRow
from app.character_identity.visual_sheet import (
    _save_pack,
    get_visual_sheet_pack,
    reconcile_generating_visual_sheet_packs,
)
from app.db import Asset, Base, Job, Project


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
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-sheet", name="Sheet Reconcile"))
    session.commit()
    yield session
    session.close()


def test_get_heals_generating_pack_when_child_jobs_terminal(db, tmp_path):
    """GENERATING + all child jobs done/cancelled → GET sets terminal pack status.

    Approved identity / pack crsRevision stay put. No new Library assets.
    """
    profile = service.seed_korri_from_canon(db, "proj-sheet")

    approved_asset_id = "b6ab91dd-0000-4000-8000-approved03"
    png = tmp_path / "approved.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    db.add(
        Asset(
            id=approved_asset_id,
            project_id="proj-sheet",
            tag="korri_approved_sheet",
            kind="image",
            filename="approved.png",
            path=str(png),
        )
    )
    db.add(
        CharacterReferenceAssetRow(
            id="c49371ed-0000-4000-8000-ref00001",
            character_profile_id=profile.id,
            asset_id=approved_asset_id,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()
    approved_before = service.resolve_approved_reference(db, profile.id, "hero_identity")
    assert approved_before == approved_asset_id

    # Stale pack projection: 6 queued/running + 1 failed; Job rows already terminal.
    child_specs = [
        ("11d17e2d-0000-4000-8000-child0001", "running", "done"),
        ("9cc051e6-0000-4000-8000-child0002", "queued", "done"),
        ("00ba9f40-0000-4000-8000-child0003", "queued", "done"),
        ("cc69550d-0000-4000-8000-child0004", "queued", "done"),
        ("50f2dafe-0000-4000-8000-child0005", "queued", "done"),
        ("bbbdd3d1-0000-4000-8000-child0006", "queued", "done"),
        ("1f37721d-0000-4000-8000-child0007", "failed", "cancelled"),
    ]
    children = []
    for jid, pack_status, db_status in child_specs:
        db.add(
            Job(
                id=jid,
                project_id="proj-sheet",
                kind="imagegen",
                status=db_status,
                params_json=json.dumps({}),
            )
        )
        children.append({"jobId": jid, "status": pack_status})
    db.commit()

    pack = {
        "schema_version": 2,
        "status": "GENERATING",
        "characterId": profile.id,
        "projectId": "proj-sheet",
        "jobs": {
            "hero": dict(children[0]),
            "hero_candidates": [dict(c) for c in children],
        },
        "candidates": [dict(c) for c in children],
        "roleAssets": {"hero_identity": approved_asset_id},
        "approvedHeroIdentity": approved_asset_id,
        "crsRevision": 37,
        "phase": "hero",
    }
    _save_pack(db, "proj-sheet", profile.id, pack)
    assets_before = {row.id for row in db.query(Asset).all()}

    hydrated = get_visual_sheet_pack(db, "proj-sheet", profile.id)

    assert hydrated["status"] != "GENERATING"
    assert hydrated["status"] == "CANCELLED"
    assert hydrated.get("crsRevision") == 37
    assert hydrated.get("approvedHeroIdentity") == approved_asset_id
    assert service.resolve_approved_reference(db, profile.id, "hero_identity") == approved_before
    assert {row.id for row in db.query(Asset).all()} == assets_before

    synced = [c.get("status") for c in (hydrated.get("jobs") or {}).get("hero_candidates") or []]
    assert synced == ["done", "done", "done", "done", "done", "done", "cancelled"]
    assert db.query(Job).filter(Job.status.in_(["queued", "running"])).count() == 0

    # Startup hook is the same recompute; already-terminal pack is a no-op heal.
    n = reconcile_generating_visual_sheet_packs(db)
    assert n == 0
    again = get_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert again["status"] == "CANCELLED"
    assert again.get("approvedHeroIdentity") == approved_asset_id
    assert again.get("crsRevision") == 37
