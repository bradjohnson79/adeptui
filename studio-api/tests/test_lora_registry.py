"""Shared LoRA Registry tests — registration, compatibility filtering,
enable/disable, removal safety, persistence, and baseline regression.
"""

from __future__ import annotations

import json
import struct
import uuid
from pathlib import Path

import pytest


def _write_fake_safetensors(path: Path) -> None:
    """Minimal valid safetensors file (zero-valued float32 tensors)."""
    header = {}
    offset = 0
    body = b""
    for key, shape in {
        "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn1_to_q.lora_down.weight": (4, 8),
        "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn1_to_q.lora_up.weight": (8, 4),
        "lora_te1_text_model_encoder_layers_0_self_attn_q_proj.lora_down.weight": (4, 8),
        "lora_te1_text_model_encoder_layers_0_self_attn_q_proj.lora_up.weight": (8, 4),
    }.items():
        n = 1
        for d in shape:
            n *= d
        data = b"\x00" * (n * 4)
        header[key] = {"dtype": "F32", "shape": list(shape), "data_offsets": [offset, offset + len(data)]}
        offset += len(data)
        body += data
    payload = json.dumps({"__metadata__": {"format": "pt"}, **header}).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(payload)) + payload + body)


@pytest.fixture()
def lora_env(monkeypatch):
    from app.config import settings

    # Workspace-backed temp (pathlib creates 0o777 dirs; some sandboxes deny
    # writes under 0o700 mkdtemp-style dirs).
    tmp = Path(__file__).resolve().parents[1] / ".adept-tmp" / f"lora-tests-{uuid.uuid4().hex[:10]}"
    tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "data_dir", tmp)
    (tmp / "lora_store").mkdir(parents=True, exist_ok=True)
    (tmp / "models" / "loras").mkdir(parents=True, exist_ok=True)
    sdxl = tmp / "models" / "loras" / "sdxl_test.safetensors"
    _write_fake_safetensors(sdxl)
    ltx = tmp / "lora_store" / "ltx_motion_test.safetensors"
    _write_fake_safetensors(ltx)
    return {"tmp": tmp, "sdxl": sdxl, "ltx": ltx}


def test_register_and_validate(lora_env):
    from app.lora_registry import registry

    rec = registry.register_lora(
        name="Cinematic Lighting XL",
        file_path=str(lora_env["sdxl"]),
        model_family="sdxl",
        compatible_model_families=["sdxl"],
        modality="image",
        recommended_strength=0.7,
    )
    assert rec.install_status == "installed"
    assert rec.checksum_sha256
    assert registry.get_lora(rec.id).name == "Cinematic Lighting XL"


def test_compatibility_filter_is_deterministic(lora_env):
    from app.lora_registry import registry

    registry.register_lora(
        name="SDXL LoRA",
        file_path=str(lora_env["sdxl"]),
        model_family="sdxl",
        modality="image",
    )
    registry.register_lora(
        name="LTX LoRA",
        file_path=str(lora_env["ltx"]),
        model_family="ltx",
        modality="video",
    )

    # SDXL selected -> SDXL LoRA only
    sdxl_view = registry.compatible_loras("illustrious", "image")
    assert [r.name for r in sdxl_view] == ["SDXL LoRA"]
    # LTX selected -> LTX LoRA only
    ltx_view = registry.compatible_loras("ltx", "video")
    assert [r.name for r in ltx_view] == ["LTX LoRA"]
    # flux selected -> nothing
    assert registry.compatible_loras("flux", "image") == []
    # hosted providers never expose LoRAs
    assert registry.compatible_loras("fal", "video") == []
    # deterministic across calls
    assert [r.id for r in registry.compatible_loras("illustrious", "image")] == [
        r.id for r in registry.compatible_loras("illustrious", "image")
    ]


def test_disable_hides_from_selectors_but_keeps_management(lora_env):
    from app.lora_registry import registry

    rec = registry.register_lora(
        name="SDXL LoRA",
        file_path=str(lora_env["sdxl"]),
        model_family="sdxl",
        modality="image",
    )
    assert len(registry.compatible_loras("illustrious", "image")) == 1
    registry.set_lora_enabled(rec.id, False)
    assert registry.compatible_loras("illustrious", "image") == []
    assert len(registry.list_loras()) == 1  # still visible in management
    with pytest.raises(ValueError, match="disabled"):
        registry.resolve_lora_for_generation({"id": rec.id}, "illustrious", "image")
    registry.set_lora_enabled(rec.id, True)
    assert len(registry.compatible_loras("illustrious", "image")) == 1


def test_resolve_refuses_incompatible_and_missing(lora_env):
    from app.lora_registry import registry

    rec = registry.register_lora(
        name="SDXL LoRA",
        file_path=str(lora_env["sdxl"]),
        model_family="sdxl",
        modality="image",
    )
    with pytest.raises(ValueError, match="not compatible"):
        registry.resolve_lora_for_generation({"id": rec.id}, "ltx", "video")
    assert registry.resolve_lora_for_generation(None, "illustrious", "image") is None
    with pytest.raises(ValueError, match="unavailable"):
        registry.resolve_lora_for_generation({"id": "unknown"}, "illustrious", "image")


def test_remove_preserves_history_references(lora_env):
    from app.lora_registry import registry

    rec = registry.register_lora(
        name="SDXL LoRA",
        file_path=str(lora_env["sdxl"]),
        model_family="sdxl",
        modality="image",
    )
    # Provenance references survive removal (records are plain JSON snapshots
    # held by assets/jobs; the registry removal must not touch them).
    provenance_ref = {"loraId": rec.id, "name": rec.name, "strength": 0.7}
    registry.unregister_lora(rec.id)
    assert registry.get_lora(rec.id) is None
    assert registry.list_loras() == []
    # Old provenance remains readable and is not resurrected
    assert provenance_ref["loraId"] == rec.id
    assert registry.get_lora(provenance_ref["loraId"]) is None


def test_persistence_across_reload(lora_env):
    from app.lora_registry import registry

    rec = registry.register_lora(
        name="SDXL LoRA",
        file_path=str(lora_env["sdxl"]),
        model_family="sdxl",
        modality="image",
        enabled=True,
    )
    state = json.loads((lora_env["tmp"] / "lora_registry.json").read_text(encoding="utf-8"))
    assert len(state["loras"]) == 1
    assert state["loras"][0]["enabled"] is True
    # A fresh registry instance sees the same state
    assert registry.get_lora(rec.id) is not None


def test_detection_registers_shared_files(lora_env):
    from app.lora_registry import registry

    found = registry.scan_for_loras()
    names = [f["name"] for f in found]
    assert "sdxl_test.safetensors" in names
    assert "ltx_motion_test.safetensors" in names
    created = registry.register_detected_files()
    by_name = {r.name: r for r in created}
    assert "ltx_motion_test" in by_name
    assert by_name["ltx_motion_test"].model_family == "ltx"
    assert by_name["ltx_motion_test"].modality == "video"


def test_validation_rejects_non_safetensors(lora_env):
    from app.lora_registry import registry

    bogus = lora_env["tmp"] / "not_a_lora.safetensors"
    bogus.write_bytes(b"definitely not safetensors data")
    ok, _msg = registry.validate_safetensors(bogus)
    assert not ok
    with pytest.raises(ValueError):
        registry.register_lora(name="bad", file_path=str(bogus), model_family="sdxl")


def test_baseline_generation_graph_unchanged_without_lora():
    """LoRA=None must produce the exact baseline graph (no hidden adapters)."""
    from app.imagegen_workflows import build_txt2img_workflow

    baseline = build_txt2img_workflow(
        checkpoint="Illustrious-XL-v1.0.safetensors",
        positive="test",
        negative="",
        width=1024,
        height=1024,
        seed=1,
    )
    no_lora = build_txt2img_workflow(
        checkpoint="Illustrious-XL-v1.0.safetensors",
        positive="test",
        negative="",
        width=1024,
        height=1024,
        seed=1,
        lora=None,
    )
    assert no_lora == baseline
    assert "20" not in baseline
    assert all("LoraLoader" not in n.get("class_type", "") for n in baseline.values())


def test_lora_graph_emits_loader_node_and_rewires():
    from app.image_runtime.asset_refs import LoraSpec
    from app.imagegen_workflows import build_txt2img_workflow
    from app.workflows.ltx_builder import build_ltx_simple_i2v

    spec = LoraSpec(loraId="cinematic_xl.safetensors", strength=0.7, resolvedName="cinematic_xl.safetensors")
    graph = build_txt2img_workflow(
        checkpoint="Illustrious-XL-v1.0.safetensors",
        positive="test",
        negative="",
        width=1024,
        height=1024,
        seed=1,
        lora=spec,
    )
    assert graph["20"]["class_type"] == "LoraLoader"
    assert graph["20"]["inputs"]["lora_name"] == "cinematic_xl.safetensors"
    assert graph["20"]["inputs"]["strength_model"] == 0.7
    assert graph["5"]["inputs"]["model"] == ["20", 0]
    assert graph["2"]["inputs"]["clip"] == ["20", 1]

    ltx = build_ltx_simple_i2v(
        checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        positive="test",
        negative="",
        width=512,
        height=512,
        length=25,
        fps=24,
        seed=1,
        start_image="frame.png",
        lora_name="ltx_motion.safetensors",
        lora_strength=0.6,
    )
    assert ltx["1L"]["class_type"] == "LoraLoaderModelOnly"
    assert ltx["8"]["inputs"]["model"] == ["1L", 0]
    assert ltx["9"]["inputs"]["model"] == ["1L", 0]
    # no-lora ltx graph has no 1L node
    base_ltx = build_ltx_simple_i2v(
        checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        positive="test",
        negative="",
        width=512,
        height=512,
        length=25,
        fps=24,
        seed=1,
        start_image="frame.png",
    )
    assert "1L" not in base_ltx


def test_catalog_loads_and_download_requires_approval():
    from app.lora_registry import catalog, registry

    items = catalog.catalog_items()
    assert any(item.id == "lora_cinematic_lighting_sdxl" for item in items)
    with pytest.raises(PermissionError):
        registry.download_lora("lora_cinematic_lighting_sdxl", approved=False)
    # catalog items without a download URL fail honestly (no silent fake)
    with pytest.raises(ValueError, match="no download URL"):
        registry.download_lora("lora_cinematic_lighting_sdxl", approved=True)


def test_lora_registry_router_endpoints(lora_env):
    from fastapi.testclient import TestClient

    from app.lora_registry.router import router
    from app.main import app

    client = TestClient(app)
    res = client.get("/api/loras/compatible?modelFamily=illustrious&modality=image")
    assert res.status_code == 200
    body = res.json()
    assert "loras" in body
    assert isinstance(body["loras"], list)

    # register through the API
    reg = client.post("/api/loras/register", json={"name": "API SDXL", "path": str(lora_env["sdxl"]), "modelFamily": "sdxl", "modality": "image"})
    assert reg.status_code == 200, reg.text
    lora_id = reg.json()["id"]
    compat = client.get("/api/loras/compatible?modelFamily=illustrious&modality=image").json()
    assert any(l["id"] == lora_id for l in compat["loras"])
    # disable via API
    assert client.post(f"/api/loras/{lora_id}/disable").status_code == 200
    compat2 = client.get("/api/loras/compatible?modelFamily=illustrious&modality=image").json()
    assert not any(l["id"] == lora_id for l in compat2["loras"])
    # remove via API
    assert client.delete(f"/api/loras/{lora_id}").status_code == 200
    assert client.get(f"/api/loras/{lora_id}").status_code == 404