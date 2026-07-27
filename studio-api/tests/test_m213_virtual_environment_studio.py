"""M2.13 Native 3D & Virtual Environment Studio proofs A-F + guards."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
EXPECTED_MANIFEST_SHA = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1", "true")
    # Isolate data dir if settings honor it
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "data"))
    # Fixture proofs below request synthetic environments, which is env-gated.
    monkeypatch.setenv("ADEPT_M213_FIXTURE_MODE", "1")
    from app.main import app
    from app import feature_flags as ff

    # Force-reload flag object fields for this process
    object.__setattr__(
        ff.feature_flags,
        "virtual_environment_studio_v1",
        True,
    ) if False else None
    # FeatureFlags is frozen dataclass — rebuild
    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def e2e_client(tmp_path, monkeypatch):
    """Client for the guided fixture slice, which is gated on STUDIO_E2E."""
    monkeypatch.setenv("STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1", "true")
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "data-e2e"))
    monkeypatch.setenv("STUDIO_E2E", "1")
    from app import feature_flags as ff
    from app.main import app

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    with TestClient(app) as c:
        yield c


def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1", raising=False)
    from app.feature_flags import FeatureFlags

    flags = FeatureFlags.from_env({})
    assert flags.virtual_environment_studio_v1 is False


def test_provider_manifest_sha_unchanged():
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert digest == EXPECTED_MANIFEST_SHA


def test_status_and_safety(client):
    r = client.get("/api/codirector/m213/status")
    assert r.status_code == 200
    body = r.json()
    assert body["flag"] == "virtual_environment_studio_v1"
    assert body["manifestSha256"] == EXPECTED_MANIFEST_SHA
    assert body["safety"]["noSilentColmapInstall"] is True
    assert "virtual-production-coordinator" == body["vpcSpecialist"]
    adapters = {a["name"]: a for a in body["adapters"]}
    assert adapters["fixture"]["available"] is True
    assert adapters["fixture"]["silentInstall"] is False


def test_disabled_returns_404(monkeypatch):
    monkeypatch.setenv("STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1", "false")
    from app import feature_flags as ff
    from app.main import app

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    with TestClient(app) as c:
        r = c.post("/api/codirector/m213/camera-spin", json={"projectId": "p", "fixture": True})
        assert r.status_code == 404


def test_proof_b_import_fixture(client, tmp_path):
    """Proof B: import GLB/fixture route B + approve."""
    src = tmp_path / "fixture.glb"
    # minimal glTF binary header magic
    src.write_bytes(b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 20)
    r = client.post(
        "/api/codirector/m213/import",
        json={"projectId": "p-b", "sourcePath": str(src), "fixture": True, "title": "Proof B"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["route"] == "imported_3d"
    assert body["approved"] is False
    assert body["fixture"] is True
    env_id = body["environmentId"]
    a = client.post(f"/api/codirector/m213/environments/{env_id}/approve", json={"note": "proof b"})
    assert a.status_code == 200
    assert a.json()["approved"] is True


def test_proof_c_camera_spin(client):
    """Proof C: camera-spin stitch levels."""
    r = client.post(
        "/api/codirector/m213/camera-spin",
        json={"projectId": "p-c", "fixture": True, "level": "C2_layers_2_5d"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "camera_spin"
    assert body["summary"]["stitch"]["fixture"] is True
    assert "honesty" in body["summary"]["stitch"]


def test_proof_a_reconstruction_fixture_and_no_silent_install(client):
    """Proof A: reconstruction assess + fixture; real adapters not silently installed."""
    adapters = client.get("/api/codirector/m213/reconstruction/adapters").json()["adapters"]
    assert any(a["name"] == "fixture" for a in adapters)
    for a in adapters:
        assert a.get("silentInstall") is False
    assess = client.post(
        "/api/codirector/m213/reconstruction/assess",
        json={"projectId": "p-a", "adapter": "fixture"},
    )
    assert assess.status_code == 200
    single = client.post(
        "/api/codirector/m213/reconstruction",
        json={"projectId": "p-a", "adapter": "fixture", "images": ["only.jpg"], "force": True},
    )
    assert single.status_code == 200
    body = single.json()
    assert body["inferred"] is True
    assert body["fixture"] is True
    assert "inferred" in body["assessment"]["honesty"].lower() or body["assessment"]["inferred"]


def test_proof_d_blocking(client):
    """Proof D: blocking canvas + approve."""
    spin = client.post(
        "/api/codirector/m213/camera-spin", json={"projectId": "p-d", "fixture": True}
    ).json()
    env_id = spin["environmentId"]
    b = client.post(
        "/api/codirector/m213/blocking",
        json={"projectId": "p-d", "environmentId": env_id, "presetId": "two_shot"},
    )
    assert b.status_code == 200
    body = b.json()
    assert body["approved"] is False
    assert len(body["state"]["channels"]) == 4
    ap = client.post(
        f"/api/codirector/m213/blocking/{body['id']}/approve", json={"note": "proof d"}
    )
    assert ap.json()["approved"] is True


def test_guided_slice_refused_outside_e2e(client, monkeypatch):
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    r = client.post("/api/codirector/m213/e2e/guided", json={"projectId": "p-e-prod", "fixture": True})
    assert r.status_code == 403


def test_proof_e_full_guided_e2e(e2e_client):
    """Proof E: source->env->blocking->camera/lighting->concept->timeline with persisted approvals."""
    client = e2e_client
    r = client.post("/api/codirector/m213/e2e/guided", json={"projectId": "p-e", "fixture": True})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["persistedApprovals"] is True
    assert body["realGeneration"] is False
    assert "source->env->blocking" in body["path"]
    assert body["published"]["ok"] is True
    assert body["plan"]["approvals"]
    assert body["dashboard"]["vpcSpecialist"] == "virtual-production-coordinator"


def test_proof_f_persistence_restore_recovery(e2e_client):
    """Proof F: versioned states + recovery."""
    client = e2e_client
    e2e = client.post("/api/codirector/m213/e2e/guided", json={"projectId": "p-f", "fixture": True}).json()
    env_id = e2e["environmentId"]
    restore = client.post(
        "/api/codirector/m213/restore",
        json={
            "projectId": "p-f",
            "environmentId": env_id,
            "restore": {"blocking": 1},
            "keep": {"scene_lighting": 1},
        },
    )
    assert restore.status_code == 200
    assert restore.json()["kept"]["scene_lighting"]["kept"] is True
    recovery = client.get("/api/codirector/m213/recovery", params={"projectId": "p-f"})
    assert recovery.status_code == 200
    assert recovery.json()["recoverable"] is True


def test_no_silent_approval_advance(client):
    plan = client.post(
        "/api/codirector/m213/plans", json={"projectId": "p-gate", "mode": "guided"}
    ).json()
    # Jump to F without environment approval should block when leaving E
    # First move to E
    a = client.post(
        f"/api/codirector/m213/plans/{plan['id']}/advance",
        json={"toStage": "E"},
    ).json()
    assert a["stage"] == "E"
    blocked = client.post(
        f"/api/codirector/m213/plans/{plan['id']}/advance",
        json={"toStage": "F"},
    ).json()
    assert blocked.get("advanced") is False
    assert blocked.get("silentAdvance") is False


def test_vpc_specialist_prompt_exists():
    prompt = ROOT / "studio-api/app/codirector/prompts/specialists/virtual-production-coordinator.md"
    text = prompt.read_text(encoding="utf-8")
    assert "id: virtual-production-coordinator" in text
    assert "may_execute_tools: false" in text


def test_capability_invoke_logged(client):
    r = client.post(
        "/api/codirector/m213/capabilities/invoke",
        json={
            "projectId": "p-cap",
            "capabilityId": "ve.vpc.coordinate",
            "action": "ping",
            "payload": {"x": 1},
            "reversible": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["schemaValidated"] is True


def test_concept_mock_labeled(client):
    spin = client.post(
        "/api/codirector/m213/camera-spin", json={"projectId": "p-con", "fixture": True}
    ).json()
    c = client.post(
        "/api/codirector/m213/concepts",
        json={
            "projectId": "p-con",
            "environmentId": spin["environmentId"],
            "tier": "draft",
            "forceMock": True,
        },
    ).json()
    assert c["generationMode"] == "mock"
    assert c["realGeneration"] is False
    assert "MOCK" in c["payload"]["honesty"].upper() or "FIXTURE" in c["payload"]["honesty"].upper()


def test_concept_defaults_refuse_mock_in_production(client, monkeypatch):
    """Without a real provider, the default request fails honestly instead of returning a mock."""
    monkeypatch.delenv("STUDIO_M213_REAL_CONCEPT_PROVIDER", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    spin = client.post(
        "/api/codirector/m213/camera-spin", json={"projectId": "p-con-real", "fixture": True}
    ).json()
    r = client.post(
        "/api/codirector/m213/concepts",
        json={"projectId": "p-con-real", "environmentId": spin["environmentId"], "tier": "draft"},
    )
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()


def test_camera_spin_defaults_to_real_frames(client):
    """SpinBody.fixture now defaults False, so an unqualified request is not a fixture spin."""
    from app.codirector.m213.api import SpinBody

    assert SpinBody(projectId="p").fixture is False


@pytest.fixture()
def production_client(tmp_path, monkeypatch):
    """Client with no fixture/E2E env — the shape a production deployment has."""
    monkeypatch.setenv("STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1", "true")
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "data-prod"))
    monkeypatch.delenv("ADEPT_M213_FIXTURE_MODE", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    from app import feature_flags as ff
    from app.main import app

    ff.feature_flags = ff.FeatureFlags.from_env(os.environ)
    with TestClient(app) as c:
        yield c


def test_camera_spin_refuses_synthetic_frames_outside_fixture(production_client):
    """M213-04: no frames + no fixture env must not fabricate a spin."""
    r = production_client.post(
        "/api/codirector/m213/camera-spin", json={"projectId": "p-prod-spin"}
    )
    assert r.status_code == 503
    assert "real captured frames" in r.json()["detail"]


def test_camera_spin_refuses_fixture_request_outside_fixture_env(production_client):
    """A client asking for fixture=true is a request, not authorisation."""
    r = production_client.post(
        "/api/codirector/m213/camera-spin",
        json={"projectId": "p-prod-spin-2", "fixture": True},
    )
    assert r.status_code == 503


def test_camera_spin_accepts_real_frames_without_fixture_env(production_client):
    frames = [
        {"index": i, "angle": float(i * 90), "assetId": f"asset-{i}"} for i in range(4)
    ]
    r = production_client.post(
        "/api/codirector/m213/camera-spin",
        json={"projectId": "p-prod-spin-3", "fixture": False, "frames": frames},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["fixture"] is False
    assert body["summary"]["ordered"]["count"] == 4


def test_reconstruct_adapter_defaults_to_detect(production_client):
    """M213-05: the fixture adapter is never selected implicitly."""
    from app.codirector.m213.api import ReconstructBody

    assert ReconstructBody(projectId="p").adapter == "detect"
    r = production_client.post(
        "/api/codirector/m213/reconstruction",
        json={"projectId": "p-prod-recon", "images": ["a.jpg", "b.jpg", "c.jpg"], "force": True},
    )
    assert r.status_code == 200
    body = r.json()
    if body["ok"] is False and body.get("requestedAdapter") == "detect":
        assert "No real reconstruction adapter is installed" in body["message"]
    else:
        # A real COLMAP/Nerfstudio/gsplat binary is installed on this machine.
        assert body.get("fixture") is not True


def test_import_security_rejects_traversal():
    from app.codirector.m213.import_security import validate_import_file

    v = validate_import_file("../etc/passwd")
    assert v.ok is False
