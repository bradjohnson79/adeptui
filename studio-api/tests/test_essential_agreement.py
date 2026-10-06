"""Essential Components agreement + Spatial Intelligence registration."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def agreement_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import diagnostics as setup_diagnostics
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    setup_status._STATUS_CACHE = None
    setup_diagnostics._VERIFY_CACHE.clear()
    return tmp_path


def test_notice_and_registry_exist():
    from app.setup.essential_agreement import CURRENT_VERSION, _document_path, document_available

    path = _document_path()
    assert path.is_file()
    body = path.read_text(encoding="utf-8")
    assert CURRENT_VERSION == "2026.08.1"
    assert "MoGe-2 Geometry Reconstruction" in body
    assert "VGGT-1B Commercial Geometry Reconstruction" in body
    assert "facebook/VGGT-1B-Commercial" in body
    assert "facebook/VGGT-1B" in body
    assert "OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION" in body
    assert "Acceptable Use Policy" in body
    assert document_available() is True
    registry = Path(__file__).resolve().parents[2] / "docs" / "setup" / "ESSENTIAL_COMPONENT_REGISTRY.md"
    assert registry.is_file()
    text = registry.read_text(encoding="utf-8")
    assert "moge2_geometry" in text
    assert "vggt_1b_commercial" in text


def test_moge_and_vggt_are_essentials_not_peripheral(agreement_dir: Path):
    from app.setup.catalog import get_component
    from app.setup.essentials_pack import ESSENTIAL_IDS, pack_status
    from app.setup.license_metadata import PERIPHERAL_COMPONENT_IDS, inspect_split_license, is_peripheral

    assert "moge2_geometry" in ESSENTIAL_IDS
    assert "vggt_1b_commercial" in ESSENTIAL_IDS
    assert get_component("moge2_geometry").name == "MoGe-2 Geometry Reconstruction"
    assert get_component("vggt_1b_commercial").name == "VGGT-1B Commercial Geometry Reconstruction"
    moge = inspect_split_license("moge2_geometry")
    vggt = inspect_split_license("vggt_1b_commercial")
    assert moge["code_license"].startswith("MIT")
    assert moge["weights_license"] == "unconfirmed"
    assert "MIT" not in moge["weights_license"]
    assert "Apache" not in moge["weights_license"]
    assert moge["license_status"] == "OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION"
    assert moge["owner_policy"] == "PERMITTED"
    assert vggt["license_status"] == "MODEL_ACCESS_GATED"
    assert vggt["license_status_secondary"] == "REQUIRES_EXTERNAL_ACCEPTANCE"
    assert vggt["model_source"] == "facebook/VGGT-1B-Commercial"
    assert vggt["owner_policy"] == "PERMITTED"
    assert is_peripheral("moge2_geometry") is False
    assert is_peripheral("vggt_1b_commercial") is False
    for peripheral in ("comfyui", "qwen_image_2512_models", "flux1_dev_local", "vjepa2_world_intelligence"):
        assert peripheral in PERIPHERAL_COMPONENT_IDS or is_peripheral(peripheral)
        assert peripheral not in ESSENTIAL_IDS
    status = pack_status()
    ids = {row["id"] for row in status["components"]}
    assert "moge2_geometry" in ids
    assert "vggt_1b_commercial" in ids
    spatial = next(group for group in status["groups"] if group["id"] == "spatial_intelligence")
    assert "moge2_geometry" in spatial["componentIds"]
    assert "vggt_1b_commercial" in spatial["componentIds"]


def test_inspect_license_splits_fields(client):
    moge = client.get("/api/setup/lifecycle/components/moge2_geometry/license")
    assert moge.status_code == 200
    payload = moge.json()
    assert payload["code_license"]
    assert payload["weights_license"] == "unconfirmed"
    assert payload["license_status"] == "OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION"
    assert payload["owner_policy"] == "PERMITTED"
    vggt = client.get("/api/setup/lifecycle/components/vggt_1b_commercial/license").json()
    assert vggt["license_status"] == "MODEL_ACCESS_GATED"
    assert vggt["modelSource"] == "facebook/VGGT-1B-Commercial"


def test_get_agreement_serves_document(client):
    response = client.get("/api/setup/essential-agreement")
    assert response.status_code == 200
    payload = response.json()
    assert payload["currentVersion"] == "2026.08.1"
    assert payload["documentAvailable"] is True
    assert payload["accepted"] is False
    assert "MoGe-2" in payload["body"]
    assert "VGGT-1B-Commercial" in payload["body"]
    ids = {row["component_id"] for row in payload["registry"]}
    assert "moge2_geometry" in ids
    assert "vggt_1b_commercial" in ids


def test_install_blocked_until_accepted(client, agreement_dir: Path):
    blocked = client.post(
        "/api/setup/lifecycle/components/moge2_geometry/install",
        json={"confirm": True, "confirmDownloadModels": False},
    )
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] in {"ESSENTIAL_AGREEMENT_REQUIRED", "ESSENTIAL_AGREEMENT_DECLINED"}
    assert detail["eligible"] is False
    vggt = client.post(
        "/api/setup/lifecycle/components/vggt_1b_commercial/install-job",
        json={"confirm": True},
    )
    assert vggt.status_code == 409


def test_accept_stale_version_and_decline(client, agreement_dir: Path):
    stale = client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2025.01.0", "documentAvailableConfirmed": True},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "UPDATED_TERMS_REQUIRE_AGREEMENT"

    accepted = client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2026.08.1", "documentAvailableConfirmed": True},
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert accepted.json()["eligible"] is True

    reload_payload = client.get("/api/setup/essential-agreement").json()
    assert reload_payload["accepted"] is True
    assert reload_payload["acceptedVersion"] == "2026.08.1"

    moge = client.post(
        "/api/setup/lifecycle/components/moge2_geometry/install",
        json={"confirm": True},
    )
    assert moge.status_code != 409

    declined = client.post("/api/setup/essential-agreement/decline")
    assert declined.status_code == 200
    assert declined.json()["eligible"] is False
    blocked = client.post(
        "/api/setup/lifecycle/components/moge2_geometry/install",
        json={"confirm": True},
    )
    assert blocked.status_code == 409


def test_document_unavailable_never_auto_accepts(client, agreement_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_ESSENTIAL_NOTICE_PATH", str(agreement_dir / "missing-notice.md"))
    payload = client.get("/api/setup/essential-agreement").json()
    assert payload["documentAvailable"] is False
    assert payload["accepted"] is False
    missing = client.get("/api/setup/essential-agreement/document")
    assert missing.status_code == 503
    accept = client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2026.08.1", "documentAvailableConfirmed": True},
    )
    assert accept.status_code == 409
    assert accept.json()["detail"]["code"] == "ESSENTIAL_NOTICE_UNAVAILABLE"
    fake = client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2026.08.1", "documentAvailableConfirmed": False},
    )
    assert fake.status_code == 409


def test_version_bump_requires_reagree(client, agreement_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    first = client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2026.08.1", "documentAvailableConfirmed": True},
    )
    assert first.status_code == 200
    bumped = client.post("/api/e2e/essential-agreement/set-version", json={"version": "2026.08.2"})
    if bumped.status_code == 404:
        from app.setup.essential_agreement import set_e2e_current_version

        set_e2e_current_version("2026.08.2")
    else:
        assert bumped.status_code == 200
    state = client.get("/api/setup/essential-agreement").json()
    assert state["accepted"] is False
    assert state["code"] == "UPDATED_TERMS_REQUIRE_AGREEMENT"
    blocked = client.post(
        "/api/setup/lifecycle/components/moge2_geometry/install",
        json={"confirm": True},
    )
    assert blocked.status_code == 409
    again = client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2026.08.2", "documentAvailableConfirmed": True},
    )
    assert again.status_code == 200
    assert again.json()["accepted"] is True


def test_vggt_gated_does_not_block_moge_after_agreement(client, agreement_dir: Path):
    client.post(
        "/api/setup/essential-agreement/accept",
        json={"version": "2026.08.1", "documentAvailableConfirmed": True},
    )
    from app.setup.essential_agreement import independence_gate
    from app.spatial_map.geometry.vggt_runtime import runtime_status
    from app.setup.license_metadata import is_model_access_gated

    moge = independence_gate("moge2_geometry")
    assert moge["ok"] is True
    assert moge["blockedByVggt"] is False
    assert is_model_access_gated("vggt_1b_commercial") is True
    vggt = runtime_status()
    assert vggt["status"] == "model_access_gated"
    assert vggt["runtimeReady"] is False
    assert vggt["modelReady"] is False
    badges = client.get("/api/setup/essential-agreement/readiness/vggt_1b_commercial").json()
    assert badges["agreementAccepted"] is True
    assert badges["ready"] is False
    assert badges["commercialModelAccess"] is False
    moge_badges = client.get("/api/setup/essential-agreement/readiness/moge2_geometry").json()
    assert moge_badges["agreementAccepted"] is True
    assert moge_badges["ready"] is False


def test_downloads_and_link_existing_are_gated(client, agreement_dir: Path):
    downloads = client.post(
        "/api/downloads",
        json={"componentId": "moge2_geometry", "destinationRoot": str(agreement_dir / "dest")},
    )
    assert downloads.status_code == 409
    assert downloads.json()["detail"]["code"] in {
        "ESSENTIAL_AGREEMENT_REQUIRED",
        "ESSENTIAL_AGREEMENT_DECLINED",
    }
    link = client.post("/api/setup/components/moge2_geometry/link-existing")
    assert link.status_code == 409
    jobs = client.post("/api/setup/install-jobs", json={"componentId": "moge2_geometry", "confirm": True})
    assert jobs.status_code == 409
    assert isinstance(jobs.json()["detail"], dict)


def test_clone_is_not_vggt_ready(agreement_dir: Path):
    from app.spatial_map.geometry.vggt_runtime import assert_commercial_model_only, runtime_status

    (agreement_dir / "runtimes" / "vggt" / ".git").mkdir(parents=True)
    status = runtime_status()
    assert status["sourceInstalled"] is True
    assert status["ready"] is False if "ready" in status else status["runtimeReady"] is False
    assert status["modelReady"] is False
    with pytest.raises(ValueError, match="VGGT-1B-Commercial"):
        assert_commercial_model_only("facebook/VGGT-1B")
