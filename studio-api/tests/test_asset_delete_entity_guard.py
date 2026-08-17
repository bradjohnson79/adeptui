"""CDX-063 — Library deletion entity guard tests.

Deleting a Library asset must never silently break canonical downstream
references: approved character identity, approved prop identity, ERS
source/composite, spatial map background, scene visual references, or asset
graph edges. Plain delete blocks with a typed payload naming the referencing
entity; force delete (bulk, force=true) detaches the links explicitly, cleans
AssetVersion/AssetEdge rows, and removes the file + Asset row.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.asset_graph import AssetEdge, AssetVersion
from app.character_identity.models import (
    CharacterProfileRow,
    CharacterPropRow,
    CharacterReferenceAssetRow,
)
from app.db import Asset, Scene
from app.spatial_map.ers_contracts import EnvironmentReferencePackage, PropEntity
from app.spatial_map.ers_persistence import (
    load_prop_entity_by_id,
    save_ers_package,
    save_prop_entity,
)
from app.spatial_map.models import SpatialMapDocumentRow


def _create_project(client, name: str = "Delete Guard Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _add_asset(db, project_id: str, isolated_data_dir: Path, tag: str = "take") -> tuple[str, Path]:
    asset_id = str(uuid.uuid4())
    dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"png-data")
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            kind="image",
            tag=tag,
            filename=dest.name,
            path=str(dest),
        )
    )
    db.commit()
    return asset_id, dest


def _ref_kinds(payload) -> list[str]:
    return [r["kind"] for r in payload.get("entityRefs") or []]


# 1) Approved character identity asset — blocked with named entity.
def test_delete_approved_character_identity_asset_blocked(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, dest = _add_asset(db, project_id, isolated_data_dir, tag="hero")
        char_id = str(uuid.uuid4())
        db.add(CharacterProfileRow(id=char_id, project_id=project_id, name="Korri"))
        db.add(
            CharacterReferenceAssetRow(
                id=str(uuid.uuid4()),
                character_profile_id=char_id,
                asset_id=asset_id,
                reference_role="hero_identity",
                approval_status="approved",
                canonical=True,
                source_type="generated",
            )
        )
        db.commit()

        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleteBlocked"] is True
        assert "character_identity" in _ref_kinds(payload)
        char_refs = [r for r in payload["entityRefs"] if r["kind"] == "character_identity"]
        assert char_refs and char_refs[0]["entityName"] == "Korri"
        assert "message" in payload and "Korri" in payload["message"]
        # Asset untouched.
        assert db.get(Asset, asset_id) is not None
        assert dest.exists()
    finally:
        db.close()


# 2) Approved prop identity asset — blocked.
def test_delete_approved_prop_identity_asset_blocked(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, _dest = _add_asset(db, project_id, isolated_data_dir, tag="prop-take")
        prop = PropEntity(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="coffee-cup",
            display_label="Coffee Cup",
            approved_asset_id=asset_id,
        )
        save_prop_entity(db, project_id, prop)

        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleteBlocked"] is True
        assert "prop_identity" in _ref_kinds(payload)
        prop_refs = [r for r in payload["entityRefs"] if r["kind"] == "prop_identity"]
        assert prop_refs and prop_refs[0]["entityName"] == "Coffee Cup"
        assert db.get(Asset, asset_id) is not None
    finally:
        db.close()


# 3a) ERS source/background asset referenced from a spatial map document_json.
def test_delete_ers_background_asset_blocked(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, _dest = _add_asset(db, project_id, isolated_data_dir, tag="atlas")
        db.add(
            SpatialMapDocumentRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                title="Atlas",
                document_json=json.dumps({"title": "Atlas", "backgroundAssetId": asset_id}),
            )
        )
        db.commit()

        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleteBlocked"] is True
        assert "spatial_map" in _ref_kinds(payload)
        refs = [r for r in payload["entityRefs"] if r["kind"] == "spatial_map"]
        assert refs and refs[0]["field"] == "backgroundAssetId"
        assert db.get(Asset, asset_id) is not None
    finally:
        db.close()


# 3b) ERS source/background asset referenced from an ERS package.
def test_delete_ers_package_asset_blocked(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, _dest = _add_asset(db, project_id, isolated_data_dir, tag="ers-src")
        pkg = EnvironmentReferencePackage(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_layout_id="map-1",
            atlas_asset_id=asset_id,
        )
        save_ers_package(db, project_id, pkg)

        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleteBlocked"] is True
        assert "ers_package" in _ref_kinds(payload)
        assert db.get(Asset, asset_id) is not None
    finally:
        db.close()


# 4) Scene visual reference asset — blocked (Scene storyboard frame).
def test_delete_scene_visual_reference_asset_blocked(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, _dest = _add_asset(db, project_id, isolated_data_dir, tag="storyboard")
        db.add(Scene(id=str(uuid.uuid4()), project_id=project_id, name="Scene 1", start_asset_id=asset_id))
        db.commit()

        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleteBlocked"] is True
        assert "scene_visual" in _ref_kinds(payload)
        assert db.get(Asset, asset_id) is not None
    finally:
        db.close()


# 4b) Scene shot exported to Timeline — blocked.
def test_delete_scene_shot_timeline_export_asset_blocked(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, _dest = _add_asset(db, project_id, isolated_data_dir, tag="timeline-export")
        from app.spatial_map.ers_contracts import SceneShot, SceneShotTakeMemory
        from app.spatial_map.ers_persistence import save_scene_shot

        shot = SceneShot(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=str(uuid.uuid4()),
            sheet_id=str(uuid.uuid4()),
            intent="test",
            take_memory=SceneShotTakeMemory(takeState={"lastTimelineAssetId": asset_id}),
        )
        save_scene_shot(db, project_id, shot)

        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleteBlocked"] is True
        assert "scene_shot" in _ref_kinds(payload)
        assert db.get(Asset, asset_id) is not None
    finally:
        db.close()


# 5) Force-delete matrix: detaches links explicitly, cleans lineage, removes
#    file + Asset row, returns a truthful payload.
def test_force_delete_detaches_references_and_cleans_lineage(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, dest = _add_asset(db, project_id, isolated_data_dir, tag="force-me")
        other_id, _ = _add_asset(db, project_id, isolated_data_dir, tag="other")

        char_id = str(uuid.uuid4())
        db.add(CharacterProfileRow(id=char_id, project_id=project_id, name="Korri"))
        char_ref = CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=char_id,
            asset_id=asset_id,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
        )
        db.add(char_ref)
        prop_row = CharacterPropRow(
            id=str(uuid.uuid4()),
            character_profile_id=char_id,
            name="Sword",
            library_asset_id=asset_id,
        )
        db.add(prop_row)
        prop_entity = PropEntity(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="sword",
            display_label="Sword",
            approved_asset_id=asset_id,
        )
        save_prop_entity(db, project_id, prop_entity)
        scene = Scene(id=str(uuid.uuid4()), project_id=project_id, name="Scene 1", start_asset_id=asset_id)
        db.add(scene)
        map_row = SpatialMapDocumentRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title="Atlas",
            document_json=json.dumps({"title": "Atlas", "backgroundAssetId": asset_id}),
        )
        db.add(map_row)
        db.add(AssetVersion(id=str(uuid.uuid4()), asset_id=asset_id, version=1, op="generate", path=str(dest)))
        db.add(AssetEdge(id=str(uuid.uuid4()), from_id=asset_id, to_id=other_id, relation="derived_from"))
        db.add(AssetEdge(id=str(uuid.uuid4()), from_id=other_id, to_id=asset_id, relation="related"))
        db.commit()

        res = client.post(
            f"/api/projects/{project_id}/assets/bulk-delete",
            json={"assetIds": [asset_id], "force": True},
        )
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        entry = results[0]
        assert entry["status"] == "deleted"
        assert entry["versionsDeleted"] == 1
        assert entry["edgesDeleted"] == 2
        detached_kinds = [d["kind"] for d in entry["detachedReferences"]]
        assert "character_identity" in detached_kinds
        assert "character_prop" in detached_kinds
        assert "prop_identity" in detached_kinds
        assert "scene_visual" in detached_kinds
        assert "spatial_map" in detached_kinds

        # File + Asset row removed.
        assert db.get(Asset, asset_id) is None
        assert dest.exists() is False
        # Lineage cleaned.
        assert db.query(AssetVersion).filter(AssetVersion.asset_id == asset_id).count() == 0
        assert (
            db.query(AssetEdge)
            .filter((AssetEdge.from_id == asset_id) | (AssetEdge.to_id == asset_id))
            .count()
            == 0
        )
        # Links detached explicitly.
        assert db.query(CharacterReferenceAssetRow).filter(CharacterReferenceAssetRow.asset_id == asset_id).count() == 0
        db.refresh(prop_row)
        assert prop_row.library_asset_id is None
        db.refresh(scene)
        assert scene.start_asset_id is None
        db.refresh(map_row)
        assert json.loads(map_row.document_json)["backgroundAssetId"] is None
        updated_prop = load_prop_entity_by_id(db, project_id, prop_entity.id)
        assert updated_prop is not None
        assert not (updated_prop.approved_asset_id or "").strip()
    finally:
        db.close()


# 5b) Bulk delete without force — blocked with entityRefs, nothing removed.
def test_bulk_delete_blocks_with_entity_refs_without_force(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, dest = _add_asset(db, project_id, isolated_data_dir, tag="blocked-bulk")
        db.add(Scene(id=str(uuid.uuid4()), project_id=project_id, name="Scene 1", start_asset_id=asset_id))
        db.commit()

        res = client.post(
            f"/api/projects/{project_id}/assets/bulk-delete",
            json={"assetIds": [asset_id], "force": False},
        )
        assert res.status_code == 200
        entry = res.json()["results"][0]
        assert entry["status"] == "blocked"
        assert "scene_visual" in [r["kind"] for r in entry["entityRefs"]]
        assert db.get(Asset, asset_id) is not None
        assert dest.exists()
    finally:
        db.close()


# 6) Unreferenced asset delete still succeeds (no regression).
def test_delete_unreferenced_asset_succeeds(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    db = _session()
    try:
        asset_id, dest = _add_asset(db, project_id, isolated_data_dir, tag="loose")
        res = client.delete(f"/api/projects/{project_id}/assets/{asset_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["deleted"] is True
        assert db.get(Asset, asset_id) is None
        assert dest.exists() is False
    finally:
        db.close()
