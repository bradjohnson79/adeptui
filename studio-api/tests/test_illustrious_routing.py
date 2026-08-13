"""Illustrious XL anime image engine — routing + integration unit tests.

Verifies the smallest-correct integration path:
- Resolver normalizes illustrious aliases and resolves txt2img to illustrious.txt2img.
- _checkpoint_for_model("illustrious") returns the configured SDXL checkpoint filename.
- IMAGEGEN_MODELS exposes Illustrious XL to the creator picker.
- Data-driven style→engine routing: anime/realistic-anime styles declare
  preferredFamily "illustrious"; recommend_image_family prefers Illustrious only
  when Certified-executable and falls back honestly while Draft; photoreal/live-
  action styles never route to Illustrious.
- Character Creator: no-reference anime candidates prefer Illustrious first when
  Certified; reference-locked candidates stay on zimage.ref_edit (Reference Law).
- The Realistic Anime builtin preset exists with preferredModelFamily "illustrious".
- No regression: zimage/qwen/flux resolution and the existing no-reference family
  order are preserved when no anime style is selected.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.image_runtime.certified_registry import (
    certified_families_for_style,
    get_workflow,
    reload_registry,
)
from app.image_runtime.contract import _normalize_family, resolve_image_workflow
from app.imagegen_workflows import IMAGEGEN_MODELS
from app.image_product.presets import BUILTIN_PRESETS
from app.image_product.recommend import recommend_image_family
from app.style_intelligence.registry import preferred_family_for_style


# --- Resolver normalization --------------------------------------------------


def test_normalize_family_recognizes_illustrious_aliases():
    for alias in ("illustrious", "Illustrious", "illustrious-xl", "illustrious_xl", "sdxl-illustrious", "sdxl_illustrious"):
        assert _normalize_family(alias, None) == "illustrious", alias
        assert _normalize_family(None, alias) == "illustrious", alias


def test_normalize_family_preserves_existing_families():
    assert _normalize_family("zimage", None) == "zimage"
    assert _normalize_family("flux", None) == "flux"
    assert _normalize_family("qwen2512", None) == "qwen2512"
    assert _normalize_family("checkpoint", None) == "checkpoint"


def test_resolve_illustrious_txt2img_workflow():
    reload_registry()
    c = resolve_image_workflow("txt2img", engine="illustrious", allow_draft=True)
    assert c.workflow_key == "illustrious.txt2img"
    assert c.model_family == "illustrious"
    assert c.builder_path == "app.imagegen_workflows:build_txt2img_workflow"
    assert "anime" in c.style_tags
    assert "realistic_anime" in c.style_tags


def test_illustrious_workflow_supports_references_is_false():
    wf = get_workflow("illustrious.txt2img")
    assert wf is not None
    assert wf.capabilities.get("supportsReferences") is False


# --- Checkpoint resolution ----------------------------------------------------


def test_checkpoint_for_model_illustrious_returns_configured_filename():
    from app.queue_worker import JobQueue

    # Instantiate without DB — _checkpoint_for_model is a pure lookup.
    worker = JobQueue.__new__(JobQueue)
    assert worker._checkpoint_for_model("illustrious") == settings.imagegen_illustrious_checkpoint
    assert worker._checkpoint_for_model("ILLUSTRIOUS") == settings.imagegen_illustrious_checkpoint
    # Existing families unchanged.
    assert worker._checkpoint_for_model("zimage") == settings.zimage_unet
    assert worker._checkpoint_for_model("auto") == settings.zimage_unet


# --- IMAGEGEN_MODELS picker --------------------------------------------------


def test_imagegen_models_exposes_illustrious():
    ids = [m["id"] for m in IMAGEGEN_MODELS]
    assert "illustrious" in ids
    illustrious = next(m for m in IMAGEGEN_MODELS if m["id"] == "illustrious")
    assert "Anime" in illustrious["label"]
    assert illustrious["group"] == "local"


# --- Data-driven style→engine routing ----------------------------------------


def test_preferred_family_for_anime_is_illustrious():
    assert preferred_family_for_style("anime") == "illustrious"
    assert preferred_family_for_style("Anime") == "illustrious"
    assert preferred_family_for_style("realistic_anime") == "illustrious"


def test_preferred_family_for_non_anime_styles_is_empty():
    # Photoreal / live-action / documentary styles have no style-specific
    # preference — they must NOT route to Illustrious.
    for style in ("live_action", "documentary_realism", "photoreal", ""):
        assert preferred_family_for_style(style) == ""


def test_recommend_anime_prefers_illustrious_when_certified(monkeypatch):
    # Simulate Illustrious being Certified-executable.
    from app.image_product import recommend

    real_executable = recommend._executable

    def fake_executable(family: str) -> bool:
        if family == "illustrious":
            return True
        return real_executable(family)

    monkeypatch.setattr(recommend, "_executable", fake_executable)
    rec = recommend_image_family(prompt="an anime warrior girl", style="anime")
    assert rec["recommendedFamily"] == "illustrious"
    assert rec["executionFamily"] == "illustrious"


def test_recommend_anime_falls_back_when_illustrious_not_certified(monkeypatch):
    # Simulate Illustrious being non-executable (Draft/Blocked). Anime must
    # fall back to an executable Certified family — never route to a
    # non-executable engine.
    from app.image_product import recommend

    real_executable = recommend._executable

    def fake_executable(family: str) -> bool:
        if family == "illustrious":
            return False
        return real_executable(family)

    monkeypatch.setattr(recommend, "_executable", fake_executable)
    rec = recommend_image_family(prompt="an anime warrior girl", style="anime")
    assert rec["executionFamily"] != "illustrious"
    assert rec["executable"] is True


def test_recommend_anime_routes_to_illustrious_when_certified():
    # With Illustrious now Certified (promoted after live smoke evidence),
    # anime style routes to Illustrious in production.
    rec = recommend_image_family(prompt="an anime warrior girl", style="anime")
    if _illustrious_certified():
        assert rec["recommendedFamily"] == "illustrious"
        assert rec["executionFamily"] == "illustrious"
        assert rec["executable"] is True


def test_recommend_photoreal_does_not_pick_illustrious(monkeypatch):
    from app.image_product import recommend

    real_executable = recommend._executable

    def fake_executable(family: str) -> bool:
        if family == "illustrious":
            return True
        return real_executable(family)

    monkeypatch.setattr(recommend, "_executable", fake_executable)
    rec = recommend_image_family(prompt="a photorealistic portrait of a man", style="live_action")
    assert rec["recommendedFamily"] != "illustrious"
    assert rec["executionFamily"] != "illustrious"


def test_recommend_explicit_preference_overrides_style(monkeypatch):
    from app.image_product import recommend

    real_executable = recommend._executable

    def fake_executable(family: str) -> bool:
        if family == "illustrious":
            return True
        return real_executable(family)

    monkeypatch.setattr(recommend, "_executable", fake_executable)
    rec = recommend_image_family(prompt="anime girl", style="anime", model_family_preference="flux")
    assert rec["recommendedFamily"] == "flux"


def test_certified_families_for_style_only_returns_certified(monkeypatch):
    from app.image_runtime import certified_registry

    # While Illustrious is Draft, it must not appear in certified_families_for_style.
    reload_registry()
    if get_workflow("illustrious.txt2img").status != "Certified":
        assert "illustrious" not in certified_families_for_style("anime")

    # Promote Illustrious in-memory by monkeypatching the cached registry loader,
    # then re-check that a Certified anime-tagged family is returned.
    real_entries = list(certified_registry.load_registry())

    class FakeWF:
        def __init__(self, base):
            self.workflow_id = base.workflow_id
            self.workflow_key = base.workflow_key
            self.status = "Certified"
            self.model_family = "illustrious"
            self.style_tags = ("anime", "realistic_anime")

    fake_illustrious = FakeWF(get_workflow("illustrious.txt2img"))

    def fake_load(*args, **kwargs):
        # Replace the illustrious entry with a Certified version.
        out = []
        replaced = False
        for w in real_entries:
            if w.workflow_key == "illustrious.txt2img":
                out.append(fake_illustrious)
                replaced = True
            else:
                out.append(w)
        if not replaced:
            out.append(fake_illustrious)
        return tuple(out)

    monkeypatch.setattr(certified_registry, "load_registry", fake_load)
    assert "illustrious" in certified_families_for_style("anime")
    # Non-anime styles do not match illustrious's tags.
    assert "illustrious" not in certified_families_for_style("live_action")


# --- Character Creator candidate routing -------------------------------------


def test_no_reference_anime_plan_prefers_illustrious_when_certified(monkeypatch):
    from app.character_identity import visual_sheet

    monkeypatch.setattr(visual_sheet, "_candidate_family_executable", lambda fam: fam == "illustrious" or fam in {"qwen2512", "zimage"})
    plan = visual_sheet._build_candidate_routing_plan(
        candidate_count=4, reference_asset_id=None, visual_style="anime"
    )
    families = [r["modelFamilyPreference"] for r in plan]
    assert families[0] == "illustrious"
    # Remaining slots use the other Certified families then reuse.
    assert set(families) <= {"illustrious", "qwen2512", "zimage"}


def test_no_reference_non_anime_plan_keeps_default_order():
    from app.character_identity.visual_sheet import NO_REFERENCE_TXT2IMG_FAMILIES

    from app.character_identity import visual_sheet
    # With no anime style, the default family order is preserved (no illustrious).
    plan = visual_sheet._build_candidate_routing_plan(
        candidate_count=4, reference_asset_id=None, visual_style="live_action"
    )
    families = [r["modelFamilyPreference"] for r in plan]
    # Illustrious is not preferred for live_action.
    assert families[0] != "illustrious" or not _illustrious_certified()
    # Default Certified families still present.
    assert set(families) <= set(NO_REFERENCE_TXT2IMG_FAMILIES) | {"illustrious"}


def test_reference_locked_plan_stays_zimage_ref_edit_with_anime_style(monkeypatch):
    from app.character_identity import visual_sheet

    monkeypatch.setattr(visual_sheet, "_candidate_family_executable", lambda fam: fam == "illustrious" or fam in {"qwen2512", "zimage"})
    plan = visual_sheet._build_candidate_routing_plan(
        candidate_count=4, reference_asset_id="sheet-1", visual_style="anime"
    )
    assert len(plan) == 4
    for route in plan:
        assert route["modelFamilyPreference"] == visual_sheet.REFERENCE_LOCKED_FAMILY
        assert route["workflowKey"] == visual_sheet.REFERENCE_LOCKED_WORKFLOW_KEY
        assert route["referenceLocked"] is True
        # Illustrious never used for reference-locked candidates (Reference Law).
        assert route["modelFamilyPreference"] != "illustrious"


def _illustrious_certified() -> bool:
    reload_registry()
    wf = get_workflow("illustrious.txt2img")
    return bool(wf and wf.status == "Certified")


# --- Realistic Anime preset ---------------------------------------------------


def test_realistic_anime_preset_exists():
    preset = next((p for p in BUILTIN_PRESETS if p["presetId"] == "builtin-realistic-anime"), None)
    assert preset is not None
    assert preset["preferredModelFamily"] == "illustrious"
    assert preset["aspectRatio"] == "16:9"
    assert preset["qualityPreset"] == "high"
    # Template keeps the character visibly anime (not photoreal).
    tpl = preset["promptTemplate"].lower()
    assert "anime" in tpl
    assert "not photoreal" in tpl or "visibly anime" in tpl


# --- No regression to existing families ---------------------------------------


def test_zimage_and_qwen_still_resolve():
    reload_registry()
    cz = resolve_image_workflow("txt2img", engine="zimage", allow_draft=False)
    assert cz.workflow_key == "zimage.txt2img"
    assert cz.status == "Certified"
    cq = resolve_image_workflow("txt2img", engine="qwen2512", allow_draft=True)
    assert cq.workflow_key == "qwen2512.txt2img"


def test_existing_no_reference_default_order_preserved_without_style():
    from app.character_identity.visual_sheet import NO_REFERENCE_TXT2IMG_FAMILIES
    from app.character_identity import visual_sheet

    plan = visual_sheet._build_candidate_routing_plan(
        candidate_count=len(NO_REFERENCE_TXT2IMG_FAMILIES), reference_asset_id=None, visual_style=None
    )
    families = [r["modelFamilyPreference"] for r in plan]
    # Without an anime style, the default Certified family order is preserved.
    for fam in NO_REFERENCE_TXT2IMG_FAMILIES:
        if visual_sheet._candidate_family_executable(fam):
            assert fam in families


# --- Model discovery ---------------------------------------------------------


def test_model_discovery_detects_illustrious():
    from app.image_runtime.model_discovery import discover_modern_image_models

    discovery = discover_modern_image_models()
    families = discovery.get("families") or {}
    assert "illustrious" in families
    ill = families["illustrious"]
    # The checkpoint was installed during this mission; discovery must see it.
    assert ill["installed"] is True
    assert ill["statusHint"] == "Draft"
