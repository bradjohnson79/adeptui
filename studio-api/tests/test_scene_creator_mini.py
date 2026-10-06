from app.spatial_map.scene_creator_mini import MINI_ASPECTS, mini_output_count, mini_pixels, require_saved_document
from app.codirector.knowledgebase.ers_compiler import compile_environment_reference_sheet_prompt
from fastapi import HTTPException


def test_mini_output_count_is_two_per_camera() -> None:
    assert mini_output_count(0) == 0
    assert mini_output_count(1) == 2
    assert mini_output_count(2) == 4
    assert mini_output_count(3) == 6
    assert mini_output_count(4) == 8
    assert mini_output_count(9) == 8
    assert mini_output_count(2, 4) == 8
    assert mini_output_count(0, 4) == 4


def test_mini_frame_sizes_do_not_distort() -> None:
    assert "4:5" in MINI_ASPECTS
    w, h = mini_pixels("16:9")
    assert w / h == 16 / 9
    w, h = mini_pixels("1:1")
    assert w == h
    w, h = mini_pixels("21:9")
    assert abs(w / h - 21 / 9) < 0.02
    w, h = mini_pixels("4:5")
    assert abs(w / h - 4 / 5) < 0.02
    w, h = mini_pixels("9:16")
    assert abs(w / h - 9 / 16) < 0.02


def test_require_saved_document_blocks_dirty() -> None:
    class Doc:
        savedVersion = "1"
        version = "2"

    try:
        require_saved_document(Doc())
        raise AssertionError("expected 409")
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Save Spatial Map" in str(exc.detail)


def test_mini_prompt_locks_camera_geography() -> None:
    from types import SimpleNamespace
    from app.spatial_map.scene_creator_mini import _compile_mini_prompt

    document = SimpleNamespace(
        gridScale=0,
        masterEnvironmentPrompt="Schnick Coffee neighborhood cafe",
        title="Schnick Coffee",
        characters=[],
        props=[],
    )
    camera = {
        "id": "cam-4",
        "label": "C4",
        "cameraSlot": 3,
        "gridColumn": 6,
        "gridRow": 7,
        "normalizedX": 0.1,
        "normalizedY": 0.5,
        "orientation": "N",
        "yawDegrees": 0,
        "fovPreset": "medium",
        "visible": True,
        "x": 0,
        "y": 1.6,
        "z": 0,
        "targetCharacterIds": [],
    }
    prompt = _compile_mini_prompt(None, "p", document, camera, variation="A", aspect="16:9")
    assert "CAMERA PLACEMENT IS CANONICAL" in prompt
    assert "C4" in prompt
    assert "G8" in prompt
    assert "C7R8" not in prompt
    assert "C14R12" not in prompt
    assert "Do not relocate the camera" in prompt
    assert "16:9" in prompt
    assert "Do not draw an Environment Reference Sheet" in prompt
    assert "one continuous photographic still" in prompt


def test_mini_prompt_c2_uses_spatial_cell_and_viewpoint() -> None:
    from types import SimpleNamespace
    from app.spatial_map.scene_creator_mini import _compile_mini_prompt

    c1 = {
        "id": "cam-1",
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
        "targetCharacterIds": [],
    }
    c2 = {
        "id": "cam-2",
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
        "targetCharacterIds": [],
    }
    document = SimpleNamespace(
        gridScale=5,
        masterEnvironmentPrompt="neighborhood cafe interior",
        title="Spatial Map",
        cameras=[c1, c2],
        characters=[],
        props=[],
        anchors=[],
    )
    prompt = _compile_mini_prompt(None, "p", document, c2, variation="B", aspect="16:9")
    assert "N12" in prompt
    assert "C14R12" not in prompt
    assert "Looks northwest" in prompt
    assert "eastern side of the mapped room" in prompt
    assert "centered north-facing hero" in prompt
    assert "Do not change camera position" in prompt
    assert "lounge-forward" in prompt
    assert "Variation B" in prompt


def test_ers_prompt_does_not_include_mini_viewpoint_facts() -> None:
    from app.codirector.knowledgebase.ers_compiler import compile_environment_reference_sheet_prompt

    cameras = [
        {
            "id": "cam-2",
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
        }
    ]
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Test Room",
        cameras=cameras,
    )
    prompt = compiled["prompt"]
    assert "CAMERA C2 VIEWPOINT" not in prompt
    assert "Looks northwest" not in prompt
    assert "Grid position: N12" in prompt


def test_mini_source_falls_back_to_atlas_without_ers() -> None:
    from types import SimpleNamespace
    from app.spatial_map.scene_creator_mini import _mini_source_asset

    document = SimpleNamespace(backgroundAssetId="atlas-1", id="map-1")
    assert _mini_source_asset(None, "p", document) == "atlas-1"


def test_crop_ers_hero_is_top_left_third(tmp_path) -> None:
    from PIL import Image
    from app.spatial_map.scene_creator_mini import crop_ers_hero

    image = Image.new("RGB", (900, 600), (10, 10, 10))
    for x in range(300):
        for y in range(200):
            image.putpixel((x, y), (200, 40, 40))
    path = tmp_path / "sheet.png"
    image.save(path)
    crop = crop_ers_hero(path)
    assert crop.size == (300, 200)
    assert crop.getpixel((10, 10)) == (200, 40, 40)


def test_inset_hero_crop_excludes_title_and_legend(tmp_path) -> None:
    from PIL import Image
    from app.spatial_map.scene_creator_mini import crop_mini_environment_plate

    gold = (212, 175, 55)
    legend = (40, 40, 10)
    environment = (0, 80, 80)
    image = Image.new("RGB", (900, 600), (20, 20, 20))
    for x in range(300):
        for y in range(200):
            if y < 40:
                image.putpixel((x, y), gold)
            elif x < 20:
                image.putpixel((x, y), legend)
            else:
                image.putpixel((x, y), environment)
    path = tmp_path / "titled-sheet.png"
    image.save(path)
    crop = crop_mini_environment_plate(path)
    pixels = set(crop.getdata())
    assert gold not in pixels
    assert legend not in pixels
    assert environment in pixels
    assert crop.size[0] < 300
    assert crop.size[1] < 200


def test_mini_source_prefers_master_environment_asset(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.spatial_map import scene_creator_mini as mini

    class _Db:
        def get(self, _cls, asset_id):
            return SimpleNamespace(id=asset_id) if asset_id == "master-1" else None

    monkeypatch.setattr(mini, "_latest_ers_master", lambda db, project_id, map_id: "master-1")
    monkeypatch.setattr(mini, "_latest_ers_composite", lambda project_id, map_id: "collage-1")
    document = SimpleNamespace(id="map-1", backgroundAssetId="atlas-1")
    assert mini._mini_source_asset(_Db(), "proj", document) == "master-1"


def test_ers_prompt_still_compiles_without_cameras() -> None:
    compiled = compile_environment_reference_sheet_prompt(environment_name="Schnick Coffee")
    assert "hero" in compiled["prompt"].lower()
    assert "CAMERA PLACEMENT IS CANONICAL" not in compiled["prompt"]


def test_library_visible_hides_mini_drafts() -> None:
    import json

    from app.routers.extra import _library_visible

    class _Asset:
        def __init__(self, meta: dict | None) -> None:
            self.prompt_meta_json = json.dumps(meta) if meta is not None else "{}"

    assert _library_visible(_Asset({"libraryVisible": False})) is False
    assert _library_visible(_Asset({"libraryVisible": True})) is True
    assert _library_visible(_Asset({})) is True


def test_mini_enqueue_sets_commit_to_library_false() -> None:
    import inspect

    from app.spatial_map import scene_creator_mini as mini

    src = inspect.getsource(mini._enqueue_variation)
    assert '"commitToLibrary": False' in src
    assert 'SOURCE_FEATURE' in src
    assert 'miniTakeId' in src
    assert '"deferEnqueue": True' in src


def test_regenerate_does_not_delete_library_assets() -> None:
    import inspect

    from app.spatial_map.scene_creator_mini import regenerate_mini, send_selected_to_library

    regen_src = inspect.getsource(regenerate_mini)
    send_src = inspect.getsource(send_selected_to_library)
    assert "db.delete" not in regen_src
    assert "unlink" not in regen_src
    assert "take[\"results\"]" in regen_src
    assert "cameraId" in regen_src
    assert "_stamp_approval_provenance" in send_src
    assert "if meta.get(\"libraryVisible\") is True" in send_src


def test_hydrate_treats_imagegen_done_as_complete() -> None:
    import inspect

    from app.spatial_map.scene_creator_mini import _hydrate_results

    src = inspect.getsource(_hydrate_results)
    assert '"done"' in src
    assert "complete" in src


def test_world_view_prompt_is_one_still_not_ers_chrome() -> None:
    from types import SimpleNamespace
    from app.spatial_map.scene_creator_mini import _compile_world_view_prompt

    document = SimpleNamespace(
        sceneDescription="Observatory control room",
        title="Observatory",
        characters=[],
        props=[],
        anchors=[],
        cameras=[],
        sceneIntent=None,
        backgroundAlignment=None,
    )
    prompt = _compile_world_view_prompt(document, "north", aspect="16:9")
    assert "NORTH" in prompt
    assert "one continuous photographic still" in prompt.lower() or "ONE continuous photographic still" in prompt
    assert "Do not draw an Environment Reference Sheet" in prompt
    assert "16:9" in prompt


def test_world_view_ids_normalize() -> None:
    from app.spatial_map.scene_creator_mini import normalize_world_view_ids, world_view_result_id

    assert normalize_world_view_ids(None) == ["north", "east", "south", "west"]
    assert normalize_world_view_ids(["east", "world_west"]) == ["east", "west"]
    assert world_view_result_id("south") == "world_south"


def test_local_mini_generators_include_zimage() -> None:
    from app.spatial_map.camera_optics import is_local_mini_generator

    assert is_local_mini_generator("zimage")
    assert is_local_mini_generator("qwen2512")
    assert not is_local_mini_generator("gpt-image-2")


def test_mini_qwen_ref_is_not_treated_as_scene_creator_edit() -> None:
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "2347bf46-3762-4763-86c5-4a6032522278",
        {
            "prompt": "Still photograph from Spatial Map camera C1.",
            "purpose": "scene_creator_mini",
            "operation": "image.generate",
            "source": "local",
            "sourceAssetId": "ers-composite-1",
            "source_asset_id": "ers-composite-1",
            "referenceImage": "ers-composite-1",
            "forceWorkflowKey": "qwen2512.ref",
            "allow_force_workflow_key": True,
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "aspectRatio": "16:9",
            "commitToLibrary": False,
            "sourceFeature": "scene_creator_mini",
        },
    )
    assert compiled["imageIntent"]["operation"] != "image.edit"
    assert compiled["imageRuntime"]["workflowKey"] == "qwen2512.ref"


def test_scene_shot_plus_crs_qwen2512_ref_still_raises() -> None:
    """Owner law: scene_shot must not consume CRS via the ERS I2I graph."""
    import pytest
    from app.image_product.compile import compile_image_request

    with pytest.raises(RuntimeError, match="qwen2512.ref"):
        compile_image_request(
            "2347bf46-3762-4763-86c5-4a6032522278",
            {
                "prompt": "Scene still using a Character Reference Sheet.",
                "purpose": "scene_shot",
                "operation": "image.generate",
                "source": "local",
                "sourceAssetId": "crs-sheet-1",
                "source_asset_id": "crs-sheet-1",
                "referenceImage": "crs-sheet-1",
                "forceWorkflowKey": "qwen2512.ref",
                "allow_force_workflow_key": True,
                "lockModelFamily": True,
                "modelFamilyPreference": "qwen2512",
                "aspectRatio": "16:9",
                "commitToLibrary": False,
            },
        )


def test_mini_atlas_ers_stills_compile_to_qwen2512_ref() -> None:
    """Observatory Atlas/ERS plate + Mini purpose compiles; no 500."""
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "2347bf46-3762-4763-86c5-4a6032522278",
        {
            "prompt": "Still photograph from Observatory Control Room camera C1.",
            "purpose": "scene_creator_mini",
            "operation": "image.generate",
            "source": "local",
            "sourceAssetId": "62888b73-2511-4323-8db3-634c94c609fc",
            "source_asset_id": "62888b73-2511-4323-8db3-634c94c609fc",
            "referenceImage": "62888b73-2511-4323-8db3-634c94c609fc",
            "forceWorkflowKey": "qwen2512.ref",
            "allow_force_workflow_key": True,
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "aspectRatio": "16:9",
            "commitToLibrary": False,
            "sourceFeature": "scene_creator_mini",
        },
    )
    assert compiled["imageRuntime"]["workflowKey"] == "qwen2512.ref"
    assert compiled["imageIntent"]["operation"] != "image.edit"


def test_mini_zimage_ref_stays_pinned() -> None:
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "2347bf46-3762-4763-86c5-4a6032522278",
        {
            "prompt": "Room view looking North.",
            "purpose": "scene_shot",
            "operation": "image.generate",
            "source": "local",
            "sourceAssetId": "ers-composite-1",
            "source_asset_id": "ers-composite-1",
            "referenceImage": "ers-composite-1",
            "forceWorkflowKey": "zimage.ref_edit",
            "allow_force_workflow_key": True,
            "lockModelFamily": True,
            "modelFamilyPreference": "zimage",
            "aspectRatio": "16:9",
            "commitToLibrary": False,
            "sourceFeature": "scene_creator_mini",
        },
    )
    assert compiled["imageRuntime"]["workflowKey"] == "zimage.ref_edit"
    assert compiled["imageIntent"].get("enginePreference") in {"zimage", None} or compiled["imageRuntime"]["workflowKey"] == "zimage.ref_edit"
