"""Scene Creator Inpaint / Region Edit — no silent txt2img fallback."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from app.environment_reference_sheet import orchestrator, store
from app.environment_reference_sheet.contracts import DirectionalViewRecord
from app.scene_creator import generation as gen_mod
from app.scene_creator.generation import (
    REGION_EDIT_UNSUPPORTED_MESSAGE,
    VISUAL_INHERITANCE_BLOCKED_MESSAGE,
    certified_visual_edit_path,
    family_region_edit_capability,
)
from app.scene_creator.service import (
    SceneCreatorError,
    apply_region_edit_compile,
    approve_candidate,
    compile_region_edit_for_final,
    create_or_update_shot,
    generate_candidates,
    region_edit_shot,
)
from app.spatial_map.ers_contracts import SceneShot, SceneShotCandidate, SceneShotTakeMemory
from app.spatial_map.ers_persistence import save_scene_shot


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Region Edit Test") -> str:
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


def _save_sheet(project_id: str):
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Atrium",
        description="Glass atrium, cool daylight.",
    )
    views = list(sheet.directionalViews or [])
    if views:
        views[0] = views[0].model_copy(update={"approvedAssetId": "north-asset", "status": "approved"})
        sheet.directionalViews = views
    else:
        sheet.directionalViews = [
            DirectionalViewRecord(
                direction="north",
                title="North",
                prompt="north view",
                sourceDirection="north",
                approvedAssetId="north-asset",
                status="approved",
            )
        ]
    store.save_sheet(sheet)
    return sheet


def _families(*ids: str):
    labels = {
        "zimage": "Z-Image Turbo",
        "flux": "FLUX.1 Kontext [dev]",
        "qwen2512": "Qwen Image 2512",
        "illustrious": "Illustrious XL 1.0 (Anime)",
    }
    out = []
    for fam in ids:
        caps = family_region_edit_capability(fam)
        out.append(
            {
                "id": fam,
                "label": labels.get(fam, fam),
                "executable": True,
                "supportsReferences": True,
                "supportsEditing": caps["supportsEditing"],
                "supportsInpaint": caps["supportsInpaint"],
            }
        )
    return out


def _seed_shot_with_parent(monkeypatch, *, family: str = "zimage", camera_version: int = 4):
    from app.db import Asset, Job

    project_id = _create_project(f"RE {family}")
    sheet = _save_sheet(project_id)
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: _families(family),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda *a, **k: SimpleNamespace(id=str(uuid.uuid4())),
    )
    db = _session()
    shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Korri at the bar")
    generated = generate_candidates(
        db, project_id, shot.id, local_enabled=True, api_enabled=False, local_family=family, candidate_count=1
    )
    take_a = generated.candidates[0]
    take_a.camera_state_version = camera_version
    take_a.camera_state_hash = "hash-v4"
    take_a.source_camera_id = "cam-1"
    save_scene_shot(db, project_id, generated)
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
    approved = approve_candidate(db, project_id, generated.id, take_a.id)
    return db, project_id, approved, take_a, asset.id


def _pin_runtime(monkeypatch, workflow_key: str, family: str):
    captured: dict[str, object] = {}

    class _Contract:
        def __init__(self) -> None:
            self.workflow_key = workflow_key

        def to_pinned_snapshot(self) -> dict:
            return {"workflowKey": workflow_key, "modelFamily": family}

    def _resolve(*args, **kwargs):
        captured["resolve"] = {"args": args, "kwargs": kwargs}
        force = kwargs.get("force_workflow_key") or ""
        if "txt2img" in str(force):
            raise AssertionError("region edit must not pin txt2img")
        return _Contract()

    def _enqueue(db, *, project_id, compiled, body):
        captured["compiled"] = compiled
        captured["body"] = body
        captured["workflowKey"] = compiled.get("workflowKey") or (compiled.get("imageRuntime") or {}).get(
            "workflowKey"
        )
        return {"jobId": str(uuid.uuid4()), "workflowKey": captured["workflowKey"]}

    monkeypatch.setattr("app.image_runtime.contract.resolve_image_workflow", _resolve)
    monkeypatch.setattr("app.image_product.edit_service._enqueue_compiled", _enqueue)
    return captured


def test_family_capability_labels_are_frozen() -> None:
    assert family_region_edit_capability("zimage")["label"] == "Native Inpaint"
    assert family_region_edit_capability("zimage")["supportsInpaint"] is True
    assert family_region_edit_capability("flux")["label"] == "Image Edit"
    assert family_region_edit_capability("flux")["supportsInpaint"] is False
    assert family_region_edit_capability("qwen2512")["label"] == "Unsupported"
    assert family_region_edit_capability("illustrious")["label"] == "Unsupported"


def test_unsupported_family_raises_and_does_not_enqueue_txt2img(monkeypatch) -> None:
    db, project_id, shot, _take, asset_id = _seed_shot_with_parent(monkeypatch, family="qwen2512")
    enqueued: list[str] = []

    def _enqueue(*a, **k):
        enqueued.append("hit")
        raise AssertionError("unsupported family must not enqueue")

    monkeypatch.setattr("app.image_product.edit_service._enqueue_compiled", _enqueue)
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no txt2img silent fallback")),
    )
    try:
        try:
            region_edit_shot(
                db,
                project_id,
                shot.id,
                operation="remove",
                prompt="the extra person on the left",
                mask_asset_id="mask-1",
                source_asset_id=asset_id,
                local_family="qwen2512",
            )
            raise AssertionError("expected unsupported error")
        except SceneCreatorError as exc:
            assert REGION_EDIT_UNSUPPORTED_MESSAGE in str(exc)
        assert enqueued == []
    finally:
        db.close()


def test_illustrious_is_unsupported(monkeypatch) -> None:
    db, project_id, shot, _take, asset_id = _seed_shot_with_parent(monkeypatch, family="illustrious")
    try:
        try:
            region_edit_shot(
                db,
                project_id,
                shot.id,
                operation="remove",
                prompt="the extra cup",
                mask_asset_id="mask-1",
                source_asset_id=asset_id,
                local_family="illustrious",
            )
            raise AssertionError("expected unsupported error")
        except SceneCreatorError as exc:
            assert "cannot edit a region" in str(exc)
    finally:
        db.close()


def test_zimage_region_edit_sets_inpaint_not_txt2img(monkeypatch) -> None:
    captured = _pin_runtime(monkeypatch, "zimage.inpaint", "zimage")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="zimage")
    try:
        edited = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="remove",
            prompt="the extra person on the left",
            mask_asset_id="mask-asset-9",
            source_asset_id=asset_id,
            local_family="zimage",
            stage="preview",
        )
        assert captured["workflowKey"] == "zimage.inpaint"
        assert "txt2img" not in str(captured["workflowKey"])
        force = (captured.get("resolve") or {}).get("kwargs", {}).get("force_workflow_key")
        assert force == "zimage.inpaint"
        intent = (edited.take_memory.userCorrection or {}).get("region_edits") or []
        assert intent[0]["workflow_key"] == "zimage.inpaint"
        assert intent[0]["maskAssetId"] == "mask-asset-9"
        assert edited.approved_candidate_id == parent.id
        assert len(edited.candidates) == 2
        child = edited.candidates[-1]
        assert child.kind == "region_edit"
        assert child.parent_candidate_id == parent.id
        assert child.camera_state_version == parent.camera_state_version == 4
        assert child.edit_operation == "remove"
        assert child.mask_id == "mask-asset-9"
        masks = (captured.get("compiled") or {}).get("imageEditIntent", {}).get("masks") or []
        assert masks[0]["maskAssetId"] == "mask-asset-9"
    finally:
        db.close()


def test_flux_region_edit_is_image_edit_not_native_inpaint(monkeypatch) -> None:
    captured = _pin_runtime(monkeypatch, "flux.img2img", "flux")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="flux")
    try:
        edited = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="replace",
            prompt="a red lantern",
            mask_asset_id="mask-flux",
            source_asset_id=asset_id,
            local_family="flux",
        )
        assert captured["workflowKey"] == "flux.img2img"
        assert "inpaint" not in str(captured["workflowKey"])
        child = edited.candidates[-1]
        assert "Image Edit" in child.provenance_label
        assert "Native Inpaint" not in child.provenance_label
        assert child.parent_candidate_id == parent.id
        assert child.camera_state_version == 4
    finally:
        db.close()


def test_candidate_appended_parent_and_approval_preserved(monkeypatch) -> None:
    _pin_runtime(monkeypatch, "zimage.inpaint", "zimage")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="zimage")
    try:
        edited = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="modify",
            prompt="soften the neon",
            mask_asset_id="mask-2",
            source_asset_id=asset_id,
            local_family="zimage",
        )
        assert edited.approved_candidate_id == parent.id
        assert edited.candidates[0].id == parent.id
        assert edited.candidates[-1].kind == "region_edit"
        assert edited.candidates[-1].camera_state_version == parent.camera_state_version
    finally:
        db.close()


def test_strategy_b_prompt_contains_approved_remove_text() -> None:
    parent = SceneShotCandidate(
        id="parent-1",
        shot_id="shot-1",
        index=0,
        status="complete",
        asset_id="asset-parent",
        family="zimage",
        camera_state_version=3,
        take_label="Take A",
    )
    child = SceneShotCandidate(
        id="edit-1",
        shot_id="shot-1",
        index=1,
        status="complete",
        asset_id="asset-edit",
        family="zimage",
        kind="region_edit",
        parent_candidate_id="parent-1",
        edit_operation="remove",
        mask_id="mask-1",
        camera_state_version=3,
        quality_profile="draft",
        take_label="Region Edit B",
    )
    shot = SceneShot(
        project_id="p",
        scene_id="s",
        sheet_id="sheet",
        intent="Two shot at the bar",
        prompt="Two shot at the bar",
        candidates=[parent, child],
        approved_candidate_id="edit-1",
        take_memory=SceneShotTakeMemory(
            userCorrection={
                "region_edits": [
                    {
                        "operation": "remove",
                        "prompt": "the extra person on the left",
                        "maskAssetId": "mask-1",
                        "candidate_id": "edit-1",
                        "approved": True,
                    }
                ]
            }
        ),
    )
    prompt, extras = compile_region_edit_for_final(shot, "Two shot at the bar")
    assert "Do not include the removed extra" in prompt
    assert "the extra person on the left" in prompt
    assert extras["strategy"] == "A"
    assert extras["sourceAssetId"] == "asset-edit"


def test_certified_visual_edit_path_skips_draft_qwen_edit() -> None:
    zimage = certified_visual_edit_path("zimage")
    assert zimage is not None
    assert zimage["workflowKey"] == "zimage.ref_edit"
    assert zimage["width"] == 1024
    flux = certified_visual_edit_path("flux")
    assert flux is not None
    assert flux["workflowKey"] == "flux.img2img"
    assert certified_visual_edit_path("qwen2512") is None
    assert certified_visual_edit_path("illustrious") is None
    assert family_region_edit_capability("qwen2512")["label"] == "Unsupported"


def test_strategy_c_when_family_cannot_visually_inherit() -> None:
    child = SceneShotCandidate(
        id="edit-1",
        shot_id="shot-1",
        index=1,
        status="complete",
        asset_id="asset-edit",
        family="qwen2512",
        kind="region_edit",
        edit_operation="remove",
    )
    shot = SceneShot(
        project_id="p",
        scene_id="s",
        sheet_id="sheet",
        prompt="Wide static",
        candidates=[child],
        approved_candidate_id="edit-1",
        take_memory=SceneShotTakeMemory(
            userCorrection={
                "region_edits": [
                    {
                        "operation": "remove",
                        "prompt": "the boom mic",
                        "maskAssetId": "mask-x",
                        "candidate_id": "edit-1",
                        "approved": True,
                    }
                ]
            }
        ),
    )
    shot.generator.local_family = "qwen2512"
    prompt, extras = compile_region_edit_for_final(shot, "Wide static")
    assert "Do not include the removed extra" in prompt
    assert extras["strategy"] == "C"
    assert extras["sourceAssetId"] == ""
    assert extras["visualInheritanceBlocked"] is True


def test_enqueue_final_includes_strategy_b_remove_text(monkeypatch) -> None:
    from app.scene_creator.service import _enqueue_shot_candidates

    captured: list[dict] = []

    def _enqueue(db, pid, body, scene_id=None):
        captured.append(body)
        return SimpleNamespace(id=str(uuid.uuid4()))

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: _families("zimage"),
    )
    project_id = _create_project("Strategy B Final")
    sheet = _save_sheet(project_id)
    db = _session()
    try:
        shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Locked camera final")
        child = SceneShotCandidate(
            shot_id=shot.id,
            index=0,
            status="complete",
            asset_id="asset-edit",
            family="zimage",
            kind="region_edit",
            edit_operation="remove",
            quality_profile="draft",
        )
        shot.candidates = [child]
        shot.approved_candidate_id = child.id
        shot.take_memory.userCorrection = {
            "region_edits": [
                {
                    "operation": "remove",
                    "prompt": "the extra person on the left",
                    "maskAssetId": "mask-1",
                    "candidate_id": child.id,
                    "approved": True,
                }
            ]
        }
        save_scene_shot(db, project_id, shot)
        _enqueue_shot_candidates(
            db,
            project_id,
            shot,
            local_enabled=True,
            api_enabled=False,
            local_family="zimage",
            api_model="",
            candidate_count=1,
            quality_profile="final",
        )
        assert captured
        prompt = str(captured[0].get("prompt") or "")
        assert "Do not include the removed extra" in prompt
        assert "the extra person on the left" in prompt
        assert captured[0].get("sourceAssetId") == "asset-edit"
        assert captured[0].get("source_asset_id") == "asset-edit"
        assert captured[0].get("operation") == "image.edit"
        assert captured[0].get("width") == 1024
        assert captured[0].get("height") == 1024
        ctx = captured[0].get("creativeContext") or {}
        assert ctx.get("workflowKey") == "zimage.ref_edit"
        assert ctx.get("finalStrategy") == "A"
        assert ctx.get("approvedEditedPreviewAssetId") == "asset-edit"
        assert captured[0].get("forceWorkflowKey") == "zimage.ref_edit"
        assert captured[0].get("allow_force_workflow_key") is True
        cine = ctx.get("cinematographer") or {}
        assert "txt2img" not in str(ctx.get("workflowKey") or "")
        assert isinstance(cine, dict)
    finally:
        db.close()


def test_approved_preview_region_edit_does_not_block_final() -> None:
    from app.scene_creator.service import approved_look_blocks_final

    preview_edit = SceneShotCandidate(
        id="edit-preview",
        shot_id="shot-1",
        index=0,
        status="complete",
        asset_id="asset-edit",
        family="zimage",
        kind="region_edit",
        quality_profile="draft",
    )
    shot = SceneShot(
        project_id="p",
        scene_id="s",
        sheet_id="sheet",
        candidates=[preview_edit],
        approved_candidate_id="edit-preview",
    )
    assert approved_look_blocks_final(shot) is False

    final_take = SceneShotCandidate(
        id="take-a",
        shot_id="shot-1",
        index=1,
        status="complete",
        asset_id="asset-final",
        family="qwen2512",
        quality_profile="final",
    )
    shot.candidates = [preview_edit, final_take]
    shot.approved_candidate_id = "take-a"
    assert approved_look_blocks_final(shot) is True


def test_qwen_final_raises_when_approved_region_edit_exists(monkeypatch) -> None:
    from app.scene_creator.service import _enqueue_shot_candidates

    captured: list[dict] = []

    def _enqueue(db, pid, body, scene_id=None):
        captured.append(body)
        return SimpleNamespace(id=str(uuid.uuid4()))

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: _families("qwen2512"),
    )
    project_id = _create_project("Qwen T2I Refusal")
    sheet = _save_sheet(project_id)
    db = _session()
    try:
        shot = create_or_update_shot(db, project_id, sheet_id=sheet.sheetId, intent="Locked camera final")
        child = SceneShotCandidate(
            shot_id=shot.id,
            index=0,
            status="complete",
            asset_id="asset-edit",
            family="qwen2512",
            kind="region_edit",
            edit_operation="remove",
            quality_profile="draft",
        )
        shot.candidates = [child]
        shot.approved_candidate_id = child.id
        shot.take_memory.userCorrection = {
            "region_edits": [
                {
                    "operation": "remove",
                    "prompt": "the extra person on the left",
                    "maskAssetId": "mask-1",
                    "candidate_id": child.id,
                    "approved": True,
                }
            ]
        }
        save_scene_shot(db, project_id, shot)
        try:
            _enqueue_shot_candidates(
                db,
                project_id,
                shot,
                local_enabled=True,
                api_enabled=False,
                local_family="qwen2512",
                api_model="",
                candidate_count=1,
                quality_profile="final",
            )
            raise AssertionError("qwen T2I final must be refused")
        except SceneCreatorError as exc:
            assert VISUAL_INHERITANCE_BLOCKED_MESSAGE in str(exc)
        assert captured == []
    finally:
        db.close()


def test_sync_final_assets_from_shots_overwrites_stale_lineage() -> None:
    from app.scene_creator.cinematographer import CameraLineage, SceneCameraRecord, SceneCinematographerPack
    from app.scene_creator.cinematographer_service import sync_final_assets_from_shots

    rec = SceneCameraRecord(
        cameraId="cam-1",
        cameraSlot=0,
        lineage=CameraLineage(finalJobId="job-final", finalAssetId="stale-asset"),
    )
    pack = SceneCinematographerPack(scene_id="s", cameras=[rec])
    shot = SceneShot(
        project_id="p",
        scene_id="s",
        sheet_id="sheet",
        candidates=[
            SceneShotCandidate(
                id="take-a",
                shot_id="shot-1",
                index=0,
                job_id="job-final",
                status="complete",
                asset_id="library-asset",
                quality_profile="final",
            )
        ],
    )
    assert sync_final_assets_from_shots(pack, [shot]) is True
    assert pack.cameras[0].lineage.finalAssetId == "library-asset"


def test_operation_profiles_pin_denoise_and_grow(monkeypatch) -> None:
    from app.scene_creator.region_edit_profiles import operation_profile

    add = operation_profile("add", expand="wide")
    assert add["denoise"] == 0.94
    assert add["grow_mask_by"] == 14
    modify = operation_profile("modify")
    assert 0.78 <= modify["denoise"] <= 0.85
    assert modify["grow_mask_by"] == 8
    remove = operation_profile("remove", expand="tight")
    assert remove["grow_mask_by"] == 2

    captured = _pin_runtime(monkeypatch, "zimage.inpaint", "zimage")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="zimage")
    try:
        edited = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="add",
            prompt="a handmade ceramic coffee cup",
            mask_asset_id="mask-add",
            source_asset_id=asset_id,
            local_family="zimage",
            expand="wide",
        )
        meta = ((captured.get("compiled") or {}).get("imageIntent") or {}).get("metadata") or {}
        assert meta["denoise"] == 0.94
        assert meta["grow_mask_by"] == 14
        assert "Create the described object" in str(((captured.get("compiled") or {}).get("imageIntent") or {}).get("prompt") or "")
        assert edited.candidates[-1].take_label.startswith("Inpaint")
        assert "Add" in edited.candidates[-1].take_label
        assert captured["body"]["grow_mask_by"] == 14
        ctx = captured["body"].get("creativeContext") or {}
        assert isinstance(ctx, dict)
        if ctx.get("cinematographer"):
            assert isinstance(ctx["cinematographer"], dict)
    finally:
        db.close()


def test_mask_too_small_blocks_enqueue(monkeypatch, tmp_path) -> None:
    from PIL import Image

    from app.scene_creator.region_edit_profiles import MASK_TOO_SMALL_MESSAGE, assert_mask_large_enough

    tiny = tmp_path / "tiny-mask.png"
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(tiny)
    try:
        assert_mask_large_enough(tiny)
        raise AssertionError("empty mask must be rejected")
    except ValueError as exc:
        assert MASK_TOO_SMALL_MESSAGE in str(exc)

    captured = _pin_runtime(monkeypatch, "zimage.inpaint", "zimage")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="zimage")
    try:
        monkeypatch.setattr(
            "app.image_product.masks.get_mask_path",
            lambda pid, mid: str(tiny),
        )
        try:
            region_edit_shot(
                db,
                project_id,
                shot.id,
                operation="modify",
                prompt="irritated expression",
                mask_asset_id="mask-tiny",
                source_asset_id=asset_id,
                local_family="zimage",
            )
            raise AssertionError("tiny mask must not enqueue")
        except SceneCreatorError as exc:
            assert MASK_TOO_SMALL_MESSAGE in str(exc)
        assert captured.get("compiled") is None
    finally:
        db.close()


def test_duplicate_region_edit_reuses_in_flight(monkeypatch) -> None:
    captured = _pin_runtime(monkeypatch, "zimage.inpaint", "zimage")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="zimage")
    try:
        first = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="remove",
            prompt="the extra person",
            mask_asset_id="mask-dup",
            source_asset_id=asset_id,
            local_family="zimage",
        )
        second = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="remove",
            prompt="the extra person",
            mask_asset_id="mask-dup",
            source_asset_id=asset_id,
            local_family="zimage",
        )
        edits = [c for c in second.candidates if c.kind == "region_edit"]
        assert len(edits) == 1
        assert first.candidates[-1].id == second.candidates[-1].id
        assert captured.get("compiled")
    finally:
        db.close()


def test_creator_facing_output_gate_message() -> None:
    from app.scene_creator.region_edit_profiles import OUTPUT_GATE_CREATOR_MESSAGE, creator_facing_job_error

    msg, detail = creator_facing_job_error("Output Gate failed: Inpaint output: masked region did not change meaningfully.")
    assert "did not change the selected region enough" in msg
    assert "Z-Image" in msg
    assert "Output Gate" in detail
    assert OUTPUT_GATE_CREATOR_MESSAGE.splitlines()[0] in msg


def test_approve_marks_previous_superseded_not_deleted(monkeypatch) -> None:
    _pin_runtime(monkeypatch, "zimage.inpaint", "zimage")
    db, project_id, shot, parent, asset_id = _seed_shot_with_parent(monkeypatch, family="zimage")
    try:
        parent.asset_id = asset_id
        parent.status = "complete"
        save_scene_shot(db, project_id, shot)
        edited = region_edit_shot(
            db,
            project_id,
            shot.id,
            operation="modify",
            prompt="irritated expression",
            mask_asset_id="mask-expr",
            source_asset_id=asset_id,
            local_family="zimage",
        )
        child = edited.candidates[-1]
        child.status = "complete"
        child.asset_id = "asset-edit-2"
        save_scene_shot(db, project_id, edited)
        approved = approve_candidate(db, project_id, edited.id, child.id)
        prev = next(c for c in approved.candidates if c.id == parent.id)
        assert prev.superseded is True
        assert approved.approved_candidate_id == child.id
        assert len(approved.candidates) == 2
        rolled = approve_candidate(db, project_id, approved.id, parent.id)
        assert rolled.approved_candidate_id == parent.id
        assert any(c.id == child.id for c in rolled.candidates)
    finally:
        db.close()

def test_apply_demotes_strategy_a_when_enqueue_family_cannot_i2i() -> None:
    """Approved zimage region-edit + qwen2512 enqueue must not set I2I flags."""
    child = SceneShotCandidate(
        id="edit-1",
        shot_id="shot-1",
        index=1,
        status="complete",
        asset_id="asset-zimage-edit",
        family="zimage",
        kind="region_edit",
        edit_operation="remove",
    )
    shot = SceneShot(
        project_id="p",
        scene_id="s",
        sheet_id="sheet",
        prompt="Wide static",
        candidates=[child],
        approved_candidate_id="edit-1",
        take_memory=SceneShotTakeMemory(
            userCorrection={
                "region_edits": [
                    {
                        "operation": "remove",
                        "prompt": "the boom mic",
                        "maskAssetId": "mask-x",
                        "candidate_id": "edit-1",
                        "approved": True,
                    }
                ]
            }
        ),
    )
    shot.generator.local_family = ""
    composite = "ers-composite-resolved"
    body = {
        "prompt": "Wide static",
        "creativeContext": {
            "ers_composite_asset_id": composite,
            "reference_image_ids": [composite],
        },
    }
    extras = apply_region_edit_compile(
        body, shot, quality_profile="draft", enqueue_family="qwen2512"
    )
    assert extras["strategy"] == "C"
    assert extras["sourceAssetId"] == ""
    assert extras.get("workflowKey") == "qwen2512.txt2img"
    assert body.get("edit") is not True
    assert not body.get("source_asset_id")
    assert not body.get("sourceAssetId")
    assert body.get("operation") != "image.edit"
    assert body.get("forceWorkflowKey") not in {"flux.img2img", "zimage.ref_edit", "qwen.edit"}
    ctx = body["creativeContext"]
    assert ctx.get("finalStrategy") == "C"
    assert ctx.get("workflowKey") != "zimage.ref_edit"
    assert ctx.get("ers_composite_asset_id") == composite
    assert composite in (ctx.get("reference_image_ids") or [])


def test_qwen2512_draft_skips_strategy_a_and_stamps_ers_composite(monkeypatch) -> None:
    """Empty local_family + approved zimage edit must enqueue honest qwen T2I."""
    from app.scene_creator.service import _enqueue_shot_candidates, resolve_ers_for_sheet

    captured: list[dict] = []

    def _enqueue(db, pid, body, scene_id=None):
        captured.append(body)
        return SimpleNamespace(id=str(uuid.uuid4()), status="queued", message="")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr(
        gen_mod,
        "list_local_generator_families",
        lambda has_reference=False: _families("qwen2512"),
    )
    real_resolve = resolve_ers_for_sheet

    def _resolve(db, project_id, sheet_id, **kwargs):
        package, runtime = real_resolve(db, project_id, sheet_id, **kwargs)
        package.ers_composite_asset_id = "ers-composite-resolved"
        package.directional_assets = {"north": None, "east": None, "south": None, "west": None}
        return package, runtime

    monkeypatch.setattr("app.scene_creator.service.resolve_ers_for_sheet", _resolve)

    project_id = _create_project("Qwen Draft Honest T2I")
    sheet = _save_sheet(project_id)
    db = _session()
    try:
        shot = create_or_update_shot(
            db, project_id, sheet_id=sheet.sheetId, intent="Preview after paint"
        )
        child = SceneShotCandidate(
            shot_id=shot.id,
            index=0,
            status="complete",
            asset_id="asset-zimage-edit",
            family="zimage",
            kind="region_edit",
            edit_operation="remove",
            quality_profile="draft",
        )
        shot.candidates = [child]
        shot.approved_candidate_id = child.id
        shot.generator.local_family = ""
        shot.take_memory.userCorrection = {
            "region_edits": [
                {
                    "operation": "remove",
                    "prompt": "the extra person on the left",
                    "maskAssetId": "mask-1",
                    "candidate_id": child.id,
                    "approved": True,
                }
            ]
        }
        save_scene_shot(db, project_id, shot)
        cands = _enqueue_shot_candidates(
            db,
            project_id,
            shot,
            local_enabled=True,
            api_enabled=False,
            local_family="",
            api_model="",
            candidate_count=1,
            quality_profile="draft",
        )
        assert captured
        body = captured[0]
        ctx = body.get("creativeContext") or {}
        assert body.get("edit") is not True
        assert not body.get("source_asset_id")
        assert not body.get("sourceAssetId")
        assert body.get("operation") != "image.edit"
        assert ctx.get("finalStrategy") != "A"
        assert ctx.get("workflowKey") == "qwen2512.txt2img"
        assert body.get("forceWorkflowKey") not in {"flux.img2img", "zimage.ref_edit", "qwen.edit"}
        composite = ctx.get("ers_composite_asset_id")
        assert composite == "ers-composite-resolved"
        assert composite in (ctx.get("reference_image_ids") or [])
        assert cands[0].family == "qwen2512"
        assert cands[0].final_strategy != "A"
        assert cands[0].final_workflow_key == "qwen2512.txt2img"
        assert cands[0].parent_candidate_id == child.id
        assert cands[0].status != "failed"
        assert not str(cands[0].job_id or "").startswith("failed_")
    finally:
        db.close()
