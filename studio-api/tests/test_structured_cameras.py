"""Canonical Spatial Map camera compile for ERS / Scene Creator Mini."""

from app.spatial_map.ers_projection import (
    camera_production_label,
    compile_structured_cameras,
    is_active_spatial_camera,
)


def test_active_cameras_exclude_unplaced_and_hidden() -> None:
    hidden = {"id": "a", "cameraSlot": 0, "gridColumn": 3, "gridRow": 3, "visible": False}
    unplaced = {"id": "b", "cameraSlot": 1, "gridColumn": -1, "gridRow": -1, "visible": True}
    placed = {
        "id": "c",
        "cameraSlot": 2,
        "gridColumn": 7,
        "gridRow": 8,
        "normalizedX": 0.2,
        "normalizedY": 0.4,
        "orientation": "N",
        "yawDegrees": 0,
        "fovPreset": "medium",
        "visible": True,
    }
    assert is_active_spatial_camera(hidden) is False
    assert is_active_spatial_camera(unplaced) is False
    assert is_active_spatial_camera(placed) is True


def test_camera_slot_label_is_stable() -> None:
    assert camera_production_label({"cameraSlot": 0, "label": "Hero"}) == "C1"
    assert camera_production_label({"cameraSlot": 3, "label": "Whatever"}) == "C4"


def test_compile_four_cameras_c1_c4() -> None:
    cameras = [
        {
            "id": "cam-4",
            "cameraSlot": 3,
            "label": "Camera",
            "gridColumn": 6,
            "gridRow": 7,
            "normalizedX": 0.1,
            "normalizedY": 0.5,
            "orientation": "N",
            "yawDegrees": 0,
            "fovPreset": "medium",
            "visible": True,
        },
        {
            "id": "cam-1",
            "cameraSlot": 0,
            "gridColumn": 1,
            "gridRow": 2,
            "normalizedX": -0.5,
            "normalizedY": -0.4,
            "orientation": "E",
            "yawDegrees": 90,
            "fovPreset": "wide",
            "visible": True,
        },
        {
            "id": "cam-2",
            "cameraSlot": 1,
            "gridColumn": 4,
            "gridRow": 4,
            "normalizedX": 0.0,
            "normalizedY": 0.0,
            "orientation": "S",
            "yawDegrees": 180,
            "fovPreset": "narrow",
            "visible": True,
        },
        {
            "id": "cam-3",
            "cameraSlot": 2,
            "gridColumn": 2,
            "gridRow": 8,
            "normalizedX": -0.2,
            "normalizedY": 0.7,
            "orientation": "W",
            "yawDegrees": 270,
            "fovPreset": "medium",
            "visible": True,
        },
        {
            "id": "cam-ghost",
            "cameraSlot": 0,
            "gridColumn": -1,
            "gridRow": -1,
            "visible": True,
        },
    ]
    compiled = compile_structured_cameras(cameras)
    assert compiled["count"] == 4
    assert compiled["labels"] == ["C1", "C2", "C3", "C4"]
    by_label = {item["label"]: item for item in compiled["cameras"]}
    assert by_label["C1"]["orientation"] == "E"
    assert by_label["C1"]["yawDegrees"] == 90
    assert by_label["C4"]["cell"] == "G8"
    assert "CAMERA C4" in compiled["lines"]
    assert "Grid position: G8" in compiled["lines"]
    assert "Facing: N (yaw 0)" in compiled["lines"]
    assert "CAMERA C1 VIEWPOINT" not in "\n".join(compiled["lines"])


def test_c2_viewpoint_facts_are_east_northwest_not_hero() -> None:
    from app.spatial_map.ers_projection import compile_camera_viewpoint_facts

    c1 = {
        "id": "1a8198ec-8c40-4608-9b9f-0d4544aabe5c",
        "label": "C1",
        "cameraSlot": 0,
        "gridColumn": 11,
        "gridRow": 11,
        "normalizedX": 0.15,
        "normalizedY": 0.15,
        "orientation": "N",
        "yawDegrees": 0,
        "fovPreset": "medium",
        "visible": True,
        "x": 0.75,
        "y": 1.6,
        "z": 0.75,
    }
    c2 = {
        "id": "7089be6e-3576-425a-8309-7616b0c058b6",
        "label": "C2",
        "cameraSlot": 1,
        "gridColumn": 13,
        "gridRow": 11,
        "normalizedX": 0.35,
        "normalizedY": 0.15,
        "orientation": "NW",
        "yawDegrees": 315,
        "fovPreset": "medium",
        "visible": True,
        "x": 1.75,
        "y": 1.6,
        "z": 0.75,
    }
    occupant = {
        "id": "char-1",
        "label": "Staff",
        "characterId": "char-1",
        "normalizedX": 0.15,
        "normalizedY": -0.05,
        "gridColumn": 11,
        "gridRow": 9,
        "x": 0.75,
        "z": -0.25,
        "visible": True,
    }
    facts = compile_camera_viewpoint_facts(
        c2,
        cameras=[c1, c2],
        characters=[occupant],
        props=[],
        anchors=[],
    )
    joined = "\n".join(facts["lines"])
    assert facts["cell"] == "N12"
    assert facts["regionX"] == "east"
    assert facts["regionY"] == "center"
    assert facts["facing"] == "NW"
    assert facts["look"] == "northwest"
    assert "Grid position: N12" in joined
    assert "Looks northwest" in joined
    assert "eastern side of the mapped room" in joined
    assert "east of C1" in joined
    assert "centered north-facing hero" in joined
    assert "Do not relocate this camera" in joined
    assert "Do not reuse a more-western camera's viewpoint (C1)" in joined
    assert "C14R12" not in joined
    assert "Staff visible ahead" in joined
    assert "east seating neighborhood" in joined
