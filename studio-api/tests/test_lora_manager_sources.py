"""LoRA source resolver, validation, discovery, and loader chain."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import uuid

import pytest

from app.lora_registry.sources import LoraSourceFile, LoraSourceResolution, parse_lora_url, resolve_lora_source


@pytest.fixture()
def lora_env(monkeypatch):
    from app.config import settings

    tmp = Path(__file__).resolve().parents[1] / ".adept-tmp" / f"lora-src-{uuid.uuid4().hex[:10]}"
    tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "data_dir", tmp)
    monkeypatch.setattr(settings, "comfy_models_dir", str(tmp / "comfy_models"), raising=False)
    monkeypatch.setattr(settings, "krea2_model_root", str(tmp / "krea"), raising=False)
    (tmp / "lora_store").mkdir(parents=True, exist_ok=True)
    (tmp / "models" / "loras").mkdir(parents=True, exist_ok=True)
    sdxl = tmp / "models" / "loras" / "sdxl_test.safetensors"
    _write_fake_safetensors(sdxl)
    return {"tmp": tmp, "sdxl": sdxl}


def _write_fake_safetensors(path: Path, metadata: dict | None = None) -> None:
    header = {"__metadata__": metadata or {"format": "pt"}}
    offset = 0
    body = b""
    shape = (4, 8)
    n = 32
    data = b"\x00" * (n * 4)
    header["lora_unet.lora_down.weight"] = {"dtype": "F32", "shape": list(shape), "data_offsets": [offset, offset + len(data)]}
    body += data
    payload = json.dumps(header).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(payload)) + payload + body)


def test_parse_huggingface_and_civitai_urls():
    hf = parse_lora_url("https://huggingface.co/org/repo/blob/main/style.safetensors")
    assert hf["provider"] == "huggingface"
    assert hf["repo_id"] == "org/repo"
    assert hf["file_path"] == "style.safetensors"
    page = parse_lora_url("https://civitai.com/models/12345/anime-line?modelVersionId=99")
    assert page["provider"] == "civitai"
    assert page["model_id"] == "12345"
    assert page["version_id"] == "99"


def test_civitai_resolve_uses_api_metadata():
    payload = {
        "id": 12345,
        "name": "Anime Linework",
        "type": "LORA",
        "creator": {"username": "ada"},
        "modelVersions": [
            {
                "id": 99,
                "baseModel": "ZImageTurbo",
                "trainedWords": ["linework"],
                "files": [
                    {
                        "name": "line.safetensors",
                        "sizeKB": 12,
                        "hashes": {"SHA256": "abc"},
                        "metadata": {"format": "SafeTensor"},
                    }
                ],
            }
        ],
    }

    def http_get(url: str):
        assert url.endswith("/models/12345")
        return 200, payload

    resolved = resolve_lora_source("https://civitai.com/models/12345", http_get=http_get)
    assert resolved.provider == "civitai"
    assert resolved.family == "zimage"
    assert resolved.trigger_words == ["linework"]
    assert resolved.selected is not None
    assert resolved.selected.sha256 == "abc"
    assert resolved.author == "ada"


def test_huggingface_resolve_selects_named_file():
    class Sibling:
        def __init__(self, name):
            self.rfilename = name
            self.lfs = {"sha256": "deadbeef", "size": 32}

    class Info:
        id = "org/repo"
        sha = "rev1"
        siblings = [Sibling("other.bin"), Sibling("lora/style.safetensors")]
        card_data = {"base_model": "flux1-dev", "license": "apache-2.0"}

    resolved = resolve_lora_source(
        "https://huggingface.co/org/repo/resolve/main/lora/style.safetensors",
        hf_info=lambda repo, revision, token: Info(),
    )
    assert resolved.family == "flux"
    assert resolved.selected is not None
    assert resolved.selected.filename.endswith("style.safetensors")
    assert resolved.license == "apache-2.0"


def test_rejects_archive_and_executable(lora_env):
    from app.lora_registry.metadata import classify_lora_file

    archive = lora_env["tmp"] / "packed.safetensors"
    archive.write_bytes(b"PK\x03\x04" + b"\x00" * 32)
    exe = lora_env["tmp"] / "run.safetensors"
    exe.write_bytes(b"MZ" + b"\x00" * 32)
    assert classify_lora_file(archive)["ok"] is False
    assert classify_lora_file(exe)["ok"] is False


def test_duplicate_checksum_does_not_copy(lora_env):
    from app.lora_registry import registry

    first = registry.import_local_file(lora_env["sdxl"], original_name="sdxl_test.safetensors")
    assert first["status"] == "installed"
    again = registry.import_local_file(lora_env["sdxl"], original_name="sdxl_test.safetensors")
    assert again["status"] == "already_installed"
    assert again["lora"]["id"] == first["lora"]["id"]
    assert len(registry.list_loras()) == 1


def test_scan_registers_external_file_in_place(lora_env):
    from app.lora_registry import registry

    created = registry.register_detected_files()
    sdxl = next(rec for rec in created if rec.file_path.endswith("sdxl_test.safetensors"))
    assert sdxl.owned_by == "external"
    assert Path(sdxl.file_path) == lora_env["sdxl"].resolve()
    assert lora_env["sdxl"].is_file()


def test_external_remove_keeps_file_and_owned_delete_requires_store(lora_env):
    from app.lora_registry import registry

    external = registry.register_lora(name="External", file_path=str(lora_env["sdxl"]), model_family="sdxl")
    registry.unregister_lora(external.id, delete_file=True)
    assert lora_env["sdxl"].is_file()

    copied = lora_env["tmp"] / "lora_store" / "owned.safetensors"
    _write_fake_safetensors(copied, {"modelspec.base_model": "flux"})
    owned = registry.import_local_file(copied, original_name="owned.safetensors")
    assert owned["lora"]["owned_by"] == "adept"
    stored = Path(owned["lora"]["file_path"])
    registry.unregister_lora(owned["lora"]["id"], delete_file=False)
    assert stored.is_file()
    owned_again = registry.import_local_file(copied, original_name="owned.safetensors")
    registry.unregister_lora(owned_again["lora"]["id"], delete_file=True)
    assert not Path(owned_again["lora"]["file_path"]).exists()


def test_unknown_family_is_not_injected(lora_env):
    from app.lora_registry import registry

    rec = registry.register_lora(name="Mystery", file_path=str(lora_env["sdxl"]), model_family="unassigned")
    assert rec.compatibility == "unknown"
    assert registry.compatible_loras("zimage", "image") == []
    try:
        registry.resolve_lora_for_generation({"id": rec.id}, "zimage", "image")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_header_family_is_known(lora_env):
    from app.lora_registry import registry

    path = lora_env["tmp"] / "models" / "loras" / "flux_style.safetensors"
    _write_fake_safetensors(path, {"modelspec.base_model": "flux1-dev", "modelspec.trigger_phrase": "glow"})
    rec = registry.register_lora(name="", file_path=str(path))
    assert rec.model_family == "flux"
    assert rec.compatibility == "known"
    assert rec.trigger_words == ["glow"]
    assert [item.id for item in registry.compatible_loras("flux", "image")] == [rec.id]
    assert registry.compatible_loras("sdxl", "image") == []


def test_loader_chain_passes_two_loras():
    from app.image_runtime.asset_refs import LoraSpec, chain_lora_loaders
    from app.imagegen_workflows import build_txt2img_workflow

    graph = build_txt2img_workflow(
        checkpoint="model.safetensors",
        positive="test",
        negative="",
        width=64,
        height=64,
        seed=1,
        lora=LoraSpec(loraId="one.safetensors", strength=0.7, resolvedName="one.safetensors"),
    )
    chained = chain_lora_loaders(
        graph,
        [LoraSpec(loraId="two.safetensors", strength=0.4, resolvedName="two.safetensors")],
    )
    loaders = [node for node in chained.values() if isinstance(node, dict) and node.get("class_type") == "LoraLoader"]
    assert len(loaders) == 2
    names = {node["inputs"]["lora_name"] for node in loaders}
    assert names == {"one.safetensors", "two.safetensors"}
    second = next(node for node in loaders if node["inputs"]["lora_name"] == "two.safetensors")
    assert chained["5"]["inputs"]["model"] == [next(node_id for node_id, node in chained.items() if node is second), 0]
    assert second["inputs"]["strength_model"] == 0.4


def test_install_url_skips_second_download(lora_env, monkeypatch):
    from app.lora_registry import registry

    calls = {"download": 0}

    def fake_resolve(url: str):
        return LoraSourceResolution(
            provider="huggingface",
            display_name="Style",
            source_url=url,
            source_model_id="org/style",
            source_version="rev1",
            family="sdxl",
            files=[LoraSourceFile(filename="style.safetensors", sha256="", repo_id="org/style", revision="rev1")],
            selected=LoraSourceFile(filename="style.safetensors", sha256="", repo_id="org/style", revision="rev1"),
            message="LoRA found.",
        )

    def fake_download(selected, dest: Path, provider: str):
        calls["download"] += 1
        _write_fake_safetensors(dest, {"modelspec.base_model": "sdxl"})

    monkeypatch.setattr("app.lora_registry.sources.resolve_lora_source", fake_resolve)
    monkeypatch.setattr("app.lora_registry.sources.download_source_file", fake_download)
    first = registry.install_from_url("https://huggingface.co/org/style", filename="style.safetensors")
    assert first["status"] == "installed"
    second = registry.install_from_url("https://huggingface.co/org/style", filename="style.safetensors")
    assert second["status"] == "already_installed"
    assert calls["download"] == 1


def test_first_run_baseline_ignores_loras():
    from app.setup.first_run import baseline_component_ids

    assert not any("lora" in item.lower() for item in baseline_component_ids())
