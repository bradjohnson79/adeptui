"""Scene Creator Express/Standard — contracts, ERS resolver, routing, approval, Re-Take, Timeline."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from app.environment_reference_sheet import orchestrator, store
from app.environment_reference_sheet.contracts import DirectionalViewRecord
from app.scene_creator import generation as gen_mod
from app.scene_creator.ers_resolver import ErsResolveError, resolve_ers_for_sheet
from app.scene_creator.generation import build_candidate_plans, hosted_image_generation_available
from app.spatial_map.ers_contracts import EnvironmentReferencePackage, SceneShot
from app.spatial_map.ers_persistence import save_ers_package


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Scene Creator Test") -> str:
    from app.db import Project, init_db, SessionLocal

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _save_sheet(project_id: str, *, approved_north: str | None = None, scene_id: str | None = None):
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Atrium",
        description="Glass atrium, cool daylight.",
        scene_id=scene_id,
    )
    if approved_north:
        views = list(sheet.directionalViews or [])
        if views:
            views[0] = views[0].model_copy(update={"approvedAssetId": approved_north, "status": "approved"})
            sheet.directionalViews = views
        else:
            sheet.directionalViews = [
                DirectionalViewRecord(
                    direction="north",
                    title="North",
                    prompt="north view",
                    sourceDirection="north",
                    approvedAssetId=approved_north,
                    status="approved",
                )
            ]
    store.save_sheet(sheet)
    return sheet


def test_scene_shot_is_not_a_candidate() -> None:
    shot = SceneShot(project_id="p", scene_id="s", sheet_id="sheet")
    dumped = shot.model_dump()
    assert "candidates" in dumped
    assert dumped["scene_id"] == "s"
    assert dumped["approved_candidate_id"] is None
    assert dumped["take_memory"]["originalTakeIntent"] == {}


def test_hosted_image_generation_is_honestly_unavailable() -> None:
    assert hosted_image_generation_available() is False


def test_local_off_and_api_off_is_zero_jobs() -> None:
    try:
        build_candidate_plans(local_enabled=False, api_enabled=False)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Enable a Local or Cloud generator" in str(exc)


def test_api_on_when_unwired_does_not_route_local() -> None:
    try:
        build_candidate_plans(local_enabled=False, api_enabled=True)
        raise AssertionError("expected API unavailable")
    except ValueError as exc:
        assert "API Generation — Not Available" in str(exc)


def test_api_on_with_local_on_still_refuses_fake_api(monkeypatch) -> None:
    monkeypatch.setattr(gen_mod, "hosted_image_generation_available", lambda: False)
    try:
        build_candidate_plans(local_enabled=True, api_enabled=True)
        raise AssertionError("expected API unavailable")
    except ValueError as exc:
        assert "API Generation — Not Available" in str(exc)


def test_candidate_diversity_one_family_uses_distinct_seeds(monkeypatch) -> None:
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    plans = build_candidate_plans(local_enabled=True, api_enabled=False, local_family="zimage", seed=7)
    assert len(plans) == 4
    assert len({p["family"] for p in plans}) == 1
    assert len({p["seed"] for p in plans}) == 4
    assert all(p["source"] == "local" for p in plans)
    assert all(p["provenance_label"].startswith("LOCAL") for p in plans)


def test_candidate_count_one_is_a_valid_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    plans = build_candidate_plans(
        local_enabled=True, api_enabled=False, local_family="zimage", candidate_count=1, seed=3
    )
    assert len(plans) == 1
    assert plans[0]["index"] == 0


def test_resolve_sheet_without_package_builds_runtime_and_does_not_require_package_uuid() -> None:
    project_id = _create_project("ERS Resolver")
    north_id = str(uuid.uuid4())
    sheet = _save_sheet(project_id, approved_north=north_id)
    db = _session()
    try:
        package, runtime = resolve_ers_for_sheet(db, project_id, sheet.sheetId)
        assert runtime is True
        assert package.id.startswith("runtime-")
        assert package.metadata.get("sheet_id") == sheet.sheetId
        assert package.directional_assets.get("north") == north_id
        again, runtime2 = resolve_ers_for_sheet(db, project_id, sheet.sheetId)
        assert again.id == package.id
        assert runtime2 is False
    finally:
        db.close()


def test_resolve_prefers_existing_package_by_sheet_id() -> None:
    project_id = _create_project("ERS Existing Package")
    sheet = _save_sheet(project_id)
    db = _session()
    try:
        real = EnvironmentReferencePackage(
            project_id=project_id,
            scene_layout_id="map-1",
            metadata={"sheet_id": sheet.sheetId},
            directional_assets={"north": "asset-n", "east": None, "south": None, "west": None},
        )
        save_ers_package(db, project_id, real)
        package, runtime = resolve_ers_for_sheet(db, project_id, sheet.sheetId)
        assert runtime is False
        assert package.id == real.id
        assert package.directional_assets.get("north") == "asset-n"
    finally:
        db.close()


def test_resolve_missing_sheet_raises() -> None:
    db = _session()
    try:
        try:
            resolve_ers_for_sheet(db, "missing-project", "missing-sheet")
            raise AssertionError("expected missing sheet")
        except ErsResolveError:
            pass
    finally:
        db.close()


def test_four_candidates_do_not_create_four_shots(monkeypatch) -> None:
    from app.scene_creator.service import create_or_update_shot, generate_candidates
    from app.spatial_map.ers_persistence import list_scene_shots

    project_id = _create_project("One Shot Four Takes")
    sheet = _save_sheet(project_id)
    jobs: list[str] = []

    def _enqueue(db, pid, body, scene_id=None):
        job_id = str(uuid.uuid4())
        jobs.append(job_id)
        return SimpleNamespace(id=job_id)

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    db = _session()
    try:
        shot = create_or_update_shot(
            db, project_id, sheet_id=sheet.sheetId, intent="Two shot, medium wide, static"
        )
        generated = generate_candidates(
            db, project_id, shot.id, local_enabled=True, api_enabled=False, candidate_count=4
        )
        shots = list_scene_shots(db, project_id, scene_id=generated.scene_id)
        assert len(shots) == 1
        assert len(generated.candidates) == 4
        assert len(jobs) == 4
        assert generated.scene_id
        assert generated.approved_candidate_id is None
    finally:
        db.close()


def test_approve_then_retake_keeps_take_a(monkeypatch) -> None:
    from app.db import Asset, Job
    from app.scene_creator.service import approve_candidate, create_or_update_shot, generate_candidates, retake_shot

    project_id = _create_project("Retake Memory")
    sheet = _save_sheet(project_id)
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())))
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    db = _session()
    try:
        shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Korri at the bar")
        generated = generate_candidates(db, project_id, shot.id, local_enabled=True, api_enabled=False)
        take_a = generated.candidates[0]
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="scene_shot",
            kind="image",
            filename="take-a.png",
            path="take-a.png",
            production_approval="none",
        )
        db.add(asset)
        job = Job(
            id=take_a.job_id,
            project_id=project_id,
            kind="imagegen",
            status="done",
            params_json=json.dumps({"output_asset_id": asset.id}),
        )
        db.add(job)
        db.commit()
        approved = approve_candidate(db, project_id, generated.id, take_a.id)
        assert approved.approved_candidate_id == take_a.id
        db.refresh(asset)
        assert asset.production_approval == "approved"

        retaken = retake_shot(
            db,
            project_id,
            generated.id,
            correction="Make the lighting warmer",
            local_enabled=True,
            api_enabled=False,
        )
        assert retaken.approved_candidate_id == take_a.id
        assert len(retaken.candidates) == 5
        assert retaken.take_memory.userCorrection.get("text") == "Make the lighting warmer"
        assert retaken.take_memory.originalTakeIntent.get("intent") == "Korri at the bar"
    finally:
        db.close()


def test_generate_after_approve_requires_retake(monkeypatch) -> None:
    from app.db import Asset, Job
    from app.scene_creator.service import (
        SceneCreatorError,
        approve_candidate,
        create_or_update_shot,
        generate_candidates,
    )

    project_id = _create_project("Generate After Approve")
    sheet = _save_sheet(project_id)
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())))
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    db = _session()
    try:
        shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Korri waits")
        generated = generate_candidates(db, project_id, shot.id, local_enabled=True, api_enabled=False)
        take_a = generated.candidates[0]
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="scene_shot",
            kind="image",
            filename="take-a.png",
            path="take-a.png",
            production_approval="none",
        )
        db.add(asset)
        db.add(
            Job(
                id=take_a.job_id,
                project_id=project_id,
                kind="imagegen",
                status="done",
                params_json=json.dumps({"output_asset_id": asset.id}),
            )
        )
        db.commit()
        approve_candidate(db, project_id, generated.id, take_a.id)
        try:
            generate_candidates(db, project_id, generated.id, local_enabled=True, api_enabled=False)
            raise AssertionError("generate after approve should fail")
        except SceneCreatorError as exc:
            assert "Re-Take" in str(exc)
    finally:
        db.close()


def test_unapproved_cannot_send_to_timeline(monkeypatch) -> None:
    from app.scene_creator.service import (
        SceneCreatorError,
        create_or_update_shot,
        generate_candidates,
        send_approved_to_timeline,
    )

    project_id = _create_project("Approved Media")
    sheet = _save_sheet(project_id)
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())))
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    db = _session()
    try:
        shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Wide static")
        generated = generate_candidates(db, project_id, shot.id, local_enabled=True, api_enabled=False)
        try:
            send_approved_to_timeline(db, project_id, generated.id)
            raise AssertionError("unapproved send should fail")
        except SceneCreatorError as exc:
            assert "Approve a take" in str(exc)
    finally:
        db.close()


def test_one_candidate_approve_retake_and_timeline_metadata(monkeypatch) -> None:
    from app.db import Asset, Job
    from app.scene_creator.service import approve_candidate, create_or_update_shot, generate_candidates, retake_shot
    from app.spatial_map.ers_persistence import save_scene_shot

    project_id = _create_project("One Candidate Final")
    sheet = _save_sheet(project_id)
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())))
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: [
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ],
    )
    db = _session()
    try:
        shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Locked camera final")
        generated = generate_candidates(
            db, project_id, shot.id, local_enabled=True, api_enabled=False, candidate_count=1
        )
        assert len(generated.candidates) == 1
        take_a = generated.candidates[0]
        take_a.source_camera_id = "cam-1"
        take_a.camera_state_version = 7
        save_scene_shot(db, project_id, generated)
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="scene_shot",
            kind="image",
            filename="final.png",
            path="final.png",
            production_approval="none",
        )
        db.add(asset)
        db.add(
            Job(
                id=take_a.job_id,
                project_id=project_id,
                kind="imagegen",
                status="done",
                params_json=json.dumps({"output_asset_id": asset.id}),
            )
        )
        db.commit()
        approved = approve_candidate(db, project_id, generated.id, take_a.id)
        assert approved.approved_candidate_id == take_a.id
        assert len(approved.candidates) == 1
        assert approved.take_memory.takeState.get("sourceCameraId") == "cam-1"
        retaken = retake_shot(
            db,
            project_id,
            generated.id,
            correction="Keep the same camera, warmer light",
            local_enabled=True,
            api_enabled=False,
        )
        assert retaken.approved_candidate_id == take_a.id
        assert len(retaken.candidates) == 2
    finally:
        db.close()


def test_empty_scene_id_rejected_on_legacy_handoff() -> None:
    from app.scene_creator.timeline_handoff import send_scene_batch_to_timeline

    db = _session()
    try:
        result = send_scene_batch_to_timeline(db, "p", "b", scene_id="")
        assert result["ok"] is False
        assert result["error"] == "SCENE_ID_REQUIRED"
    finally:
        db.close()


def test_ensure_scene_creates_studio_row() -> None:
    from app.scene_creator.service import ensure_scene_id

    project_id = _create_project("Scene Ownership")
    db = _session()
    try:
        scene = ensure_scene_id(db, project_id, "")
        assert scene.id
        assert scene.project_id == project_id
        again = ensure_scene_id(db, project_id, "")
        assert again.id == scene.id
    finally:
        db.close()


def test_workspace_hydrate_resolves_sheet_id() -> None:
    from app.scene_creator.service import hydrate_workspace

    project_id = _create_project("Hydrate Workspace")
    sheet = _save_sheet(project_id)
    db = _session()
    try:
        body = hydrate_workspace(db, project_id)
        assert body["selected_sheet_id"] == sheet.sheetId
        assert body["selected_scene_id"]
        assert body["api_generation_available"] is False
        assert body["resolved_ers"]["runtime"] is True
    finally:
        db.close()
