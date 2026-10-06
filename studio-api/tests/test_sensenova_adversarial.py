"""Adversarial fail-closed checks for SenseNova. No hang, no fake success."""

from pathlib import Path

import pytest

from app.image_product.resolve import resolve_image_capability
from app.image_runtime.workflow_execute import build_leaf_graph
from app.workflows.sensenova_u15 import (
    build_sensenova_edit_workflow,
    inspect_weights,
    is_sensenova_family,
)


def test_edit_without_image_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="requires a source"):
        build_sensenova_edit_workflow(prompt="edit", image_name="")


def test_ers_without_atlas_refuses() -> None:
    cap = resolve_image_capability(
        {
            "purpose": "environment_reference_sheet",
            "modelFamilyPreference": "sensenova",
            "source": "local",
        }
    )
    assert cap["canExecute"] is False
    assert "authoritative source image" in str(cap.get("reason") or "").lower()


def test_character_sheet_cannot_steal_ers_graph() -> None:
    from app.image_product.compile import compile_image_request, refuse_character_sheet_ers_i2i

    msg = refuse_character_sheet_ers_i2i(
        {"purpose": "character_sheet", "forceWorkflowKey": "sensenova.ers"}
    )
    assert msg
    assert "sensenova" in msg.lower()
    assert "qwen2512" not in msg.lower()
    with pytest.raises(RuntimeError, match="SenseNova U1.5"):
        compile_image_request(
            "lab",
            {"purpose": "character_sheet", "forceWorkflowKey": "sensenova.ers", "prompt": "x"},
        )


def test_wrong_family_is_not_sensenova() -> None:
    assert is_sensenova_family("flux") is False
    assert is_sensenova_family("qwen2512.ref") is False


def test_live_d_drive_partial_weights_are_not_ready() -> None:
    probe = inspect_weights()
    if not Path(str(probe.get("root") or "")).is_dir():
        pytest.skip("SenseNova D: path is not present on this machine")
    if int(probe.get("completeShards") or 0) < int(probe.get("expectedShards") or 13):
        assert probe["runtimeReady"] is False
        assert probe["installed"] is False


def test_twelve_complete_shards_without_thirteenth_are_not_ready(tmp_path: Path) -> None:
    from app.workflows.sensenova_u15 import EXPECTED_WEIGHT_FILES

    for name, min_bytes in EXPECTED_WEIGHT_FILES.items():
        if name == "model-00013-of-00013.safetensors":
            continue
        (tmp_path / name).write_bytes(b"x" * min_bytes)
    probe = inspect_weights(tmp_path)
    assert probe["runtimeReady"] is False
    assert probe["completeShards"] == 12
    assert any("model-00013-of-00013.safetensors" in item for item in probe["missing"])


def test_partial_shards_are_not_runtime_ready(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00001-of-00013.safetensors").write_bytes(b"partial")
    probe = inspect_weights(tmp_path)
    assert probe["installed"] is False
    assert probe["runtimeReady"] is False
    assert probe["completeShards"] == 0
    assert any("model-00013-of-00013.safetensors" in item for item in probe["missing"])


def test_missing_builder_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    with pytest.raises(RuntimeError, match="No local Comfy builder"):
        build_leaf_graph(
            {"workflowKey": "sensenova.not_a_real_key"},
            settings=settings,
            prompt="x",
        )
