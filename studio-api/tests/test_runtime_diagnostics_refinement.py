"""Backend tests for the Runtime Health / Model Readiness Refinement.

Covers:
- New verifier branches (text_encoder_file / vae_file / latent_upscale_model_file)
  surface the exact missing filename + expected path on miss.
- LTX 2.5 workflow readiness requires all three components (checkpoint +
  text_encoder + video_vae), not the checkpoint alone.
- Required-vs-optional filtering in the comfy health payload: an optional
  component missing does NOT flip the runtime to degraded, and
  missingRequiredModelComponentIds is the required-only subset.
- Dependency-type taxonomy maps component_id → semantic type.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import diagnostics as setup_diagnostics
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "comfy_input_dir", tmp_path / "missing-comfy" / "input")
    if hasattr(settings, "comfy_models_dir"):
        monkeypatch.setattr(settings, "comfy_models_dir", None)
    setup_status._STATUS_CACHE = None
    setup_diagnostics._VERIFY_CACHE.clear()
    return tmp_path


# ── New verifier branches ────────────────────────────────────────────────


def test_text_encoder_file_missing_surfaces_filename_and_path(setup_data_dir: Path) -> None:
    """LTX 2.5 text encoder missing must report the exact filename + expected path,
    not 'unsupported_verifier'."""
    from app.setup.diagnostics import verify_component
    from app.setup.state import save_state

    model_dir = setup_data_dir / "models"
    model_dir.mkdir()
    save_state({"components": {}, "model_locations": {"ltx_2_5_text_encoder": str(model_dir)}})

    result = verify_component("ltx_2_5_text_encoder")
    assert result.healthy is False
    assert result.issue_code == "required_model_missing"
    # Must surface the exact filename, not a vague count.
    details_text = " ".join(result.details or ())
    from app.config import settings
    assert settings.ltx_2_5_text_encoder in details_text, details_text
    assert "models/text_encoders/" in details_text, details_text


def test_text_encoder_file_present_reads_it(setup_data_dir: Path) -> None:
    from app.config import settings
    from app.setup.diagnostics import verify_component
    from app.setup.state import save_state

    model_dir = setup_data_dir / "models" / "text_encoders"
    model_dir.mkdir(parents=True)
    (model_dir / settings.ltx_2_5_text_encoder).write_bytes(b"encoder-weights")
    save_state({"components": {}, "model_locations": {"ltx_2_5_text_encoder": str(model_dir)}})

    result = verify_component("ltx_2_5_text_encoder")
    assert result.healthy is True
    assert result.issue_code is None


def test_vae_file_missing_surfaces_filename_and_path(setup_data_dir: Path) -> None:
    from app.setup.diagnostics import verify_component
    from app.setup.state import save_state

    model_dir = setup_data_dir / "models"
    model_dir.mkdir()
    save_state({"components": {}, "model_locations": {"ltx_2_5_video_vae": str(model_dir)}})

    result = verify_component("ltx_2_5_video_vae")
    assert result.healthy is False
    assert result.issue_code == "required_model_missing"
    details_text = " ".join(result.details or ())
    from app.config import settings
    assert settings.ltx_2_5_video_vae in details_text
    assert "models/vae/" in details_text


def test_vae_file_present_reads_it(setup_data_dir: Path) -> None:
    from app.config import settings
    from app.setup.diagnostics import verify_component
    from app.setup.state import save_state

    model_dir = setup_data_dir / "models" / "vae"
    model_dir.mkdir(parents=True)
    (model_dir / settings.ltx_2_5_video_vae).write_bytes(b"vae-weights")
    save_state({"components": {}, "model_locations": {"ltx_2_5_video_vae": str(model_dir)}})

    result = verify_component("ltx_2_5_video_vae")
    assert result.healthy is True


def test_upscale_file_missing_surfaces_filename_and_path(setup_data_dir: Path) -> None:
    from app.setup.diagnostics import verify_component
    from app.setup.state import save_state

    model_dir = setup_data_dir / "models"
    model_dir.mkdir()
    save_state({"components": {}, "model_locations": {"ltx_2_5_spatial_upscaler": str(model_dir)}})

    result = verify_component("ltx_2_5_spatial_upscaler")
    assert result.healthy is False
    assert result.issue_code == "required_model_missing"
    details_text = " ".join(result.details or ())
    from app.config import settings
    assert settings.ltx_2_5_spatial_upscaler in details_text
    assert "models/upscale_models/" in details_text


# ── LTX 2.5 workflow readiness ───────────────────────────────────────────


def test_ltx_25_workflow_requires_all_three_components() -> None:
    """ltx_25.t2v must require checkpoint + text_encoder + video_vae together."""
    from app.workflows.readiness import WORKFLOW_MODEL_COMPONENTS

    for key in ("ltx_25.t2v", "ltx_25.i2v",):
        required = WORKFLOW_MODEL_COMPONENTS.get(key)
        assert required == (
            "ltx_2_5_checkpoint",
            "ltx_2_5_text_encoder",
            "ltx_2_5_video_vae",
        ), f"{key} must require all three LTX 2.5 components, got {required}"


# ── Dependency-type taxonomy ─────────────────────────────────────────────


def test_dependency_type_taxonomy_mapping() -> None:
    from app.setup.catalog import (
        DEPENDENCY_TYPE_MODEL,
        DEPENDENCY_TYPE_TEXT_ENCODER,
        DEPENDENCY_TYPE_VAE,
        DEPENDENCY_TYPE_UPSCALE_MODEL,
        dependency_type_for,
    )

    assert dependency_type_for("ltx_2_5_checkpoint") == DEPENDENCY_TYPE_MODEL
    assert dependency_type_for("ltx_2_5_text_encoder") == DEPENDENCY_TYPE_TEXT_ENCODER
    assert dependency_type_for("ltx_2_5_video_vae") == DEPENDENCY_TYPE_VAE
    assert dependency_type_for("ltx_2_5_spatial_upscaler") == DEPENDENCY_TYPE_UPSCALE_MODEL
    assert dependency_type_for("ltx_checkpoint") == DEPENDENCY_TYPE_MODEL


def test_dependency_type_unknown_for_missing_component() -> None:
    from app.setup.catalog import DEPENDENCY_TYPE_UNKNOWN, dependency_type_for

    assert dependency_type_for("does_not_exist_xyz") == DEPENDENCY_TYPE_UNKNOWN


# ── ComfyHealth model_component_states enrichment ────────────────────────


def test_model_component_states_carries_dependency_metadata(setup_data_dir: Path) -> None:
    from app.comfy_health import model_component_states
    from app.setup.state import save_state

    # No model files present → all missing, but metadata must still be attached.
    save_state({"components": {}, "model_locations": {}})

    states = model_component_states()
    te = next((s for s in states if s["componentId"] == "ltx_2_5_text_encoder"), None)
    assert te is not None, "ltx_2_5_text_encoder must be in model component states"
    assert te["dependencyType"] == "TEXT_ENCODER"
    assert te["filename"] is not None  # exact filename surfaced
    assert te["expectedPath"] == "models/text_encoders/"
    assert te["present"] is False


# ── Required-vs-optional filtering in ComfyHealth ─────────────────────────


def test_comfy_health_optional_missing_does_not_degrade_runtime(setup_data_dir: Path) -> None:
    """When ComfyUI is reachable but an OPTIONAL component is missing, the runtime
    status must NOT be 'degraded' for MODEL_MISSING. missingRequiredModelComponentIds
    must be the required-only subset."""
    import asyncio

    from app.comfy_health import comfy_health
    from app.setup.state import save_state

    # No files present → all catalogued components missing, but only the REQUIRED
    # ones (ltx_checkpoint is required=True in the catalog) should count toward
    # missingRequiredModelComponentIds. LTX 2.5 components are required=False.
    save_state({"components": {}, "model_locations": {}})

    # Mock the comfy client so we simulate a reachable, healthy ComfyUI.
    fake_stats = {"comfyui_version": "0.3.0", "devices": []}
    fake_catalogue = {"VAELoader": {}, "CheckpointLoaderSimple": {}}

    async def _run():
        with patch("app.comfy_client.comfy.health", new=AsyncMock(return_value=fake_stats)), \
             patch("app.comfy_client.comfy.get_object_info", new=AsyncMock(return_value=fake_catalogue)):
            return await comfy_health(include_nodes=True)

    payload = asyncio.run(_run())

    assert payload["reachable"] is True
    missing_required = payload.get("missingRequiredModelComponentIds", [])
    missing_all = payload.get("missingModelComponentIds", [])
    # Required-only subset must be a subset of all-missing.
    assert set(missing_required).issubset(set(missing_all))
    # LTX 2.5 text encoder is optional at the runtime level (required=False in catalog)
    # so it must NOT be in missingRequiredModelComponentIds.
    assert "ltx_2_5_text_encoder" in missing_all
    assert "ltx_2_5_text_encoder" not in missing_required
    missing_optional = payload.get("missingOptionalModelComponentIds", [])
    assert "ltx_2_5_text_encoder" in missing_optional
    assert "krea2_models" in missing_all
    assert "krea2_models" not in missing_required
    assert "krea2_models" in missing_optional


# ── _eval_models_video LTX 2.5 requires all three ────────────────────────


def test_eval_models_video_ltx_25_requires_all_components(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present LTX 2.5 checkpoint alone must NOT satisfy models.video.ready
    when the text encoder or VAE is missing."""
    from app.capabilities import service as cap_service
    from app.capabilities.models import CapabilityDefinition
    from app.capabilities.probes import ProbeSnapshot

    # Build a fake snapshot where only the LTX 2.5 checkpoint is ready.
    fake_components = {
        "ltx_2_5_checkpoint": {"status": "ready", "present": True},
        "ltx_2_5_text_encoder": {"status": "missing", "present": False},
        "ltx_2_5_video_vae": {"status": "missing", "present": False},
        "wan_models": {"status": "missing", "present": False},
        "ltx_checkpoint": {"status": "missing", "present": False},
    }

    class FakeSnapshot(ProbeSnapshot):
        def __init__(self):
            pass

        setup_components = fake_components  # type: ignore[assignment]

        def component(self, component_id):
            return fake_components.get(component_id, {"status": "unknown"})

        def component_ready(self, component_id):
            return fake_components.get(component_id, {}).get("present") is True

    snapshot = FakeSnapshot()
    definition = CapabilityDefinition(
        id="video.generate",
        display_name="Video Generation",
        subsystem="video",
        baseline_status="locally_verified",
        summary="",
    )

    result = cap_service._eval_models_video(definition, snapshot)
    # With checkpoint present but text encoder + VAE missing, the LTX 2.5 variant
    # is NOT ready, so the aggregate must not report ok.
    assert result.available is not True or result.healthy is not True


# ── Status probe: optional missing does not flip runtime to warning ──────


def test_status_probe_optional_missing_stays_healthy() -> None:
    """_probe_comfy must return 'healthy' (not 'warning') when ComfyUI is reachable
    and only optional/generator-specific components are missing."""
    import asyncio

    from app.codirector.status.registry import _probe_comfy

    fake_payload = {
        "reachable": True,
        "status": "ready",
        "version": "0.3.0",
        "nodeCatalogAvailable": True,
        "nodeTypeCount": 100,
        "models": [
            {"componentId": "ltx_2_5_text_encoder", "required": False, "present": False},
        ],
        "missingModelComponentIds": ["ltx_2_5_text_encoder"],
        "missingRequiredModelComponentIds": [],
        "message": "ComfyUI is reachable.",
    }

    class FakeShared:
        comfy_health = fake_payload

    class FakeCtx:
        shared = FakeShared()

    result = asyncio.run(_probe_comfy(FakeCtx()))
    assert result["status"] == "healthy", f"optional-missing must stay healthy, got {result['status']}"

def test_health_endpoint_top_level_missing_lists_exclude_optional(monkeypatch) -> None:
    """Top-level missing_models / missing_model_component_ids must stay required-only.

    Optional krea2_models belongs on missing_optional_* so a frontend ||-fallthrough
    from empty missingRequiredModelComponentIds cannot treat Krea 2 as required.
    """
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.routers import api as api_mod

    fake = {
        "reachable": True,
        "status": "ready",
        "version": "0.3.0",
        "nodeCatalogAvailable": True,
        "reasonCode": None,
        "recommendedAction": None,
        "message": "ComfyUI is reachable.",
        "models": [
            {"componentId": "ltx_checkpoint", "name": "LTX Checkpoint", "required": True, "present": True},
            {"componentId": "krea2_models", "name": "Krea 2 Turbo (+RAW) Models", "required": False, "present": False},
        ],
        "missingModelComponentIds": ["krea2_models"],
        "missingRequiredModelComponentIds": [],
        "missingOptionalModelComponentIds": ["krea2_models"],
    }

    async def _fake_comfy_health(*_a, **_k):
        return fake

    monkeypatch.setattr("app.comfy_health.comfy_health", _fake_comfy_health)

    fake_caps = SimpleNamespace(
        callable=[],
        blockers=[],
        capabilities=[],
        deferred=[],
        counts={},
        readinessTotal=0,
    )
    monkeypatch.setattr(
        "app.capabilities.service.get_capabilities",
        AsyncMock(return_value=fake_caps),
    )
    monkeypatch.setattr(
        "app.codirector.service.get_health",
        AsyncMock(return_value=SimpleNamespace(
            provider_id=None,
            status="unavailable",
            reachable=False,
            model_available=False,
            selected_model=None,
        )),
    )
    monkeypatch.setattr(api_mod, "_probe_bible_storage", lambda: "ready")

    payload = asyncio.run(api_mod.health())
    data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    assert "krea2_models" not in (data.get("missing_model_component_ids") or [])
    assert "Krea 2 Turbo (+RAW) Models" not in (data.get("missing_models") or [])
    assert data.get("missing_optional_model_component_ids") == ["krea2_models"]
    assert "Krea 2 Turbo (+RAW) Models" in (data.get("missing_optional_models") or [])
    assert (data.get("comfy") or {}).get("missingRequiredModelComponentIds") == []
    assert data.get("comfy_status") == "ready"

