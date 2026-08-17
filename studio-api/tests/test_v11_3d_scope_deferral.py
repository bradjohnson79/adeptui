"""Version 1.1 native-3D scope lock: deferred status, readiness denominator, API gates."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_capability_cache():
    from app.capabilities import service

    service.invalidate_cache()
    yield
    service.invalidate_cache()


def test_deferred_status_excluded_from_readiness_denominator(client):
    res = client.get("/api/capabilities", params={"refresh": "true"})
    assert res.status_code == 200
    snap = res.json()
    deferred = snap.get("deferred") or []
    assert deferred, "expected deferred_version_1_2 capability ids"
    assert snap["readinessTotal"] == len(snap["capabilities"]) - len(deferred)
    by_id = {c["id"]: c for c in snap["capabilities"]}
    for cid in deferred:
        item = by_id[cid]
        assert item["status"] == "deferred_version_1_2"
        assert item["available"] is False
        assert item["reasonCode"] == "DEFERRED_VERSION_1_2"
        assert "Coming in Version 1.2" in (item["message"] or "") or "Version 1.2" in (
            item["message"] or ""
        )


def test_deferred_never_in_blockers_or_callable(client):
    snap = client.get("/api/capabilities", params={"refresh": "true"}).json()
    deferred = set(snap.get("deferred") or [])
    assert deferred.isdisjoint(set(snap.get("callable") or []))
    blocker_ids = {b["capabilityId"] for b in snap.get("blockers") or []}
    assert deferred.isdisjoint(blocker_ids)


def test_health_registry_total_excludes_deferred(client):
    # /api/health is liveness-only; registry totals live on /api/capabilities.
    caps = client.get("/api/capabilities", params={"refresh": "true"}).json()
    health = client.get("/api/health").json()
    assert caps.get("readinessTotal") is not None
    assert (health.get("operator") or {}).get("virtualStageEnabled") is False
    assert (health.get("operator") or {}).get("virtualEnvironmentStudioEnabled") is False


def test_m213_import_returns_canonical_deferred(client):
    res = client.post(
        "/api/codirector/m213/import",
        json={"projectId": "p", "sourcePath": "C:/tmp/mesh.glb", "title": "x"},
    )
    assert res.status_code == 403
    detail = res.json().get("detail") or {}
    assert detail.get("code") == "DEFERRED_VERSION_1_2"
    assert "Version 1.2" in (detail.get("message") or "")


def test_virtual_stage_create_returns_canonical_deferred(client):
    res = client.post(
        "/api/codirector/m28/virtual-stage",
        json={"projectId": "p", "sceneId": "s", "name": "Stage"},
    )
    assert res.status_code == 403
    detail = res.json().get("detail") or {}
    assert detail.get("code") == "DEFERRED_VERSION_1_2"
    assert detail.get("message") == (
        "Native 3D importing and animation are planned for Adept UI Version 1.2."
    )


def test_native_3d_capabilities_are_deferred(client):
    by_id = {c["id"]: c for c in client.get("/api/capabilities", params={"refresh": "true"}).json()["capabilities"]}
    for cid in (
        "3d.mesh",
        "3d.rigging",
        "3d.animation",
        "3d.mocap_import",
        "ve.import.validate",
        "virtual_stage.render",
    ):
        assert by_id[cid]["status"] == "deferred_version_1_2", cid


def test_game_cinematic_library_has_no_3d_slot():
    from app.templates_presets.catalog.project_types import get_builtin_project_type

    gc = get_builtin_project_type("game_cinematic")
    assert gc is not None
    lib = list(gc.profile.library_emphasis)
    assert "3D" not in lib
    assert "Scenes" in lib
