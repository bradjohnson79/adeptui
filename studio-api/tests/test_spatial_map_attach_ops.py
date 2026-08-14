"""Spatial Map attach/detach/relationship operations (Workstream B)."""

from __future__ import annotations

from pathlib import Path

import uuid


def _create_project(client, name: str = "SM Attach Ops") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _insert_asset(project_id: str, kind: str, filename: str, isolated_data_dir: Path) -> str:
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    dest = isolated_data_dir / "assets" / project_id / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"spatial-map-attach-ops")
    db = _session()
    try:
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                kind=kind,
                tag=kind,
                filename=filename,
                path=str(dest),
            )
        )
        db.commit()
    finally:
        db.close()
    return asset_id


def _create_map(client, project_id: str) -> str:
    create = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={"title": "Cafe Blocking", "masterEnvironmentPrompt": "Warm cafe."},
    )
    assert create.status_code == 200
    return create.json()["document"]["id"]


def _place_korri(client, project_id: str, document_id: str, *, grid_row: int = 4, grid_column: int = 4) -> dict:
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={
            "characterId": "korri",
            "label": "Korri",
            "slotIndex": 0,
            "colorKey": "red",
            "tag": "@Korri",
            "gridRow": grid_row,
            "gridColumn": grid_column,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["document"]["characters"][0]


def _place_coffee(client, project_id: str, document_id: str, **extra) -> dict:
    body = {
        "label": "Coffee Cup",
        "propId": "coffee-1",
        "tag": "#coffeecup",
        "slotIndex": 0,
        "colorKey": "purple",
        "gridRow": 3,
        "gridColumn": 3,
    }
    body.update(extra)
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json=body,
    )
    assert res.status_code == 200, res.text
    return res.json()["document"]["props"][0]


def _attach_coffee(client, project_id: str, document_id: str, prop_placement_id: str, **extra):
    body = {
        "attachedCharacterId": "korri",
        "attachedCharacterSlot": 1,
        "relationship": "held",
        "attachmentPoint": "right_hand",
    }
    body.update(extra)
    return client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{prop_placement_id}/attach",
        json=body,
    )


def _prop(document: dict) -> dict:
    return document["props"][0]


def test_attach_korri_coffee_held_right_hand(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    _place_korri(client, project_id, document_id)
    coffee = _place_coffee(client, project_id, document_id)
    assert coffee["propId"] == "coffee-1"
    assert coffee["placementMode"] == "independent"
    assert coffee["normalizedX"] is not None

    attached = _attach_coffee(client, project_id, document_id, coffee["id"])
    assert attached.status_code == 200, attached.text
    prop = _prop(attached.json()["document"])
    assert prop["id"] == coffee["id"]
    assert prop["propId"] == "coffee-1"
    assert prop["placementMode"] == "attached"
    assert prop["attachedCharacterId"] == "korri"
    assert prop["attachedCharacterSlot"] == 1
    assert prop["relationship"] == "held"
    assert prop["attachmentPoint"] == "right_hand"
    assert prop["normalizedX"] is None
    assert prop["normalizedY"] is None
    assert prop["gridRow"] == -1
    assert prop["gridColumn"] == -1
    assert prop["x"] is None
    assert prop["y"] is None
    assert prop["z"] is None


def test_character_move_keeps_attachment_no_independent_pos(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    korri = _place_korri(client, project_id, document_id, grid_row=4, grid_column=4)
    coffee = _place_coffee(client, project_id, document_id)
    attached = _attach_coffee(client, project_id, document_id, coffee["id"])
    assert attached.status_code == 200

    moved = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{korri['id']}",
        json={"gridRow": 6, "gridColumn": 7},
    )
    assert moved.status_code == 200, moved.text
    document = moved.json()["document"]
    character = document["characters"][0]
    prop = _prop(document)
    assert character["gridRow"] == 6
    assert character["gridColumn"] == 7
    assert character["normalizedX"] is not None
    assert prop["placementMode"] == "attached"
    assert prop["attachedCharacterId"] == "korri"
    assert prop["attachedCharacterSlot"] == 1
    assert prop["relationship"] == "held"
    assert prop["attachmentPoint"] == "right_hand"
    assert prop["normalizedX"] is None
    assert prop["normalizedY"] is None
    assert prop["gridRow"] == -1
    assert prop["gridColumn"] == -1
    assert prop["propId"] == "coffee-1"


def test_detach_clears_fields_and_leaves_unplaced(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    _place_korri(client, project_id, document_id)
    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    detached = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}/detach"
    )
    assert detached.status_code == 200, detached.text
    prop = _prop(detached.json()["document"])
    assert prop["id"] == coffee["id"]
    assert prop["propId"] == "coffee-1"
    assert prop["placementMode"] == "independent"
    assert prop["attachedCharacterId"] is None
    assert prop["attachedCharacterSlot"] is None
    assert prop["relationship"] is None
    assert prop["attachmentPoint"] is None
    assert prop["normalizedX"] is None
    assert prop["normalizedY"] is None
    assert prop["gridRow"] == -1
    assert prop["gridColumn"] == -1


def test_xor_reject_attached_and_independent_position(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    _place_korri(client, project_id, document_id)

    xor_place = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={
            "label": "Coffee Cup",
            "propId": "coffee-1",
            "placementMode": "attached",
            "attachedCharacterId": "korri",
            "attachedCharacterSlot": 1,
            "relationship": "held",
            "attachmentPoint": "right_hand",
            "gridRow": 3,
            "gridColumn": 3,
        },
    )
    assert xor_place.status_code == 400, xor_place.text
    assert xor_place.json()["detail"]["code"] == "ATTACHMENT_INVALID"

    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    xor_update = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}",
        json={"gridRow": 2, "gridColumn": 5},
    )
    assert xor_update.status_code == 400, xor_update.text
    assert xor_update.json()["detail"]["code"] == "ATTACHMENT_INVALID"

    missing = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}/attach",
        json={"attachedCharacterId": "korri"},
    )
    assert missing.status_code == 422

    slot_zero = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}/attach",
        json={"attachedCharacterSlot": 0, "relationship": "held"},
    )
    assert slot_zero.status_code == 422


def test_attach_persists_across_reload(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    _place_korri(client, project_id, document_id)
    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    reloaded = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}")
    assert reloaded.status_code == 200
    prop = _prop(reloaded.json()["document"])
    assert prop["propId"] == "coffee-1"
    assert prop["placementMode"] == "attached"
    assert prop["attachedCharacterId"] == "korri"
    assert prop["attachedCharacterSlot"] == 1
    assert prop["relationship"] == "held"
    assert prop["attachmentPoint"] == "right_hand"
    assert prop["normalizedX"] is None
    assert prop["gridRow"] == -1


def test_backward_compat_independent_does_not_move_positions(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    coffee = _place_coffee(client, project_id, document_id, gridRow=2, gridColumn=6)
    assert coffee["placementMode"] == "independent"
    assert coffee["attachedCharacterId"] is None
    assert coffee["relationship"] is None
    nx, ny = coffee["normalizedX"], coffee["normalizedY"]
    assert nx is not None and ny is not None

    reloaded = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}")
    prop = _prop(reloaded.json()["document"])
    assert prop["placementMode"] == "independent"
    assert prop["attachedCharacterSlot"] is None
    assert prop["attachedCharacterId"] is None
    assert prop["relationship"] is None
    assert prop["attachmentPoint"] is None
    assert prop["normalizedX"] == nx
    assert prop["normalizedY"] == ny
    assert prop["gridRow"] == 2
    assert prop["gridColumn"] == 6
    assert prop["propId"] == "coffee-1"


def test_update_prop_relationship(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    _place_korri(client, project_id, document_id)
    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    updated = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}/relationship",
        json={"relationship": "carried", "attachmentPoint": "left_hand"},
    )
    assert updated.status_code == 200, updated.text
    prop = _prop(updated.json()["document"])
    assert prop["placementMode"] == "attached"
    assert prop["relationship"] == "carried"
    assert prop["attachmentPoint"] == "left_hand"
    assert prop["attachedCharacterId"] == "korri"
    assert prop["normalizedX"] is None

    placed = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Mug", "propId": "coffee-2", "gridRow": 1, "gridColumn": 1},
    )
    assert placed.status_code == 200, placed.text
    independent = next(item for item in placed.json()["document"]["props"] if item["propId"] == "coffee-2")
    assert independent["placementMode"] == "independent"
    rejected = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{independent['id']}/relationship",
        json={"relationship": "held"},
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "ATTACHMENT_INVALID"


def test_remove_character_rejects_attached_props_then_detach_unplaced(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    korri = _place_korri(client, project_id, document_id)
    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    blocked = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{korri['id']}"
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "CHARACTER_HAS_ATTACHED_PROPS"
    assert detail["attachedPropCount"] == 1
    assert detail["attachedProps"][0]["id"] == coffee["id"]
    assert detail["attachedProps"][0]["propId"] == "coffee-1"
    assert "Detach Props to Unplaced" in detail["recovery"]

    still = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}")
    assert len(still.json()["document"]["characters"]) == 1
    assert still.json()["document"]["props"][0]["placementMode"] == "attached"

    detached = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}/detach"
    )
    assert detached.status_code == 200
    removed = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{korri['id']}"
    )
    assert removed.status_code == 200, removed.text
    document = removed.json()["document"]
    assert document["characters"] == []
    prop = _prop(document)
    assert prop["id"] == coffee["id"]
    assert prop["propId"] == "coffee-1"
    assert prop["placementMode"] == "independent"
    assert prop["relationship"] is None
    assert prop["gridRow"] == -1


def test_remove_leftover_character_does_not_claim_canonical_attachment(client) -> None:
    """slotIndex -1 leftover must delete without detaching the slot-0 cup."""
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    korri = _place_korri(client, project_id, document_id)
    leftover_res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={
            "characterId": "korri",
            "label": "Korri leftover",
            "slotIndex": -1,
            "colorKey": "red",
            "tag": "@Korri",
        },
    )
    assert leftover_res.status_code == 200, leftover_res.text
    leftover_id = next(
        item["id"]
        for item in leftover_res.json()["document"]["characters"]
        if item["id"] != korri["id"]
    )
    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    removed_leftover = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{leftover_id}"
    )
    assert removed_leftover.status_code == 200, removed_leftover.text
    after_leftover = removed_leftover.json()["document"]
    assert [item["id"] for item in after_leftover["characters"]] == [korri["id"]]
    leftover_prop = _prop(after_leftover)
    assert leftover_prop["id"] == coffee["id"]
    assert leftover_prop["placementMode"] == "attached"
    assert leftover_prop["attachedCharacterId"] == "korri"
    assert leftover_prop["attachedCharacterSlot"] == 1
    assert leftover_prop["relationship"] == "held"

    blocked = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{korri['id']}"
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "CHARACTER_HAS_ATTACHED_PROPS"
    assert detail["attachedPropCount"] == 1
    assert detail["attachedProps"][0]["id"] == coffee["id"]

    still = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}")
    still_prop = still.json()["document"]["props"][0]
    assert still_prop["placementMode"] == "attached"
    assert still_prop["attachedCharacterId"] == "korri"
    assert still_prop["attachedCharacterSlot"] == 1

    detached = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{korri['id']}",
        params={"detachAttachedProps": True},
    )
    assert detached.status_code == 200, detached.text
    document = detached.json()["document"]
    assert document["characters"] == []
    detached_prop = _prop(document)
    assert detached_prop["placementMode"] == "independent"
    assert detached_prop["attachedCharacterId"] is None


def test_remove_character_detach_attached_props_confirm(client) -> None:
    project_id = _create_project(client)
    document_id = _create_map(client, project_id)
    korri = _place_korri(client, project_id, document_id)
    coffee = _place_coffee(client, project_id, document_id)
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    removed = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{korri['id']}",
        params={"detachAttachedProps": True},
    )
    assert removed.status_code == 200, removed.text
    document = removed.json()["document"]
    assert document["characters"] == []
    prop = _prop(document)
    assert prop["id"] == coffee["id"]
    assert prop["propId"] == "coffee-1"
    assert prop["placementMode"] == "independent"
    assert prop["attachedCharacterId"] is None
    assert prop["relationship"] is None
    assert prop["normalizedX"] is None
    assert prop["gridRow"] == -1


def test_remove_attached_prop_unlinks_without_library_delete(client, isolated_data_dir: Path) -> None:
    from app.db import Asset

    project_id = _create_project(client, "SM Attach Library")
    document_id = _create_map(client, project_id)
    _place_korri(client, project_id, document_id)
    asset_id = _insert_asset(project_id, "image", "coffee.png", isolated_data_dir)
    coffee = _place_coffee(client, project_id, document_id, assetId=asset_id)
    assert coffee["assetId"] == asset_id
    assert _attach_coffee(client, project_id, document_id, coffee["id"]).status_code == 200

    removed = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{coffee['id']}"
    )
    assert removed.status_code == 200, removed.text
    document = removed.json()["document"]
    assert document["props"] == []
    assert len(document["characters"]) == 1

    db = _session()
    try:
        asset = db.get(Asset, asset_id)
        assert asset is not None
        assert asset.id == asset_id
        assert asset.filename == "coffee.png"
    finally:
        db.close()

