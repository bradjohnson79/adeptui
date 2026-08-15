"""Focused capture_intelligence tests: attached/unplaced coords must not crash or fake origin."""

from __future__ import annotations

import inspect

from app.spatial_map import capture_intelligence as ci
from app.spatial_map.schemas import (
    SpatialCamera,
    SpatialMapDocument,
    SpatialPropPlacement,
)


def _document(*props: SpatialPropPlacement) -> SpatialMapDocument:
    return SpatialMapDocument(
        projectId="p-ers-hygiene",
        title="ERS bearing",
        cameras=[
            SpatialCamera(label="Hero", hero=True, x=0.0, y=1.6, z=0.0, yawDegrees=0.0),
        ],
        props=list(props),
    )


def _attached_coffee() -> SpatialPropPlacement:
    return SpatialPropPlacement(
        label="Coffee",
        propId="coffee-1",
        placementMode="attached",
        attachedCharacterId="korri",
        attachedCharacterSlot=1,
        relationship="held",
        attachmentPoint="right_hand",
        x=None,
        y=None,
        z=None,
    )


def _unplaced_crate() -> SpatialPropPlacement:
    return SpatialPropPlacement(
        label="Crate",
        propId="crate-1",
        placementMode="independent",
        x=None,
        y=None,
        z=None,
    )


def _placed_lamp() -> SpatialPropPlacement:
    return SpatialPropPlacement(
        label="Lamp",
        propId="lamp-1",
        placementMode="independent",
        x=2.0,
        y=0.0,
        z=3.0,
    )


def _prompts(document: SpatialMapDocument) -> dict[str, str]:
    return ci.build_directional_prompts_for_document(
        document,
        master_environment_prompt="Atrium.",
        include_characters=False,
        camera_height_meters=1.6,
        lens_mm=35.0,
    )


def test_attached_prop_x_none_does_not_crash_bearing() -> None:
    prompts = _prompts(_document(_attached_coffee()))
    joined = " ".join(prompts.values())
    assert prompts
    assert "Coffee visible ahead" not in joined
    assert "Coffee partially visible" not in joined


def test_unplaced_vs_attached_semantics_skip_world_bearing() -> None:
    prompts = _prompts(_document(_attached_coffee(), _unplaced_crate(), _placed_lamp()))
    joined = " ".join(prompts.values())
    assert "Coffee visible ahead" not in joined
    assert "Crate visible ahead" not in joined
    assert "Lamp visible ahead" in joined


def test_capture_intelligence_has_no_or_0_origin() -> None:
    src = inspect.getsource(ci._spatial_visibility_clause)
    assert "or 0" not in src
    assert "or 0.0" not in src
    bearing_src = inspect.getsource(ci._bearing_degrees)
    assert "or 0" not in bearing_src
    assert "or 0.0" not in bearing_src


def test_attached_prop_keeps_held_by_without_world_bearing() -> None:
    from app.spatial_map.schemas import SpatialCharacterPlacement

    document = SpatialMapDocument(
        projectId="p-ers-hygiene",
        title="ERS bearing",
        cameras=[
            SpatialCamera(label="Hero", hero=True, x=0.0, y=1.6, z=0.0, yawDegrees=0.0),
        ],
        characters=[
            SpatialCharacterPlacement(
                characterId="korri",
                label="Korri",
                slotIndex=0,
                x=1.5,
                y=0.0,
                z=2.0,
            ),
        ],
        props=[_attached_coffee()],
    )
    prompts = _prompts(document)
    joined = " ".join(prompts.values())
    assert "held by Korri" in joined
    assert "Coffee visible ahead" not in joined
    assert "or 0" not in __import__("inspect").getsource(ci._spatial_visibility_clause)


def test_unplaced_required_prop_rejects_readably() -> None:
    required = SpatialPropPlacement(
        label="Key Prop",
        propId="key-1",
        placementMode="independent",
        state="required",
        x=None,
        y=None,
        z=None,
    )
    try:
        _prompts(_document(required))
        raise AssertionError("required unplaced prop must reject, not origin-fill")
    except ci.SpatialCaptureGeometryError as exc:
        msg = str(exc)
        assert "Key Prop" in msg
        assert "no world position" in msg
        assert "Place it" in msg
        assert "TypeError" not in msg
        assert "HANDLER_ERROR" not in msg
