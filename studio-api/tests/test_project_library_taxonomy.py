"""M3.0j Studio Project Library — taxonomy, classification, and authority fields."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.project_library import (
    LIBRARY_SCHEMA_VERSION,
    all_system_keys,
    classify_asset,
    display_path_for_system_key,
    system_folder_id,
)
from app.project_library.classify import ClassifyInput
from app.project_library.service import (
    assign_asset,
    ensure_entity_folder,
    get_tree,
    init_project_library,
    migrate_project_library,
    read_asset_library_meta,
    repair_library,
    resolve_path,
)
from app.project_library.taxonomy import UNSUPPORTED_3D_EXTENSIONS


def _create_project(client, name: str = "Library Test Project") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def test_all_system_keys_unique_and_cover_taxonomy() -> None:
    keys = all_system_keys()
    assert len(keys) == len(set(keys))
    assert "audio.music" in keys
    assert "characters.identity_references" in keys
    assert "three_d.environments" in keys
    assert "exports.final" in keys
    assert "root" not in keys


def test_system_folder_ids_are_prefixed() -> None:
    assert system_folder_id("audio.music") == "sys:audio.music"
    assert display_path_for_system_key("audio.music") == "Project/Audio/Music"


def test_classify_music_to_audio_music() -> None:
    result = classify_asset(
        ClassifyInput(kind="audio", role="music", provider="ace_step", tag="score", filename="theme.wav")
    )
    assert result.target_folder == "audio.music"
    assert result.confidence >= 0.9
    assert not result.needs_clarification
    assert "music" in result.reason.lower()


def test_classify_low_confidence_needs_clarification() -> None:
    result = classify_asset(ClassifyInput(kind="image", tag="", filename="photo.png"))
    assert result.needs_clarification
    assert result.confidence < 0.6


def test_usd_extension_unsupported() -> None:
    # CDX-073: committed classify.py semantics classify native 3D as DEFERRED to
    # Version 1.2 (design intent: 3D import/animation lands in v1.2, not a
    # technical failure). The tests previously asserted NOT_APPLICABLE + "USD"
    # in the reason, which never matched the committed code.
    for ext in (".usd", ".usda", ".usdc", ".usdz"):
        assert ext in UNSUPPORTED_3D_EXTENSIONS
        result = classify_asset(ClassifyInput(kind="model", filename=f"asset{ext}"))
        assert result.needs_clarification
        assert result.subtype == "DEFERRED_VERSION_1_2"
        assert "Version 1.2" in result.reason
        assert result.target_folder == "miscellaneous"


def test_init_project_library_sets_schema_version(client) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Project

        project = db.get(Project, project_id)
        assert project is not None
        settings = json.loads(project.settings_json or "{}")
        assert settings["library"]["schemaVersion"] == LIBRARY_SCHEMA_VERSION
        assert settings["library"]["folders"] == {}
    finally:
        db.close()


def test_lazy_entity_folder_path(client) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        folder = ensure_entity_folder(
            db,
            project_id,
            entity_type="character",
            entity_name="Anadriya",
            entity_id="char-anadriya-001",
            subfolder_system_key="characters.identity_references",
        )
        assert folder.display_path == "Project/Characters/Anadriya/Identity References"
        assert folder.entity_name == "Anadriya"
        assert folder.system_key == "characters.identity_references"

        tree = get_tree(db, project_id)
        assert tree["entityFolderCount"] == 2
        assert tree["librarySchemaVersion"] == LIBRARY_SCHEMA_VERSION

        characters = next(f for f in tree["folders"] if f["systemKey"] == "characters")
        assert any(c.get("entityName") == "Anadriya" for c in characters.get("children", []))
    finally:
        db.close()


def test_authority_fields_canonical_folder_id_over_path(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset, Project

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-audio")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="audio",
            tag="music",
            filename="theme.wav",
            path=str(dest),
        )
        db.add(asset)
        db.commit()

        meta = assign_asset(
            db,
            asset,
            system_key="audio.music",
            classified_by="test",
        )
        assert meta.canonical_folder_id == system_folder_id("audio.music")
        assert meta.folder_system_key == "audio.music"
        assert meta.library_path == display_path_for_system_key("audio.music")

        resolved = resolve_path(db, project_id, folder_id=meta.canonical_folder_id)
        assert resolved == meta.library_path

        meta.library_path = "Stale/Audio/Music"
        from app.project_library.service import write_asset_library_meta

        write_asset_library_meta(asset, meta)
        db.commit()

        repaired = repair_library(db, project_id)
        assert repaired["repairedPaths"] >= 1

        reloaded = read_asset_library_meta(db.get(Asset, asset_id))
        assert reloaded.library_path == display_path_for_system_key("audio.music")
        assert reloaded.canonical_folder_id == system_folder_id("audio.music")
    finally:
        db.close()


def test_library_api_filter_by_system_key(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"sfx-bytes")

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="audio",
            tag="sfx",
            filename="hit.wav",
            path=str(dest),
        )
        db.add(asset)
        db.commit()
        assign_asset(db, asset, system_key="audio.sfx")

        all_items = client.get(f"/api/projects/{project_id}/library").json()
        assert all_items["librarySchemaVersion"] == LIBRARY_SCHEMA_VERSION
        assert "tree" in all_items
        assert "folderMap" in all_items
        row = next(i for i in all_items["items"] if i["id"] == asset_id)
        assert row["folderSystemKey"] == "audio.sfx"
        assert row["canonicalFolderId"] == system_folder_id("audio.sfx")
        assert row["libraryPath"] == display_path_for_system_key("audio.sfx")

        filtered = client.get(f"/api/projects/{project_id}/library?system_key=audio.sfx").json()
        assert len(filtered["items"]) == 1
        assert filtered["items"][0]["id"] == asset_id
    finally:
        db.close()


def test_migrate_project_library_idempotent(client) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        first = migrate_project_library(db, project_id)
        second = migrate_project_library(db, project_id)
        assert first["toVersion"] == LIBRARY_SCHEMA_VERSION
        assert second["fromVersion"] == LIBRARY_SCHEMA_VERSION
        assert second["toVersion"] == LIBRARY_SCHEMA_VERSION
    finally:
        db.close()


def test_create_project_does_not_seed_empty_folder_rows(client) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        from app.db import Project

        project = db.get(Project, project_id)
        settings = json.loads(project.settings_json or "{}")
        assert settings["library"]["folders"] == {}

        tree = get_tree(db, project_id)
        assert tree["entityFolderCount"] == 0
        assert tree["systemFolderCount"] > 0
        assert any(f["systemKey"] == "audio" for f in tree["folders"])
    finally:
        db.close()
