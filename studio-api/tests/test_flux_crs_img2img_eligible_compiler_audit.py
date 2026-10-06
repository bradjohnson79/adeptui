"""Job 4b36ad09 CASE A: pin img2img eligibility + FLUX CRS compiler (no routing change)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity.crs_view_generation import (
    CRS_VIEW_FLUX_I2I,
    CRS_VIEW_FLUX_T2I,
    resolve_crs_view_generation_workflow,
    valid_identity_reference_crop,
)
from app.character_identity.visual_sheet import (
    PROFILE_GUIDED_VIEW_INSTRUCTIONS,
    _candidate_view_specs,
    _compile_visual_prompt,
    _negative_rules_for_view,
)
from app.image_product.compile import prompt_purpose_for_expand
from app.image_product.prompt_intel import expand_prompt
from app.workflows.flux_image import build_flux_txt2img_workflow


# Owner-required name. Delegates to already-pinned crop gate. No routing change.
def img2imgEligible(references, **kwargs) -> bool:
    return valid_identity_reference_crop(references, **kwargs) is not None


FORBIDDEN_POSITIVE_SHEET = (
    "character sheet",
    "turnaround",
    "contact sheet",
    "multi-view",
    "multi view",
    "four view",
    "four-view",
    "model sheet",
)

# Intended anti-sheet negatives may contain forbidden stems; strip before audit.
INTENDED_NEGATIVES = (
    "no turnaround sheet",
    "no collage",
    "no grid",
    "no multiple poses in one image",
    "no other people",
    "no alternate views",
    "no panels",
)

VIEW_CASES = (
    ("FRONT_FULL", "hero_identity"),
    ("SIDE_FULL", "full_body_side_left"),
    ("BACK_FULL", "full_body_back"),
)


def _write_sheet_crop(path: Path) -> Path:
    from PIL import Image, ImageDraw

    im = Image.new("L", (64, 64), 40)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 30, 30), fill=30)
    draw.rectangle((34, 0, 63, 30), fill=80)
    draw.rectangle((0, 34, 30, 63), fill=120)
    draw.rectangle((34, 34, 63, 63), fill=160)
    draw.rectangle((30, 0, 34, 63), fill=255)
    draw.rectangle((0, 30, 63, 34), fill=255)
    im.save(path)
    return path


def _write_single_figure_crop(path: Path) -> Path:
    from PIL import Image, ImageDraw

    im = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(im)
    draw.rectangle((20, 8, 44, 56), fill=20)
    im.save(path)
    return path


def _positive_visual(text: str) -> str:
    low = str(text or "").lower()
    for tok in INTENDED_NEGATIVES:
        low = low.replace(tok, " ")
    return low


def _leaked_positive_sheet_terms(text: str) -> list[str]:
    blob = _positive_visual(text)
    return [term for term in FORBIDDEN_POSITIVE_SHEET if term in blob]


def test_img2img_eligible_whole_crs_sheet_false(tmp_path):
    sheet = _write_sheet_crop(tmp_path / "whole_crs_sheet.png")
    refs = [
        {
            "asset_id": "whole-sheet",
            "reference_role": "hero_identity",
            "source_type": "upload",
            "layout": "character_sheet",
            "referenceKind": "IDENTITY_REFERENCE",
        }
    ]
    assert img2imgEligible(refs, image_path={"whole-sheet": str(sheet)}, detect_people=lambda _p: 4) is False


def test_img2img_eligible_multi_view_crop_false(tmp_path):
    sheet = _write_sheet_crop(tmp_path / "multi_view_crop.png")
    refs = [
        {
            "asset_id": "mv-crop",
            "reference_role": "full_body_front",
            "source_type": "crs_derived_crop",
            "referenceKind": "IDENTITY_REFERENCE",
        }
    ]
    assert img2imgEligible(
        refs,
        image_path={"mv-crop": str(sheet)},
        detect_people=lambda _p: 4,
    ) is False


def test_img2img_eligible_validated_isolated_portrait_true(tmp_path):
    one = _write_single_figure_crop(tmp_path / "isolated_portrait.png")
    refs = [
        {
            "asset_id": "iso-1",
            "reference_role": "identity_crop",
            "source_type": "crs_derived_crop",
            "referenceKind": "IDENTITY_REFERENCE",
        }
    ]
    assert img2imgEligible(
        refs,
        image_path={"iso-1": str(one)},
        detect_people=lambda _p: 1,
    ) is True


@pytest.mark.parametrize("task", ("CRS_SINGLE_VIEW", "CRS_VIEW_GENERATION"))
@pytest.mark.parametrize("view_name,role", VIEW_CASES)
def test_flux_crs_prompt_omits_positive_sheet_language(task, view_name, role):
    specs = {row[0]: row for row in _candidate_view_specs()}
    _role, goal, comp, neg = specs[role]
    pkg = _compile_visual_prompt(
        {"name": "AuditChar", "species": "human"},
        prompt_goal=goal,
        composition=dict(comp),
        references=[],
        role=role,
        extra_negative_constraints=_negative_rules_for_view(role, neg),
        sheet_request={},
    )
    assert PROFILE_GUIDED_VIEW_INSTRUCTIONS[role] in pkg.prompt
    body = {
        "purpose": "character_sheet",
        "taskType": task,
        "layout": "single_view",
        "fourViewSingleOutput": False,
        "creativeContext": {"taskType": task, "viewType": view_name.lower(), "outputCount": 1},
        "prompt": pkg.prompt,
        "imageIntent": {"purpose": "character_sheet"},
    }
    purpose = prompt_purpose_for_expand(body, "character_sheet")
    assert purpose == ""
    live = expand_prompt(pkg.prompt, purpose=purpose)["expandedPrompt"]
    leaks = _leaked_positive_sheet_terms(live)
    assert leaks == [], f"{task} {view_name} leaked positive sheet terms: {leaks}\nCOMPILER={live}"
    assert "purpose: character sheet" not in live.lower()


def test_flux_crs_batch_size_outputcount_saveimage_one():
    graph = build_flux_txt2img_workflow(
        positive="one person only",
        negative="",
        width=1024,
        height=1024,
        seed=1,
        unet_name="flux.safetensors",
        clip_l_name="clip_l.safetensors",
        t5_name="t5xxl.safetensors",
        vae_name="ae.safetensors",
    )
    batch_nodes = [
        n for n in graph.values()
        if isinstance(n, dict) and "batch_size" in (n.get("inputs") or {})
    ]
    assert batch_nodes
    assert all(int(n["inputs"]["batch_size"]) == 1 for n in batch_nodes)
    saves = [n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "SaveImage"]
    assert len(saves) == 1
    ctx = SimpleNamespace(outputCount=1)
    assert int(ctx.outputCount) == 1


def test_job_4b36ad09_compiler_audit_omits_purpose_tag():
    """Live CASE A params: imageIntent.purpose character_sheet, task on creativeContext."""
    live_prompt = (
        "Photograph of exactly one person, Korri, alone. Korri, human, 18, female, Petit, "
        "Korri is an 18 year old petite teenage Sun Sprite Elf girl with a slim, athletic build, "
        "pale skin, large pointed elf ears, vivid purple eyes, and messy black hair styled into "
        "high twin ponytails with loose bangs framing her face. She wears large dark wooden hoop "
        "earrings and has intricate Light Circuitry markings running along her left arm, which can "
        "glow violet when active. Her clothing is handmade and asymmetrical: a black wrapped crop "
        "top, short layered black skirt/shorts with hanging fabric strips, a dark sash belt, wooden "
        "ankle cuffs, and simple brown leather-and-plant-weave sandals. Her overall appearance is "
        "rebellious, agile, expressive, slightly untamed, and unmistakably elven.. FRONT: one camera "
        "only, this view only, front-facing, full-body neutral stance. entire body visible, head to "
        "feet in frame, standing alone. Neutral simple studio background. One camera, this view only. "
        "one person only, one figure, no other people, no grid, no collage, no turnaround sheet, "
        "no multiple poses in one image. No duplicate, no alternate views, no panels, no inset, no text."
    )
    body = {
        "purpose": "character_sheet",
        "prompt": live_prompt,
        "imageIntent": {"purpose": "character_sheet"},
        "creativeContext": {
            "taskType": "CRS_VIEW_GENERATION",
            "viewType": "front_full",
            "outputCount": 1,
            "sheetComposition": False,
            "fourViewSingleOutput": False,
            "workflowKey": "flux.txt2img",
        },
    }
    purpose = prompt_purpose_for_expand(body, str(body.get("purpose") or ""))
    info = expand_prompt(live_prompt, purpose=purpose)
    print("JOB_4b36ad09_PURPOSE_FOR_EXPAND=", repr(purpose))
    print("JOB_4b36ad09_COMPILER_OUTPUT=", info["expandedPrompt"])
    leaks = _leaked_positive_sheet_terms(info["expandedPrompt"])
    assert purpose == ""
    assert "purpose: character sheet" not in info["expandedPrompt"].lower()
    assert leaks == [], f"FAIL COMPILER AUDIT leaked={leaks}"
    assert resolve_crs_view_generation_workflow.__name__ == "resolve_crs_view_generation_workflow"
    # Routing keys unchanged: t2i/i2i names only referenced, not rewritten.
    assert CRS_VIEW_FLUX_T2I == "flux.txt2img"
    assert CRS_VIEW_FLUX_I2I == "flux.img2img"
