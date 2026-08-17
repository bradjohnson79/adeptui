"""Scene Spatial Profile / production-handoff — pointer identity and idempotency."""

from __future__ import annotations

import uuid

from app.environment_reference_sheet import orchestrator, store
from app.scene_creator.production_handoff import (
    list_profiles,
    load_selection,
    reset_workspace,
    select_profile,
    synchronize_production_handoff,
)
from app.scene_creator.service import hydrate_workspace
from app.spatial_map.ers_persistence import list_scene_shots, save_scene_shot
from app.spatial_map.ers_contracts import SceneShot
from app.spatial_map.schemas import (
    SpatialCharacterPlacementBody,
    SpatialMapCreateBody,
    SpatialPropPlacementBody,
)
from app.spatial_map.service import create_document, place_character, place_prop


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Spatial Profile Test") -> str:
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


def _seed_canonical(db, project_id: str) -> None:
    """CDX-013/015: placements and handoff must reference canonical entities."""
    from app.character_identity.models import CharacterProfileRow
    from app.spatial_map.ers_contracts import PropEntity
    from app.spatial_map.ers_persistence import save_prop_entity

    existing = db.get(CharacterProfileRow, "korri-1")
    if existing is not None:
        db.delete(existing)
        db.commit()
    db.add(CharacterProfileRow(id="korri-1", project_id=project_id, name="Korri"))
    db.commit()
    save_prop_entity(
        db,
        project_id,
        PropEntity(
            id="prop-cup-1",
            project_id=project_id,
            tag="prop-cup-1",
            display_label="Cup",
            approved_asset_id="approved-cup-1",
        ),
    )


def _save_sheet(project_id: str, *, scene_id: str | None = None, composite: str = "ers-lib-1"):
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Café ERS",
        description="Warm café interior.",
        scene_id=scene_id,
    )
    sheet.ers_composite_asset_id = composite
    sheet.status = "registered"
    store.save_sheet(sheet)
    return sheet


def test_production_handoff_is_pointer_only_and_idempotent() -> None:
    project_id = _create_project("Schnick Coffee")
    db = _session()
    try:
        from app.scene_creator.service import ensure_scene_id

        scene = ensure_scene_id(db, project_id, "")
        _seed_canonical(db, project_id)
        sheet = _save_sheet(project_id, scene_id=scene.id, composite="ers-asset-canonical")
        doc = create_document(db, project_id, SpatialMapCreateBody(title="Schnick Coffee", sceneId=scene.id))
        place_character(
            db,
            project_id,
            doc.id,
            SpatialCharacterPlacementBody(characterId="korri-1", label="Korri", slotIndex=0),
        )
        place_prop(
            db,
            project_id,
            doc.id,
            SpatialPropPlacementBody(label="Cup", propId="prop-cup-1"),
        )

        first = synchronize_production_handoff(db, project_id, scene_id=scene.id, sheet_id=sheet.sheetId)
        second = synchronize_production_handoff(db, project_id, scene_id=scene.id, sheet_id=sheet.sheetId)

        assert first["handoffId"] == second["handoffId"]
        assert first["sceneId"] == scene.id
        assert first["sheetId"] == sheet.sheetId
        assert first["ersLibraryAssetId"] == "ers-asset-canonical"
        assert first["spatialMapId"] == doc.id
        assert second["noop"] is True
        assert second["revision"] == first["revision"] + 1
        assert "profile" in first
        profile = first["profile"]
        assert "ersPackageId" in profile
        assert profile.get("copiedErs") is None
        shots_a = [s.id for s in list_scene_shots(db, project_id, scene_id=scene.id)]
        shots_b = [s.id for s in list_scene_shots(db, project_id, scene_id=scene.id)]
        assert shots_a == shots_b
        assert len(list_profiles(db, project_id)) == 1
        assert "korri-1" in first["profile"]["characterIds"]
        assert "prop-cup-1" in first["profile"]["propIds"]
    finally:
        db.close()


def test_handoff_does_not_create_shots_when_scene_already_has_them() -> None:
    project_id = _create_project()
    db = _session()
    try:
        from app.scene_creator.service import ensure_scene_id

        scene = ensure_scene_id(db, project_id, "")
        sheet = _save_sheet(project_id, scene_id=scene.id)
        existing = SceneShot(project_id=project_id, scene_id=scene.id, sheet_id=sheet.sheetId, intent="Keep me")
        save_scene_shot(db, project_id, existing)
        result = synchronize_production_handoff(db, project_id, scene_id=scene.id, sheet_id=sheet.sheetId)
        shots = list_scene_shots(db, project_id, scene_id=scene.id)
        assert len(shots) == 1
        assert shots[0].id == existing.id
        assert shots[0].intent == "Keep me"
        assert shots[0].sheet_id == sheet.sheetId
        assert result["profile"]["shotIds"] == [existing.id]
    finally:
        db.close()


def test_reset_clears_selection_without_deleting_profile() -> None:
    project_id = _create_project()
    db = _session()
    try:
        from app.scene_creator.service import ensure_scene_id

        scene = ensure_scene_id(db, project_id, "")
        sheet = _save_sheet(project_id, scene_id=scene.id)
        result = synchronize_production_handoff(db, project_id, scene_id=scene.id, sheet_id=sheet.sheetId)
        reset = reset_workspace(db, project_id)
        assert reset["selectedProfileId"] is None
        assert reset["workspaceReset"] is True
        assert list_profiles(db, project_id)[0].handoffId == result["handoffId"]
        selection = load_selection(db, project_id)
        assert selection.selectedProfileId is None
        ws = hydrate_workspace(db, project_id)
        assert ws["selected_spatial_profile_id"] is None
        assert ws["workspace_reset"] is True
        assert any(p["handoffId"] == result["handoffId"] for p in ws["spatial_profiles"])
        selected = select_profile(db, project_id, result["handoffId"])
        assert selected["selectedProfileId"] == result["handoffId"]
        restored = hydrate_workspace(db, project_id, spatial_profile_id=result["handoffId"])
        assert restored["selected_spatial_profile_id"] == result["handoffId"]
        assert restored["selected_sheet_id"] == sheet.sheetId
        ctx = restored["production_context"]
        assert ctx is not None
        assert ctx["loaded"] is True
        assert ctx["handoffId"] == result["handoffId"]
        assert ctx["sceneId"] == scene.id
        assert ctx["ersLibraryAssetId"] == sheet.ers_composite_asset_id
        reset_workspace(db, project_id)
        reset_ws = hydrate_workspace(db, project_id)
        assert reset_ws["production_context"] is None
        bogus = hydrate_workspace(db, project_id, spatial_profile_id="not-a-real-profile")
        assert bogus["selected_spatial_profile_id"] is None
        assert bogus["production_context"] is None
    finally:
        db.close()


def test_handoff_ids_match_generation_context() -> None:
    project_id = _create_project("Identity")
    db = _session()
    try:
        from app.codirector.entity_resolver import compile_shot_prompt
        from app.scene_creator.ers_resolver import resolve_ers_for_sheet
        from app.scene_creator.service import _apply_cinematic, _shot_request_from_scene_shot, ensure_scene_id

        scene = ensure_scene_id(db, project_id, "")
        sheet = _save_sheet(project_id, scene_id=scene.id, composite="ers-lib-identity")
        result = synchronize_production_handoff(db, project_id, scene_id=scene.id, sheet_id=sheet.sheetId)
        shots = list_scene_shots(db, project_id, scene_id=scene.id)
        assert shots
        shot = shots[0]
        package, _runtime = resolve_ers_for_sheet(db, project_id, shot.sheet_id)
        body = compile_shot_prompt(db, project_id, _shot_request_from_scene_shot(shot), package)
        _apply_cinematic(body, shot)
        ctx = body["creativeContext"]
        assert ctx["sceneId"] == result["sceneId"]
        assert ctx["sheetId"] == result["sheetId"]
        assert ctx["ers_package_id"] == result["ersPackageId"]
        package_composite = str(getattr(package, "ers_composite_asset_id", "") or "")
        if package_composite:
            assert package_composite == result["ersLibraryAssetId"]
        assert ctx["sheetId"] == result["sheetId"]
        assert shot.character_ids == result["profile"]["characterIds"] or all(
            cid in (shot.character_ids or []) for cid in result["profile"]["characterIds"]
        )
    finally:
        db.close()


def test_select_profile_is_project_scoped() -> None:
    a = _create_project("A")
    b = _create_project("B")
    db = _session()
    try:
        from app.scene_creator.service import ensure_scene_id

        scene = ensure_scene_id(db, a, "")
        sheet = _save_sheet(a, scene_id=scene.id)
        result = synchronize_production_handoff(db, a, scene_id=scene.id, sheet_id=sheet.sheetId)
        try:
            select_profile(db, b, result["handoffId"])
            raised = False
        except Exception:
            raised = True
        assert raised is True
    finally:
        db.close()


def test_delete_shot_candidate_removes_library_asset_not_reset() -> None:
    from pathlib import Path

    from app.db import Asset
    from app.scene_creator.production_handoff import reset_workspace
    from app.scene_creator.service import delete_shot_candidate, ensure_scene_id
    from app.spatial_map.ers_contracts import SceneShotCandidate

    project_id = _create_project("Delete Take")
    db = _session()
    try:
        scene = ensure_scene_id(db, project_id, "")
        sheet = _save_sheet(project_id, scene_id=scene.id, composite="ers-keep")
        asset_id = str(uuid.uuid4())
        asset_path = Path("data") / "tmp-take-delete" / f"{asset_id}.png"
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(b"png")
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                kind="image",
                tag="scene_take",
                filename=asset_path.name,
                path=str(asset_path),
            )
        )
        db.commit()
        shot = SceneShot(
            project_id=project_id,
            scene_id=scene.id,
            sheet_id=sheet.sheetId,
            intent="Korri at the counter",
            candidates=[
                SceneShotCandidate(
                    id="cand-take-1",
                    shot_id="pending",
                    asset_id=asset_id,
                    status="complete",
                    take_label="Take A",
                    quality_profile="final",
                )
            ],
            approved_candidate_id="cand-take-1",
        )
        shot.candidates[0].shot_id = shot.id
        save_scene_shot(db, project_id, shot)
        updated = delete_shot_candidate(db, project_id, shot.id, "cand-take-1")
        assert updated.candidates == []
        assert updated.approved_candidate_id is None
        assert db.get(Asset, asset_id) is None
        assert asset_path.exists() is False
        reset_workspace(db, project_id)
        assert db.get(Asset, asset_id) is None
    finally:
        db.close()
