from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "comfy_input_dir", tmp_path / "comfy" / "input")
    (tmp_path / "models" / "loras").mkdir(parents=True)
    (tmp_path / "comfy" / "input").mkdir(parents=True)
    return tmp_path


def _png(path: Path, size: tuple[int, int] = (512, 512), color=(200, 100, 50)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_registry_entry_exists():
    from app.references.models import INGREDIENTS_MODEL_ID, get_reference_model
    from app.workflows.registry import DEFAULT_WORKFLOW_REGISTRY

    model = get_reference_model(INGREDIENTS_MODEL_ID)
    assert model.filename.endswith(".safetensors")
    assert model.gated is True
    assert DEFAULT_WORKFLOW_REGISTRY.get("ltx.ingredients_ic_lora").key == "ltx.ingredients_ic_lora"
    assert "ic_lora" in DEFAULT_WORKFLOW_REGISTRY.get("ltx.ingredients_ic_lora").capabilities


def test_empty_dir_not_ready(data_dir: Path):
    from app.references.ic_lora_status import ingredients_status

    empty = data_dir / "empty_loras"
    empty.mkdir()
    status = ingredients_status(str(empty))
    assert status["status"] != "ready"
    assert status["issue_code"] == "ic_lora_model_missing"


def test_installed_file_verifies_ready(data_dir: Path):
    from app.references.ic_lora_status import ingredients_status
    from app.references.models import INGREDIENTS_FILENAME

    target = data_dir / "models" / "loras" / INGREDIENTS_FILENAME
    target.write_bytes(b"0" * (2 * 1024 * 1024))
    status = ingredients_status()
    assert status["status"] == "ready"
    assert status["filename"] == INGREDIENTS_FILENAME


def test_incompatible_filename_rejected(data_dir: Path):
    from app.references.ic_lora_status import ingredients_status

    wrong = data_dir / "models" / "loras" / "some-other-lora.safetensors"
    wrong.write_bytes(b"abc")
    status = ingredients_status(str(wrong))
    assert status["issue_code"] == "ic_lora_model_incompatible"


def test_gated_auth_status_without_token(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    from app.references import ic_lora_status

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("ADEPT_HF_TOKEN", raising=False)

    def fake_probe():
        return {
            "authorized": False,
            "gated": True,
            "http_status": 401,
            "issue_code": "ic_lora_authorization_required",
            "message": "Authorization Required. Accept the model terms on Hugging Face and connect your Hugging Face token.",
            "has_token": False,
        }

    monkeypatch.setattr(ic_lora_status, "probe_hf_authorization", fake_probe)
    status = ic_lora_status.ingredients_status()
    assert status["issue_code"] == "ic_lora_authorization_required"
    assert "Authorization Required" in (status.get("message") or "")


def test_strength_presets_resolve():
    from app.references.models import resolve_strength

    assert resolve_strength("subtle")[1] == 0.8
    assert resolve_strength("balanced")[1] == 1.4
    assert resolve_strength("strong")[1] == 1.8
    assert resolve_strength("balanced", 1.25)[1] == 1.25


def test_probe_prefers_ltxvideo_strategy():
    from app.workflows.ltx_ingredients_compiler import probe_ic_lora_nodes

    probe = probe_ic_lora_nodes(
        {
            "LTXICLoRALoaderModelOnly": {},
            "LTXAddVideoICLoRAGuide": {},
            "LoraLoaderModelOnly": {},
            "GetICLoRAParameters": {},
            "LTXVAddGuide": {},
        }
    )
    assert probe["strategy"] == "ltxvideo"
    assert probe["available"] is True


def test_missing_nodes_fail(data_dir: Path):
    from app.references.models import ReferenceError
    from app.workflows.ltx_ingredients_compiler import compile_ingredients_workflow

    with pytest.raises(ReferenceError) as exc:
        compile_ingredients_workflow(
            object_info={},
            checkpoint="ltx.safetensors",
            positive="walks",
            negative="",
            width=768,
            height=448,
            length=121,
            fps=24,
            seed=1,
            reference_image="studio/sheet.png",
            skip_model_check=True,
        )
    assert exc.value.code == "ic_lora_nodes_missing"


def test_compiler_inserts_lora_and_reference(data_dir: Path):
    from app.references.models import INGREDIENTS_FILENAME
    from app.workflows.ltx_ingredients_compiler import compile_ingredients_workflow

    (data_dir / "models" / "loras" / INGREDIENTS_FILENAME).write_bytes(b"0" * (2 * 1024 * 1024))
    object_info = {
        "LTXICLoRALoaderModelOnly": {},
        "LTXAddVideoICLoRAGuide": {},
        "LoadImage": {},
        "EmptyLTXVLatentVideo": {},
    }
    compiled = compile_ingredients_workflow(
        object_info=object_info,
        checkpoint="ltx-2.3.safetensors",
        positive="Barnes turns toward the corridor",
        negative="",
        width=768,
        height=448,
        length=121,
        fps=24,
        seed=7,
        reference_image="studio/ref_sheet.png",
        strength_preset="balanced",
    )
    classes = {n["class_type"]: n for n in compiled["workflow"].values()}
    assert "LTXICLoRALoaderModelOnly" in classes
    assert classes["LTXICLoRALoaderModelOnly"]["inputs"]["lora_name"] == INGREDIENTS_FILENAME
    assert "LoadImage" in classes
    assert classes["LoadImage"]["inputs"]["image"] == "studio/ref_sheet.png"
    assert "LTXAddVideoICLoRAGuide" in classes
    assert compiled["provenance"]["workflow_version"]
    assert "Reference sheet:" in compiled["prompt"]
    assert "Generated video:" in compiled["prompt"]
    dumped = json.dumps(compiled["sanitized_debug"])
    assert "HF_TOKEN" not in dumped
    assert "Bearer" not in dumped


def test_disabled_ingredients_uses_normal_path():
    from app.workflows.ltx_ingredients_compiler import wants_ingredients_ic_lora

    assert wants_ingredients_ic_lora({"reference_method": "none"}) is False
    assert wants_ingredients_ic_lora({"ingredients_ic_lora": False}) is False
    assert wants_ingredients_ic_lora({"reference_method": "ingredients_ic_lora"}) is True


def test_sheet_builder_retains_source_provenance(data_dir: Path):
    from app.references.sheet_builder import SheetPanel, build_reference_sheet

    a = _png(data_dir / "a.png", (400, 400), (255, 0, 0))
    b = _png(data_dir / "b.png", (400, 400), (0, 255, 0))
    c = _png(data_dir / "c.png", (600, 300), (0, 0, 255))
    out = data_dir / "sheet.png"
    built = build_reference_sheet(
        [
            SheetPanel(a, "character", "Barnes", "primary"),
            SheetPanel(b, "prop", "Door", "supporting"),
            SheetPanel(c, "environment", "Corridor", "primary"),
        ],
        layout="character_props_environment",
        out_path=out,
    )
    assert out.is_file() and out.stat().st_size > 0
    assert len(built["panels"]) >= 3
    roles = {p["role"] for p in built["panels"]}
    assert "character" in roles and "environment" in roles


def test_missing_source_fails_validation(data_dir: Path):
    from app.references.validation import validate_generation_ready

    result = validate_generation_ready(
        sheet={"composite_path": str(data_dir / "missing.png")},
        source_paths=[data_dir / "nope.png"],
        nodes_ok=True,
    )
    assert result["ok"] is False
    codes = {e["code"] for e in result["errors"]}
    assert "reference_sheet_missing" in codes or "reference_sheet_invalid" in codes


def test_continuity_preset_reuse(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import settings
    from app.references import store

    monkeypatch.setattr(settings, "data_dir", data_dir)
    pid = "proj-test"
    store.save_sheet(
        pid,
        {
            "id": "sheet-1",
            "version": 1,
            "layout": "auto",
            "source_ingredient_ids": ["ing-1"],
            "image_path": str(data_dir / "x.png"),
        },
    )
    preset = store.save_preset(
        pid,
        {
            "name": "Barnes + Corridor",
            "sheet_id": "sheet-1",
            "source_reference_ids": ["a1"],
            "strength_preset": "balanced",
            "strength_value": 1.4,
        },
    )
    got = store.get_preset(pid, preset["id"])
    assert got is not None
    assert got["name"] == "Barnes + Corridor"
    sheet = store.get_sheet(pid, "sheet-1")
    assert sheet is not None


def test_replace_ingredient_new_sheet_version(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import settings
    from app.references import store

    monkeypatch.setattr(settings, "data_dir", data_dir)
    pid = "proj-2"
    store.upsert_ingredient(pid, {"asset_id": "a1", "role": "character", "id": "ing-1"})
    store.save_sheet(pid, {"id": "sheet-old", "version": 1, "source_ingredient_ids": ["ing-1"]})
    store.upsert_ingredient(pid, {"asset_id": "a2", "role": "character", "id": "ing-1"})
    store.save_sheet(pid, {"id": "sheet-new", "version": 2, "source_ingredient_ids": ["ing-1"]})
    old = store.get_sheet(pid, "sheet-old")
    new = store.get_sheet(pid, "sheet-new")
    assert old["version"] == 1
    assert new["version"] == 2
    assert old["id"] != new["id"]


def test_setup_catalog_has_ic_lora_component():
    from app.setup.catalog import get_component

    component = get_component("ltx23_ic_lora_ingredients")
    assert component.verifier == "ic_lora_file"
    assert component.installer == "path_link"
    assert "ltx_checkpoint" in component.dependencies


def test_ic_lora_option_hidden_when_nodes_missing(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    from app.references import capabilities

    monkeypatch.setattr(capabilities, "fetch_object_info", lambda: {})
    caps = capabilities.reference_capabilities(object_info={})
    assert caps["ic_lora_option_enabled"] is False
    assert caps["identity_option_enabled"] is False
    assert caps["nodes_available"] is False
