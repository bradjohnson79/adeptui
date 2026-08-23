"""CDX-075 local readiness authority - Certified metadata never implies installed.

Covers:
- imagegen_workflows.build_local_generator_models gates executability on
  Setup/Source Manager component verification (verify_component); a family
  whose weights do not verify (or whose verification fails) is not offered as
  an executable generator.
- production_control.model_registry static _CATALOG no longer claims
  lifecycle=Installed / executable=True for local rows; runtime truth is
  derived from Setup component status at list time.
- image_studio.providers reports "ready" only when the model's Setup component
  verifies on disk (_local_readiness / _COMPONENT_GATE_BY_MODEL).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.setup.diagnostics import Verification


def _unhealthy(issue: str = "required_models_missing") -> Verification:
    return Verification(False, True, issue, "Required model files are missing.")


def _healthy() -> Verification:
    return Verification(True, False, None, "Model files are readable.")


def _fake_verify(healthy: bool):
    def _verify(component_id: str, state=None):
        return _healthy() if healthy else _unhealthy()
    return _verify


# ---------------------------------------------------------------------------
# imagegen_workflows: executability gating
# ---------------------------------------------------------------------------

def test_certified_family_not_offered_when_weights_absent(monkeypatch):
    """CDX-075: Certified registry status alone must not put a family in the
    executable roster. When verify_component reports the weights missing, the
    family is not offered as an executable local generator."""
    from app.imagegen_workflows import build_local_generator_models

    monkeypatch.setattr("app.setup.diagnostics.verify_component", _fake_verify(False))
    opts = {o["id"]: o for o in build_local_generator_models()}
    # Only Auto Select (and possibly the honest non-executable krea2 candidate).
    for fid in ("qwen2512", "zimage", "flux", "illustrious"):
        assert fid not in opts, f"{fid} must not be offered when its weights are absent"
    for o in opts.values():
        if o["id"] == "auto":
            continue
        assert o["executable"] is False, f"{o['id']} must fail closed (not executable)"


def test_certified_family_offered_when_weights_verify(monkeypatch):
    """CDX-075: with weights on disk (Setup component healthy), Certified
    families are offered as executable."""
    from app.imagegen_workflows import build_local_generator_models

    monkeypatch.setattr("app.setup.diagnostics.verify_component", _fake_verify(True))
    opts = {o["id"]: o for o in build_local_generator_models()}
    for fid in ("qwen2512", "zimage", "flux", "illustrious"):
        assert fid in opts, f"{fid} must be offered when its weights verify on disk"
        assert opts[fid]["executable"] is True
        assert opts[fid]["status"] == "Certified"


def test_verification_failure_fails_closed(monkeypatch):
    """A probe exception must never upgrade readiness: the family fails closed."""
    from app.imagegen_workflows import build_local_generator_models

    def _boom(component_id: str, state=None):
        raise RuntimeError("probe exploded")
    monkeypatch.setattr("app.setup.diagnostics.verify_component", _boom)
    opts = {o["id"]: o for o in build_local_generator_models()}
    for fid in ("qwen2512", "zimage", "flux", "illustrious"):
        assert fid not in opts, f"{fid} must fail closed when verification cannot run"


def test_unknown_family_fails_closed():
    """A family with no Setup component mapping is never assumed installed."""
    from app.imagegen_workflows import _family_verified_on_disk

    assert _family_verified_on_disk("does-not-exist") is False


# ---------------------------------------------------------------------------
# production_control.model_registry: static catalog honesty
# ---------------------------------------------------------------------------

def test_static_catalog_local_rows_do_not_claim_install_truth():
    """The static _CATALOG must not assert lifecycle=Installed / executable for
    local rows - those are runtime facts derived from Setup component status."""
    from app.production_control.model_registry import _CATALOG

    local = [m for m in _CATALOG if m.locality == "local"]
    assert local, "expected local static rows"
    for m in local:
        assert m.executable is False, f"{m.id} static catalog must not claim executable"
        assert m.lifecycle is None, f"{m.id} static catalog must not claim an install lifecycle"
        # Metadata is preserved: certification/capability labels stay.
        assert m.capabilityLabel in {
            "Certified",
            "Available",
            "Testing",
            "Draft",
            "Requires Setup",
            "Unavailable",
        }


def test_list_models_derives_executable_from_setup_status(monkeypatch):
    """list_models() overlays Setup/Source Manager component truth on the static
    catalog: a verified component makes the row executable; a missing one does
    not."""
    from app.production_control import model_registry
    from app.production_control.model_registry import get_model

    # _apply_setup_status derives image-modality executable from verify_component
    # (the same setup-status source build_status aggregates) plus the lifecycle
    # certified flag, rather than a full build_status probe (which would re-probe
    # slow audio/avatar components on every image resolve).
    def _cert(certified: bool):
        return lambda component_id: SimpleNamespace(certified=certified)

    monkeypatch.setattr("app.setup.diagnostics.verify_component", _fake_verify(True))
    monkeypatch.setattr("app.setup.lifecycle.service.get_certification", _cert(True))
    model_registry._IMAGE_VERIFY_CACHE.clear()
    m = get_model("krea2-turbo-local")
    assert m is not None
    assert m.executable is True
    assert m.lifecycle == "Installed"

    monkeypatch.setattr("app.setup.diagnostics.verify_component", _fake_verify(False))
    monkeypatch.setattr("app.setup.lifecycle.service.get_certification", _cert(False))
    model_registry._IMAGE_VERIFY_CACHE.clear()
    m2 = get_model("krea2-turbo-local")
    assert m2 is not None
    assert m2.executable is False
    assert m2.capabilityLabel == "Requires Setup"


# ---------------------------------------------------------------------------
# image_studio.providers: ready only when disk-verified
# ---------------------------------------------------------------------------

def _qwen_model() -> SimpleNamespace:
    return SimpleNamespace(
        id="qwen-image-2512-local",
        label="Qwen Image 2512 (Local)",
        executionClass="native_local",
        providerId="comfy",
        capabilityLabel="Certified",
        lifecycle="Installed",
        supports=["text_to_image", "edit", "inpaint", "reference_conditioning"],
        estimatedVramGb=12.0,
        executable=True,
    )


def test_image_studio_ready_only_when_disk_verified(monkeypatch):
    """CDX-075: a Certified+executable dock row is NOT 'ready' until its Setup
    component verifies on disk."""
    from app.image_studio.providers import _from_local_model

    monkeypatch.setattr("app.setup.diagnostics.verify_component", _fake_verify(False))
    desc = _from_local_model(_qwen_model())
    assert desc.readiness == "not_installed"
    assert desc.metadata.get("capabilityLabel") != "Certified"
    assert desc.metadata.get("lifecycle") != "Installed"


def test_image_studio_ready_when_disk_verified(monkeypatch):
    from app.image_studio.providers import _from_local_model

    monkeypatch.setattr("app.setup.diagnostics.verify_component", _fake_verify(True))
    desc = _from_local_model(_qwen_model())
    assert desc.readiness == "ready"


def test_map_local_readiness_is_pure_field_mapping():
    """_map_local_readiness alone maps fields; disk gating lives in _local_readiness."""
    from app.image_studio.providers import _map_local_readiness

    ready = _map_local_readiness(_qwen_model())
    assert ready == "ready"
    missing = SimpleNamespace(**{**vars(_qwen_model()), "executable": False})
    assert _map_local_readiness(missing) == "incompatible"

