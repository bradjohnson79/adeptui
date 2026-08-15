"""M42 Wave 4 — advanced image editing tests."""

from __future__ import annotations

from pathlib import Path

from app.image_product.edit_intent import default_edit_layers, validate_basic
from app.image_product.edit_ops import EDIT_OPERATIONS, validate_operation
from app.image_product.edit_recommend import recommend_edit
from app.image_product.edit_compile import compile_edit_request
from app.image_product.recipes import BUILTIN_RECIPES, apply_recipe_to_request, list_recipes
from app.image_product.layers import default_stack
from app.image_product.versions import create_version, set_state, add_review_note, get_tree
from app.image_product.masks import save_mask, get_mask_path
from app.image_product.kontext import create_session, add_turn
from app.image_product.production_gate import evaluate_image_wave4_gate
from app.image_runtime.certified_registry import get_workflow, production_ready_keys, reload_registry
from app.image_runtime.contract import resolve_image_workflow
from app.image_runtime.job_model import ImageJobStage
from app.image_runtime.output_gate import validate_edit_output
from app.image_runtime.production_gate import evaluate_image_wave2_gate, evaluate_image_gate


def test_edit_ops_taxonomy_complete():
    required = {
        "image.inpaint",
        "image.outpaint",
        "image.object_remove",
        "image.upscale",
        "image.reference_edit",
        "image.relight",
        "image.multi_reference_compose",
    }
    assert required.issubset(set(EDIT_OPERATIONS))
    validate_operation("image.inpaint")


def test_builtin_recipes():
    names = {r["name"] for r in BUILTIN_RECIPES}
    for n in ("Remove Object", "Fix Hands", "Repair Face", "Moonlight Grade", "Poster Cleanup"):
        assert n in names
    assert len(list_recipes("test-w4-recipes")) >= 8
    recipe = next(r for r in BUILTIN_RECIPES if r["name"] == "Remove Object")
    applied = apply_recipe_to_request(recipe, detail="chair")
    assert applied["operation"] == "image.object_remove" or "inpaint" in applied["operation"]


def test_edit_layers_default():
    layers = default_edit_layers()
    kinds = {l.get("kind") for l in layers}
    assert {"background", "foreground", "mask", "reference"}.issubset(kinds) or len(default_stack()) >= 4


def test_recommend_edit_envelope():
    rec = recommend_edit(
        operation="image.inpaint",
        prompt="remove the chair",
        has_masks=True,
        source_asset_ids=["a1"],
    )
    assert rec["recommendedFamily"]
    assert rec["whyThisModel"]
    assert rec["estimates"]["costLabel"]
    assert rec["overridable"] is True


def test_compile_inpaint_certified():
    reload_registry()
    compiled = compile_edit_request(
        "test-w4-compile",
        {
            "operation": "image.inpaint",
            "prompt": "remove object in mask",
            "sourceAssetIds": ["src-1"],
            "masks": [{"maskAssetId": "mask-1", "role": "replace"}],
            "allowIncomplete": True,
        },
    )
    assert compiled["imageEditIntent"]["operation"] == "image.inpaint"
    assert compiled["imageRuntime"]["workflowKey"] in {"zimage.inpaint", "zimage.ref_edit"}
    assert compiled["imageIntent"]["workflowPreference"] is None


def test_required_edit_keys_certified():
    reload_registry()
    ready = set(production_ready_keys())
    for key in ("zimage.ref_edit", "zimage.inpaint", "zimage.outpaint", "image.upscale"):
        assert key in ready
        assert get_workflow(key).status == "Certified"


def test_resolve_edit_ops_production():
    c = resolve_image_workflow("image.inpaint", engine="zimage", allow_draft=False)
    assert c.workflow_key == "zimage.inpaint"
    c2 = resolve_image_workflow("image.outpaint", engine="zimage", allow_draft=False)
    assert c2.workflow_key == "zimage.outpaint"
    c3 = resolve_image_workflow("image.upscale", engine="zimage", allow_draft=False)
    assert c3.workflow_key == "image.upscale"


def test_masks_and_versions():
    pid = "test-w4-masks-ver"
    # Minimal 1x1 PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x00\x00\x00\x00:~\x9bU\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    mask = save_mask(pid, source_asset_id="src", png_bytes=png, role="replace")
    assert get_mask_path(pid, mask["maskId"])
    ver = create_version(pid, source_asset_id="src", output_asset_id="out1", name="Inpaint A")
    set_state(pid, ver["versionId"], "PendingReview")
    add_review_note(pid, ver["versionId"], author="producer", text="Looks good")
    set_state(pid, ver["versionId"], "Approved")
    tree = get_tree(pid)
    assert tree.get("versions") or tree.get("nodes")


def test_kontext_draft_or_blocked():
    sess = create_session("p-k", source_asset_id="a1")
    # With FLUX weights present, flux.kontext_edit is Draft; without weights it is Blocked.
    assert sess["status"] in {"Draft", "Blocked"}
    assert sess["status"] != "CertifiedReady"
    turn = add_turn("p-k", sess["sessionId"], role="user", text="make it blue")
    assert turn.get("status") in {"Draft", "Blocked"}
    assert not (turn.get("turn") or {}).get("executed")


def test_edit_job_stages():
    stages = {s.value for s in ImageJobStage}
    for s in ("PreparingMasks", "PreparingControls", "Compositing", "CreatingVersion", "Retrying"):
        assert s in stages


def test_semantic_gate_upscale(tmp_path: Path):
    from PIL import Image

    src = tmp_path / "src.png"
    out = tmp_path / "out.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(src)
    Image.new("RGB", (128, 128), (10, 20, 30)).save(out)
    gate = validate_edit_output(out, operation="image.upscale", source_path=src, generate_previews=False)
    assert gate.ok
    assert gate.checks.get("resolutionIncreased")


def test_composite_generated_into_source_keeps_unmasked_pixels(tmp_path: Path):
    from PIL import Image, ImageDraw

    from app.image_runtime.output_gate import composite_generated_into_source

    src = tmp_path / "src.png"
    gen = tmp_path / "gen.png"
    mask = tmp_path / "mask.png"
    out = tmp_path / "out.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(src)
    Image.new("RGB", (64, 64), (200, 10, 10)).save(gen)
    mask_im = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(mask_im).rectangle((16, 16, 48, 48), fill=255)
    mask_im.save(mask)
    composite_generated_into_source(gen, src, mask, out, feather_px=0)
    result = Image.open(out).convert("RGB")
    assert result.getpixel((0, 0)) == (10, 20, 30)
    assert result.getpixel((32, 32)) == (200, 10, 10)


def test_w1_w2_preserved():
    assert evaluate_image_gate().get("wave1Go") is True
    assert evaluate_image_wave2_gate().get("wave2Go") is True


def test_no_product_builder_imports():
    root = Path(__file__).resolve().parents[1] / "app" / "image_product"
    banned = ("build_leaf_graph", "from ..comfy", "workflow_execute")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name}: {token}"


def test_wave4_gate_structure():
    gate = evaluate_image_wave4_gate()
    assert gate["phase"] == "M42-W4"
    assert "wave4Go" in gate
    assert "missingRequirements" in gate
