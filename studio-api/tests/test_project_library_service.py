"""Service-layer Studio Project Library behavior."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.project_library import system_folder_id
from app.project_library.service import (
    assign_asset,
    compute_content_hash,
    find_duplicates_by_hash,
    read_asset_library_meta,
)


def _create_project(client, name: str = "Library Service Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def test_find_duplicates_by_content_hash(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        content = b"duplicate-content-bytes"
        asset_ids = []
        for idx in range(2):
            asset_id = str(uuid.uuid4())
            dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

            asset = Asset(
                id=asset_id,
                project_id=project_id,
                kind="audio",
                tag="music",
                filename=f"dup{idx}.wav",
                path=str(dest),
            )
            db.add(asset)
            db.commit()
            assign_asset(db, asset, system_key="audio.music")
            asset_ids.append(asset_id)

        content_hash = compute_content_hash(
            isolated_data_dir / "assets" / project_id / f"{asset_ids[0]}.wav"
        )
        assert content_hash
        dupes = find_duplicates_by_hash(db, project_id, content_hash)
        assert len(dupes) == 2
        assert {a.id for a in dupes} == set(asset_ids)
    finally:
        db.close()


def test_usd_assign_is_deferred_version_1_2_not_failure(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.usd"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-usd")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="model",
            tag="",
            filename="hero.usd",
            path=str(dest),
        )
        db.add(asset)
        db.commit()

        meta = assign_asset(db, asset)
        # CDX-073: committed classify.py assigns DEFERRED_VERSION_1_2 to native
        # 3D (deferred to v1.2, not a technical failure / NOT_APPLICABLE).
        assert meta.classification.subtype == "DEFERRED_VERSION_1_2"
        assert meta.folder_system_key == "miscellaneous"
        assert meta.canonical_folder_id == system_folder_id("miscellaneous")
        assert "Version 1.2" in meta.classification.reason

        reloaded = read_asset_library_meta(db.get(Asset, asset_id))
        assert reloaded.classification.subtype == "DEFERRED_VERSION_1_2"
    finally:
        db.close()


def test_override_blocks_auto_reclassify(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"override-lock")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="audio",
            tag="music",
            filename="locked.wav",
            path=str(dest),
        )
        db.add(asset)
        db.commit()

        assign_asset(db, asset, system_key="audio.music", override=True, classified_by="manual")
        locked = read_asset_library_meta(asset)
        assert locked.folder_system_key == "audio.music"
        assert locked.override is True

        assign_asset(db, asset, system_key="audio.sfx", classified_by="auto")
        still_locked = read_asset_library_meta(asset)
        assert still_locked.folder_system_key == "audio.music"
        assert still_locked.override is True
    finally:
        db.close()
