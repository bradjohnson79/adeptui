"""Interior / Exterior Spatial Layout Compiler + Local-only environmentType."""

from __future__ import annotations

import json
import uuid

from PIL import Image
import numpy as np

from app.codirector.capabilities.handlers import atlas_generate
from app.spatial_map.atlas_provider import RETIRED_LOCAL_ATLAS_KEYS, resolve_local_atlas_design_provider
from app.spatial_map.design_guide import rasterize_design_guide
from app.spatial_map.layout_compiler import compile_spatial_layout, render_appearance_prior
from app.spatial_map.scene_intent import compile_environment_design
from app.workflows.qwen_image_2512_atlas import (
    QWEN_2512_ATLAS_LAYOUT_KEY,
    build_qwen_2512_atlas_layout_workflow,
)


CORRIDOR = (
    "Long silver metallic corridor with an elevator door at the end of the corridor. "
    "Around the middle area of the corridor is a door to the Combat chamber on the right side. "
    "Yellow strip against the wall leading to the Combat Chamber."
)

FOREST = (
    "Dense pine forest with a circular clearing in the center. "
    "A river runs north to south along the western edge. "
    "A dirt trail enters from the southeast and leads to the clearing. "
    "A large fallen tree sits northeast of the clearing. "
    "A rocky hill rises at the northern edge."
)


def _patch_enqueue(monkeypatch, captured: list[dict]):
    class _Job:
        id = "job-layout-1"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)


def test_interior_packet_and_guide_are_parser_derived() -> None:
    packet = compile_environment_design(CORRIDOR, environment_class="interior")
    assert packet.environmentClass == "interior"
    assert packet.environmentSubtype == "corridor"
    assert any(z.type == "corridor" for z in packet.zones)
    assert any(a.type == "elevator" for a in packet.anchors)
    assert any("combat" in (a.label or "").lower() for a in packet.anchors)
    assert any(p.type == "guidance_strip" for p in packet.paths)
    layout = compile_spatial_layout(packet, description=CORRIDOR, environment_class="interior")
    kinds = {p.type for p in layout.primitives}
    assert "corridor" in kinds
    assert "elevator" in kinds
    assert "doorway" in kinds
    assert "guidance_strip" in kinds
    png = rasterize_design_guide(packet, description=CORRIDOR, width=256, height=256, environment_class="interior")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    arr = np.asarray(Image.open(__import__("io").BytesIO(png)).convert("RGB"))
    yellow = ((arr[:, :, 0] > 180) & (arr[:, :, 1] > 140) & (arr[:, :, 2] < 90)).mean()
    assert yellow > 0.002


def test_exterior_packet_is_not_forced_into_rooms() -> None:
    packet = compile_environment_design(FOREST, environment_class="exterior")
    assert packet.environmentClass == "exterior"
    types = {z.type for z in packet.zones}
    assert "vegetation" in types
    assert "clearing" in types
    assert "water" in types
    assert "elevation" in types
    assert not any(z.type in {"room", "corridor"} for z in packet.zones)
    layout = compile_spatial_layout(packet, description=FOREST, environment_class="exterior")
    kinds = {p.type for p in layout.primitives}
    assert "clearing" in kinds
    assert "river" in kinds
    assert "trail" in kinds
    assert "landmark" in kinds
    assert "elevation" in kinds
    png = rasterize_design_guide(packet, description=FOREST, width=256, height=256, environment_class="exterior")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert packet.environmentSubtype in {"forest_clearing", "forest", "waterside", "landscape"}


def test_exterior_recompile_does_not_keep_interior_subtype() -> None:
    prior = compile_environment_design(CORRIDOR, environment_class="interior")
    assert prior.environmentSubtype == "corridor"
    repaired = compile_environment_design(
        FOREST,
        environment_class="exterior",
        extra={**prior.model_dump(), "environmentSubtype": "interior"},
    )
    assert repaired.environmentClass == "exterior"
    assert repaired.environmentSubtype in {"forest_clearing", "forest", "waterside", "landscape"}
    assert repaired.environmentSubtype != "interior"


def test_local_exterior_handle_drops_stale_interior_subtype(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    prior = compile_environment_design(CORRIDOR, environment_class="interior")
    result = atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt=FOREST,
        scene_description=FOREST,
        generationMethod="local",
        mode="express",
        environmentType="exterior",
        environmentDesign=prior.model_dump(),
    )
    leak = json.dumps(captured[0], default=str).lower()
    assert captured[0].get("forceWorkflowKey") not in {
        "qwen2512.atlas_layout",
        "flux.txt2img",
        "flux.atlas_layout_control",
    }
    assert "gpt-image-2" in leak
    assert "qwen2512.atlas_layout" not in leak


def test_appearance_prior_is_material_swatch_not_floorplan() -> None:
    packet = compile_environment_design(CORRIDOR, environment_class="interior")
    png = render_appearance_prior(packet, environment_class="interior", width=128, height=128)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    arr = np.asarray(Image.open(__import__("io").BytesIO(png)).convert("RGB"))
    assert arr.mean() > 80


def test_qwen_layout_is_in_readiness_catalog() -> None:
    from app.workflows.readiness import WORKFLOW_MODEL_COMPONENTS

    assert "qwen2512.atlas_layout" in WORKFLOW_MODEL_COMPONENTS
    assert WORKFLOW_MODEL_COMPONENTS["qwen2512.atlas_layout"] == ("qwen_image_2512_models",)


def test_local_resolver_is_qwen_layout_not_retired_i2i() -> None:
    resolved = resolve_local_atlas_design_provider(require_ready=False)
    assert resolved["ok"] is False
    assert resolved["code"] == "LOCAL_ATLAS_NOT_PRODUCTION_CERTIFIED"
    refused = resolve_local_atlas_design_provider(explicit="qwen2512.atlas", require_ready=False)
    assert refused["ok"] is False
    flux = resolve_local_atlas_design_provider(explicit="flux.txt2img", require_ready=False)
    assert flux["ok"] is False


def test_local_interior_sends_environment_type_and_guide(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    result = atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt=CORRIDOR,
        scene_description=CORRIDOR,
        generationMethod="local",
        mode="express",
        environmentType="interior",
    )
    body = captured[0]
    assert result["geometrySource"] == "designed"
    assert body.get("forceWorkflowKey") not in {
        "qwen2512.atlas_layout",
        "flux.txt2img",
        "flux.atlas_layout_control",
    }
    leak = json.dumps(body, default=str).lower()
    assert "gpt-image-2" in leak
    assert "qwen2512.atlas_layout" not in leak


def test_local_exterior_routes_exterior_compiler(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt=FOREST,
        scene_description=FOREST,
        generationMethod="local",
        mode="express",
        environmentType="exterior",
    )
    body = captured[0]
    leak = json.dumps(body, default=str).lower()
    assert "gpt-image-2" in leak
    assert "qwen2512.atlas_layout" not in leak
    assert body.get("forceWorkflowKey") not in {"qwen2512.atlas_layout", "flux.txt2img"}


def test_api_ignores_stale_environment_type(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Create a new underground lab environment.",
        scene_description="a silver underground research corridor for Spatial Map",
        generationMethod="api",
        generation_route="designed",
        environmentType="exterior",
        environment_type="exterior",
    )
    body = captured[0]
    assert body["source"] == "api"
    assert body["hostedModelId"] == "gpt-image-2-kie"
    assert body["creativeContext"]["engineNote"] == "gpt_image_2_atlas_design"
    assert body.get("forceWorkflowKey") in {None, ""}
    ctx = str(body["creativeContext"])
    assert "environmentType" not in body["creativeContext"] or body["creativeContext"].get("environmentType") in {None, ""}
    assert "qwen2512.atlas_layout" not in ctx
    assert "spatialLayout" not in body["creativeContext"]


def test_qwen_layout_workflow_guide_only_and_dual() -> None:
    single = build_qwen_2512_atlas_layout_workflow(
        unet_name="u.safetensors",
        clip_name="c.safetensors",
        vae_name="v.safetensors",
        positive="paint the guide",
        guide_image="guide.png",
    )
    loads = [n for n in single.values() if n.get("class_type") == "LoadImage"]
    assert len(loads) == 1
    assert loads[0]["inputs"]["image"] == "guide.png"
    dual_guide_first = build_qwen_2512_atlas_layout_workflow(
        unet_name="u.safetensors",
        clip_name="c.safetensors",
        vae_name="v.safetensors",
        positive="paint the guide",
        guide_image="guide.png",
        appearance_image="look.png",
        slot_order="guide_source",
    )
    dual_look_first = build_qwen_2512_atlas_layout_workflow(
        unet_name="u.safetensors",
        clip_name="c.safetensors",
        vae_name="v.safetensors",
        positive="paint the guide",
        guide_image="guide.png",
        appearance_image="look.png",
        slot_order="source_guide",
    )
    g1 = [n["inputs"]["image"] for n in dual_guide_first.values() if n.get("class_type") == "LoadImage"]
    g2 = [n["inputs"]["image"] for n in dual_look_first.values() if n.get("class_type") == "LoadImage"]
    assert g1 == ["guide.png", "look.png"]
    assert g2 == ["look.png", "guide.png"]
    assert QWEN_2512_ATLAS_LAYOUT_KEY == "qwen2512.atlas_layout"


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


def test_guide_alignment_rejects_rearranged_and_keeps_negatives() -> None:
    from app.codirector.vision.atlas_gate import pixel_prefilter_candidate
    import io

    packet = compile_environment_design(CORRIDOR, environment_class="interior")
    guide = rasterize_design_guide(packet, description=CORRIDOR, width=160, height=160, environment_class="interior")
    guide_arr = np.asarray(Image.open(io.BytesIO(guide)).convert("RGB"))

    forest = compile_environment_design(FOREST, environment_class="exterior")
    forest_png = rasterize_design_guide(forest, description=FOREST, width=160, height=160, environment_class="exterior")
    forest_arr = np.asarray(Image.open(io.BytesIO(forest_png)).convert("RGB"))
    mismatch = pixel_prefilter_candidate(forest_arr, 160, 160, guide_arr=guide_arr)
    assert mismatch["ok"] is False
    assert mismatch["failCode"] == "FAIL_TOPOLOGY"

    persp = _perspective_corridor()
    grid = _corridor_plus_grid()
    persp_v = pixel_prefilter_candidate(persp, persp.shape[1], persp.shape[0], source_arr=persp, source_w=persp.shape[1], source_h=persp.shape[0])
    assert persp_v["ok"] is False
    assert persp_v["failCode"] == "FAIL_TOP_DOWN"
    grid_v = pixel_prefilter_candidate(grid, grid.shape[1], grid.shape[0], source_arr=persp, source_w=persp.shape[1], source_h=persp.shape[0])
    assert grid_v["ok"] is False
    assert grid_v["failCode"] == "FAIL_TOP_DOWN"


def _flux_like_abstract(size: int = 160) -> np.ndarray:
    """Owner-rejected FLUX class: metallic top-down-ish pattern, no corridor topology."""
    yy, xx = np.mgrid[0:size, 0:size]
    arr = np.stack(
        [
            (80 + (xx * 3) % 40).astype(np.uint8),
            (90 + (yy * 2) % 30).astype(np.uint8),
            (100 + ((xx + yy) * 2) % 20).astype(np.uint8),
        ],
        axis=2,
    )
    arr[20:40, 20:140] = [200, 190, 60]
    arr[80:100, 10:150] = [40, 180, 80]
    return arr


def test_rejected_flux_class_fails_guide_gate() -> None:
    from app.codirector.vision.atlas_gate import pixel_prefilter_candidate
    import io

    packet = compile_environment_design(CORRIDOR, environment_class="interior")
    guide = rasterize_design_guide(packet, description=CORRIDOR, width=160, height=160, environment_class="interior")
    guide_arr = np.asarray(Image.open(io.BytesIO(guide)).convert("RGB"))
    flux = _flux_like_abstract()
    verdict = pixel_prefilter_candidate(flux, flux.shape[1], flux.shape[0], guide_arr=guide_arr)
    assert verdict["ok"] is False
    assert verdict["failCode"] in {"FAIL_TOPOLOGY", "FAIL_TOP_DOWN", "FAIL_UNRELATED_SCENE"}
