"""Prop Creator Express — PropEntity identity, drafts, routing honesty, compiler, approval."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from app.prop_creator import generation as prop_gen
from app.prop_creator.generation import build_prop_candidate_plans
from app.prop_creator.prompt import IDENTITY_VIEW, compile_prop_prompt
from app.scene_creator.generation import hosted_image_generation_available
from app.spatial_map.ers_contracts import PropEntity


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Prop Creator Test") -> str:
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


def _families(*rows):
    return list(rows)


def test_draft_saves_without_approval() -> None:
    from app.prop_creator.service import create_or_update_prop, list_props

    project_id = _create_project("Draft Prop")
    db = _session()
    try:
        prop = create_or_update_prop(
            db,
            project_id,
            name="Coffee Mug",
            visual_style="live_action",
            description="White ceramic mug with a chip on the rim.",
        )
        assert prop.id
        assert prop.display_label == "Coffee Mug"
        assert not (prop.approved_asset_id or "").strip()
        assert (prop.library_asset_id or "") == ""
        assert list_props(db, project_id, approved_only=True) == []
        listed = list_props(db, project_id, approved_only=False)
        assert len(listed) == 1
        assert listed[0].id == prop.id
    finally:
        db.close()


def test_library_asset_id_mirrors_approved_only(monkeypatch) -> None:
    from app.db import Asset, Job
    from app.prop_creator.service import approve_candidate, create_or_update_prop, generate_candidates

    project_id = _create_project("Approve Mirror")
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())))
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ),
    )
    db = _session()
    try:
        prop = create_or_update_prop(db, project_id, name="Rifle")
        generated = generate_candidates(db, project_id, prop.id, local_enabled=True, api_enabled=False)
        take = generated.candidates[0]
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="prop",
            kind="image",
            filename="rifle.png",
            path="rifle.png",
            production_approval="none",
        )
        db.add(asset)
        db.add(
            Job(
                id=take.job_id,
                project_id=project_id,
                kind="imagegen",
                status="done",
                params_json=json.dumps({"output_asset_id": asset.id}),
            )
        )
        db.commit()
        approved = approve_candidate(db, project_id, generated.id, take.id)
        assert approved.approved_asset_id == asset.id
        assert approved.library_asset_id == asset.id
        from app.prop_creator.service import list_props

        assert [p.id for p in list_props(db, project_id, approved_only=True)] == [approved.id]
    finally:
        db.close()


def test_clear_reference_keeps_approved_identity() -> None:
    from app.prop_creator.service import create_or_update_prop
    from app.spatial_map.ers_persistence import save_prop_entity

    project_id = _create_project("Reference Unlink")
    db = _session()
    try:
        prop = create_or_update_prop(
            db,
            project_id,
            name="Table",
            reference_asset_id="ref-1",
        )
        prop.approved_asset_id = "approved-9"
        prop.library_asset_id = "approved-9"
        save_prop_entity(db, project_id, prop)
        updated = create_or_update_prop(
            db,
            project_id,
            prop_id=prop.id,
            name="Table",
            clear_reference=True,
        )
        assert updated.reference_asset_id is None
        assert updated.approved_asset_id == "approved-9"
        assert updated.library_asset_id == "approved-9"
    finally:
        db.close()


def test_compiler_is_identity_still_not_a_held_scene() -> None:
    prop = PropEntity(
        project_id="p",
        display_label="Coffee Mug",
        description="White ceramic diner mug.",
        visual_style="documentary_realism",
    )
    compiled = compile_prop_prompt(prop)
    prompt = compiled["prompt"].lower()
    assert "coffee mug" in prompt
    assert "white ceramic diner mug" in prompt
    assert "photorealistic" in prompt
    assert IDENTITY_VIEW.split(",")[0].lower() in prompt
    assert "four-view" in prompt
    assert "character holding the prop" in compiled["negative_prompt"]
    assert "environment scene" in compiled["negative_prompt"]


def test_no_reference_is_description_guided(monkeypatch) -> None:
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True},
            {"id": "illustrious", "label": "Illustrious XL", "executable": True, "supportsReferences": False},
        ),
    )
    plans = build_prop_candidate_plans(local_enabled=True, api_enabled=False, has_reference=False, seed=3)
    assert len(plans) == 4
    assert all(p["conditioning"] == "description_guided" for p in plans)
    assert all("Description Guided" in p["provenance_label"] for p in plans)


def test_reference_keeps_txt2img_as_description_guided(monkeypatch) -> None:
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True},
            {"id": "illustrious", "label": "Illustrious XL", "executable": True, "supportsReferences": False},
            {"id": "qwen_image", "label": "Qwen Image", "executable": True, "supportsReferences": False},
        ),
    )
    plans = build_prop_candidate_plans(local_enabled=True, api_enabled=False, has_reference=True, seed=4)
    by_family = {p["family"]: p for p in plans}
    assert by_family["zimage"]["conditioning"] == "reference_conditioned"
    assert "Reference Conditioned" in by_family["zimage"]["provenance_label"]
    assert by_family["illustrious"]["conditioning"] == "description_guided"
    assert by_family["qwen_image"]["conditioning"] == "description_guided"
    assert "Reference Conditioned" not in by_family["illustrious"]["provenance_label"]


def test_local_off_and_api_off_is_zero_jobs() -> None:
    try:
        build_prop_candidate_plans(local_enabled=False, api_enabled=False)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Enable a Local or API generator" in str(exc)


def test_api_on_when_unwired_is_not_available() -> None:
    assert hosted_image_generation_available() is False
    try:
        build_prop_candidate_plans(local_enabled=False, api_enabled=True)
        raise AssertionError("expected API unavailable")
    except ValueError as exc:
        assert "API Generation — Not Available" in str(exc)


def test_api_on_with_local_on_still_refuses_fake_api(monkeypatch) -> None:
    monkeypatch.setattr(prop_gen, "hosted_image_generation_available", lambda: False)
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ),
    )
    try:
        build_prop_candidate_plans(local_enabled=True, api_enabled=True)
        raise AssertionError("expected API unavailable")
    except ValueError as exc:
        assert "API Generation — Not Available" in str(exc)


def test_generate_attaches_pixels_only_on_reference_conditioned(monkeypatch) -> None:
    from app.prop_creator.service import create_or_update_prop, generate_candidates

    project_id = _create_project("Pixel Honesty")
    captured: list[dict] = []

    def _enqueue(_db, _project_id, body):
        captured.append(body)
        return SimpleNamespace(id=str(uuid.uuid4()))

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True},
            {"id": "illustrious", "label": "Illustrious XL", "executable": True, "supportsReferences": False},
        ),
    )
    db = _session()
    try:
        prop = create_or_update_prop(
            db,
            project_id,
            name="Mug",
            reference_asset_id="ref-pixels",
        )
        generate_candidates(db, project_id, prop.id, local_enabled=True, api_enabled=False)
        assert len(captured) == 4
        zimage = [b for b in captured if b["modelFamilyPreference"] == "zimage"]
        illustrious = [b for b in captured if b["modelFamilyPreference"] == "illustrious"]
        assert zimage
        assert all(b.get("source_asset_id") == "ref-pixels" for b in zimage)
        assert illustrious
        assert all("source_asset_id" not in b for b in illustrious)
        assert all(b["creativeContext"].get("conditioning") != "reference_conditioned" for b in illustrious)
    finally:
        db.close()


def test_retry_replaces_one_candidate(monkeypatch) -> None:
    from app.prop_creator.service import create_or_update_prop, generate_candidates, retry_candidate

    project_id = _create_project("Retry One")
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())))
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True}
        ),
    )
    db = _session()
    try:
        prop = create_or_update_prop(db, project_id, name="Lamp")
        generated = generate_candidates(db, project_id, prop.id, local_enabled=True, api_enabled=False)
        failed_id = generated.candidates[1].id
        sibling_ids = [c.id for c in generated.candidates if c.id != failed_id]
        retried = retry_candidate(db, project_id, generated.id, failed_id)
        assert len(retried.candidates) == 4
        assert failed_id not in [c.id for c in retried.candidates]
        assert all(sid in [c.id for c in retried.candidates] for sid in sibling_ids)
    finally:
        db.close()


def test_scene_creator_resolves_approved_prop_visual() -> None:
    from app.codirector.entity_resolver import _prop_metadata, compile_shot_prompt
    from app.scene_creator.service import _ensure_placed_project_props, _hydrate_prop
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage, SceneShot, ShotRequest
    from app.spatial_map.ers_persistence import save_ers_package, save_prop_entity
    from app.environment_reference_sheet import orchestrator, store

    project_id = _create_project("Scene Prop Resolve")
    db = _session()
    try:
        prop = PropEntity(
            project_id=project_id,
            tag="coffee-mug",
            display_label="Coffee Mug",
            description="White ceramic diner mug.",
            approved_asset_id="approved-visual",
            library_asset_id="approved-visual",
            reference_asset_id="source-ref",
        )
        save_prop_entity(db, project_id, prop)
        meta = _prop_metadata(db, project_id, [prop.id])
        assert meta[0]["approved_asset_id"] == "approved-visual"
        assert meta[0]["library_asset_id"] == "approved-visual"
        assert meta[0]["description"] == "White ceramic diner mug."
        hydrated = _hydrate_prop(
            db,
            project_id,
            prop_id=prop.id,
            asset_id="stale-library",
            label="ignored",
        )
        assert hydrated["prop_id"] == prop.id
        assert hydrated["approved_asset_id"] == "approved-visual"
        assert hydrated["description"] == "White ceramic diner mug."

        sheet = orchestrator.create_sheet(project_id=project_id, name="Bar", description="Bar")
        store.save_sheet(sheet)
        package = EnvironmentReferencePackage(
            project_id=project_id,
            scene_layout_id="map-1",
            metadata={"sheet_id": sheet.sheetId},
            placements=[{"propId": prop.id, "label": "Coffee Mug", "assetId": "stale-library"}],
            directional_assets={"north": "north-ref", "east": None, "south": None, "west": None},
        )
        save_ers_package(db, project_id, package)
        shot = SceneShot(project_id=project_id, scene_id="s1", sheet_id=sheet.sheetId)
        assert shot.prop_entity_ids == []
        bound = _ensure_placed_project_props(db, project_id, shot)
        assert bound == [prop.id]
        parsed = ShotRequest(
            index=0,
            raw_text="The mug on the bar",
            prop_entities=shot.prop_entity_ids,
        )
        compiled = compile_shot_prompt(db, project_id, parsed, ers_package=package)
        prompt = (compiled.get("prompt") or "").lower()
        assert "coffee mug" in prompt
        assert "white ceramic diner mug" in prompt
        refs = compiled.get("reference_image_ids") or compiled.get("referenceImage") or []
        if isinstance(refs, str):
            refs = [refs]
        ctx = compiled.get("creativeContext") or {}
        ref_ids = refs or ctx.get("reference_image_ids") or ctx.get("referenceImageIds") or []
        visual_ok = "approved-visual" in str(compiled)
        assert visual_ok or "approved-visual" in [str(x) for x in ref_ids]
    finally:
        db.close()
