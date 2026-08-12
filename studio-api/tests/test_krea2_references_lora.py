"""Krea 2 Phase C — reference images & LoRA wiring tests (no GPU, no queue).

Covers style/moodboard/character/environment reference conditioning, LoRA
loading, registry capability flags, and the ERS Semantic Role Law (environment
references are never reassigned to another role). All model/LoRA/asset paths
are temp files or placeholders — no real weights, no ComfyUI submission.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.image_runtime.asset_refs import (
    AssetRef,
    RoleGroupedReferences,
    asset_refs_from_ers_sheet,
    resolve_krea2_lora,
)
from app.image_runtime.certified_registry import get_workflow, reload_registry
from app.image_runtime.contract import resolve_image_workflow
from app.image_runtime.workflow_execute import build_leaf_graph
from app.workflows.krea2_image import (
    build_krea2_raw_txt2img_workflow,
    build_krea2_turbo_txt2img_workflow,
)

TEST_UNET = "test_krea2_unet.safetensors"
TEST_CLIP = "test_qwen3vl_encoder.safetensors"
TEST_VAE = "test_qwen_image_vae.safetensors"
TEST_CLIP_VISION = "test_clip_vision.safetensors"
TEST_IPADAPTER = "test_ipadapter.safetensors"

BASE_NODE_IDS = {str(i) for i in range(1, 11)}


@pytest.fixture()
def krea2_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Monkeypatched settings: placeholder weights + isolated Krea 2 root."""
    root = tmp_path / "krea2"
    (root / "loras").mkdir(parents=True)
    (root / "loras" / "my-style.safetensors").write_bytes(b"stub-lora")
    monkeypatch.setattr(settings, "krea2_turbo_checkpoint", TEST_UNET)
    monkeypatch.setattr(settings, "krea2_raw_checkpoint", "test_krea2_raw.safetensors")
    monkeypatch.setattr(settings, "krea2_text_encoder", TEST_CLIP)
    monkeypatch.setattr(settings, "krea2_vae", TEST_VAE)
    monkeypatch.setattr(settings, "krea2_clip_vision", TEST_CLIP_VISION)
    monkeypatch.setattr(settings, "krea2_ipadapter", TEST_IPADAPTER)
    monkeypatch.setattr(settings, "krea2_model_root", str(root))
    monkeypatch.delenv("ADEPT_MODEL_ROOT", raising=False)
    return settings


def _nodes_by_class(graph: dict, class_type: str) -> dict[str, dict]:
    return {
        nid: node for nid, node in graph.items() if node.get("class_type") == class_type
    }


def _node_by_class(graph: dict, class_type: str) -> dict:
    nodes = _nodes_by_class(graph, class_type)
    assert nodes, f"node class missing: {class_type}"
    return next(iter(nodes.values()))


def _role_nodes(graph: dict, role: str) -> list[dict]:
    return [
        node
        for node in graph.values()
        if (node.get("_meta") or {}).get("adeptRole") == role
    ]


def _model_chain_roles(graph: dict) -> list[str]:
    """Walk KSampler.model upstream, collecting adeptRole labels on the chain."""
    roles: list[str] = []
    ref = _node_by_class(graph, "KSampler")["inputs"]["model"]
    seen: set[str] = set()
    while ref and ref[0] not in seen:
        nid = str(ref[0])
        seen.add(nid)
        node = graph[nid]
        role = (node.get("_meta") or {}).get("adeptRole")
        if role:
            roles.append(role)
        ref = node["inputs"].get("model")
    return roles


def _turbo_with_refs(**kwargs) -> dict:
    kwargs.setdefault("references", None)
    return build_krea2_turbo_txt2img_workflow(
        unet_name=TEST_UNET,
        clip_name=TEST_CLIP,
        vae_name=TEST_VAE,
        positive="a lighthouse keeper at dawn",
        clip_vision_name=TEST_CLIP_VISION,
        ipadapter_name=TEST_IPADAPTER,
        **kwargs,
    )


# ------------------------------------------------------------------ references


def test_turbo_graph_with_style_references_connected():
    refs = RoleGroupedReferences.from_inputs(
        styleReferences=[
            {"assetId": "asset-style-1", "role": "style"},
            AssetRef(assetId="asset-style-2", role="style", image="style2.png", weight=0.6),
        ]
    )
    graph = _turbo_with_refs(references=refs)

    # Reference support nodes present
    clip_vision = _node_by_class(graph, "CLIPVisionLoader")
    assert clip_vision["inputs"]["clip_name"] == TEST_CLIP_VISION
    ipadapter = _node_by_class(graph, "IPAdapterLoader")
    assert ipadapter["inputs"]["ipadapter_name"] == TEST_IPADAPTER

    # One LoadImage per reference, using the Adept asset path / image name
    loads = _nodes_by_class(graph, "LoadImage")
    assert len(loads) == 2
    images = sorted(n["inputs"]["image"] for n in loads.values())
    assert images == ["asset-style-1", "style2.png"]

    # Each reference routes CLIP vision into its own apply node
    applies = _nodes_by_class(graph, "IPAdapterApply")
    assert len(applies) == 2
    encodes = _nodes_by_class(graph, "CLIPVisionEncode")
    assert len(encodes) == 2
    for node in encodes.values():
        assert node["inputs"]["clip_vision"] == ["30", 0]
    weights = sorted(n["inputs"]["weight"] for n in applies.values())
    assert weights == [0.6, 1.0]

    # The chain is connected into the conditioning path upstream of the sampler:
    # UNETLoader → IPAdapterApply → IPAdapterApply → ModelSamplingAuraFlow → KSampler
    apply_ids = sorted(applies, key=int)
    assert applies[apply_ids[0]]["inputs"]["model"] == ["1", 0]
    assert applies[apply_ids[1]]["inputs"]["model"] == [apply_ids[0], 0]
    sampling = _node_by_class(graph, "ModelSamplingAuraFlow")
    assert sampling["inputs"]["model"] == [apply_ids[1], 0]
    assert _node_by_class(graph, "KSampler")["inputs"]["model"] == ["4", 0]
    assert _model_chain_roles(graph) == ["style", "style"]


def test_moodboard_and_character_refs_keep_distinct_roles():
    refs = RoleGroupedReferences.from_inputs(
        styleReferences=[{"assetId": "s1"}],
        moodboardReferences=[{"assetId": "m1"}],
        characterReferences=[{"assetId": "c1", "role": "character"}],
    )
    graph = _turbo_with_refs(references=refs)
    assert _role_nodes(graph, "style"), "style ref missing"
    assert _role_nodes(graph, "moodboard"), "moodboard ref missing"
    identity_nodes = _role_nodes(graph, "identity")
    assert identity_nodes, "character ref missing"
    # character alias normalizes onto the identity conditioning role
    assert all(
        n["_meta"]["adeptRole"] == "identity" for n in identity_nodes
    )
    # Stable conditioning order: style → moodboard → identity → environment
    assert _model_chain_roles(graph) == ["identity", "moodboard", "style"]


# ------------------------------------------------------------------------ LoRA


def test_resolve_krea2_lora_from_model_root(krea2_settings):
    spec = resolve_krea2_lora("my-style", settings=krea2_settings)
    assert spec is not None and spec.resolved is True
    assert spec.resolvedName == "my-style.safetensors"
    assert spec.resolvedPath and spec.resolvedPath.endswith("my-style.safetensors")
    assert spec.strength == 0.8  # default

    # Explicit filename + custom strength
    spec2 = resolve_krea2_lora("my-style.safetensors", strength=0.5, settings=krea2_settings)
    assert spec2 is not None and spec2.resolved is True
    assert spec2.strength == 0.5

    # Unknown LoRA is never invented: unresolved spec keeps the honest name
    ghost = resolve_krea2_lora("ghost", settings=krea2_settings)
    assert ghost is not None and ghost.resolved is False
    assert ghost.resolvedName == "ghost.safetensors"
    assert ghost.resolvedPath is None


def test_resolve_krea2_lora_from_adept_model_root_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    adept_root = tmp_path / "adept_models"
    (adept_root / "loras").mkdir(parents=True)
    (adept_root / "loras" / "env-lora.safetensors").write_bytes(b"stub")
    monkeypatch.setenv("ADEPT_MODEL_ROOT", str(adept_root))
    empty = tmp_path / "empty_krea2"
    empty.mkdir()
    monkeypatch.setattr(settings, "krea2_model_root", str(empty))

    spec = resolve_krea2_lora("env-lora", settings=settings)
    assert spec is not None and spec.resolved is True
    assert spec.resolvedName == "env-lora.safetensors"


def test_turbo_graph_with_lora(krea2_settings):
    spec = resolve_krea2_lora("my-style", settings=krea2_settings)
    graph = _turbo_with_refs(lora=spec)

    lora_node = _node_by_class(graph, "LoraLoader")
    assert lora_node["inputs"]["lora_name"] == "my-style.safetensors"
    assert lora_node["inputs"]["strength_model"] == 0.8
    assert lora_node["inputs"]["strength_clip"] == 0.8
    assert lora_node["inputs"]["model"] == ["1", 0]
    assert lora_node["inputs"]["clip"] == ["2", 0]
    assert lora_node["_meta"]["adeptLoraId"] == "my-style"
    assert lora_node["_meta"]["adeptLoraResolved"] is True

    # LoRA sits before the model enters the mu shift node and the text encoders
    assert _node_by_class(graph, "ModelSamplingAuraFlow")["inputs"]["model"] == ["20", 0]
    for encode in ("5", "6"):
        assert graph[encode]["inputs"]["clip"] == ["20", 1]

    # Custom strength flows through
    strong = _turbo_with_refs(lora=resolve_krea2_lora("my-style", strength=0.5, settings=krea2_settings))
    assert _node_by_class(strong, "LoraLoader")["inputs"]["strength_model"] == 0.5

    # Unresolved LoRA still emits the node — ComfyUI surfaces the honest error
    ghost = _turbo_with_refs(lora=resolve_krea2_lora("ghost", settings=krea2_settings))
    ghost_node = _node_by_class(ghost, "LoraLoader")
    assert ghost_node["inputs"]["lora_name"] == "ghost.safetensors"
    assert ghost_node["_meta"]["adeptLoraResolved"] is False


def test_lora_applies_before_reference_conditioning(krea2_settings):
    refs = RoleGroupedReferences.from_inputs(styleReferences=[{"assetId": "s1"}])
    spec = resolve_krea2_lora("my-style", settings=krea2_settings)
    graph = _turbo_with_refs(references=refs, lora=spec)
    applies = _nodes_by_class(graph, "IPAdapterApply")
    apply_id = next(iter(applies))
    assert applies[apply_id]["inputs"]["model"] == ["20", 0]  # conditioned model is post-LoRA
    assert _node_by_class(graph, "ModelSamplingAuraFlow")["inputs"]["model"] == [apply_id, 0]


# ----------------------------------------------------------- ERS semantic role


def test_environment_references_preserve_role_in_graph_metadata():
    refs = RoleGroupedReferences.from_inputs(
        environmentReferences=[{"assetId": "ers-asset-1"}, {"assetId": "ers-asset-2"}],
        styleReferences=[{"assetId": "style-1"}],
    )
    graph = _turbo_with_refs(references=refs)

    env_nodes = [
        node
        for node in graph.values()
        if (node.get("_meta") or {}).get("adeptAssetId", "").startswith("ers-asset")
    ]
    assert env_nodes, "environment reference nodes missing"
    for node in env_nodes:
        assert node["_meta"]["adeptRole"] == "environment"
        assert node["_meta"]["adeptRoleLaw"] == "ERS_SEMANTIC_ROLE_PRESERVED"

    # Environment refs get dedicated conditioning nodes — never merged into style
    style_applies = {id(n) for n in _role_nodes(graph, "style")}
    env_applies = {id(n) for n in _role_nodes(graph, "environment")}
    assert style_applies.isdisjoint(env_applies)

    # Request-side provenance carries the role too
    meta = refs.role_metadata()
    assert meta["rolePreservation"]["environmentRolesPreserved"] is True
    by_asset = {r["assetId"]: r["role"] for r in meta["references"]}
    assert by_asset["ers-asset-1"] == "environment"
    assert by_asset["ers-asset-2"] == "environment"
    assert by_asset["style-1"] == "style"


def test_environment_role_never_reassigned_by_grouping():
    """ERS law: a declared environment role wins even inside another bucket."""
    refs = RoleGroupedReferences.from_inputs(
        styleReferences=[AssetRef(assetId="ers-hero", role="environment")],
    )
    flat = refs.flattened()
    assert flat[0].role == "environment"
    graph = _turbo_with_refs(references=refs)
    nodes = [
        n
        for n in graph.values()
        if (n.get("_meta") or {}).get("adeptAssetId") == "ers-hero"
    ]
    assert nodes and all(n["_meta"]["adeptRole"] == "environment" for n in nodes)
    assert not _role_nodes(graph, "style")


def test_ers_sheet_module_bridge_preserves_environment_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The environment_reference_sheet API retrieves ERS assets for a scene and
    the Krea 2 builder accepts them without changing their role."""
    from app.environment_reference_sheet.contracts import (
        DirectionalViewRecord,
        EnvironmentProfile,
        EnvironmentReferenceSheet,
        ERSCreationPlan,
        ERSCompositionRecord,
    )
    from app.environment_reference_sheet.store import load_sheet, save_sheet

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    sheet = EnvironmentReferenceSheet(
        projectId="proj-ers",
        sceneId="scene-1",
        name="Harbor District",
        description="Night harbor environment",
        profile=EnvironmentProfile(environmentName="Harbor District", description="docks"),
        creationPlan=ERSCreationPlan(summary="plan", creatorPreview="preview"),
        composition=ERSCompositionRecord(sheetTitle="Harbor ERS"),
        directionalViews=[
            DirectionalViewRecord(
                direction="north",
                title="North",
                prompt="north view",
                sourceDirection="front",
                approvedAssetId="ers-north-asset",
                status="approved",
            ),
            DirectionalViewRecord(
                direction="east",
                title="East",
                prompt="east view",
                sourceDirection="right",
                approvedAssetId="ers-east-asset",
                status="approved",
            ),
            DirectionalViewRecord(
                direction="south",
                title="South",
                prompt="south view",
                sourceDirection="rear",
                status="missing",  # no approved asset yet — must be skipped
            ),
        ],
    )
    save_sheet(sheet)
    loaded = load_sheet("proj-ers", sheet.sheetId)
    assert loaded is not None

    refs = asset_refs_from_ers_sheet(loaded)
    assert [r.assetId for r in refs] == ["ers-north-asset", "ers-east-asset"]
    assert all(r.role == "environment" for r in refs)
    assert "Harbor District" in refs[0].displayName

    graph = _turbo_with_refs(
        references=RoleGroupedReferences.from_inputs(environmentReferences=refs)
    )
    env_nodes = _role_nodes(graph, "environment")
    assert env_nodes, "ERS environment conditioning missing"
    env_assets = {
        n["_meta"]["adeptAssetId"]
        for n in graph.values()
        if (n.get("_meta") or {}).get("adeptRole") == "environment"
    }
    assert env_assets == {"ers-north-asset", "ers-east-asset"}
    # No ERS asset was reassigned to a different role anywhere in the graph
    for node in graph.values():
        meta = node.get("_meta") or {}
        if meta.get("adeptAssetId") in env_assets:
            assert meta["adeptRole"] == "environment"


# --------------------------------------------------------------- RAW vs Turbo


def test_raw_graph_with_references_and_lora_differs_from_turbo(krea2_settings):
    refs = RoleGroupedReferences.from_inputs(
        environmentReferences=[{"assetId": "ers-1"}],
    )
    spec = resolve_krea2_lora("my-style", settings=krea2_settings)
    raw = build_krea2_raw_txt2img_workflow(
        unet_name=TEST_UNET,
        clip_name=TEST_CLIP,
        vae_name=TEST_VAE,
        positive="weathered fisherman portrait",
        references=refs,
        lora=spec,
        clip_vision_name=TEST_CLIP_VISION,
        ipadapter_name=TEST_IPADAPTER,
    )
    turbo = _turbo_with_refs(references=refs, lora=spec)

    raw_sampler = _node_by_class(raw, "KSampler")["inputs"]
    turbo_sampler = _node_by_class(turbo, "KSampler")["inputs"]
    assert (raw_sampler["steps"], raw_sampler["cfg"]) == (52, 3.5)
    assert (turbo_sampler["steps"], turbo_sampler["cfg"]) == (8, 0.0)
    # RAW mu is resolution-derived; Turbo pins the distilled constant
    assert _node_by_class(raw, "ModelSamplingAuraFlow")["inputs"]["shift"] == pytest.approx(0.90625)
    assert _node_by_class(turbo, "ModelSamplingAuraFlow")["inputs"]["shift"] == 1.15

    # References + LoRA wire identically on both variants
    for graph in (raw, turbo):
        assert _node_by_class(graph, "LoraLoader")["inputs"]["lora_name"] == "my-style.safetensors"
        assert _role_nodes(graph, "environment"), "environment ref missing"


# ------------------------------------------------------ registry & descriptors


def test_registry_advertises_reference_and_lora_capabilities():
    reload_registry()
    for key in ("krea2.turbo_txt2img", "krea2.raw_txt2img"):
        wf = get_workflow(key)
        assert wf is not None
        caps = wf.capabilities
        assert caps["supportsReferenceImages"] is True
        assert caps["supportsStyleReferences"] is True
        assert caps["supportsMoodboards"] is True
        assert caps["supportsCharacterReference"] is True
        assert caps["supportsLoRA"] is True
        assert caps["supportsReferences"] is True
        assert caps["supportsImageEditing"] is False
        assert caps["supportsEditing"] is False
        for input_name in (
            "styleReferences",
            "characterReferences",
            "environmentReferences",
            "moodboardReferences",
            "loraId",
            "loraStrength",
        ):
            assert input_name in wf.optional_inputs
        for node in ("LoadImage", "CLIPVisionLoader", "IPAdapterApply", "LoraLoader"):
            assert node in wf.optional_nodes
        assert any(
            "ERS assets are preserved as ENVIRONMENT conditioning" in lim
            for lim in wf.limitations
        ), f"{key} missing ERS role-law limitation note"


def test_model_registry_and_provider_descriptor_advertise_capabilities(
    krea2_settings,
):
    from app.image_studio.providers import providers_for_mode
    from app.production_control.model_registry import get_model

    reload_registry()
    for model_id in ("krea2-turbo-local", "krea2-raw-local"):
        model = get_model(model_id)
        assert model is not None
        assert "reference_conditioning" in model.supports
        assert "lora" in model.supports
        assert "edit" in model.doesNotSupport  # image editing stays unsupported

    payload = providers_for_mode("all_models")
    turbo = next(p for p in payload["providers"] if p["id"] == "krea2-turbo-local")
    caps = (turbo.get("metadata") or {}).get("capabilities") or {}
    assert caps.get("supportsReferenceImages") is True
    assert caps.get("supportsLoRA") is True
    assert caps.get("supportsMoodboards") is True
    assert caps.get("supportsCharacterReference") is True
    assert caps.get("supportsImageEditing") is False
    assert "support nodes" in (caps.get("reason") or "")


# ---------------------------------------------------------- dispatch & contract


def test_build_leaf_graph_dispatch_with_references_and_lora(krea2_settings):
    reload_registry()
    contract = resolve_image_workflow(
        "txt2img",
        engine="krea2",
        allow_draft=True,
        present_inputs={
            "styleReferences": [{"assetId": "s1"}],
            "environmentReferences": [{"assetId": "e1"}],
            "loraId": "my-style",
            "loraStrength": 0.6,
        },
    )
    # The canonical contract carries the reference/LoRA inputs
    assert contract.style_references == [{"assetId": "s1"}]
    assert contract.environment_references == [{"assetId": "e1"}]
    assert contract.lora_id == "my-style"
    assert contract.lora_strength == 0.6
    as_dict = contract.to_dict()
    assert as_dict["styleReferences"] == [{"assetId": "s1"}]
    assert as_dict["loraId"] == "my-style"
    assert as_dict["loraStrength"] == 0.6

    graph = build_leaf_graph(contract, settings=krea2_settings, prompt="neon harbor")
    lora_node = _node_by_class(graph, "LoraLoader")
    assert lora_node["inputs"]["lora_name"] == "my-style.safetensors"
    assert lora_node["inputs"]["strength_model"] == 0.6  # contract strength honored
    assert _role_nodes(graph, "style"), "contract style ref missing"
    assert _role_nodes(graph, "environment"), "contract environment ref missing"

    # Explicit call-site values beat the contract carriers
    overridden = build_leaf_graph(
        contract,
        settings=krea2_settings,
        prompt="neon harbor",
        lora_strength=0.9,
    )
    assert _node_by_class(overridden, "LoraLoader")["inputs"]["strength_model"] == 0.9


def test_default_graph_unchanged_without_references_or_lora(krea2_settings):
    """Fingerprint safety: no refs / no LoRA → the exact Phase B topology."""
    graph = build_krea2_turbo_txt2img_workflow(
        unet_name=TEST_UNET,
        clip_name=TEST_CLIP,
        vae_name=TEST_VAE,
        positive="canonical fingerprint probe",
    )
    assert set(graph.keys()) == BASE_NODE_IDS
    assert not _nodes_by_class(graph, "LoraLoader")
    assert not _nodes_by_class(graph, "LoadImage")

    # Empty group / None behave identically (dispatch always passes a group)
    empty = _turbo_with_refs(references=RoleGroupedReferences.from_inputs())
    assert set(empty.keys()) == BASE_NODE_IDS

    via_dispatch = build_leaf_graph(
        resolve_image_workflow("txt2img", engine="krea2", allow_draft=True),
        settings=krea2_settings,
        prompt="canonical fingerprint probe",
    )
    assert set(via_dispatch.keys()) == BASE_NODE_IDS
