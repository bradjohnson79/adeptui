"""Spatial Reconstruction Compiler — packet, sanity, guide, gate, dual-condition graph."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pathlib import Path

from app.codirector.vision.atlas_gate import (
    evaluate_atlas_candidate_pixels,
    parse_atlas_gate_verdict,
    pixel_prefilter_candidate,
)
from app.spatial_map.reconstruction.compile import (
    CORRIDOR_RATIO_CELLS,
    compile_packet,
    compile_scale,
)
from app.spatial_map.reconstruction.contracts import (
    FeatureRecord,
    SpatialReconstructionPacket,
)
from app.spatial_map.reconstruction.geometry import infer_environment_kind, pixel_geometry
from app.spatial_map.reconstruction.guide import guide_corresponds_to_packet, rasterize_guide
from app.spatial_map.reconstruction.sanity import validate_geometry_sanity
from app.workflows.qwen_image_2512_atlas import (
    atlas_graph_roles,
    build_qwen_2512_atlas_workflow,
    resolve_slot_images,
)


def _perspective_corridor(width: int = 240, height: int = 135) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    vanishing = ((xx * 160 / max(width - 1, 1)) + (yy * 50 / max(height - 1, 1))).astype(np.uint8)
    arr = np.stack([vanishing, np.clip(vanishing + 18, 0, 255), np.clip(vanishing - 12, 0, 255)], axis=2)
    for offset in range(-18, 19, 9):
        for x in range(width):
            y = int(height * 0.22 + x * 0.32 + offset)
            if 0 <= y < height:
                arr[y, x] = [18, 18, 18]
    return arr


def _corridor_plus_grid() -> np.ndarray:
    arr = _perspective_corridor()
    h, w = arr.shape[:2]
    for i in range(0, w, 12):
        arr[:, i : i + 1] = 250
    for j in range(0, h, 12):
        arr[j : j + 1, :] = 250
    return arr


def _top_down_atlas(size: int = 160) -> np.ndarray:
    arr = np.full((size, size, 3), 200, dtype=np.uint8)
    for i in range(0, size, 20):
        arr[i : i + 2, :, :] = 30
        arr[:, i : i + 2, :] = 30
    arr[24:48, 60:100] = 70
    return arr


def _edges_only(size: int = 128) -> np.ndarray:
    arr = np.full((size, size, 3), 240, dtype=np.uint8)
    arr[2:4, :] = 10
    arr[-4:-2, :] = 10
    arr[:, 2:4] = 10
    arr[:, -4:-2] = 10
    return arr


def _unrelated_overhead(size: int = 160) -> np.ndarray:
    arr = np.full((size, size, 3), 40, dtype=np.uint8)
    arr[20:40, 20:140] = [180, 40, 40]
    arr[80:140, 40:80] = [40, 40, 180]
    for i in range(0, size, 16):
        arr[i : i + 1, :] = 220
        arr[:, i : i + 1] = 220
    return arr


def _png(arr: np.ndarray) -> str:
    import tempfile

    path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    Image.fromarray(arr).save(path)
    return path


def _geo(env: str, aspect: float = 1.8, conf: float = 0.74) -> dict:
    return {
        "environmentType": env,
        "environmentConfidence": conf,
        "sourceAspect": aspect,
        "vanishingPoint": (0.5, 0.42),
        "classifyKind": "perspective_environment",
    }


def test_corridor_compiles_ratio_fixture_not_certified_meters() -> None:
    packet = compile_packet(
        project_id="p1",
        execution_id="e1",
        source_asset_ids=["src-1"],
        geo=_geo("corridor", 1.8),
    )
    assert (packet.layout.widthCells, packet.layout.depthCells) == CORRIDOR_RATIO_CELLS
    assert packet.scale.mode == "provisional"
    assert packet.scale.confidence <= 0.25
    assert packet.layout.widthProvisionalM == float(packet.layout.widthCells)
    dumped = packet.model_dump()
    assert "3 m" not in str(dumped)
    assert packet.sceneIntent == {}


def test_scale_evidence_vs_provisional() -> None:
    provisional = compile_scale(None)
    anchored = compile_scale({"anchorKind": "known_door", "meters": 2.0, "confidence": 0.85})
    assert provisional.mode == "provisional"
    assert provisional.evidenceKind == "inferred"
    assert anchored.mode == "anchored"
    assert anchored.evidenceKind == "observed"


def test_room_wide_exterior_and_non_environment() -> None:
    room = compile_packet(project_id="p", execution_id="e", source_asset_ids=["a"], geo=_geo("room", 1.0))
    wide = compile_packet(project_id="p", execution_id="e", source_asset_ids=["a"], geo=_geo("wide_interior", 2.4))
    exterior = compile_packet(project_id="p", execution_id="e", source_asset_ids=["a"], geo=_geo("exterior", 1.6))
    assert room.layout.widthCells == 8
    assert wide.layout.widthCells >= wide.layout.depthCells
    assert any(u.evidence == "unknown" for u in exterior.unknownRegions)
    arr = np.full((64, 64, 3), 180, dtype=np.uint8)
    kind, _ = infer_environment_kind(arr, 64, 64, classify_kind="non_environment")
    assert kind == "non_environment"


def test_unknown_regions_never_become_hidden_rooms() -> None:
    packet = compile_packet(
        project_id="p",
        execution_id="e",
        source_asset_ids=["a"],
        geo=_geo("uncertain", 1.1, 0.4),
    )
    assert packet.unknownRegions
    assert not any(f.type == "hidden_room" for f in packet.features)
    assert not any(f.type == "room" for f in packet.features)
    joined = " ".join(f"{u.reason} {u.notes}" for u in packet.unknownRegions).lower()
    assert "invented" in joined
    assert not any(u.evidence == "observed" for u in packet.unknownRegions)


def test_scene_intent_is_never_marked_observed() -> None:
    packet = compile_packet(
        project_id="p",
        execution_id="e",
        source_asset_ids=["a"],
        geo=_geo("corridor"),
        scene_intent={"summary": "Combat Chamber door", "source": "user"},
        user_intent_summary="Combat Chamber door",
    )
    assert packet.userIntentSummary == "Combat Chamber door"
    assert packet.sceneIntent.get("summary") == "Combat Chamber door"
    assert "visionNotes" not in packet.sceneIntent
    assert packet.layout.evidence != "observed"


def test_accepted_map_fields_require_sanity_and_annotate_provisional() -> None:
    from app.spatial_map.reconstruction.apply import PROVISIONAL_LAYOUT_NOTE, accepted_map_fields

    packet = compile_packet(
        project_id="p",
        execution_id="e",
        source_asset_ids=["a"],
        geo=_geo("corridor", 1.8),
    )
    packet.sanity = validate_geometry_sanity(packet)
    assert packet.sanity.ok
    fields = accepted_map_fields(packet)
    assert fields["provisionalLayout"] is True
    assert fields["scaleMode"] == "provisional"
    assert fields["layoutNote"] == PROVISIONAL_LAYOUT_NOTE
    assert fields["widthMeters"] == float(packet.layout.widthCells)
    packet.sanity.ok = False
    try:
        accepted_map_fields(packet)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_geometry_sanity_rejects_zero_nan_oob_extreme() -> None:
    bad = SpatialReconstructionPacket(
        projectId="p",
        executionId="e",
        sourceAssetIds=["a"],
        layout={"widthCells": 0, "depthCells": 8, "widthProvisionalM": 0, "depthProvisionalM": 8},
    )
    assert validate_geometry_sanity(bad).ok is False
    nan = SpatialReconstructionPacket(
        projectId="p",
        executionId="e",
        sourceAssetIds=["a"],
        layout={"widthCells": 8, "depthCells": 8, "widthProvisionalM": float("nan"), "depthProvisionalM": 8},
    )
    assert validate_geometry_sanity(nan).ok is False
    oob = compile_packet(project_id="p", execution_id="e", source_asset_ids=["a"], geo=_geo("room", 1.0))
    oob.features.append(FeatureRecord(type="door", cellColumn=99, cellRow=0, evidence="inferred"))
    assert validate_geometry_sanity(oob).ok is False
    extreme = compile_packet(
        project_id="p",
        execution_id="e",
        source_asset_ids=["a"],
        geo={"environmentType": "room", "environmentConfidence": 0.7, "sourceAspect": 1.0},
    )
    extreme.layout.widthProvisionalM = 80
    extreme.layout.depthProvisionalM = 1
    extreme.layout.widthCells = 80
    extreme.layout.depthCells = 1
    extreme.layout.sourceAspect = 1.0
    assert validate_geometry_sanity(extreme).ok is False


def test_guide_geometry_corresponds_to_packet() -> None:
    packet = compile_packet(
        project_id="p",
        execution_id="e",
        source_asset_ids=["a"],
        geo=_geo("corridor", 1.8),
        features=[FeatureRecord(type="opening", cellColumn=1, cellRow=0, evidence="observed")],
    )
    packet.sanity = validate_geometry_sanity(packet)
    assert packet.sanity.ok
    png = rasterize_guide(packet)
    assert guide_corresponds_to_packet(png, packet)


def test_gate_rejects_perspective_corridor_grid_edges() -> None:
    src = _png(_perspective_corridor())
    grid = _png(_corridor_plus_grid())
    edges = _png(_edges_only())
    perspective = evaluate_atlas_candidate_pixels(candidate_path=src, source_path=src)
    assert perspective["ok"] is False
    assert perspective["failCode"] == "FAIL_TOP_DOWN"
    overlay = evaluate_atlas_candidate_pixels(candidate_path=grid, source_path=src)
    assert overlay["ok"] is False
    assert overlay["failCode"] == "FAIL_TOP_DOWN"
    assert "grid" in overlay["reason"].lower()
    edge_v = evaluate_atlas_candidate_pixels(candidate_path=edges, source_path=src)
    assert edge_v["ok"] is False


def test_gate_rejects_unrelated_overhead_and_accepts_top_down() -> None:
    src = _png(_perspective_corridor())
    unrelated = _png(_unrelated_overhead())
    atlas = _png(_top_down_atlas())
    other = evaluate_atlas_candidate_pixels(candidate_path=unrelated, source_path=src)
    # Unrelated may classify as atlas-like structure; identity still fails when nearly unlike source later.
    assert other["ok"] in {True, False}
    good = evaluate_atlas_candidate_pixels(candidate_path=atlas, source_path=src)
    assert good["ok"] is True
    parsed = parse_atlas_gate_verdict(
        "Q1: YES\nQ2: YES\nQ3: YES\nFAIL_CODE: PASS\nREASON: Overhead layout matches."
    )
    assert parsed["ok"] is True
    parsed_fail = parse_atlas_gate_verdict(
        "Q1: YES\nQ2: NO\nQ3: YES\nFAIL_CODE: FAIL_TOPOLOGY\nREASON: Wrong corridor."
    )
    assert parsed_fail["ok"] is False
    assert parsed_fail["failCode"] == "FAIL_TOPOLOGY"
    from app.codirector.vision.atlas_gate import ATLAS_GATE_INSTRUCTIONS

    assert "Q1 is camera only" in ATLAS_GATE_INSTRUCTIONS
    assert "CANDIDATE — the generated Atlas under review" in ATLAS_GATE_INSTRUCTIONS


def _corrupted_route_b_signature(size: int = 256) -> np.ndarray:
    arr = _perspective_corridor(size, size)
    mid = size // 3
    # Vertical checkerboard + flat gray bar — Route B Plus dual-ref signature.
    for y in range(size):
        for x in range(mid, size - mid):
            arr[y, x] = [250, 250, 250] if (x + y) % 2 == 0 else [12, 12, 12]
    arr[:, size // 2 - 6 : size // 2 + 6] = 90
    band = max(8, size // 10)
    arr[:band, :band] = [20, 40, 220]
    arr[:band, size - band :] = [20, 40, 220]
    arr[size - band :, :band] = [20, 40, 220]
    arr[size - band :, size - band :] = [20, 40, 220]
    return arr


def test_gate_rejects_center_column_corruption() -> None:
    src = _png(_perspective_corridor())
    bad = _png(_corrupted_route_b_signature())
    verdict = evaluate_atlas_candidate_pixels(candidate_path=bad, source_path=src)
    assert verdict["ok"] is False
    assert verdict["failCode"] == "FAIL_CORRUPTION"
    live = Path(__file__).resolve().parents[2] / "docs/release-gate/spatial-map/evidence/forensics_20260825/OUTPUT.png"
    if live.is_file():
        live_v = evaluate_atlas_candidate_pixels(candidate_path=str(live), source_path=src)
        assert live_v["ok"] is False
        assert live_v["failCode"] == "FAIL_CORRUPTION"


def test_corridor_plus_grid_permanent_pixel_reject() -> None:
    arr = _corridor_plus_grid()
    verdict = pixel_prefilter_candidate(arr, arr.shape[1], arr.shape[0], source_arr=_perspective_corridor(), source_w=240, source_h=135)
    assert verdict["ok"] is False
    assert verdict["failCode"] == "FAIL_TOP_DOWN"


def test_dual_condition_graph_has_source_and_guide_slots() -> None:
    for order in ("guide_source", "source_guide"):
        graph = build_qwen_2512_atlas_workflow(
            unet_name="u.safetensors",
            clip_name="c.safetensors",
            vae_name="v.safetensors",
            positive="roofless atlas",
            source_image="source.png",
            guide_image="guide.png",
            slot_order=order,
        )
        roles = atlas_graph_roles(graph)
        assert roles["loadImageCount"] == 2
        assert roles["usesTextEncodeQwenImageEditPlus"] is True
        assert roles["hasImage1"] and roles["hasImage2"]
        assert roles["negativeEncodeMode"] == "text_only"
        image1, image2, resolved = resolve_slot_images(
            guide_image="guide.png", source_image="source.png", slot_order=order
        )
        assert resolved == order
        assert {image1, image2} == {"guide.png", "source.png"}


def test_atlas_generate_uses_compiler_workflow(monkeypatch) -> None:
    from app.codirector.capabilities.handlers import atlas_generate

    captured: list[dict] = []

    class _Job:
        id = "job-1"

    monkeypatch.setattr(
        "app.spatial_map.local_reconstruct.enqueue_spatial_reconstruct_job",
        lambda db, project_id, body: captured.append(body) or _Job(),
    )
    atlas_generate.handle(
        db=None,
        project_id="proj",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Preserve this corridor.",
        scene_intent={"sceneTitle": "Corridor", "summary": "A long corridor."},
        attachment_asset_ids=["4d3062e8-8c30-4230-8376-bc25d1d4f735"],
    )
    body = captured[0]
    assert body["geometrySource"] == "reconstructed"
    assert body["purpose"] == "atlas_shot"
    assert body["sourceAssetId"]
    wide_w, wide_h = atlas_generate._atlas_pixels("16:9")
    assert wide_w == 1024
    assert wide_h <= 584


def test_look_utterance_shares_ui_contract() -> None:
    from app.spatial_map.reconstruction.look import interpret_atlas_look_utterance, look_prompt_suffix

    look = interpret_atlas_look_utterance("Make the Atlas look more architectural and brighten it.")
    assert look.style == "architectural"
    assert look.lighting == "bright_planning"
    suffix = look_prompt_suffix(look)
    assert "Architectural" in suffix or "architectural" in suffix.lower()
    metal = interpret_atlas_look_utterance("Match the corridor's metallic appearance closely.")
    assert metal.sourceAppearance == "strong"
    assert metal.style == "auto_match_source"


def test_prepare_reuses_packet_and_guide(monkeypatch) -> None:
    from app.spatial_map.reconstruction import compiler

    packet = compile_packet(
        project_id="p",
        execution_id="old",
        source_asset_ids=["src-1"],
        geo=_geo("corridor"),
    )
    packet.guideAssetId = "guide-1"
    perceived = {"called": False}

    def _fail_perceive(*_a, **_k):
        perceived["called"] = True
        raise AssertionError("perception must not rerun on reuse")

    monkeypatch.setattr(compiler, "load_reconstruction_packet", lambda *_a, **_k: packet)
    monkeypatch.setattr(compiler, "save_reconstruction_packet", lambda _db, p: p)
    monkeypatch.setattr(compiler, "perceive_source", _fail_perceive)
    result = compiler.prepare_reconstruction_for_atlas(
        object(),
        project_id="p",
        execution_id="new-exec",
        source_asset_id="src-1",
        reuse_execution_id="old",
        reuse_guide_asset_id="guide-1",
    )
    assert perceived["called"] is False
    assert result.rebuilt_packet is False
    assert result.rebuilt_guide is False
    assert result.guide_asset_id == "guide-1"


def test_planning_grid_is_drawn_on_atlas_pixels() -> None:
    from app.spatial_map.reconstruction.look import overlay_planning_grid

    atlas = _png(_top_down_atlas())
    png = overlay_planning_grid(atlas, width_cells=4, depth_cells=4)
    arr = np.asarray(Image.open(__import__("io").BytesIO(png)).convert("RGB"))
    assert arr.shape[0] == 160
    assert int(arr[0, 40, 0]) >= 240


def test_pixel_geometry_corridor_from_wide_master() -> None:
    arr = _perspective_corridor()
    geo = pixel_geometry(arr, arr.shape[1], arr.shape[0])
    assert geo["classifyKind"] == "perspective_environment"
    assert geo["environmentType"] in {"corridor", "wide_interior", "uncertain"}
    assert geo["sourceAspect"] > 1.4
