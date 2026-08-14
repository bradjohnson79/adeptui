"""Krea 2 Phase A — provider-family registration & discovery (no GPU, no real weights).

Covers the five-point registration checklist from the Krea 2 image pipeline audit:
provider registry family, model discovery, Production Dock catalog, dock->family map,
Image Studio provider layer, capability binding, Setup component verification, and
Source Manager subtree discoverability. All filesystem probes use temp dirs or
monkeypatched settings — never real model weights.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _krea2_verify_cache_reset():
    from app.setup.diagnostics import invalidate_verify_cache

    invalidate_verify_cache("krea2_models")
    yield
    invalidate_verify_cache("krea2_models")


@pytest.fixture()
def krea2_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the Krea 2 model root at an isolated temp dir."""
    root = tmp_path / "krea2"
    root.mkdir()
    from app.config import settings

    monkeypatch.setattr(settings, "krea2_model_root", str(root))
    return root


def _write_official_layout(root: Path) -> None:
    """Official HF layout: bare turbo/raw checkpoint names in a krea-scoped tree."""
    (root / "checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "text_encoders").mkdir(parents=True, exist_ok=True)
    (root / "vae").mkdir(parents=True, exist_ok=True)
    (root / "checkpoints" / "turbo.safetensors").write_bytes(b"stub")
    (root / "checkpoints" / "raw.safetensors").write_bytes(b"stub")
    (root / "text_encoders" / "qwen3_vl_4b_fp8.safetensors").write_bytes(b"stub")
    (root / "vae" / "qwen_image_vae.safetensors").write_bytes(b"stub")


# ---------------------------------------------------------------- provider registry


def test_provider_registry_lists_krea2_under_comfyui() -> None:
    from app.image_runtime.provider_registry import get_provider, reload_provider_registry

    reload_provider_registry()
    provider = get_provider("comfyui")
    assert provider is not None
    assert provider.get("kind") == "local"
    families = provider.get("supportedModelFamilies") or []
    assert "krea2" in families
    # Krea 2 is a family under the existing local provider — not a new provider entry.
    assert "image.generate" in (provider.get("operations") or [])


# -------------------------------------------------------------- model discovery


def test_model_discovery_finds_krea2_patterns(
    krea2_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.image_runtime.model_discovery import discover_modern_image_models

    # Official-layout files inside the configured Krea 2 root.
    _write_official_layout(krea2_root)
    # Repack-style filename (family token in the name) in a separate scan root.
    scan_root = tmp_path / "scan_models"
    scan_root.mkdir()
    (scan_root / "Krea-2-Turbo-fp8.safetensors").write_bytes(b"stub")
    # A same-token decoy that must never count as Krea 2.
    (scan_root / "z_image_turbo_bf16.safetensors").write_bytes(b"stub")
    monkeypatch.setenv("ADEPT_MODELS_ROOT", str(scan_root))

    discovery = discover_modern_image_models()
    family = discovery["families"]["krea2"]
    assert family["modelFamily"] == "krea2"
    assert family["variants"] == ["turbo", "raw"]
    assert family["installed"] is True
    samples = family["sampleFiles"]
    assert any(p.endswith("turbo.safetensors") for p in samples)
    assert any("Krea-2-Turbo-fp8.safetensors" in p for p in samples)
    assert not any("z_image_turbo" in p for p in samples)
    assert family["statusHint"] == "Draft"
    assert family["license"] == "krea-2-community-license"


def test_model_discovery_krea2_absent(
    krea2_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.image_runtime.model_discovery import discover_modern_image_models

    empty_scan = tmp_path / "empty_models"
    empty_scan.mkdir()
    monkeypatch.setattr(settings, "comfy_models_dir", empty_scan)
    monkeypatch.setenv("ADEPT_MODELS_ROOT", str(empty_scan))
    monkeypatch.delenv("COMFY_MODELS_PATH", raising=False)

    discovery = discover_modern_image_models()
    family = discovery["families"]["krea2"]
    assert family["installed"] is False
    assert family["fileCount"] == 0
    assert family["statusHint"] == "Blocked"


# ------------------------------------------------------- production dock catalog


def test_model_registry_catalog_contains_krea2_entries() -> None:
    from app.production_control.model_registry import get_model

    turbo = get_model("krea2-turbo-local")
    assert turbo is not None
    assert turbo.modality == "image"
    assert turbo.capabilityLabel == "Certified"
    assert turbo.executable is True
    assert turbo.gpuCompatible is True
    assert turbo.estimatedVramGb == 24.0
    assert "text_to_image" in turbo.supports

    raw = get_model("krea2-raw-local")
    assert raw is not None
    assert raw.modality == "image"
    assert raw.capabilityLabel == "Requires Setup"
    assert raw.executable is False
    assert raw.estimatedVramGb == 24.0


def test_runtime_map_resolves_krea2_family() -> None:
    from app.production_control.runtime_map import image_family_for_dock_model

    assert image_family_for_dock_model("krea2-turbo-local") == "krea2"
    assert image_family_for_dock_model("krea2-raw-local") == "krea2"


# ------------------------------------------------------------- image studio layer


def test_image_studio_providers_include_krea2_with_license() -> None:
    from app.image_studio.providers import providers_for_mode

    payload = providers_for_mode("all_models")
    providers = payload["providers"]
    turbo = next((p for p in providers if p["id"] == "krea2-turbo-local"), None)
    assert turbo is not None
    assert turbo["family"] == "krea2"
    assert "Krea 2 Community License" in (turbo["licenseNote"] or "")
    assert turbo["costHint"]
    assert turbo["nativeResolutions"] == ["1K", "2K"]
    assert "2048x2048" in (turbo["metadata"].get("nativePixelSizes") or [])

    raw = next((p for p in providers if p["id"] == "krea2-raw-local"), None)
    assert raw is not None
    assert raw["family"] == "krea2"
    assert "Krea 2 Community License" in (raw["licenseNote"] or "")


def test_image_studio_family_catalog_includes_krea2() -> None:
    from app.image_studio.providers import family_catalog

    catalog = {entry["family"]: entry for entry in family_catalog()}
    assert "krea2" in catalog
    assert catalog["krea2"]["label"] == "Krea 2"
    # No certified krea2.* workflows exist yet — honest non-executable status.
    assert catalog["krea2"]["executable"] is False
    assert catalog["krea2"]["status"] in {"Unknown", "Draft", "Deferred", "Blocked"}
    assert catalog["krea2"]["estimates"]["vramGb"] == 24.0


def test_missing_krea2_files_produce_not_installed(krea2_root: Path) -> None:
    from app.image_studio.providers import _from_local_model
    from app.production_control.model_registry import get_model

    turbo = get_model("krea2-turbo-local")
    assert turbo is not None
    descriptor = _from_local_model(turbo)
    assert descriptor.readiness == "not_installed"
    assert descriptor.metadata.get("capabilityLabel") != "Certified"
    assert descriptor.metadata.get("lifecycle") != "Installed"

    raw = get_model("krea2-raw-local")
    assert raw is not None
    raw_desc = _from_local_model(raw)
    assert raw_desc.readiness == "not_installed"
    assert raw_desc.metadata.get("capabilityLabel") != "Certified"
    assert raw_desc.metadata.get("lifecycle") != "Installed"


def test_installed_krea2_files_map_to_static_readiness(krea2_root: Path) -> None:
    from app.image_studio.providers import _from_local_model
    from app.production_control.model_registry import get_model

    _write_official_layout(krea2_root)
    turbo = get_model("krea2-turbo-local")
    assert turbo is not None
    assert _from_local_model(turbo).readiness == "ready"


# --------------------------------------------------------------- setup component


def test_setup_catalog_component_shape() -> None:
    from app.setup.catalog import get_component

    component = get_component("krea2_models")
    assert component.category == "Still Image Models"
    assert component.installer == "path_link"
    assert component.verifier == "krea2_files"
    assert component.required is False
    assert "comfyui" in component.dependencies


def test_krea2_files_verifier_missing(krea2_root: Path) -> None:
    from app.setup.diagnostics import verify_component

    result = verify_component("krea2_models")
    assert result.healthy is False
    assert result.absent is True
    assert result.issue_code == "optional_models_missing"
    assert any("Turbo checkpoint" in detail for detail in result.details)


def test_krea2_files_verifier_accepts_official_layout(krea2_root: Path) -> None:
    from app.setup.diagnostics import verify_component

    _write_official_layout(krea2_root)
    result = verify_component("krea2_models")
    assert result.healthy is True
    assert result.issue_code is None


def test_krea2_files_verifier_discovers_repack_filenames(krea2_root: Path) -> None:
    """Comfy-Org-style repack names are discovered by pattern, never hardcoded."""
    from app.setup.diagnostics import verify_component

    (krea2_root / "diffusion_models").mkdir(parents=True)
    (krea2_root / "text_encoders").mkdir(parents=True)
    (krea2_root / "vae").mkdir(parents=True)
    (krea2_root / "diffusion_models" / "krea2_turbo_fp8_e4m3fn.safetensors").write_bytes(b"stub")
    (krea2_root / "diffusion_models" / "krea2_raw_fp8_e4m3fn.safetensors").write_bytes(b"stub")
    (krea2_root / "text_encoders" / "qwen3_vl_4b_instruct_fp8.safetensors").write_bytes(b"stub")
    (krea2_root / "vae" / "qwen_image_vae_bf16.safetensors").write_bytes(b"stub")

    result = verify_component("krea2_models")
    assert result.healthy is True


def test_comfy_health_model_component_ids_include_krea2() -> None:
    from app.comfy_health import MODEL_COMPONENT_IDS

    assert "krea2_models" in MODEL_COMPONENT_IDS


# ---------------------------------------------------------- capability registry


def test_capability_registry_binds_krea2_component() -> None:
    from app.capabilities.registry import BY_ID, validate_registry

    validate_registry()
    definition = BY_ID["models.image.krea2.ready"]
    assert definition.component_ids == ("krea2_models",)
    assert definition.subsystem == "models"

    from app.capabilities.service import EVALUATORS

    assert "models.image.krea2.ready" in EVALUATORS


def test_capability_evaluation_blocks_when_krea2_missing(krea2_root: Path) -> None:
    from app.capabilities.probes import ProbeSnapshot
    from app.capabilities.registry import BY_ID
    from app.capabilities.service import EVALUATORS

    snapshot = ProbeSnapshot(setup_components={"krea2_models": {"status": "not_installed"}})
    evaluation = EVALUATORS["models.image.krea2.ready"](BY_ID["models.image.krea2.ready"], snapshot)
    assert evaluation.available is False
    assert evaluation.component_ids == ("krea2_models",)


# -------------------------------------------------------------- source manager


def test_source_manager_krea2_subtree_discoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.model_storage import store

    monkeypatch.setattr(store, "storage_path", lambda: tmp_path / "model_storage.json")
    image_root = tmp_path / "models"
    state = store.load_model_storage()
    state["roots"]["image"] = str(image_root)
    store.save_model_storage(state)

    status = store.krea2_registration_status()
    assert status["path"].endswith("krea2")
    assert status["discoverable"] is False

    (image_root / "krea2").mkdir(parents=True)
    status = store.krea2_registration_status()
    assert status["exists"] is True
    assert status["discoverable"] is True
    assert status["imageCategoryRoot"] == str(image_root)
