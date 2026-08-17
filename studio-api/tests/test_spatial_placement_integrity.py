"""Spatial Map placement integrity (CDX-013 / CDX-019 / CDX-014 / CDX-015).

Placement writes must reference canonical project-owned entities or be rejected
with typed errors; attachments must reference a character actually placed on the
document; Scene Creator prop auto-union must consult the LIVE map in addition
to the stale ERS snapshot; production handoff must apply the approved-only rule.

Design decision (CDX-013 scope): the placement gate is canonical-registry
membership (id resolves to a project-owned PropEntity via load_prop_entity_by_id).
Approval is enforced downstream by _placed_project_prop_ids / _prop_ids_from_map
(tests 4 and 5). Empty propId (character-prop / library placeholder) remains
legacy-tolerant and map-only (test 6).
"""

from __future__ import annotations

import uuid

from app.environment_reference_sheet import orchestrator, store
from app.spatial_map.ers_contracts import EnvironmentReferencePackage, PropEntity
from app.spatial_map.ers_persistence import save_ers_package, save_prop_entity
from app.spatial_map.schemas import (
    SpatialCharacterPlacementBody,
    SpatialMapCreateBody,
    SpatialPropPlacementBody,
)
from app.spatial_map.service import create_document, place_prop


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Placement Integrity") -> str:
    from app.db import Project, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _seed_character(project_id: str, character_id: str) -> None:
    from app.character_identity.models import CharacterProfileRow

    db = _session()
    try:
        existing = db.get(CharacterProfileRow, character_id)
        if existing is not None:
            db.delete(existing)
            db.commit()
        db.add(CharacterProfileRow(id=character_id, project_id=project_id, name=character_id))
        db.commit()
    finally:
        db.close()


def _seed_prop(project_id: str, prop_id: str, *, approved: bool = True) -> PropEntity:
    db = _session()
    try:
        prop = PropEntity(
            id=prop_id,
            project_id=project_id,
            tag=prop_id,
            display_label=prop_id,
            approved_asset_id=f"approved-{prop_id}" if approved else None,
        )
        save_prop_entity(db, project_id, prop)
        if approved:
            # Mirror production: approval sets production_approval on a real
            # asset row. The CDX-015 stale-asset hardening requires the row.
            from app.db import Asset, Project

            if db.get(Asset, f"approved-{prop_id}") is None:
                if db.get(Project, project_id) is None:
                    db.add(Project(id=project_id, name=f"project-{project_id[:8]}"))
                    db.commit()
                db.add(
                    Asset(
                        id=f"approved-{prop_id}",
                        project_id=project_id,
                        tag=prop_id,
                        kind="image",
                        filename=f"approved-{prop_id}.png",
                        path=f"/fake/approved-{prop_id}.png",
                        production_approval="approved",
                    )
                )
                db.commit()
        return prop
    finally:
        db.close()


def _create_project_client(client) -> str:
    res = client.post("/api/projects", json={"name": "Placement Integrity API"})
    assert res.status_code == 200
    return res.json()["id"]


def _create_map(client, project_id: str) -> str:
    create = client.post(f"/api/spatial-map/projects/{project_id}/maps", json={"title": "Stage"})
    assert create.status_code == 200
    return create.json()["document"]["id"]


# ---------------------------------------------------------------------------
# CDX-013 — placement writes must reference canonical project-owned entities
# ---------------------------------------------------------------------------


def test_place_unknown_character_rejected_with_character_not_found(client) -> None:
    project_id = _create_project_client(client)
    document_id = _create_map(client, project_id)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "no-such-character", "label": "Ghost"},
    )
    assert res.status_code == 404, res.text
    assert res.json()["detail"]["code"] == "CHARACTER_NOT_FOUND"

    # The failed placement must not mutate the document.
    doc = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}").json()["document"]
    assert doc["characters"] == []

    # Control: a project-owned character places fine.
    _seed_character(project_id, "korri")
    ok = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "korri", "label": "Korri", "slotIndex": 0},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["document"]["characters"][0]["characterId"] == "korri"


def test_place_character_from_another_project_rejected(client) -> None:
    foreign_project = _create_project_client(client)
    _seed_character(foreign_project, "foreign-hero")
    project_id = _create_project_client(client)
    document_id = _create_map(client, project_id)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "foreign-hero", "label": "Foreign"},
    )
    assert res.status_code in (403, 404), res.text
    assert res.json()["detail"]["code"] in ("PROJECT_SCOPE", "CHARACTER_NOT_FOUND")


def test_place_prop_unknown_and_foreign_prop_id_rejected_approved_accepted(client) -> None:
    project_id = _create_project_client(client)
    document_id = _create_map(client, project_id)

    unknown = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Ghost", "propId": "prop-not-in-registry"},
    )
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["detail"]["code"] == "PROP_ENTITY_NOT_FOUND"

    # Foreign: entity exists but belongs to another project -> project-scoped
    # lookup fails and the placement is rejected.
    _seed_prop("other-project", "prop-foreign", approved=True)
    foreign = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Foreign", "propId": "prop-foreign"},
    )
    assert foreign.status_code == 404, foreign.text
    assert foreign.json()["detail"]["code"] == "PROP_ENTITY_NOT_FOUND"

    # Draft in-registry entity: registry membership is the placement gate
    # (approval is enforced downstream by _placed_project_prop_ids / handoff).
    _seed_prop(project_id, "prop-draft", approved=False)
    draft = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Draft", "propId": "prop-draft"},
    )
    assert draft.status_code == 200, draft.text

    # Approved project-owned PropEntity places fine.
    _seed_prop(project_id, "prop-approved", approved=True)
    ok = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Approved", "propId": "prop-approved"},
    )
    assert ok.status_code == 200, ok.text
    prop_ids = {p["propId"] for p in ok.json()["document"]["props"]}
    assert prop_ids == {"prop-draft", "prop-approved"}


def test_update_prop_rejects_unknown_prop_id(client) -> None:
    project_id = _create_project_client(client)
    document_id = _create_map(client, project_id)
    _seed_prop(project_id, "prop-a", approved=True)
    placed = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "A", "propId": "prop-a"},
    )
    assert placed.status_code == 200, placed.text
    placement_id = placed.json()["document"]["props"][0]["id"]

    bad = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{placement_id}",
        json={"propId": "prop-unknown"},
    )
    assert bad.status_code == 404, bad.text
    assert bad.json()["detail"]["code"] == "PROP_ENTITY_NOT_FOUND"


# ---------------------------------------------------------------------------
# CDX-019 — attachment must reference a character actually placed on the map
# ---------------------------------------------------------------------------


def _place_character(client, project_id: str, document_id: str, character_id: str, slot_index: int) -> str:
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": character_id, "label": character_id, "slotIndex": slot_index},
    )
    assert res.status_code == 200, res.text
    return res.json()["document"]["characters"][0]["id"]


def _place_prop(client, project_id: str, document_id: str, prop_id: str, label: str = "Prop") -> str:
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": label, "propId": prop_id},
    )
    assert res.status_code == 200, res.text
    return res.json()["document"]["props"][0]["id"]


def test_attach_to_unoccupied_slot_rejected_with_attachment_invalid(client) -> None:
    project_id = _create_project_client(client)
    for cid in ("korri", "milo"):
        _seed_character(project_id, cid)
    _seed_prop(project_id, "coffee-1", approved=True)
    document_id = _create_map(client, project_id)

    _place_character(client, project_id, document_id, "korri", slot_index=0)
    _place_character(client, project_id, document_id, "milo", slot_index=1)
    prop_id = _place_prop(client, project_id, document_id, "coffee-1")

    # Two characters occupy slots 1-2; slot 4 is empty -> 4xx ATTACHMENT_INVALID.
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{prop_id}/attach",
        json={"attachedCharacterSlot": 4, "relationship": "held"},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "ATTACHMENT_INVALID"

    # Control: slot 1 is occupied by the placed korri -> 200.
    ok = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{prop_id}/attach",
        json={"attachedCharacterSlot": 1, "relationship": "held", "attachmentPoint": "right_hand"},
    )
    assert ok.status_code == 200, ok.text


def test_attach_to_unplaced_character_id_rejected(client) -> None:
    project_id = _create_project_client(client)
    _seed_character(project_id, "korri")
    _seed_prop(project_id, "coffee-1", approved=True)
    document_id = _create_map(client, project_id)

    _place_character(client, project_id, document_id, "korri", slot_index=0)
    prop_id = _place_prop(client, project_id, document_id, "coffee-1")

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{prop_id}/attach",
        json={"attachedCharacterId": "not-placed-char", "attachedCharacterSlot": 1, "relationship": "held"},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "ATTACHMENT_INVALID"


def test_place_attached_prop_to_unoccupied_slot_rejected(client) -> None:
    project_id = _create_project_client(client)
    _seed_character(project_id, "korri")
    _seed_prop(project_id, "coffee-1", approved=True)
    document_id = _create_map(client, project_id)

    _place_character(client, project_id, document_id, "korri", slot_index=0)
    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={
            "label": "Cup",
            "propId": "coffee-1",
            "placementMode": "attached",
            "attachedCharacterSlot": 4,
            "relationship": "held",
        },
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "ATTACHMENT_INVALID"


# ---------------------------------------------------------------------------
# CDX-014 — _placed_project_prop_ids unions ERS snapshot + LIVE map placements
# ---------------------------------------------------------------------------


def _save_sheet(project_id: str, *, scene_id: str | None = None):
    sheet = orchestrator.create_sheet(
        project_id=project_id, name="Atrium", description="Glass atrium.", scene_id=scene_id
    )
    sheet.ers_composite_asset_id = "ers-lib"
    sheet.status = "registered"
    store.save_sheet(sheet)
    return sheet


def test_placed_project_prop_ids_unions_package_snapshot_and_live_map() -> None:
    from app.scene_creator.service import _placed_project_prop_ids

    project_id = _create_project("ERS Union")
    db = _session()
    try:
        prop_a = _seed_prop(project_id, "prop-a", approved=True)
        prop_b = _seed_prop(project_id, "prop-b", approved=True)

        sheet = _save_sheet(project_id)
        package = EnvironmentReferencePackage(
            project_id=project_id,
            scene_layout_id="map-ers",
            metadata={"sheet_id": sheet.sheetId},
            placements=[{"propId": prop_a.id, "label": "A", "assetId": "asset-a"}],
            directional_assets={"north": "asset-n", "east": None, "south": None, "west": None},
        )
        save_ers_package(db, project_id, package)

        # Approved prop placed on the LIVE map AFTER ERS generation.
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Live Map"))
        place_prop(db, project_id, doc.id, SpatialPropPlacementBody(label="B", propId=prop_b.id))

        ids = _placed_project_prop_ids(db, project_id, sheet.sheetId)
        assert prop_a.id in ids, "ERS snapshot placement must be preserved"
        assert prop_b.id in ids, "live-map approved placement must be auto-unioned (CDX-014)"
        assert len(ids) == 2
    finally:
        db.close()


def test_placed_project_prop_ids_skips_draft_and_unplaced_rows() -> None:
    from app.scene_creator.service import _placed_project_prop_ids

    project_id = _create_project("ERS Draft Skip")
    db = _session()
    try:
        draft = _seed_prop(project_id, "prop-draft-skip", approved=False)
        approved = _seed_prop(project_id, "prop-ok", approved=True)

        sheet = _save_sheet(project_id)
        package = EnvironmentReferencePackage(
            project_id=project_id,
            scene_layout_id="map-ers-2",
            metadata={"sheet_id": sheet.sheetId},
            placements=[{"propId": draft.id, "label": "Draft"}],
            directional_assets={"north": "asset-n", "east": None, "south": None, "west": None},
        )
        save_ers_package(db, project_id, package)

        doc = create_document(db, project_id, SpatialMapCreateBody(title="Live 2"))
        place_prop(db, project_id, doc.id, SpatialPropPlacementBody(label="OK", propId=approved.id))
        # map-only placeholder (empty propId) is legacy-tolerant and excluded.
        place_prop(db, project_id, doc.id, SpatialPropPlacementBody(label="Lib", assetId="asset-lib"))

        ids = _placed_project_prop_ids(db, project_id, sheet.sheetId)
        assert approved.id in ids
        assert draft.id not in ids
        assert len(ids) == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-015 — production handoff applies the approved-only rule to map propIds
# ---------------------------------------------------------------------------


def test_handoff_excludes_draft_prop_from_shot_prop_entity_ids() -> None:
    from app.scene_creator.production_handoff import synchronize_production_handoff
    from app.scene_creator.service import ensure_scene_id
    from app.spatial_map.ers_persistence import list_scene_shots

    project_id = _create_project("Handoff Filter")
    db = _session()
    try:
        draft = _seed_prop(project_id, "prop-handoff-draft", approved=False)
        approved = _seed_prop(project_id, "prop-handoff-ok", approved=True)

        scene = ensure_scene_id(db, project_id, "")
        sheet = _save_sheet(project_id, scene_id=scene.id)

        doc = create_document(db, project_id, SpatialMapCreateBody(title="Handoff Map", sceneId=scene.id))
        place_prop(db, project_id, doc.id, SpatialPropPlacementBody(label="Draft", propId=draft.id))
        place_prop(db, project_id, doc.id, SpatialPropPlacementBody(label="Approved", propId=approved.id))

        result = synchronize_production_handoff(db, project_id, scene_id=scene.id, sheet_id=sheet.sheetId)
        shots = list_scene_shots(db, project_id, scene_id=scene.id)
        assert shots, "handoff must create shots for an empty scene"
        for shot in shots:
            assert draft.id not in (shot.prop_entity_ids or []), (
                "draft prop must never be written into shot.prop_entity_ids (CDX-015)"
            )
        assert any(approved.id in (shot.prop_entity_ids or []) for shot in shots)
        assert approved.id in result["profile"]["propIds"]
        assert draft.id not in result["profile"]["propIds"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-013 — legacy tolerance: empty propId placeholders stay acceptable
# ---------------------------------------------------------------------------


def test_empty_prop_id_placeholder_still_accepted(client) -> None:
    project_id = _create_project_client(client)
    document_id = _create_map(client, project_id)

    res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Library Prop", "assetId": "asset-lib-1", "category": "prop"},
    )
    assert res.status_code == 200, res.text
    placement = res.json()["document"]["props"][0]
    assert placement["propId"] is None
    assert placement["assetId"] == "asset-lib-1"

    # Such a placeholder is map-only: it never propagates to shot prop ids.
    from app.scene_creator.service import _placed_project_prop_ids

    db = _session()
    try:
        ids = _placed_project_prop_ids(db, project_id, "")
        assert ids == []
    finally:
        db.close()
