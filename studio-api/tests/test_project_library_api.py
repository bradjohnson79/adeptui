"""REST endpoints for Studio Project Library."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.project_library import LIBRARY_SCHEMA_VERSION, display_path_for_system_key, system_folder_id
from app.project_library.service import assign_asset, read_asset_library_meta


def _create_project(client, name: str = "Library API Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def test_library_get_includes_tree_and_folder_map(client) -> None:
    project_id = _create_project(client)
    res = client.get(f"/api/projects/{project_id}/library")
    assert res.status_code == 200
    payload = res.json()
    assert payload["librarySchemaVersion"] == LIBRARY_SCHEMA_VERSION
    assert "items" in payload
    assert "tree" in payload
    assert payload["tree"]["systemFolderCount"] > 0
    assert "folderMap" in payload
    assert system_folder_id("audio.music") in payload["folderMap"]
    assert payload["folderMap"][system_folder_id("audio.music")]["displayPath"] == display_path_for_system_key(
        "audio.music"
    )


def test_library_migrate_endpoint(client) -> None:
    project_id = _create_project(client)
    res = client.post(f"/api/projects/{project_id}/library/migrate")
    assert res.status_code == 200
    body = res.json()
    assert body["toVersion"] == LIBRARY_SCHEMA_VERSION
    assert body["projectId"] == project_id


def test_library_repair_endpoint(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"repair-test")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="audio",
            tag="music",
            filename="repair.wav",
            path=str(dest),
        )
        db.add(asset)
        db.commit()

        assign_asset(db, asset, system_key="audio.music")
        meta = read_asset_library_meta(asset)
        meta.library_path = "Stale/Path"
        from app.project_library.service import write_asset_library_meta

        write_asset_library_meta(asset, meta)
        db.commit()
    finally:
        db.close()

    res = client.post(f"/api/projects/{project_id}/library/repair")
    assert res.status_code == 200
    body = res.json()
    assert body["repairedPaths"] >= 1
    assert body["librarySchemaVersion"] == LIBRARY_SCHEMA_VERSION


def test_library_resolve_path_endpoint(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/projects/{project_id}/library/resolve-path",
        json={"systemKey": "audio.music"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["libraryPath"] == display_path_for_system_key("audio.music")
    assert body["systemKey"] == "audio.music"


def test_patch_asset_library_override(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"override-test")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="audio",
            tag="sfx",
            filename="boom.wav",
            path=str(dest),
        )
        db.add(asset)
        db.commit()
        assign_asset(db, asset, system_key="audio.sfx")
    finally:
        db.close()

    res = client.patch(
        f"/api/assets/{asset_id}/library",
        json={"systemKey": "audio.music", "override": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["asset"]["folderSystemKey"] == "audio.music"
    assert body["meta"]["override"] is True


def test_patch_asset_library_entity_folder(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"png-bytes")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="image",
            tag="character",
            filename="ref.png",
            path=str(dest),
        )
        db.add(asset)
        db.commit()
    finally:
        db.close()

    res = client.patch(
        f"/api/assets/{asset_id}/library",
        json={
            "systemKey": "characters.identity_references",
            "entityType": "character",
            "entityName": "Anadriya",
            "entityId": "char-001",
            "override": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "Anadriya" in body["asset"]["libraryPath"]
    assert body["asset"]["characterId"] == "char-001"

    db = _session()
    try:
        from app.db import Project

        project = db.get(Project, project_id)
        settings = json.loads(project.settings_json or "{}")
        assert len(settings["library"]["folders"]) == 2
    finally:
        db.close()
