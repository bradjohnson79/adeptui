"""Cinematographer command engine, lock law, and one-candidate Scene Creator regression."""

from __future__ import annotations

from types import SimpleNamespace

from app.scene_creator.cinematographer import (
    CameraPose,
    SceneCameraRecord,
    apply_command_to_pack,
    bind_pack_from_spatial,
    camera_state_hash,
    can_lock,
    empty_pack,
    lock_camera,
    lock_is_valid,
    reset_camera,
    undo_camera,
    validate_command,
)
from app.spatial_map.ers_contracts import SceneShot, SceneShotCandidate


def test_framing_requires_a_subject() -> None:
    try:
        validate_command("extreme_close_up")
        raise AssertionError("expected error")
    except ValueError as exc:
        assert "character or a prop" in str(exc).lower()


def test_step_does_not_require_subject() -> None:
    spec = validate_command("step_back")
    assert spec.id == "step_back"
    assert spec.physical is True


def _cam(slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"cam-{slot}",
        label=f"Camera {slot + 1}",
        cameraSlot=slot,
        visible=True,
        gridColumn=5,
        gridRow=5,
        normalizedX=0.0,
        normalizedY=0.0,
        x=0.0,
        y=1.6,
        z=0.0,
        yawDegrees=0.0,
        pitchDegrees=0.0,
        rollDegrees=0.0,
        heightMeters=1.6,
        orientation="N",
        fovPreset="medium",
        lensMm=35.0,
        shotType="medium",
        targetCharacterIds=["korri"],
        hero=False,
    )


def test_one_step_back_moves_cell_not_fov() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0)],
        density=10,
        grid_scale=0,
    )
    rec = pack.cameras[0]
    before_row = rec.current.gridRow
    before_fov = rec.current.fovPreset
    before_lens = rec.current.lensMm
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="step_back")
    rec = pack.cameras[0]
    # N looks toward decreasing row; back is +row
    assert rec.current.gridRow == before_row + 1
    assert rec.current.fovPreset == before_fov
    assert rec.current.lensMm == before_lens
    assert rec.current.targetEntityId == "korri"
    assert rec.cameraStateVersion == 2


def test_zoom_does_not_move_cell() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0)],
        density=10,
        grid_scale=0,
    )
    rec = pack.cameras[0]
    col, row = rec.current.gridColumn, rec.current.gridRow
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="zoom_in")
    rec = pack.cameras[0]
    assert rec.current.gridColumn == col
    assert rec.current.gridRow == row
    assert rec.current.fovPreset == "narrow"
    assert rec.current.opticalZoomStep == 1


def test_undo_restores_structured_state() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0)],
        density=10,
        grid_scale=0,
    )
    cam_id = pack.cameras[0].cameraId
    apply_command_to_pack(pack, camera_id=cam_id, operation_id="step_back")
    apply_command_to_pack(
        pack, camera_id=cam_id, operation_id="high_angle", character_id="korri", character_slot=1
    )
    apply_command_to_pack(pack, camera_id=cam_id, operation_id="zoom_in")
    assert pack.cameras[0].current.anglePreset == "high"
    assert pack.cameras[0].current.opticalZoomStep == 1
    undo_camera(pack, cam_id)
    assert pack.cameras[0].current.opticalZoomStep == 0
    assert pack.cameras[0].current.anglePreset == "high"
    undo_camera(pack, cam_id)
    assert pack.cameras[0].current.anglePreset == "eye_level"
    undo_camera(pack, cam_id)
    assert pack.cameras[0].current.physicalStepOffset.forwardBack == 0


def test_lock_survives_missing_preview_asset() -> None:
    rec = SceneCameraRecord(
        cameraId="c1",
        cameraSlot=0,
        current=CameraPose(cameraId="c1"),
        cameraStateVersion=7,
        cameraStateHash="deadbeef",
    )
    rec.cameraStateHash = camera_state_hash(rec.current)
    rec.lineage.previewStatus = "ready"
    rec.lineage.previewStateVersion = 7
    rec.lineage.previewStateHash = rec.cameraStateHash
    rec.lineage.previewAssetId = "asset-1"
    rec.cameraStateVersion = 7
    pack = empty_pack("p", "s")
    pack.cameras = [rec]
    lock_camera(pack, "c1")
    rec.lineage.previewAssetId = ""
    rec.lineage.previewJobId = ""
    assert lock_is_valid(rec) is True


def test_reset_returns_to_baseline_without_deleting_camera() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0)],
        density=10,
        grid_scale=0,
    )
    cam_id = pack.cameras[0].cameraId
    apply_command_to_pack(pack, camera_id=cam_id, operation_id="step_back")
    reset_camera(pack, cam_id)
    assert pack.cameras[0].cameraId == cam_id
    assert pack.cameras[0].current.gridRow == pack.cameras[0].baseline.gridRow
    assert pack.cameras[0].lineage.locked is False


def test_four_cameras_are_independent() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0), _cam(1), _cam(2), _cam(3)],
        density=10,
        grid_scale=0,
    )
    apply_command_to_pack(
        pack,
        camera_id=pack.cameras[0].cameraId,
        operation_id="extreme_close_up",
        character_id="korri",
        character_slot=1,
    )
    assert pack.cameras[0].current.shotType == "extreme_close_up"
    assert pack.cameras[1].current.shotType == "medium"
    assert pack.cameras[1].cameraStateVersion == 1


def test_one_candidate_shot_is_valid() -> None:
    shot = SceneShot(
        project_id="p",
        scene_id="s",
        sheet_id="sheet",
        candidates=[
            SceneShotCandidate(
                shot_id="shot",
                index=0,
                status="complete",
                asset_id="a1",
                take_label="Take A",
                source_camera_id="cam-0",
                camera_state_version=7,
                quality_profile="final",
            )
        ],
    )
    assert len(shot.candidates) == 1
    shot.approved_candidate_id = shot.candidates[0].id
    assert shot.approved_candidate_id
    assert shot.candidates[0].source_camera_id == "cam-0"


def test_can_lock_requires_matching_version() -> None:
    rec = SceneCameraRecord(cameraId="c1", cameraSlot=0, cameraStateVersion=8, cameraStateHash="h8")
    rec.lineage.previewStatus = "ready"
    rec.lineage.previewStateVersion = 7
    rec.lineage.previewStateHash = "h7"
    assert can_lock(rec) is False


def test_high_angle_does_not_move_cell() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0)],
        density=10,
        grid_scale=0,
    )
    rec = pack.cameras[0]
    col, row = rec.current.gridColumn, rec.current.gridRow
    apply_command_to_pack(
        pack, camera_id=rec.cameraId, operation_id="high_angle", character_id="korri", character_slot=1
    )
    rec = pack.cameras[0]
    assert rec.current.gridColumn == col
    assert rec.current.gridRow == row
    assert rec.current.anglePreset == "high"
    assert rec.current.pitchDegrees < 0


def test_compile_includes_held_by_without_relocating_prop() -> None:
    from app.scene_creator.cinematographer import compile_camera_context

    rec = SceneCameraRecord(
        cameraId="c1",
        cameraSlot=0,
        current=CameraPose(cameraId="c1", targetEntityId="korri", targetEntityType="character", inclusionPropId="cup"),
    )
    ctx = compile_camera_context(rec, held_association="Prop is held the character (right hand).")
    assert "held" in ctx["prose"].lower()
    assert rec.current.gridColumn == 0
    assert rec.current.inclusionPropId == "cup"


def test_mutation_after_lock_clears_lock_and_stales_preview() -> None:
    pack = bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=[_cam(0)],
        density=10,
        grid_scale=0,
    )
    rec = pack.cameras[0]
    rec.lineage.previewStatus = "ready"
    rec.lineage.previewStateVersion = rec.cameraStateVersion
    rec.lineage.previewStateHash = rec.cameraStateHash
    rec.lineage.previewAssetId = "asset-1"
    lock_camera(pack, rec.cameraId)
    assert lock_is_valid(pack.cameras[0]) is True
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="step_back")
    rec = pack.cameras[0]
    assert rec.lineage.locked is False
    assert rec.lineage.previewStatus == "stale"
    assert can_lock(rec) is False


def test_lock_model_family_keeps_requested_engine_for_scene_preview() -> None:
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "cine-lock-family",
        {
            "prompt": "CAMERA 1 take EXTREME CLOSE-UP on CHARACTER 1.",
            "purpose": "scene_shot_preview",
            "modelFamilyPreference": "zimage",
            "lockModelFamily": True,
            "allowDraft": True,
            "width": 512,
            "height": 288,
        },
    )
    assert compiled["recommendation"]["executionFamily"] == "zimage"
    assert compiled["allowDraft"] is True
