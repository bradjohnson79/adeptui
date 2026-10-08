"""MiniMax H3 model-license gate. Does not download H3."""

from __future__ import annotations

from pathlib import Path

import pytest

H3 = "minimax_h3_base_optimized"
MODEL = "minimax-h3"


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import diagnostics as setup_diagnostics
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    setup_status._STATUS_CACHE = None
    setup_diagnostics._VERIFY_CACHE.clear()
    return tmp_path


def test_simulation_cases_lock_and_unlock_without_download() -> None:
    from app.setup.model_license import simulate

    cases = {
        "LICENSE METADATA FAILURE": False,
        "NO ACKNOWLEDGEMENT": False,
        "STANDARD LICENSE": False,
        "SEPARATE AUTHORIZATION": False,
        "ACKNOWLEDGED": True,
        "LICENSE VERSION CHANGED": False,
    }
    for name, unlocked in cases.items():
        result = simulate(name)
        assert result["case"] == name
        assert result["installationUnlocked"] is unlocked

    standard = simulate("STANDARD LICENSE")
    assert standard["route"] == "standard"
    assert standard["requiresAcknowledgement"] is True
    assert standard["status"] == "LICENSE SETUP REQUIRED"

    separate = simulate("SEPARATE AUTHORIZATION")
    assert separate["route"] == "separate_authorization"
    assert separate["status"] == "SEPARATE AUTHORIZATION REQUIRED"
    assert separate["authorizationUrl"] == "https://platform.minimax.io/h3-license"

    failed = simulate("LICENSE METADATA FAILURE")
    assert failed["verified"] is False
    assert failed["status"] == "LICENSE SETUP REQUIRED"

    changed = simulate("LICENSE VERSION CHANGED")
    assert changed["status"] == "LICENSE SETUP REQUIRED"


def test_regional_routes_follow_official_excluded_territories() -> None:
    from app.setup.model_license import definition_for, route_for_region

    definition = definition_for(MODEL)
    assert definition is not None
    assert definition["licenseName"] == "MiniMax H3 Community License"
    assert definition["licenseVersion"] == "2026-08-02"
    assert definition["licenseUrl"] == "https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE"
    assert definition["officialSource"] == "https://huggingface.co/MiniMaxAI/MiniMax-H3"
    assert definition["attributionRequired"] is True

    for code in ("CA", "JP", "AU", "BR", "MX"):
        assert route_for_region(definition, code) == "standard"
    for code in ("US", "GB", "KR", "DE", "FR", "IE", "SE"):
        assert route_for_region(definition, code) == "separate_authorization"
    assert route_for_region(definition, "") is None
    assert route_for_region(definition, "ZZ") is None


def test_fresh_user_keeps_installation_locked(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.lifecycle import service
    from app.setup.model_license import ModelLicenseLocked, license_summary_for_component

    summary = license_summary_for_component(H3)
    assert summary is not None
    assert summary["status"] == "LICENSE SETUP REQUIRED"
    assert summary["installationUnlocked"] is False
    assert summary["licenseName"] == "MiniMax H3 Community License"
    assert "regions" not in summary

    def fail_if_download(*_args, **_kwargs):
        raise AssertionError("download started")

    monkeypatch.setattr(service, "create_or_resume_install", fail_if_download)
    with pytest.raises(ModelLicenseLocked):
        service.install_component(H3, confirm=True, confirm_download_models=True)

    from app.setup.orchestrator import start_choose_install_location, start_link_existing_pack
    from app.setup_wizard import approve_install

    with pytest.raises(ModelLicenseLocked):
        start_link_existing_pack(H3)
    with pytest.raises(ModelLicenseLocked):
        start_choose_install_location(H3)
    with pytest.raises(ModelLicenseLocked):
        approve_install(H3, action="install")


def test_install_job_pipeline_stays_locked_until_acknowledgement(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup.model_license import ModelLicenseLocked
    from app.source_manager.install_jobs import service as jobs

    def fail_if_reached(*_args, **_kwargs):
        raise AssertionError("download started")

    monkeypatch.setattr(jobs, "get_component", fail_if_reached)
    with pytest.raises(ModelLicenseLocked):
        jobs.create_or_resume_install(H3, confirm=True, confirm_download_models=True)


def test_standard_region_unlocks_existing_installer(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.lifecycle import service
    from app.setup.model_license import acknowledge, public_view

    before = public_view(MODEL)
    assert before["installationUnlocked"] is False
    assert any(item["code"] == "CA" and item["route"] == "standard" for item in before["regions"])

    with pytest.raises(ValueError, match="Acknowledgement is required"):
        acknowledge(MODEL, "CA", confirmed=False)

    after = acknowledge(MODEL, "ca", confirmed=True)
    assert after["status"] == "LICENSE CONFIRMED"
    assert after["installationUnlocked"] is True
    assert after["route"] == "standard"
    assert after["region"] == "CA"
    assert after["message"] == "You have confirmed the applicable MiniMax licensing requirements."
    assert "legally permitted" not in after["message"].lower()

    calls: list[str] = []

    def fake_install(component_id, **_kwargs):
        calls.append(component_id)
        return {"component_id": component_id, "queued": False, "simulated": True}

    monkeypatch.setattr(service, "create_or_resume_install", fake_install)
    result = service.install_component(H3, confirm=True, confirm_download_models=False)
    assert calls == [H3]
    assert result["simulated"] is True

    # A model without a license definition keeps the existing installer.
    other = service.install_component("ltx_2_5_checkpoint", confirm=True, confirm_download_models=False)
    assert other["component_id"] == "ltx_2_5_checkpoint"
    assert calls == [H3, "ltx_2_5_checkpoint"]


def test_separate_authorization_region_stays_locked_until_confirmation(setup_data_dir: Path) -> None:
    from app.setup.model_license import ModelLicenseLocked, acknowledge, assert_installation_allowed, public_view

    view = public_view(MODEL)
    united_states = next(item for item in view["regions"] if item["code"] == "US")
    assert united_states["route"] == "separate_authorization"
    assert view["authorizationUrl"] == "https://platform.minimax.io/h3-license"

    with pytest.raises(ModelLicenseLocked):
        assert_installation_allowed(H3)

    confirmed = acknowledge(MODEL, "US", confirmed=True)
    assert confirmed["route"] == "separate_authorization"
    assert confirmed["status"] == "LICENSE CONFIRMED"
    assert confirmed["installationUnlocked"] is True
    assert_installation_allowed(H3)


def test_acknowledgement_persists_and_preserves_existing_install(setup_data_dir: Path) -> None:
    from app.setup.state import load_state, save_state
    from app.setup.model_license import acknowledge, public_view

    existing = {
        "components": {
            H3: {"status": "ready", "path": "D:/models/Video/MiniMax-H3"},
            "ltx_2_5_checkpoint": {"status": "ready", "path": "D:/models/ltx"},
        },
        "model_locations": {H3: "D:/models/Video/MiniMax-H3"},
    }
    save_state(existing)
    acknowledge(MODEL, "JP", confirmed=True)

    restored = load_state()
    assert restored["components"] == existing["components"]
    assert restored["model_locations"] == existing["model_locations"]
    record = restored["model_license_acknowledgements"][MODEL]
    assert record == {
        "model": MODEL,
        "license": "MiniMax H3 Community License",
        "license_version": "2026-08-02",
        "license_url": "https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE",
        "route": "standard",
        "region": "JP",
        "acknowledged": True,
        "acknowledged_at": record["acknowledged_at"],
    }
    assert record["acknowledged_at"]
    again = public_view(MODEL)
    assert again["status"] == "LICENSE CONFIRMED"
    assert again["installationUnlocked"] is True


def test_license_version_change_requires_acknowledgement_again(setup_data_dir: Path) -> None:
    from app.setup.model_license import acknowledge, public_view
    from app.setup.state import update_state

    acknowledge(MODEL, "CA", confirmed=True)
    assert public_view(MODEL)["installationUnlocked"] is True

    def stale(state: dict) -> None:
        state["model_license_acknowledgements"][MODEL]["license_version"] = "1999-01-01"

    update_state(stale)
    stale_view = public_view(MODEL)
    assert stale_view["installationUnlocked"] is False
    assert stale_view["status"] == "LICENSE SETUP REQUIRED"

    renewed = acknowledge(MODEL, "CA", confirmed=True)
    assert renewed["licenseVersion"] == "2026-08-02"
    assert renewed["installationUnlocked"] is True


def test_invalid_license_metadata_keeps_installation_locked(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.setup.model_license as model_license
    from app.setup.lifecycle import service

    broken = dict(model_license.definition_for(MODEL) or {})
    broken["licenseUrl"] = ""
    broken["licenseVersion"] = ""
    broken["regions"] = []
    monkeypatch.setitem(model_license._DEFINITIONS, MODEL, broken)

    view = model_license.public_view(MODEL)
    assert view["verified"] is False
    assert view["installationUnlocked"] is False
    assert view["message"] == "MiniMax H3 licensing information could not be verified."
    assert view["officialSource"] == "https://huggingface.co/MiniMaxAI/MiniMax-H3"

    def fail_if_download(*_args, **_kwargs):
        raise AssertionError("download started")

    monkeypatch.setattr(service, "create_or_resume_install", fail_if_download)
    with pytest.raises(model_license.ModelLicenseLocked):
        service.install_component(H3, confirm=True, confirm_download_models=True)
    with pytest.raises(model_license.ModelLicenseLocked):
        model_license.acknowledge(MODEL, "CA", confirmed=True)


def test_ready_h3_stays_ready_while_license_is_unacknowledged(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import status
    from app.setup.diagnostics import Verification
    from app.setup.model_license import acknowledge

    def fake_verify(component_id: str, state=None):
        if component_id == H3:
            return Verification(True, False, None, "ok", "D:/models/Video/MiniMax-H3", "installed")
        return Verification(True, False, None, "ok", "present", "1")

    monkeypatch.setattr(status, "verify_component", fake_verify)
    before = status.build_status()
    card = next(item for item in before["components"] if item["id"] == H3)
    assert card["status"] == "ready"
    assert card["installation_path"] == "D:/models/Video/MiniMax-H3"
    assert card["install_disabled"] is True
    assert card["model_license"]["status"] == "LICENSE SETUP REQUIRED"
    assert card["model_license"]["displayName"] == "MiniMax H3"
    assert card["primary_action"] is None

    acknowledge(MODEL, "CA", confirmed=True)
    status._STATUS_CACHE = None
    after = status.build_status()
    confirmed = next(item for item in after["components"] if item["id"] == H3)
    assert confirmed["status"] == "ready"
    assert confirmed["installation_path"] == "D:/models/Video/MiniMax-H3"
    assert confirmed["model_license"]["status"] == "LICENSE CONFIRMED"
    assert confirmed["model_license"]["installationUnlocked"] is True
    assert confirmed.get("install_disabled") is not True

    other = next(item for item in after["components"] if item["id"] == "ltx_2_5_checkpoint")
    assert "model_license" not in other
