"""Co-Director Project Library awareness — API and tool tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.project_library import display_path_for_system_key, system_folder_id
from app.project_library.service import assign_asset, read_asset_library_meta


def _create_project(client, name: str = "CD Library Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def test_library_resolve_audio_music(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/projects/{project_id}/library/resolve",
        json={"path": "Audio/Music"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["resolved"] is True
    assert body["match"]["systemKey"] == "audio.music"
    assert body["match"]["libraryPath"] == display_path_for_system_key("audio.music")


def test_library_resolve_nl_put_in_audio_music(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/projects/{project_id}/library/resolve",
        json={"query": "put this in Audio/Music"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["resolved"] is True
    assert body["match"]["systemKey"] == "audio.music"


def test_library_resolve_ambiguous_audio(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/projects/{project_id}/library/resolve",
        json={"query": "Audio"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["resolved"] is False
    assert body["ambiguous"] is True
    assert len(body["candidates"]) >= 2


def test_library_entity_folder_lazy_create(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/projects/{project_id}/library/preflight",
        json={
            "task": "generate_prop_reference",
            "entityType": "prop",
            "entityName": "Crystal Codex",
            "entityId": "prop-codex-001",
            "systemKey": "props.references",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is True
    assert "Crystal Codex" in body["targetPath"]

    db = _session()
    try:
        from app.db import Project

        project = db.get(Project, project_id)
        settings = json.loads(project.settings_json or "{}")
        assert len(settings["library"]["folders"]) == 2
    finally:
        db.close()


def test_library_codirector_context_endpoint(client) -> None:
    project_id = _create_project(client)
    res = client.get(f"/api/projects/{project_id}/library/codirector-context")
    assert res.status_code == 200
    body = res.json()
    assert "folderMap" in body
    assert system_folder_id("audio.music") in body["folderMap"]


def test_codirector_tool_resolve_library_location(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": "resolve_library_location", "arguments": {"path": "Audio/Music"}},
    )
    assert res.status_code == 200
    payload = res.json()
    # Wave 3 normalized ToolResult envelope: payload lives under result.data.
    assert payload["result"]["data"]["resolved"] is True


def test_codirector_tool_link_bible_entity_folder(client) -> None:
    project_id = _create_project(client)
    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={
            "toolId": "link_bible_entity_folder",
            "arguments": {
                "entityType": "prop",
                "entityName": "Crystal Codex",
                "entityId": "prop-codex-001",
                "systemKey": "props.references",
            },
        },
    )
    assert res.status_code == 200
    result = res.json()["result"]
    # Wave 3 normalized ToolResult envelope: payload lives under result.data.
    assert "Crystal Codex" in result["data"]["displayPath"]


def test_manual_override_not_reverted_by_auto_assign(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"override-persist")

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
        assign_asset(db, asset, system_key="audio.music", classified_by="manual", override=True)
    finally:
        db.close()

    db = _session()
    try:
        from app.db import Asset

        asset = db.get(Asset, asset_id)
        assign_asset(db, asset, system_key="audio.sfx", classified_by="auto", override=False)
        meta = read_asset_library_meta(asset)
        assert meta.folder_system_key == "audio.music"
        assert meta.override is True
    finally:
        db.close()
