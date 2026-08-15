"""3D camera orientation — hash compatibility, math, compile, isolation."""

from __future__ import annotations

from types import SimpleNamespace

from app.scene_creator.cinematographer import (
    HASH_FIELDS,
    CameraPose,
    apply_command_to_pack,
    bind_pack_from_spatial,
    camera_state_hash,
    compile_camera_context,
    empty_pack,
    undo_camera,
    wrap_yaw_degrees,
)


# Frozen pre-orientation3d hash for this exact pose (no orientation3d keys).
_OLD_POSE_HASH = "7ebd23e42d5ca1b6"


def _old_pose_dict() -> dict:
    return {
        "cameraId": "c1",
        "cameraSlot": 0,
        "gridColumn": 5,
        "gridRow": 5,
        "normalizedX": 0.55,
        "normalizedY": 0.55,
        "yawDegrees": 0.0,
        "pitchDegrees": 0.0,
        "rollDegrees": 0.0,
        "heightMeters": 1.6,
        "fovPreset": "medium",
        "lensMm": 35.0,
        "opticalZoomStep": 0,
        "anglePreset": "eye_level",
        "shotType": "medium",
        "targetEntityId": "korri",
        "targetEntityType": "character",
        "orientation": "N",
        "inclusionPropId": "",
    }


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


def _pack(*slots: int):
    cams = [_cam(s) for s in (slots or (0,))]
    return bind_pack_from_spatial(
        empty_pack("p", "s"),
        project_id="p",
        scene_id="s",
        spatial_cameras=cams,
        density=10,
        grid_scale=0,
    )


def test_hash_fields_includes_inclusion_prop() -> None:
    assert "inclusionPropId" in HASH_FIELDS


def test_old_pack_hash_unchanged_after_validate() -> None:
    old = _old_pose_dict()
    assert "orientation3d" not in old
    pose = CameraPose.model_validate(old)
    assert pose.orientation3d.enabled is False
    assert camera_state_hash(pose) == _OLD_POSE_HASH
    pose2 = CameraPose.model_validate(pose.model_dump())
    assert camera_state_hash(pose2) == _OLD_POSE_HASH


def test_enable_and_yaw_bumps_version_hash_keeps_cell() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    col, row = rec.current.gridColumn, rec.current.gridRow
    version = rec.cameraStateVersion
    before_hash = rec.cameraStateHash
    rec.lineage.previewStatus = "ready"
    rec.lineage.previewStateVersion = rec.cameraStateVersion
    rec.lineage.previewStateHash = rec.cameraStateHash
    rec.lineage.locked = True
    rec.lineage.lockedStateVersion = rec.cameraStateVersion
    rec.lineage.lockedStateHash = rec.cameraStateHash
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_enable")
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    rec = pack.cameras[0]
    assert rec.cameraStateVersion == version + 2
    assert rec.cameraStateHash != before_hash
    assert rec.current.gridColumn == col
    assert rec.current.gridRow == row
    assert rec.current.yawDegrees == 32.0
    assert rec.current.orientation3d.enabled is True
    assert rec.lineage.previewStatus == "stale"
    assert rec.lineage.locked is False


def test_orient_zoom_changes_lens_not_cell() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    col, row = rec.current.gridColumn, rec.current.gridRow
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_enable")
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_zoom",
        orientation_patch={"zoom": 1.35},
    )
    rec = pack.cameras[0]
    assert rec.current.gridColumn == col
    assert rec.current.gridRow == row
    assert rec.current.orientation3d.zoom == 1.35
    assert abs(rec.current.lensMm - 35.0 * 1.35) < 0.01
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="dolly_in")
    rec = pack.cameras[0]
    assert rec.current.gridRow != row


def test_roll_in_json_does_not_move_cell() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    col, row = rec.current.gridColumn, rec.current.gridRow
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_roll",
        orientation_patch={"rollDegrees": 8},
    )
    rec = pack.cameras[0]
    assert rec.current.gridColumn == col
    assert rec.current.gridRow == row
    assert rec.current.rollDegrees == 8.0


def test_target_lock_preserves_target_entity() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    assert rec.current.targetEntityId == "korri"
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_enable")
    rec = pack.cameras[0]
    assert rec.current.orientation3d.targetLock is True
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 45},
    )
    rec = pack.cameras[0]
    assert rec.current.targetEntityId == "korri"
    assert rec.current.targetEntityType == "character"


def test_disable_omits_orientation3d_hash_keys() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_enable")
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    enabled_hash = pack.cameras[0].cameraStateHash
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_disable")
    rec = pack.cameras[0]
    assert rec.current.orientation3d.enabled is False
    disabled_hash = rec.cameraStateHash
    assert disabled_hash != enabled_hash
    twin = rec.current.model_copy(deep=True)
    twin.orientation3d.zoom = 2.5
    twin.orientation3d.targetLock = True
    twin.orientation3d.axisLocks.yaw = True
    assert camera_state_hash(twin) == disabled_hash
    enabled_twin = rec.current.model_copy(deep=True)
    enabled_twin.orientation3d.enabled = True
    assert camera_state_hash(enabled_twin) != disabled_hash


def test_compile_camera_context_uses_human_language() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_enable")
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_roll",
        orientation_patch={"rollDegrees": 8},
    )
    rec = pack.cameras[0]
    ctx = compile_camera_context(rec)
    prose = ctx["prose"]
    assert "yaw" in prose.lower() or "dutch" in prose.lower()
    assert '{"yaw' not in prose
    assert "Dutch" in prose or "dutch" in prose.lower()
    assert "orientation3d" in ctx
    assert isinstance(ctx["orientation3d"], dict)


def test_snap_front_sets_yaw_zero() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 90},
    )
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_snap",
        orientation_patch={"snapId": "front"},
    )
    rec = pack.cameras[0]
    assert abs(rec.current.yawDegrees) < 0.01


def test_orient_reset_restores_aim_keeps_shot_type() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="close_up",
        character_id="korri",
        character_slot=1,
    )
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    rec = pack.cameras[0]
    assert rec.current.shotType == "close_up"
    assert rec.current.yawDegrees == 32.0
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_reset")
    rec = pack.cameras[0]
    assert rec.current.shotType == "close_up"
    assert rec.current.yawDegrees == rec.baseline.yawDegrees
    assert rec.current.orientation3d.enabled is rec.baseline.orientation3d.enabled
    assert rec.current.gridColumn == rec.baseline.gridColumn


def test_orientation_keeps_dropdown_camera_command() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="extreme_close_up",
        character_id="korri",
        character_name="Korri",
        character_slot=1,
        prop_id="cup",
        prop_name="Coffee Cup",
        prop_slot=1,
    )
    rec = pack.cameras[0]
    semantic = rec.displayInstruction
    assert "EXTREME CLOSE-UP" in semantic
    assert "Korri" in semantic
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    rec = pack.cameras[0]
    assert rec.displayInstruction == semantic
    assert rec.current.orientation3d.enabled is True
    ctx = compile_camera_context(rec, character_name="Korri", prop_name="Coffee Cup")
    assert "EXTREME CLOSE-UP" in rec.displayInstruction
    assert "three-quarter" in ctx["prose"].lower() or "yaw" in ctx["prose"].lower()
    assert '{"yaw' not in ctx["prose"]


def test_c1_mutation_does_not_change_c2() -> None:
    pack = _pack(0, 1)
    c1, c2 = pack.cameras[0], pack.cameras[1]
    c2_hash = c2.cameraStateHash
    c2_version = c2.cameraStateVersion
    c2_yaw = c2.current.yawDegrees
    apply_command_to_pack(
        pack,
        camera_id=c1.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    c2 = pack.cameras[1]
    assert c2.cameraStateHash == c2_hash
    assert c2.cameraStateVersion == c2_version
    assert c2.current.yawDegrees == c2_yaw
    assert pack.cameras[0].current.yawDegrees == 32.0


def test_undo_restores_previous_yaw() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(pack, camera_id=rec.cameraId, operation_id="orient_3d_enable")
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 32},
    )
    assert pack.cameras[0].current.yawDegrees == 32.0
    undo_camera(pack, rec.cameraId)
    assert pack.cameras[0].current.yawDegrees == 0.0


def test_yaw_wrap_and_pitch_roll_zoom_clamps() -> None:
    assert wrap_yaw_degrees(200.0) == -160.0
    assert wrap_yaw_degrees(-180.0) == 180.0
    assert wrap_yaw_degrees(180.0) == 180.0
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_pitch",
        orientation_patch={"pitchDegrees": 90},
    )
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_roll",
        orientation_patch={"rollDegrees": -40},
    )
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_zoom",
        orientation_patch={"zoom": 9.0},
    )
    rec = pack.cameras[0]
    assert rec.current.pitchDegrees == 60.0
    assert rec.current.rollDegrees == -25.0
    assert rec.current.orientation3d.zoom == 3.0
    assert rec.current.lensMm == 105.0


def test_axis_lock_skips_yaw() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_axis_lock",
        orientation_patch={"axisLocks": {"yaw": True}},
    )
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_yaw",
        orientation_patch={"yawDegrees": 45},
    )
    assert pack.cameras[0].current.yawDegrees == 0.0


def test_snap_front_high_combines_yaw_and_pitch() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_snap",
        orientation_patch={"snapId": "front_high"},
    )
    rec = pack.cameras[0]
    assert abs(rec.current.yawDegrees) < 0.01
    assert rec.current.pitchDegrees == -28.0


def test_orient_target_lock_can_aim_at_a_prop() -> None:
    pack = _pack(0)
    rec = pack.cameras[0]
    apply_command_to_pack(
        pack,
        camera_id=rec.cameraId,
        operation_id="orient_target_lock",
        prop_id="cup",
        prop_name="Coffee Cup",
        orientation_patch={"targetLock": True},
    )
    rec = pack.cameras[0]
    assert rec.current.targetEntityId == "cup"
    assert rec.current.targetEntityType == "prop"
    assert rec.current.orientation3d.targetLock is True
