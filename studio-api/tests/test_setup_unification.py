"""Adept Setup scan, review plan, updates, and clean-machine simulation."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return tmp_path


def test_windows_disk_scan_uses_disk_usage(isolated_lifecycle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    from app.setup.lifecycle import service

    root = isolated_lifecycle / "models"
    root.mkdir()
    class _Usage:
        total = 1000
        used = 400
        free = 600

    monkeypatch.setattr(service, "query_gpu_stats", lambda: {"gpus": []})
    monkeypatch.setattr("app.setup.paths.default_models_root", lambda: root)
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: _Usage())

    hardware = service.inspect_hardware()

    assert hardware["freeBytes"] == 600
    assert hardware["totalBytes"] == 1000
    assert hardware["modelsRoot"] == str(root)


def test_plan_blocks_when_disk_cannot_cover_install(isolated_lifecycle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import unification

    monkeypatch.setattr(
        unification,
        "build_install_plan",
        lambda component_id, **_kwargs: type("Plan", (), {"model_dump": lambda self, mode="json": {"componentId": component_id}})(),
    )
    plan = unification.build_recommendation_plan(
        ["python"],
        free_bytes=1,
        verifications={"python": {"healthy": False, "absent": True, "path": None}},
        vram_gb=32.0,
        destination_root=str(isolated_lifecycle / "models"),
    )

    assert plan["diskBlocked"] is True
    assert plan["requiresApproval"] is True
    assert plan["jobs"] == []
    assert plan["installedBytes"] > 1


def test_install_requires_approval_before_job(isolated_lifecycle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import unification

    calls: list[dict] = []

    def _fake_job(component_id: str, **kwargs):
        calls.append({"componentId": component_id, **kwargs})
        return {"componentId": component_id, "state": "queued", "confirm": kwargs.get("confirm")}

    monkeypatch.setattr(unification, "create_install_job", _fake_job)
    monkeypatch.setattr(
        unification,
        "verify_component",
        lambda component_id: type("V", (), {"healthy": False, "absent": True, "path": None})(),
    )

    blocked = unification.approve_recommendation_plan(["python"], confirm=False)
    assert blocked["approved"] is False
    assert blocked["jobs"] == []
    assert calls == []

    approved = unification.approve_recommendation_plan(["python"], confirm=True)
    assert approved["approved"] is True
    assert calls[0]["confirm"] is True
    assert calls[0]["componentId"] == "python"


def test_update_classification_does_not_replace_a_healthy_pin(isolated_lifecycle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.catalog import get_component
    from app.setup import unification

    component = get_component("python")
    monkeypatch.setattr(unification, "public_components", lambda: (component,))
    monkeypatch.setattr(
        unification,
        "check_updates",
        lambda _component_id: {
            "updateAvailable": False,
            "currentCertifiedVersion": "1",
            "latestCertifiedVersion": "1",
            "reason": "Already on latest certified recipe.",
        },
    )
    monkeypatch.setattr(
        unification,
        "verify_component",
        lambda _component_id: type("V", (), {"healthy": True, "absent": False, "path": "C:/python"})(),
    )

    plan = unification.check_update_plan(force=True)

    assert plan["available"] is True
    assert plan["unhealthy"] is False
    assert plan["rollbackAvailable"] is False
    assert plan["items"] == []


def test_update_check_failure_stays_available_message(isolated_lifecycle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.catalog import get_component
    from app.setup import unification

    monkeypatch.setattr(unification, "public_components", lambda: (get_component("python"),))

    def _boom(_component_id: str):
        raise RuntimeError("offline")

    monkeypatch.setattr(unification, "check_updates", _boom)
    plan = unification.check_update_plan(force=True)

    assert plan["available"] is False
    assert plan["message"] == "Update check unavailable"
    assert plan["unhealthy"] is False


def test_clean_machine_simulation_readies_essentials_without_live_ready(isolated_lifecycle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import unification
    from app.source_manager.install_jobs.states import InstallState

    live_calls: list[str] = []

    def _live_verify(component_id: str):
        live_calls.append(component_id)
        raise AssertionError("simulation must not use live verify_component for Ready")

    monkeypatch.setattr(unification, "verify_component", _live_verify)
    monkeypatch.setattr(
        unification,
        "build_install_plan",
        lambda component_id, **_kwargs: type("Plan", (), {"model_dump": lambda self, mode="json": {"componentId": component_id}})(),
    )
    monkeypatch.setattr(unification, "default_models_root", lambda: isolated_lifecycle / "models")

    artifacts: list[str] = []
    result = unification.simulate_clean_machine(
        free_bytes=10**15,
        verifier=lambda component_id: {"healthy": True, "fixture": True, "componentId": component_id},
        artifact_ready=artifacts.append,
    )

    assert result["ok"] is True, result["failures"]
    assert "python" in result["ready"]
    assert "ffmpeg" in result["ready"]
    assert "comfyui" in result["ready"]
    assert "minimax_h3_base_optimized" in result["ready"]
    assert result["liveReady"] is False
    assert live_calls == []
    assert artifacts
    assert unification.legal_install_transition(InstallState.QUEUED.value, InstallState.READY.value, approved=True) is False
    assert unification.legal_install_transition(
        InstallState.AWAITING_CONFIRMATION.value,
        InstallState.QUEUED.value,
        approved=False,
    ) is False
