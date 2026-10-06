from types import SimpleNamespace

from PIL import Image

from app.spatial_map.ers_compose_2k import choose_aspect, compose_ers_png, score_layout
from app.spatial_map.ers_packet import CARDINAL_YAW, compile_component_prompt, compile_ers_packet, placement_fingerprint
from app.spatial_map.ers_component_pipeline import (
    accepted_from_package,
    bind_component_asset,
    force_full_requested,
    next_component,
    resolve_pipeline_mode,
)


def test_cardinal_yaws_are_atlas_north_up() -> None:
    assert CARDINAL_YAW == {"north": 0, "east": 90, "south": 180, "west": 270}
    north = compile_component_prompt({"environmentDescription": "lab", "environmentName": "Lab"}, "north")
    assert "Yaw 0" in north
    assert "NORTH" in north
    east = compile_component_prompt({"environmentDescription": "lab", "environmentName": "Lab"}, "east")
    assert "Yaw 90" in east
    master = compile_component_prompt({"environmentDescription": "lab", "environmentName": "Lab"}, "master")
    assert "MASTER" in master
    assert "cardinal" in master.lower()
    assert "multi-panel" in master.lower()
    three = compile_component_prompt({"environmentDescription": "lab", "environmentName": "Lab"}, "three_d")
    assert "REPRESENTATION" in three
    assert "mesh" not in three.lower()


def test_packet_does_not_copy_placements_into_gpt_authority() -> None:
    document = SimpleNamespace(
        id="map-1",
        projectId="p1",
        title="Lab",
        backgroundAssetId="atlas-1",
        sceneDescription="silver corridor",
        sceneIntent=SimpleNamespace(summary="silver corridor"),
        widthMeters=20,
        depthMeters=12,
        metersPerCell=1,
        characters=[SimpleNamespace(id="c1", label="Korri", normalizedX=0.1, normalizedY=-0.2, yawDegrees=90)],
        props=[SimpleNamespace(id="p1", label="Crate", normalizedX=-0.4, normalizedY=0.3, yawDegrees=0)],
        cameras=[SimpleNamespace(id="cam1", label="C1", normalizedX=0.0, normalizedY=0.0, yawDegrees=90, pitchDegrees=0)],
        environmentalAnchors=[SimpleNamespace(type="elevator", label="South elevator")],
    )
    packet = compile_ers_packet(document, project_id="p1")
    assert packet["backgroundAlignment"]["offsetX"] == 0.0
    assert packet["backgroundAlignment"]["offsetY"] == 0.0
    assert packet["backgroundAlignment"]["scale"] == 1.0
    assert packet["backgroundAlignment"]["sourceAspectRatio"] == 1.0
    assert packet["directionConvention"]["northYaw"] == 0
    assert packet["spatialMapAssetId"] == "atlas-1"
    assert packet["threeDKind"] == "representation"
    assert placement_fingerprint(packet) != placement_fingerprint({**packet, "characters": []})


def test_layout_scorer_prefers_wider_when_json_is_dense() -> None:
    assert choose_aspect(map_cells=10, json_lines=18) == "16:9"
    assert score_layout("16:9", map_cells=10, json_lines=18) > score_layout("1:1", map_cells=10, json_lines=18)


def test_compose_labels_and_skips_missing_three_d() -> None:
    packet = {
        "environmentName": "Lab",
        "scale": "1 square = 1 meter",
        "dimensions": {"widthMeters": 20, "depthMeters": 12},
        "characters": [],
        "props": [],
        "cameras": [],
    }
    red = Image.new("RGB", (64, 64), (200, 40, 40))
    from io import BytesIO

    def png() -> bytes:
        buf = BytesIO()
        red.save(buf, format="PNG")
        return buf.getvalue()

    images = {key: png() for key in ("master", "north", "east", "south", "west")}
    raw = compose_ers_png(packet, images, width=2560, height=1440)
    sheet = Image.open(BytesIO(raw))
    assert sheet.size == (2560, 1440)


def test_pipeline_order_and_targeted_retry() -> None:
    assert resolve_pipeline_mode("", gpt_selected=True) == "full_sheet"
    assert resolve_pipeline_mode("full_sheet_api", gpt_selected=True) == "full_sheet"
    assert resolve_pipeline_mode("collage", gpt_selected=True) == "collage"
    assert resolve_pipeline_mode("components") == "components"
    assert resolve_pipeline_mode("full_sheet", retry_component="occupied") == "components"
    assert resolve_pipeline_mode("", gpt_selected=False) == "collage"
    accepted = {"master": "a"}
    assert next_component(accepted) == "north"
    accepted.update({"north": "n", "east": "e", "south": "s", "west": "w"})
    assert next_component(accepted) == "three_d"
    assert next_component(accepted, skip_three_d=True) is None
    package = SimpleNamespace(
        master_environment_asset_id=None,
        directional_assets={"north": None, "east": None, "south": None, "west": None},
        metadata={},
    )
    bind_component_asset(package, "east", "east-1")
    assert accepted_from_package(package)["east"] == "east-1"
    assert package.directional_assets["east"] == "east-1"
    bind_component_asset(package, "master", "master-1")
    bind_component_asset(package, "north", "north-1")
    assert set(accepted_from_package(package)) == {"master", "north", "east"}
    assert next_component(accepted_from_package(package)) == "south"


def test_force_full_requested_reads_creator_regenerate_flags() -> None:
    assert force_full_requested(None) is False
    assert force_full_requested({}) is False
    assert force_full_requested({"forceFull": True}) is True
    assert force_full_requested({"force_full": "true"}) is True
    assert force_full_requested({"creativeContext": {"ers_force_full": 1}}) is True
    assert force_full_requested({"forceFull": False}, force_full=True) is True
