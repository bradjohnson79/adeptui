"""Model Storage — register path-only, classify, drive unavailable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.model_storage import classify, store, validate


@pytest.fixture()
def storage_tmp(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(store.settings, "data_dir", data)
    return data


def test_register_folder_path_only_no_copy(storage_tmp, tmp_path):
    model_dir = tmp_path / "my-gguf"
    model_dir.mkdir()
    (model_dir / "tiny.gguf").write_bytes(b"GGUF")
    entry = store.register_folder(path=str(model_dir), category="llm", import_into_library=False)
    assert entry["imported"] is False
    assert entry["importDestination"] is None
    assert Path(entry["path"]).exists()
    assert (model_dir / "tiny.gguf").exists()
    assert entry["runtimeType"] == "gguf"
    assert entry["validationStatus"] in ("Ready", "Ready With Limitations", "Runtime Missing")


def test_classify_ollama_store_uses_manifests_not_blobs(tmp_path):
    root = tmp_path / "ollama"
    (root / "blobs").mkdir(parents=True)
    man = root / "manifests" / "registry.ollama.ai" / "library" / "gemma4" / "31b"
    man.parent.mkdir(parents=True)
    man.write_text("{}", encoding="utf-8")
    (root / "blobs" / "sha256-deadbeef").write_bytes(b"x")
    result = classify.classify_folder(str(root))
    assert result["runtimeType"] == "ollama"
    names = [m["name"] for m in result["models"]]
    assert any("gemma4" in n for n in names)
    assert not any("sha256" in n for n in names)


def test_drive_unavailable_keeps_honest_status(storage_tmp):
    missing = storage_tmp / "missing-drive" / "models"
    result = validate.validate_registration(str(missing), runtime_type="gguf")
    assert result["status"] == "Drive Unavailable"
    assert result.get("silentSwitchForbidden") is True
    assert result.get("autoRedownloadForbidden") is True


def test_set_root_persists(storage_tmp):
    state = store.set_root("llm", r"E:\Models\LLM")
    assert state["roots"]["llm"] == r"E:\Models\LLM"
    reloaded = store.load_model_storage()
    assert reloaded["roots"]["llm"] == r"E:\Models\LLM"
