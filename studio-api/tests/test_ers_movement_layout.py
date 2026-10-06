from app.spatial_map.ers_camera_overlay import ERS_TOPDOWN_PANEL
from app.spatial_map.ers_movement_strip import layout_rects, validate_layout
from app.spatial_map.scene_creator_mini import MINI_HERO_PANEL


def test_movement_layout_does_not_overlap_and_keeps_hero_on_core() -> None:
    rects = layout_rects(2560, movement_count=3)
    assert rects["core"]["height"] == 1440
    assert rects["height"] > 1440
    assert validate_layout(rects) == []
    hero = rects["heroPanel"]
    assert hero["left"] == 0
    assert hero["top"] == 0
    assert abs(hero["width"] - 2560 / 3) < 1
    assert abs(hero["height"] - 1440 / 3) < 1
    assert hero["top"] + hero["height"] <= rects["core"]["height"]
    assert MINI_HERO_PANEL["left"] == 0.0
    assert MINI_HERO_PANEL["top"] == 0.0
    assert ERS_TOPDOWN_PANEL["top"] == 0.0


def test_single_movement_keeps_core_16_9() -> None:
    rects = layout_rects(2560, movement_count=1)
    assert rects["core"]["width"] == 2560
    assert rects["core"]["height"] == 1440
    assert len(rects["movementCells"]) == 1
    assert validate_layout(rects) == []
