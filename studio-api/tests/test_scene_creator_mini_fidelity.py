"""Scene Creator Mini production fidelity tests (Part 43).

Covers: shotSize/primarySubject persistence, CameraShotPacket compile,
required-character derivation, placement relations, camera relational facts,
no-mirror constraints, production prompt compilation, Qwen routing, clean
reference inputs, validation state machine, send gate, camera-reference
staleness, and low-overhead regeneration.
"""

from __future__ import annotations

import json

from types import SimpleNamespace


def _camera(
    *,
    camera_id: str = "cam-2",
    slot: int = 1,
    col: int = 13,
    row: int = 11,
    nx: float = 0.35,
    ny: float = 0.15,
    orientation: str = "NW",
    yaw: float = 315.0,
    fov: str = "medium",
    shot_size: str = "medium",
    primary_subject: str = "auto",
    x: float = 1.75,
    z: float = 0.75,
) -> dict:
    return {
        "id": camera_id,
        "label": f"C{slot + 1}",
        "cameraSlot": slot,
        "gridColumn": col,
        "gridRow": row,
        "normalizedX": nx,
        "normalizedY": ny,
        "orientation": orientation,
        "yawDegrees": yaw,
        "fovPreset": fov,
        "shotSize": shot_size,
        "primarySubject": primary_subject,
        "visible": True,
        "x": x,
        "y": 1.6,
        "z": z,
        "targetCharacterIds": [],
    }


def _character(
    *,
    placement_id: str = "char-1",
    character_id: str = "korri",
    label: str = "Korri",
    col: int = 12,
    row: int = 10,
    nx: float = 0.25,
    ny: float = 0.05,
    x: float = 1.0,
    z: float = 0.1,
    visible: bool = True,
    yaw: float = 180.0,
) -> dict:
    return {
        "id": placement_id,
        "characterId": character_id,
        "label": label,
        "tag": "@Korri",
        "gridColumn": col,
        "gridRow": row,
        "normalizedX": nx,
        "normalizedY": ny,
        "x": x,
        "y": 0.0,
        "z": z,
        "yawDegrees": yaw,
        "visible": visible,
        "slotIndex": 0,
        "colorKey": "red",
        "miniPrompt": "",
    }


def _document(**overrides) -> SimpleNamespace:
    base = SimpleNamespace(
        id="map-1",
        version="5",
        savedVersion="5",
        projectId="p-1",
        sceneId="scene-1",
        title="Schnick Coffee",
        masterEnvironmentPrompt="neighborhood coffee shop",
        sceneIntent=None,
        backgroundAssetId="atlas-1",
        gridScale=5,
        anchors=[],
        characters=[],
        props=[],
        cameras=[],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


# ---------------------------------------------------------------------------
# shotSize / primarySubject persistence (schema + service wiring)
# ---------------------------------------------------------------------------


def test_spatial_camera_schema_carries_shot_size_and_primary_subject() -> None:
    from app.spatial_map.schemas import SpatialCamera, SpatialCameraCreateBody, SpatialCameraUpdateBody

    cam = SpatialCamera(shotSize="close_up", primarySubject="korri")
    assert cam.shotSize == "close_up"
    assert cam.primarySubject == "korri"
    assert SpatialCamera(shotSize="auto").shotSize == "auto"

    create = SpatialCameraCreateBody(shotSize="wide", primarySubject="environment")
    assert create.shotSize == "wide"
    assert create.primarySubject == "environment"

    update = SpatialCameraUpdateBody(shotSize="medium_close")
    assert update.model_dump(exclude_unset=True) == {"shotSize": "medium_close"}


def test_shot_sizes_enum_covers_product_values() -> None:
    from app.spatial_map.schemas import SHOT_SIZES

    assert list(SHOT_SIZES) == [
        "auto",
        "wide",
        "medium_wide",
        "medium",
        "medium_close",
        "close_up",
        "extreme_close",
    ]


# ---------------------------------------------------------------------------
# CameraShotPacket compile
# ---------------------------------------------------------------------------


def _packet_for(camera: dict, document=None):
    from app.spatial_map.camera_shot_packet import compile_camera_shot_packet

    doc = document or _document(
        characters=[_character()],
        cameras=[camera],
        anchors=[{"id": "a1", "label": "Service Counter", "x": 1.4, "z": 0.5}],
    )
    return compile_camera_shot_packet(None, "p-1", doc, camera)


def test_packet_locks_environment_and_camera_facts() -> None:
    packet = _packet_for(_camera(shot_size="close_up", primary_subject="korri"))
    data = packet.model_dump(mode="json")

    env = data["environment"]
    assert env["spatialMapId"] == "map-1"
    assert env["savedVersion"] == "5"
    assert env["mapVersion"] == "5"
    assert env["environmentIdentity"] == "neighborhood coffee shop"
    assert env["northLock"] == "north"
    assert env["anchors"][0]["label"] == "Service Counter"

    cam = data["camera"]
    assert cam["label"] == "C2"
    assert cam["cell"] == "N12"
    assert cam["orientation"] == "NW"
    assert cam["yawDegrees"] == 315.0
    assert cam["fovPreset"] == "medium"
    assert cam["shotSize"] == "close_up"
    assert "eastern" in cam["region"]

    locked = "\n".join(data["lockedFacts"])
    assert "Shot size: close up" in locked
    assert "does NOT move the camera" in locked
    assert "Camera C2 is at grid cell N12" in locked
    assert "must not move to the near side" in locked
    assert "Do not mirror the room" in locked


def test_packet_marks_required_character_and_presence_fact() -> None:
    packet = _packet_for(_camera(primary_subject="korri"))
    data = packet.model_dump(mode="json")
    assert data["requiredCharacterIds"] == ["korri"]
    korri = next(c for c in data["characters"] if c["characterId"] == "korri")
    assert korri["mandatoryForCamera"] is True
    assert korri["primarySubject"] is True
    locked = "\n".join(data["lockedFacts"])
    assert "KORRI MUST BE PRESENT." in locked


def test_hidden_character_is_not_required() -> None:
    hidden = _character(visible=False)
    doc = _document(characters=[hidden], cameras=[_camera(primary_subject="korri")])
    packet = _packet_for(_camera(primary_subject="korri"), document=doc)
    data = packet.model_dump(mode="json")
    assert data["requiredCharacterIds"] == []
    assert data["characters"][0]["mandatoryForCamera"] is False


def test_targeted_character_is_required_even_out_of_view() -> None:
    cam = _camera()
    cam["targetCharacterIds"] = ["korri"]
    doc = _document(characters=[_character(x=4.0, z=-4.0, nx=-0.8, ny=-0.8)], cameras=[cam])
    packet = _packet_for(cam, document=doc)
    data = packet.model_dump(mode="json")
    assert data["requiredCharacterIds"] == ["korri"]


def test_character_behind_fixture_derives_placement_lock() -> None:
    # Korri at z=0.1 (north of counter z=0.5), camera C2 at z=0.75 (south).
    packet = _packet_for(_camera())
    data = packet.model_dump(mode="json")
    korri = next(c for c in data["characters"] if c["characterId"] == "korri")
    assert any("behind the Service Counter" in line for line in korri["sideRelations"])
    locked = "\n".join(data["lockedFacts"])
    assert "behind the Service Counter from this camera" in locked


def test_camera_relational_facts_present() -> None:
    packet = _packet_for(_camera())
    data = packet.model_dump(mode="json")
    relational = "\n".join(data["camera"]["relationalFacts"])
    assert "CAMERA C2 VIEWPOINT" in relational
    assert "Looks northwest" in relational
    assert "FOV: medium" in relational


# ---------------------------------------------------------------------------
# Production prompt compiler
# ---------------------------------------------------------------------------


def _compile(camera: dict, document=None, **kw):
    from app.spatial_map.mini_production_compiler import compile_production_prompt

    packet = _packet_for(camera, document=document)
    return compile_production_prompt(
        packet.model_dump(mode="json"),
        generator=kw.get("generator", "gpt-image-2"),
        aspect=kw.get("aspect", "16:9"),
        variation=kw.get("variation", "A"),
    )


def test_prompt_locks_camera_and_character() -> None:
    prompt = _compile(_camera(shot_size="close_up", primary_subject="korri"))
    assert "CAMERA PLACEMENT IS CANONICAL" in prompt
    assert "KORRI MUST BE PRESENT." in prompt
    assert "N12" in prompt
    assert "Shot size: CLOSE UP" in prompt
    assert "does NOT move the camera" in prompt
    assert "Do not mirror the room" in prompt
    assert "Do not draw an Environment Reference Sheet" in prompt
    assert "one continuous photographic still" in prompt
    assert "16:9" in prompt


def test_shot_size_never_relocates_camera() -> None:
    wide = _compile(_camera(shot_size="wide"))
    close = _compile(_camera(shot_size="close_up"))
    # Geography lines identical; only framing language differs.
    for line in wide.splitlines():
        if "Shot size" in line:
            continue
        assert line in close.splitlines()
    assert "MEDIUM CLOSE" not in wide
    assert "WIDE" not in close or "Shot size: WIDE" in close


def test_variation_b_keeps_lounge_guard() -> None:
    prompt = _compile(_camera(), variation="B")
    assert "lounge-forward" in prompt
    assert "Do not change camera position" in prompt


def test_qwen_prompt_variant() -> None:
    prompt = _compile(_camera(), generator="qwen2512")
    assert "Documentary still photograph" in prompt


# ---------------------------------------------------------------------------
# Qwen / GPT routing
# ---------------------------------------------------------------------------


def test_mini_qwen_routing_stays_reference_not_edit() -> None:
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "p-1",
        {
            "prompt": "Still photograph from Spatial Map camera C2.",
            "purpose": "scene_shot",
            "operation": "image.generate",
            "source": "local",
            "sourceAssetId": "hero-inset-1",
            "source_asset_id": "hero-inset-1",
            "referenceImage": "hero-inset-1",
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


def test_mini_gpt_routing_pins_i2i_and_keeps_source() -> None:
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "p-1",
        {
            "prompt": "Still photograph from Spatial Map camera C2.",
            "purpose": "scene_shot",
            "operation": "image.generate",
            "source": "api",
            "sourceAssetId": "hero-inset-1",
            "referenceImage": "hero-inset-1",
            "hostedModelId": "gpt-image-2-kie",
            "kieImageModelId": "gpt-image-2-image-to-image",
            "lockModelFamily": True,
            "aspectRatio": "16:9",
            "commitToLibrary": False,
            "sourceFeature": "scene_creator_mini",
        },
    )
    assert compiled["imageRuntime"]["provider"] == "kie"
    assert compiled["imageRuntime"]["officialModelId"] == "gpt-image-2-image-to-image"
    assert "text-to-image" not in compiled["imageRuntime"]["officialModelId"]


# ---------------------------------------------------------------------------
# Clean reference inputs
# ---------------------------------------------------------------------------


def test_mini_source_never_returns_full_composite_when_inset_fails(monkeypatch, tmp_path) -> None:
    import app.spatial_map.scene_creator_mini as mini

    def _broken_plate(db, project_id, composite_id):
        raise RuntimeError("inset failed")

    monkeypatch.setattr(mini, "_latest_ers_composite", lambda pid, mid: "composite-1")
    monkeypatch.setattr(mini, "_ensure_hero_plate_asset", _broken_plate)
    doc = _document()
    # Atlas present -> atlas wins, never the chrome composite.
    assert mini._mini_source_asset(None, "p-1", doc) == "atlas-1"
    # No atlas -> honest block, never the composite.
    doc_no_atlas = _document(backgroundAssetId=None)
    try:
        mini._mini_source_asset(None, "p-1", doc_no_atlas)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "clean environment pixels" in str(exc)


def test_hero_inset_crop_excludes_title_band(tmp_path) -> None:
    from PIL import Image

    from app.spatial_map.scene_creator_mini import crop_mini_environment_plate

    gold = (212, 175, 55)
    env = (0, 80, 80)
    image = Image.new("RGB", (900, 600), (20, 20, 20))
    for x in range(300):
        for y in range(200):
            if y < 40:
                image.putpixel((x, y), gold)
            else:
                image.putpixel((x, y), env)
    path = tmp_path / "sheet.png"
    image.save(path)
    crop = crop_mini_environment_plate(path)
    assert gold not in set(crop.getdata())
    assert env in set(crop.getdata())


# ---------------------------------------------------------------------------
# Validation state machine + gates
# ---------------------------------------------------------------------------


def _result(status: str = "complete", validation: dict | None = None, asset: bool = True) -> dict:
    return {
        "id": "r1",
        "status": status,
        "assetId": "a1" if asset else None,
        "validation": validation,
        "inLibrary": False,
    }


def test_validation_state_machine() -> None:
    from app.spatial_map.mini_validation import validation_state_for_result

    assert validation_state_for_result(_result("queued")) == "generating"
    assert validation_state_for_result(_result("generating")) == "generating"
    assert validation_state_for_result(_result("complete")) == "validating"
    assert validation_state_for_result(_result("complete", {"state": "validating"})) == "validating"
    assert validation_state_for_result(_result("complete", {"state": "pass"})) == "pass"
    assert validation_state_for_result(_result("complete", {"state": "continuity_failed"})) == "continuity_failed"
    assert validation_state_for_result(_result("complete", {"state": "validation_unavailable"})) == "validation_unavailable"
    assert validation_state_for_result(_result("failed")) == "generation_failed"


def test_result_selectability() -> None:
    from app.spatial_map.mini_validation import result_is_selectable

    assert result_is_selectable(_result("complete", {"state": "pass"})) is True
    assert result_is_selectable(_result("complete", {"state": "continuity_failed"})) is False
    assert result_is_selectable(_result("complete")) is False  # validating
    assert result_is_selectable(_result("failed")) is False
    assert result_is_selectable(_result("complete", {"state": "pass"}, asset=False)) is False
    lib = _result("complete", {"state": "pass"})
    lib["inLibrary"] = True
    assert result_is_selectable(lib) is False


def test_parse_field_verdicts() -> None:
    from app.codirector.vision.vision_review import parse_field_verdicts

    text = (
        "FIELD: environment\nPASS\n"
        "FIELD: required_character_present\nFAIL\n"
        "FIELD: camera_geography\nPASS\n"
        "VERDICT: FAIL\n"
    )
    parsed = parse_field_verdicts(text)
    assert parsed["environment"] == "PASS"
    assert parsed["required_character_present"] == "FAIL"
    assert parsed["camera_geography"] == "PASS"
    assert parsed["VERDICT"] == "FAIL"


def test_failed_candidate_not_library_ingestable(monkeypatch, tmp_path) -> None:
    """send gate: non-PASS results are skipped server-side."""
    import json

    from app.spatial_map import scene_creator_mini as mini

    monkeypatch.setattr(mini, "_mini_dir", lambda pid: tmp_path / "mini")
    (tmp_path / "mini").mkdir(exist_ok=True)
    take = {
        "id": "t1",
        "projectId": "p-1",
        "mapId": "map-1",
        "results": [
            {"id": "ok", "status": "complete", "assetId": "asset-ok", "jobId": "j1", "validation": {"state": "pass", "verdict": "PASS"}},
            {"id": "bad", "status": "complete", "assetId": "asset-bad", "jobId": "j2", "validation": {"state": "continuity_failed", "verdict": "FAIL"}},
            {"id": "pending", "status": "complete", "assetId": "asset-p", "jobId": "j3"},
        ],
    }
    mini.save_take("p-1", take)

    class _Asset:
        def __init__(self, asset_id: str):
            self.id = asset_id
            self.prompt_meta_json = "{}"

    sent_ids: list[str] = []
    assets = {"asset-ok": _Asset("asset-ok"), "asset-bad": _Asset("asset-bad"), "asset-p": _Asset("asset-p")}

    class _DB:
        def get(self, model, asset_id):  # noqa: A002
            if model.__name__ == "Asset":
                return assets.get(asset_id)
            return None

        def commit(self):
            pass

    from app.spatial_map.scene_creator_mini import MiniSendBody

    body = MiniSendBody(resultIds=["ok", "bad", "pending"])
    saved = mini.send_selected_to_library(_DB(), "p-1", "t1", body)
    assert saved["lastLibrarySendCount"] == 1
    assert saved["lastLibrarySkippedIds"] == ["bad", "pending"]
    by_id = {r["id"]: r for r in saved["results"]}
    assert by_id["ok"]["inLibrary"] is True
    assert by_id["ok"]["libraryVisible"] is True
    assert by_id["bad"].get("inLibrary") is not True
    assert by_id["pending"].get("inLibrary") is not True


# ---------------------------------------------------------------------------
# Camera reference staleness + low-overhead
# ---------------------------------------------------------------------------


def test_camera_reference_staleness() -> None:
    from app.spatial_map.camera_reference import compute_staleness

    record = {
        "savedVersion": "5",
        "mapVersion": "5",
        "ersRevision": "fp-1",
        "shotSize": "medium",
        "primarySubject": "auto",
        "orientation": "NW",
        "yawDegrees": 315.0,
        "fovPreset": "medium",
        "normalizedX": 0.35,
        "normalizedY": 0.15,
    }
    cam = _camera()
    doc = _document()
    stale, reasons = compute_staleness(record, doc, cam, "fp-1")
    assert stale is False
    assert reasons == []

    stale, reasons = compute_staleness(record, doc, cam, "fp-2")
    assert stale is True
    assert any("ERS revision changed" in r for r in reasons)

    cam_changed = _camera(shot_size="close_up")
    stale, reasons = compute_staleness(record, doc, cam_changed, "fp-1")
    assert stale is True
    assert any("Shot size changed" in r for r in reasons)

    cam_moved = _camera(nx=-0.3)
    stale, reasons = compute_staleness(record, doc, cam_moved, "fp-1")
    assert stale is True
    assert any("moved" in r for r in reasons)


def test_camera_reference_generate_touches_only_target(monkeypatch, tmp_path) -> None:
    """Low-overhead rule: one camera's reference never rewrites others."""
    import app.spatial_map.camera_reference as refs

    monkeypatch.setattr(refs, "_refs_root", lambda pid: tmp_path / "refs")
    (tmp_path / "refs").mkdir(exist_ok=True)
    refs.save_ref("p-1", "map-1", {"cameraId": "c1", "label": "C1"})
    refs.save_ref("p-1", "map-1", {"cameraId": "c2", "label": "C2"})

    from pathlib import Path

    # Only the C2 file is rewritten; C1 remains byte-identical.
    c1_before = (tmp_path / "refs" / "map-1" / "c1.json").read_bytes()
    refs.save_ref("p-1", "map-1", {"cameraId": "c2", "label": "C2", "updated": True})
    c1_after = (tmp_path / "refs" / "map-1" / "c1.json").read_bytes()
    assert c1_before == c1_after
    assert "updated" in json.loads((tmp_path / "refs" / "map-1" / "c2.json").read_text(encoding="utf-8"))




def test_compiled_cameras_carry_shot_size_and_primary_subject() -> None:
    """compile_structured_cameras must preserve shotSize/primarySubject so
    staleness checks and Mini takes see current framing metadata."""
    from app.spatial_map.ers_projection import compile_structured_cameras

    compiled = compile_structured_cameras([_camera(shot_size="close_up", primary_subject="korri")])
    cam = compiled["cameras"][0]
    assert cam["shotSize"] == "close_up"
    assert cam["primarySubject"] == "korri"


def test_camera_reference_staleness_with_nested_position() -> None:
    """Staleness reads position from the nested record form."""
    from app.spatial_map.camera_reference import compute_staleness

    record = {
        "savedVersion": "175",
        "mapVersion": "175",
        "ersRevision": "fp-1",
        "shotSize": "medium",
        "primarySubject": "auto",
        "orientation": "NW",
        "yawDegrees": 315.0,
        "fovPreset": "medium",
        "position": {"normalizedX": 0.35, "normalizedY": 0.15},
    }
    doc = SimpleNamespace(savedVersion="175", version="175", groundingFingerprint="fp-1")
    stale, reasons = compute_staleness(record, doc, _camera(), "fp-1")
    assert stale is False
    assert reasons == []

def test_shot_size_framing_language() -> None:
    from app.spatial_map.mini_production_compiler import shot_size_framing_line

    assert "WIDE" in shot_size_framing_line("wide")
    assert "MEDIUM CLOSE" in shot_size_framing_line("medium_close")
    assert shot_size_framing_line("auto") == ""
    assert "face" in shot_size_framing_line("close_up")
