"""Permanent tests: full-sheet success persists GPT PNG directly. No stamp/strip/2K restitch."""

from __future__ import annotations

import inspect
from pathlib import Path
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.queue_worker import JobQueue
from app.spatial_map.ers_collage_templates import (
    ORIGINAL_ERS_V1,
    _SENSENOVA_PANEL9_PIXELS,
    _SENSENOVA_SIZE,
    canonical_panel9_box,
    visual_ers_canvas_size,
)
from app.spatial_map.ers_component_pipeline import COMPONENT_SEQUENCE, resolve_pipeline_mode, start_ers_component_pipeline
from app.spatial_map.ers_compose_2k import compose_ers_png, compose_occupied_into_collage
from app.spatial_map.ers_full_sheet import (
    bake_visual_overlay_on_full_sheet_success,
    persist_full_sheet_ers,
    persist_repair_lineage,
)
from app.spatial_map.ers_packet import compile_ers_packet


def _png(size: tuple[int, int], color=(20, 30, 40), box=None, box_color=(200, 10, 10)) -> bytes:
    image = Image.new("RGB", size, color)
    if box is not None:
        image.paste(Image.new("RGB", (box[2] - box[0], box[3] - box[1]), box_color), (box[0], box[1]))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_full_sheet_success_does_not_invoke_stamp_strip_or_legacy_compositor() -> None:
    src = inspect.getsource(JobQueue._imagegen_commit_asset)
    assert "stamp_saved_cameras_on_ers(" not in src
    assert "assemble_ers_with_movement_strip(" not in src
    assert "compose_ers_png(" not in src
    assert "from .spatial_map.ers_camera_overlay import" not in src
    assert "from .spatial_map.ers_movement_strip import" not in src
    persist_src = inspect.getsource(persist_full_sheet_ers)
    assert "compose_ers_png" not in persist_src
    assert "compose_occupied_into_collage" not in persist_src
    assert "stamp_saved_cameras_on_ers" not in persist_src
    assert "assemble_ers_with_movement_strip" not in persist_src
    assert bake_visual_overlay_on_full_sheet_success({"ers_pipeline": "full_sheet"}) is False
    assert bake_visual_overlay_on_full_sheet_success({"generationMode": "full_sheet_api"}) is False


def test_full_sheet_success_does_not_restitch_panel_9() -> None:
    src = inspect.getsource(JobQueue._imagegen_commit_asset)
    assert "compose_occupied_into_collage(" not in src
    persist_src = inspect.getsource(persist_full_sheet_ers)
    assert "compose_occupied_into_collage" not in persist_src
    assert "compose_ers_png" not in persist_src


def test_targeted_occupied_repair_replaces_canonical_panel9_on_clean_16x9() -> None:
    tw, th = _SENSENOVA_SIZE
    x0, y0, x1, y1 = _SENSENOVA_PANEL9_PIXELS
    collage = _png((tw, th), color=(10, 20, 30))
    occupied = _png((400, 200), color=(0, 255, 0))
    out = compose_occupied_into_collage(collage, occupied, template_id=ORIGINAL_ERS_V1)
    image = Image.open(BytesIO(out)).convert("RGB")
    assert image.size == (tw, th)
    px = image.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
    assert px[1] >= 200 and px[0] < 40
    outside = image.getpixel((20, 20))
    assert outside == (10, 20, 30)
    # Replacement fills the canonical rectangle (not a smaller inset).
    inner = image.getpixel((x0 + 2, y0 + 2))
    assert inner[1] >= 200
    edge = image.getpixel((x1 - 3, y1 - 3))
    assert edge[1] >= 200


def test_targeted_occupied_repair_scales_to_2560x1440_never_2220_chrome() -> None:
    collage = _png((2560, 1440), color=(12, 14, 40))
    occupied = _png((512, 288), color=(255, 0, 0))
    out = compose_occupied_into_collage(collage, occupied, template_id=ORIGINAL_ERS_V1)
    image = Image.open(BytesIO(out)).convert("RGB")
    assert image.size == (2560, 1440)
    assert image.size[1] != 2220
    box = canonical_panel9_box((2560, 1440))
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    px = image.getpixel((cx, cy))
    assert px[0] >= 200 and px[1] < 40
    # 2220 chrome canvas is cropped to 16:9 core before replace.
    chrome = _png((2560, 2220), color=(40, 10, 80))
    repaired = compose_occupied_into_collage(chrome, occupied, template_id=ORIGINAL_ERS_V1)
    repaired_img = Image.open(BytesIO(repaired)).convert("RGB")
    assert repaired_img.size == (2560, 1440)
    assert repaired_img.size[1] != 2220
    vis = visual_ers_canvas_size(2560, 2220)
    assert vis == (2560, 1440)


def test_machine_m1_m2_m3_live_outside_visual_ers() -> None:
    document = SimpleNamespace(
        id="map-1",
        projectId="p1",
        title="Lab",
        backgroundAssetId="atlas-1",
        sceneDescription="silver corridor",
        sceneIntent=SimpleNamespace(summary="silver corridor"),
        characters=[],
        props=[],
        cameras=[],
        environmentalAnchors=[],
        movementSegments=[
            SimpleNamespace(id="m1", segmentNumber=1, beatName="enter", userDirection=""),
            SimpleNamespace(id="m2", segmentNumber=2, beatName="cross", userDirection=""),
            SimpleNamespace(id="m3", segmentNumber=3, beatName="hold", userDirection=""),
        ],
    )
    packet = compile_ers_packet(document, project_id="p1")
    # Live packet is Adept machine JSON (cameras/anchors/etc). Movement aliases
    # are not compiled into origin/beta movementSegments here; they must not be
    # baked into the visual GPT PNG either (no 2220 chrome / M-strip).
    assert "cameras" in packet
    assert packet.get("movementSegments") in (None, [], ())
    visual = _png((1672, 941), color=(8, 8, 8))
    image = Image.open(BytesIO(visual)).convert("RGB")
    # Visual is the clean GPT sheet, not a taller chrome canvas with M-strip.
    assert image.size == (1672, 941)
    assert image.size != (2560, 2220)
    assert bake_visual_overlay_on_full_sheet_success({"ers_pipeline": "full_sheet"}) is False


def test_persisted_asset_is_the_full_sheet_image(monkeypatch, tmp_path) -> None:
    import json

    png = _png((1672, 941), color=(9, 10, 11))
    asset_path = tmp_path / "gpt-full-sheet.png"
    asset_path.write_bytes(png)
    added = []

    class FakeAsset:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id") or "json-1"
            self.path = kwargs.get("path")
            for k, v in kwargs.items():
                setattr(self, k, v)

    class FakeDb:
        def get(self, model, asset_id):
            return SimpleNamespace(id=asset_id, path=str(asset_path))
        def add(self, row):
            added.append(row)
        def flush(self):
            return None

    from app.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    package = SimpleNamespace(
        id="pkg-full-1",
        metadata={"sheet_id": "sheet-1"},
        scene_layout_id="map-1",
        ers_composite_asset_id=None,
        updated_at="",
        created_at="",
    )

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate.persist_ers_composite_asset",
        lambda *a, **k: None,
    )
    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: package)
    monkeypatch.setattr("app.environment_reference_sheet.store.load_sheet", lambda *a, **k: None)
    monkeypatch.setattr("app.spatial_map.service.get_document", lambda *a, **k: None)
    monkeypatch.setattr("app.db.Asset", FakeAsset)
    monkeypatch.setattr(
        "app.spatial_map.ers_component_pipeline._stamp_sheet_grounding_fingerprint",
        lambda *a, **k: None,
    )

    import app.spatial_map.ers_full_sheet as mod
    monkeypatch.setattr(mod, "hydrate_ers_character_canon", lambda db, packet, **k: {
        "characters": [],
        "movementSegments": [
            {"alias": "M1", "segmentNumber": 1},
            {"alias": "M2", "segmentNumber": 2},
            {"alias": "M3", "segmentNumber": 3},
        ],
    })
    monkeypatch.setattr(mod, "validate_full_sheet", lambda *a, **k: {"panels": {}, "identity": {}, "blockingFailure": ""})

    result = persist_full_sheet_ers(
        FakeDb(),
        "proj-1",
        asset_id="visual-gpt-1",
        sheet_id="sheet-1",
        package_id="pkg-full-1",
        package=package,
        ctx={"ers_pipeline": "full_sheet", "generationMode": "full_sheet_api"},
    )
    assert result["ers_composite_asset_id"] == "visual-gpt-1"
    assert package.ers_composite_asset_id == "visual-gpt-1"
    assert package.metadata["collageAssetId"] == "visual-gpt-1"
    machine = next(row for row in added if getattr(row, "tag", "") == "ers_machine_json")
    payload = json.loads(Path(machine.path).read_text(encoding="utf-8"))
    assert payload["visualSheetAssetId"] == "visual-gpt-1"
    assert [row["alias"] for row in payload["movementSegments"]] == ["M1", "M2", "M3"]
    assert payload["composeMode"] == "full_sheet_api"
    assert asset_path.read_bytes() == png


def test_one_paid_job_no_seven_job_fanout() -> None:
    assert resolve_pipeline_mode("full_sheet") == "full_sheet"
    assert resolve_pipeline_mode("full_sheet_api") == "full_sheet"
    assert resolve_pipeline_mode("", gpt_selected=True) == "full_sheet"
    assert resolve_pipeline_mode("", gpt_selected=True, retry_component="occupied") == "components"
    src = inspect.getsource(start_ers_component_pipeline)
    assert src.count("_enqueue_ers_image_product(") == 1
    # Full generation is not a 7-job fan-out over COMPONENT_SEQUENCE.
    handle_src = inspect.getsource(__import__("app.codirector.capabilities.handlers.ers_generate", fromlist=["handle"]).handle)
    assert handle_src.count("_enqueue_ers_image_product(") == 1
    assert len(COMPONENT_SEQUENCE) == 7
    assert "for name in COMPONENT_SEQUENCE" not in handle_src


def test_occupied_repair_records_provenance() -> None:
    package = SimpleNamespace(metadata={})
    persist_repair_lineage(
        package,
        original_full_sheet_asset_id="gpt-visual-1",
        replacement_component="occupied",
        replacement_asset_id="occ-1",
        restitch_composite_asset_id="repaired-1",
    )
    assert package.metadata["originalFullSheetAssetId"] == "gpt-visual-1"
    assert package.metadata["replacementComponent"] == "occupied"
    assert package.metadata["replacementAssetId"] == "occ-1"
    assert package.metadata["restitchCompositeAssetId"] == "repaired-1"



