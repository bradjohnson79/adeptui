"""Phase 6 library truth — CDX-064/065/066/067/068/070 backend verification.

Each test maps to one finding:
  CDX-064  approval truth lives on Asset.production_approval, never in the meta blob
  CDX-065  global-scope assets discoverable from other projects (route + Co-Director)
  CDX-066  entity folders keyed by entityId only; rename follows without forking
  CDX-067  paged retrieval reaches assets beyond the old 500-window / 100-cap
  CDX-068  upload_asset content-hashes, classifies, and flags duplicates (no deletion)
  CDX-070  propose-assignment defaults override=False; preview discloses overrides
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.project_library.schema import LibraryState
from app.project_library.service import (
    assign_asset,
    ensure_entity_folder,
    find_duplicates_by_hash,
    get_tree,
    read_asset_library_meta,
    rename_entity_folder,
    write_asset_library_meta,
)
from app.project_library.codirector import search_library_assets


def _create_project(client, name: str = "Library Truth Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _make_asset(db, project_id, isolated_data_dir: Path, *, tag: str, filename: str, kind: str = "image", age: int = 0):
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    dest = isolated_data_dir / "assets" / project_id / f"{asset_id}{Path(filename).suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"phase6-truth-bytes")
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=tag,
        kind=kind,
        filename=filename,
        path=str(dest),
        created_at=datetime.utcnow() - timedelta(seconds=age),
    )
    db.add(asset)
    db.commit()
    return asset


# ---------------------------------------------------------------------------
# CDX-064: approval truth
# ---------------------------------------------------------------------------

def test_approval_truth_ranks_search_and_payload(client, isolated_data_dir: Path) -> None:
    """Approved assets rank first and payloads report the column, not a stale blob."""
    from app.db import Asset

    project_id = _create_project(client)
    db = _session()
    try:
        # The OLDER asset is the approved one -> approval must outrank recency.
        older_approved = _make_asset(db, project_id, isolated_data_dir, tag="hero-shot", filename="hero-v1.png", age=120)
        newer_draft = _make_asset(db, project_id, isolated_data_dir, tag="hero-shot", filename="hero-v2.png", age=60)

        # Simulate the approval write prop_creator/scene_creator/vision perform.
        older_approved.production_approval = "approved"
        db.commit()

        # Stale blob approval must NOT win: plant "draft" in the meta blob.
        stale = read_asset_library_meta(older_approved)
        stale.approval_state = "draft"
        stale.is_canonical = False
        write_asset_library_meta(older_approved, stale)
        db.commit()

        # Read path derives truth from the column.
        reloaded = read_asset_library_meta(db.get(Asset, older_approved.id))
        assert reloaded.approval_state == "approved"
        assert reloaded.is_canonical is True

        # Co-Director search returns the approved asset first with truthful payload.
        result = search_library_assets(db, project_id, query="hero-shot")
        assert result["items"], "expected at least one hit"
        assert result["items"][0]["id"] == older_approved.id
        assert result["items"][0]["approvalState"] == "approved"
        assert result["items"][0]["isCanonical"] is True
        assert result["preferred"]["approvalState"] == "approved"

        # Library API payload is truthful too.
        body = client.get(f"/api/projects/{project_id}/library?q=hero-shot").json()
        rows = {i["id"]: i for i in body["items"]}
        assert rows[older_approved.id]["approvalState"] == "approved"
        assert rows[older_approved.id]["isCanonical"] is True
        assert rows[newer_draft.id]["approvalState"] == "draft"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-065: global scope
# ---------------------------------------------------------------------------

def test_global_scope_discoverable_across_projects(client, isolated_data_dir: Path) -> None:
    """Promoted (scope=global) assets are visible cross-project; project scope stays local."""
    project_a = _create_project(client, "Library A")
    project_b = _create_project(client, "Library B")

    db = _session()
    try:
        promoted = _make_asset(db, project_a, isolated_data_dir, tag="global-hero", filename="hero.png")
        promoted.scope = "global"
        local_a = _make_asset(db, project_a, isolated_data_dir, tag="global-hero", filename="local.png")
        db.commit()
        promoted_id = promoted.id
        local_a_id = local_a.id
    finally:
        db.close()

    # Default scope=project on B must not leak A's assets (promoted or not).
    default_items = client.get(f"/api/projects/{project_b}/library?q=global-hero").json()["items"]
    assert all(i["project_id"] == project_b for i in default_items)
    assert not any(i["id"] == promoted_id for i in default_items)
    assert not any(i["id"] == local_a_id for i in default_items)

    # scope=global on B returns the promoted asset; A's project-local asset stays out.
    global_body = client.get(f"/api/projects/{project_b}/library?scope=global&q=global-hero").json()
    global_ids = [i["id"] for i in global_body["items"]]
    assert promoted_id in global_ids
    assert local_a_id not in global_ids
    assert global_body["totalMatches"] == 1

    # Co-Director search on B finds the promoted global asset.
    db = _session()
    try:
        result = search_library_assets(db, project_b, query="global-hero")
        assert any(i["id"] == promoted_id for i in result["items"])
        assert not any(i["id"] == local_a_id for i in result["items"])
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-066: entity folders by entityId; rename follows
# ---------------------------------------------------------------------------

def test_entity_folder_id_only_and_rename_follows(client) -> None:
    """Two same-name entities get separate folders; renaming follows the folder."""
    from app.db import Project

    project_id = _create_project(client)
    db = _session()
    try:
        f1 = ensure_entity_folder(
            db, project_id,
            entity_type="character", entity_name="Ada", entity_id="char-ada-1",
            subfolder_system_key="characters.identity_references",
        )
        f2 = ensure_entity_folder(
            db, project_id,
            entity_type="character", entity_name="Ada", entity_id="char-ada-2",
            subfolder_system_key="characters.identity_references",
        )
        assert f1.folder_id != f2.folder_id, "same-name entities must not share a folder"

        tree = get_tree(db, project_id)
        chars = next(f for f in tree["folders"] if f["systemKey"] == "characters")
        kids = chars.get("children") or []
        assert len(kids) == 2
        assert {k["displayName"] for k in kids} == {"Ada"}

        # Rename one entity -> its folder follows, no fork.
        renamed = rename_entity_folder(
            db, project_id, entity_type="character", entity_id="char-ada-1", new_name="Ada Prime"
        )
        assert renamed.display_name == "Ada Prime"
        assert renamed.display_path == "Project/Characters/Ada Prime"

        tree2 = get_tree(db, project_id)
        assert tree2["entityFolderCount"] == 4  # 2 entity folders + 2 subfolders, no fork
        chars2 = next(f for f in tree2["folders"] if f["systemKey"] == "characters")
        names2 = {c["displayName"] for c in (chars2.get("children") or [])}
        assert names2 == {"Ada", "Ada Prime"}

        # Subfolder display paths follow the renamed entity.
        project = db.get(Project, project_id)
        state = LibraryState.from_dict(json.loads(project.settings_json or "{}").get("library"))
        sub_paths = [
            row.get("displayPath")
            for row in state.folders.values()
            if row.get("parentFolderId") == renamed.folder_id
        ]
        assert sub_paths and all(p.startswith("Project/Characters/Ada Prime/") for p in sub_paths)

        # HTTP rename endpoint mirrors the service behavior.
        res = client.patch(
            f"/api/projects/{project_id}/library/entity-folder",
            json={"entityType": "character", "entityId": "char-ada-1", "entityName": "Ada Prime v2"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["displayName"] == "Ada Prime v2"
        assert body["displayPath"] == "Project/Characters/Ada Prime v2"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-067: paged retrieval
# ---------------------------------------------------------------------------

def test_search_reaches_old_assets_via_paging(client) -> None:
    """Assets beyond the old 500-row window stay reachable via pagination."""
    from app.db import Asset

    project_id = _create_project(client)
    db = _session()
    try:
        now = datetime.utcnow()
        ids = []
        for i in range(510):
            aid = f"bulk-{i:04d}"
            db.add(
                Asset(
                    id=aid,
                    project_id=project_id,
                    tag="bulkasset",
                    kind="image",
                    filename=f"bulk-{i:04d}.png",
                    path=f"/nonexistent/bulk-{i:04d}.png",
                    created_at=now - timedelta(seconds=i),
                )
            )
            ids.append(aid)
        db.commit()
        oldest = ids[-1]  # bulk-0509
        newest = ids[0]   # bulk-0000
    finally:
        db.close()

    body = client.get(f"/api/projects/{project_id}/library?q=bulkasset&limit=100&offset=500").json()
    assert body["totalMatches"] == 510
    page_ids = [i["id"] for i in body["items"]]
    assert oldest in page_ids
    assert newest not in page_ids

    # The oldest asset is reachable by exact name from page 0 (name LIKE scan).
    by_name = client.get(f"/api/projects/{project_id}/library?q=bulk-0509&limit=100&offset=0").json()
    assert any(i["id"] == oldest for i in by_name["items"])

    # Co-Director search pages through and reaches the oldest by name too.
    db = _session()
    try:
        result = search_library_assets(db, project_id, query="bulk-0509")
        assert any(i["id"] == oldest for i in result["items"])
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-068: upload classification + hash dedupe
# ---------------------------------------------------------------------------

def test_upload_classifies_and_flags_duplicate(client) -> None:
    """Identical bytes uploaded twice -> second is flagged as a duplicate, never deleted."""
    from app.db import Asset

    project_id = _create_project(client)
    payload = b"phase6-duplicate-bytes-000"

    res1 = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": ("hero.png", payload, "image/png")},
        data={"tag": "hero", "kind": "image"},
    )
    assert res1.status_code == 200, res1.text
    first = res1.json()

    res2 = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": ("hero-copy.png", payload, "image/png")},
        data={"tag": "hero", "kind": "image"},
    )
    assert res2.status_code == 200, res2.text
    second = res2.json()
    assert second["id"] != first["id"], "duplicate uploads are flagged, not collapsed"

    db = _session()
    try:
        from app.project_library.service import enrich_library_item

        first_row = db.get(Asset, first["id"])
        second_row = db.get(Asset, second["id"])

        # Classification + content hash are written on upload.
        meta_first = read_asset_library_meta(first_row)
        meta_second = read_asset_library_meta(second_row)
        assert meta_first.content_hash and meta_second.content_hash
        assert meta_first.content_hash == meta_second.content_hash
        assert meta_first.folder_system_key, "upload should classify into a library folder"

        # Hash-based dedupe flags the second upload; neither copy is deleted.
        dupes = find_duplicates_by_hash(db, project_id, meta_second.content_hash)
        assert {a.id for a in dupes} == {first["id"], second["id"]}
        assert enrich_library_item(second_row)["duplicateOf"] == first["id"]
        assert enrich_library_item(first_row)["duplicateOf"] is None

        # Library payload discloses the flag.
        items = client.get(f"/api/projects/{project_id}/library?q=hero").json()["items"]
        row2 = next(i for i in items if i["id"] == second["id"])
        assert row2["duplicateOf"] == first["id"]
        row1 = next(i for i in items if i["id"] == first["id"])
        assert row1["duplicateOf"] is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-070: propose assignment override default
# ---------------------------------------------------------------------------

def test_propose_assignment_respects_manual_override(client, isolated_data_dir: Path) -> None:
    """apply without override preserves a manual override; override=true replaces it."""
    from app.db import Asset
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import library as lib_handler

    project_id = _create_project(client)
    db = _session()
    try:
        asset_id = str(uuid.uuid4())
        dest = isolated_data_dir / "assets" / project_id / f"{asset_id}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"override-bytes")

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

        ctx = ToolContext(db=db, project_id=project_id, capabilities={})

        # Preview discloses the existing override and the requested override flag.
        preview = lib_handler.preview_propose_asset_library_assignment(
            ctx, {"assetId": asset_id, "systemKey": "audio.sfx"}
        )
        joined = "\n".join(preview.lines)
        assert "currentOverride: True" in joined
        assert "override: False" in joined
        assert preview.warnings, "preview must warn that the manual override will be respected"

        # Apply WITHOUT override -> manual override wins, assignment unchanged.
        lib_handler.apply_propose_asset_library_assignment(ctx, {"assetId": asset_id, "systemKey": "audio.sfx"})
        meta = read_asset_library_meta(db.get(Asset, asset_id))
        assert meta.folder_system_key == "audio.music"
        assert meta.override is True

        # Apply WITH override=true -> the requested assignment is applied.
        lib_handler.apply_propose_asset_library_assignment(
            ctx, {"assetId": asset_id, "systemKey": "audio.sfx", "override": True}
        )
        meta = read_asset_library_meta(db.get(Asset, asset_id))
        assert meta.folder_system_key == "audio.sfx"
        assert meta.override is True
    finally:
        db.close()
