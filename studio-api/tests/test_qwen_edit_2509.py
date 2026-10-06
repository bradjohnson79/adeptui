from __future__ import annotations

from app.character_identity.crs_view_generation import resolve_crs_view_generation_workflow
import pytest

from app.character_identity.visual_sheet import (
    QWEN_EDIT_2509_CRS_KEY,
    QWEN_EDIT_2509_FAMILY,
    QWEN_EDIT_2509_NEEDS_CROP,
    QWEN_EDIT_2509_WORKFLOW_KEY,
    _build_stage1_route,
    _coerce_single_crs_sources,
    _family_supports_references,
    _txt2img_workflow_key,
    resolve_character_creator_generator_sources,
)
from app.image_runtime.certified_registry import get_workflow, reload_registry
from app.image_runtime.contract import _normalize_family, resolve_image_workflow
from app.imagegen_workflows import build_local_generator_models
from app.workflows.qwen_image_edit_2509 import (
    build_qwen_edit_2509_i2i_workflow,
    compose_discover_reason,
    discover_qwen_edit_2509,
    graph_contract,
    inspect_weights,
    probe_comfy_runtime,
    unet_weight_dtype,
)


def test_2509_not_classified_t2i_only():
    reload_registry()
    disc = discover_qwen_edit_2509()
    assert disc["t2iOnly"] is False
    assert disc["classification"] == "i2i_edit"
    assert disc["certified"] is False
    assert _normalize_family("qwen_edit_2509", "qwen_edit_2509") == "qwen_edit_2509"
    assert _normalize_family("qwen-image-edit-2509", None) == "qwen_edit_2509"
    contract = resolve_image_workflow("image.generate", engine="qwen_edit_2509", allow_draft=True)
    assert contract.workflow_key == "qwen_edit_2509.edit"
    assert "txt2img" not in contract.workflow_key
    edit = resolve_image_workflow("image.edit", engine="qwen_edit_2509", allow_draft=True)
    assert edit.workflow_key == "qwen_edit_2509.edit"


def test_2509_registry_is_draft_not_certified():
    reload_registry()
    wf = get_workflow("qwen_edit_2509.edit")
    crs = get_workflow("qwen_edit_2509.crs_single_view")
    assert wf is not None and crs is not None
    assert wf.status == "Draft"
    assert crs.status == "Draft"
    assert wf.certification_record_id in {None, ""}
    assert "QwenImageEditApi" not in (wf.required_nodes or ())
    assert "TextEncodeQwenImageEditPlus" in wf.required_nodes


def test_crs_single_view_uses_edit_workflow():
    assert _txt2img_workflow_key(QWEN_EDIT_2509_FAMILY) == QWEN_EDIT_2509_WORKFLOW_KEY
    assert _family_supports_references(QWEN_EDIT_2509_FAMILY) is True
    route = _build_stage1_route(
        family=QWEN_EDIT_2509_FAMILY,
        reference_asset_id="asset-identity-1",
        provider_kind="local",
    )
    assert route["workflowKey"] == QWEN_EDIT_2509_CRS_KEY
    assert route["workflowKey"] in {"qwen_edit_2509.edit", "qwen_edit_2509.crs_single_view"}
    assert route["workflowKey"] != "qwen2512.txt2img"
    assert route["source_asset_id"] == "asset-identity-1"
    assert route["conditioningMode"] == "REFERENCE_CONDITIONED"
    resolved = resolve_crs_view_generation_workflow(requested_family="qwen_edit_2509")
    assert resolved["workflowKey"] == "qwen_edit_2509.crs_single_view"
    assert resolved["mode"] == "i2i_edit"
    assert resolved["t2iOnly"] is False
    auto = resolve_crs_view_generation_workflow()
    assert auto["family"] != "qwen_edit_2509" or auto.get("explicit") is False


def test_identity_role_and_not_whole_crs_canvas():
    graph = build_qwen_edit_2509_i2i_workflow(
        image_name="identity_crop.png",
        positive="same person, three-quarter view",
    )
    contract = graph_contract(graph)
    assert contract["saveImageCount"] == 1
    assert contract["usesHostedEditApi"] is False
    assert contract["usesTextEncodeQwenImageEditPlus"] is True
    assert contract["usesLayeredLatent"] is False
    assert contract["latentFromEmpty"] is True
    assert contract["t2iOnly"] is False
    sampler = next(n for n in graph.values() if n["class_type"] == "KSampler")
    unet = next(n for n in graph.values() if n["class_type"] == "UNETLoader")
    assert sampler["inputs"]["steps"] == 8
    assert sampler["inputs"]["cfg"] == 1.0
    assert unet["inputs"]["weight_dtype"] == "fp8_e4m3fn"
    load = next(n for n in graph.values() if n["class_type"] == "LoadImage")
    plus = next(
        n for n in graph.values()
        if n["class_type"] == "TextEncodeQwenImageEditPlus" and "side" not in str(n)
    )
    plus_nodes = [n for n in graph.values() if n["class_type"] == "TextEncodeQwenImageEditPlus"]
    assert plus_nodes[0]["inputs"]["image1"][0]
    assert load["inputs"]["image"] == "identity_crop.png"
    assert any(n["class_type"] == "EmptyLatentImage" for n in graph.values())
    types = [n["class_type"] for n in graph.values()]
    assert types.count("SaveImage") == 1
    assert "QwenImageEditApi" not in types
    assert "DiffusersLoader" not in types
    assert "UNETLoader" in types
    assert "TextEncodeQwenImageEditPlus" in types


def test_explicit_override_and_2509_first_in_character_order():
    roster = build_local_generator_models(surface="character")
    ids = [row["id"] for row in roster if row["id"] != "auto"]
    disc = discover_qwen_edit_2509()
    if disc.get("runtimeReady"):
        assert ids[0] == "qwen_edit_2509"
    else:
        assert "qwen_edit_2509" not in ids
    assert "sd15" not in ids
    scene = build_local_generator_models(surface="default")
    scene_ids = [row["id"] for row in scene]
    assert scene_ids[0] == "auto"
    qwen2512 = resolve_image_workflow("image.generate", engine="qwen2512", allow_draft=True)
    assert qwen2512.workflow_key == "qwen2512.txt2img"
    explicit = resolve_crs_view_generation_workflow(requested_family="qwen2512")
    assert explicit["workflowKey"] == "qwen2512.txt2img"
    explicit_2509 = resolve_crs_view_generation_workflow(requested_family="qwen_edit_2509")
    assert explicit_2509["workflowKey"] == "qwen_edit_2509.crs_single_view"


def test_installed_vs_runtime_ready_separate():
    weights = inspect_weights()
    disc = discover_qwen_edit_2509()
    assert disc["statusHint"] == "Draft"
    assert disc["certified"] is False
    if weights.get("installed"):
        assert disc["installed"] is True
        assert disc["runtimeReady"] in {True, False}
        if not disc["runtimeReady"]:
            assert disc["recoverRequired"] is True
    row = next((r for r in build_local_generator_models(surface="character") if r["id"] == "qwen_edit_2509"), None)
    if disc.get("runtimeReady"):
        assert row is not None
        assert row["status"] == "Draft"
        assert row["executable"] is True
        assert row["installed"] is True
    else:
        assert row is None

def test_loader_uses_comfy_basenames_not_diffusers():
    graph = build_qwen_edit_2509_i2i_workflow(
        image_name="identity_crop.png",
        positive="same person, side view",
    )
    assert graph_contract(graph)["usesDiffusersLoader"] is False
    assert graph["1"]["class_type"] == "UNETLoader"
    assert graph["2"]["class_type"] == "CLIPLoader"
    assert graph["3"]["class_type"] == "VAELoader"
    dumped = str(graph)
    assert "D:" not in dumped and "d:" not in dumped
    assert "01_Models" not in dumped
    assert "DiffusersLoader" not in dumped
    forced = build_qwen_edit_2509_i2i_workflow(
        image_name="identity_crop.png",
        positive="same person, side view",
        model_path=r"D:\01_Models\Qwen\Qwen-Image-Edit-2509",
        unet_name=r"D:\01_Models\Qwen\Qwen-Image-Edit-2509\transformer\x.safetensors",
    )
    assert forced["1"]["inputs"]["unet_name"] == "x.safetensors"
    assert "D:" not in forced["1"]["inputs"]["unet_name"]
    assert unet_weight_dtype("qwen_image_edit_2509_fp8_e4m3fn.safetensors") == "fp8_e4m3fn"
    assert unet_weight_dtype("qwen_image_edit_2509_bf16.safetensors") == "default"


def test_2509_without_identity_crop_fails_closed():
    with pytest.raises(ValueError, match="single-character identity"):
        _build_stage1_route(
            family=QWEN_EDIT_2509_FAMILY,
            reference_asset_id=None,
            provider_kind="local",
        )
    assert QWEN_EDIT_2509_NEEDS_CROP


def test_coerce_and_saved_prefs_honor_2509():
    sources = _coerce_single_crs_sources(
        {"local": [{"family": "qwen_edit_2509", "enabled": True, "batchCount": 1}]}
    )
    assert sources["local"][0]["family"] == "qwen_edit_2509"
    from_pack = resolve_character_creator_generator_sources(
        pack={"generatorPreferences": sources}
    )
    assert from_pack["local"][0]["family"] == "qwen_edit_2509"
    auto = resolve_character_creator_generator_sources(args={}, pack={})
    assert auto["local"][0]["family"] == "auto"


def test_2509_capability_roles_not_t2i():
    from app.image_core.capability import qwen_edit_2509_crs_capability

    snap = qwen_edit_2509_crs_capability()
    assert snap["provider"] == "qwen_edit_2509"
    assert snap["t2iOnly"] is False
    assert snap["autoPreferred"] is False
    assert "crs_single_view" in snap["roles"]
    assert "identity_preserving_edit" in snap["roles"]
    assert snap["certified"] is False


def test_readiness_uses_discover_when_setup_catalog_lacks_component(monkeypatch):
    from app.workflows import readiness as wr

    monkeypatch.setattr(
        "app.workflows.qwen_image_edit_2509.discover_qwen_edit_2509",
        lambda: {"runtimeReady": True, "installed": True, "reason": "Runtime Ready"},
    )
    monkeypatch.setattr(
        "app.setup.catalog.get_component",
        lambda _cid: (_ for _ in ()).throw(KeyError("Unknown component")),
    )
    states = wr._component_states(("qwen_image_edit_2509_models",))
    assert states[0]["present"] is True
    report = wr.workflow_readiness(
        "qwen_edit_2509.edit",
        node_types=set(),
        model_states={"qwen_image_edit_2509_models": True},
    )
    assert report["status"] == "ready"


def test_discover_reason_is_the_actual_failed_predicate():
    assert compose_discover_reason(
        installed=True,
        runtime_ready=False,
        runtime={"reason": "Comfy object_info unavailable: Connection refused"},
    ) == "Comfy object_info unavailable: Connection refused"
    assert "pending Comfy single-file UNET" not in compose_discover_reason(
        installed=True,
        runtime_ready=False,
        runtime={"reason": "Comfy is missing required nodes: UNETLoader"},
    )
    assert compose_discover_reason(installed=True, runtime_ready=True, runtime={}) == "Runtime Ready"
    assert compose_discover_reason(installed=False, runtime_ready=False, runtime={}) == (
        "Qwen Image Edit 2509 weights not found"
    )
    down = discover_qwen_edit_2509(object_info={})
    assert down["runtimeReady"] is False
    assert "pending Comfy single-file UNET" not in str(down["reason"])
    assert "UNETLoader" in str(down["reason"]) or "missing required nodes" in str(down["reason"]).lower()
    files_missing = probe_comfy_runtime(
        {
            "UNETLoader": {"input": {"required": {"unet_name": [["other.safetensors"]]}}},
            "CLIPLoader": {"input": {"required": {"clip_name": [["other.safetensors"]]}}},
            "VAELoader": {"input": {"required": {"vae_name": [["other.safetensors"]]}}},
            "LoadImage": {},
            "TextEncodeQwenImageEditPlus": {},
            "EmptyLatentImage": {},
            "KSampler": {},
            "VAEDecode": {},
            "SaveImage": {},
            "ModelSamplingAuraFlow": {},
        }
    )
    assert files_missing["runtimeReady"] is False
    assert "not visible to Comfy" in files_missing["reason"]
    assert "unet=" in files_missing["reason"]


def test_cis_multi_ref_wires_identity_and_scene_slots() -> None:
    from app.workflows.qwen_image_edit_2509 import build_qwen_edit_2509_i2i_workflow, graph_contract

    graph = build_qwen_edit_2509_i2i_workflow(
        image_name="cami.png",
        positive="@Cami in #Corridor",
        scene_image="corridor.png",
        identity_role="IDENTITY_REFERENCE",
        scene_role="SCENE_REFERENCE",
    )
    contract = graph_contract(graph)
    assert contract["hasImage2"] is True
    assert contract["loadImageCount"] == 2
    plus = [
        n for n in graph.values()
        if n.get("class_type") == "TextEncodeQwenImageEditPlus"
    ]
    assert plus[0]["inputs"]["image1"] == ["5", 0]
    assert plus[0]["inputs"]["image2"] == ["12", 0]
    assert graph["5"]["inputs"]["image"] == "cami.png"
    assert graph["12"]["inputs"]["image"] == "corridor.png"

