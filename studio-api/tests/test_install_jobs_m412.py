from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_install_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "comfy_input_dir", tmp_path / "missing-comfy" / "input")
    if hasattr(settings, "comfy_models_dir"):
        monkeypatch.setattr(settings, "comfy_models_dir", None)
    return tmp_path


def test_download_operation_maps_to_install_job() -> None:
    from app.source_manager.downloads.models import create_install_plan, create_operation
    from app.source_manager.install_jobs.adapter import download_operation_to_install_job

    plan = create_install_plan(
        component_id="pack_essential_photoreal",
        source_id="src_123",
        provider_id="direct_http",
        artifacts=[{"remotePath": "pack.zip", "destinationRelativePath": "pack.zip", "expectedSize": 100}],
        destination_root="C:/Models/Pack",
        estimated_download_bytes=100,
        estimated_extracted_bytes=200,
    )
    operation = create_operation(plan, priority=55)
    operation["phase"] = "downloading"
    operation["queuePosition"] = 2
    operation["progress"]["bytesDownloaded"] = 25
    operation["progress"]["bytesTotal"] = 100
    operation["progress"]["percent"] = 25.0
    operation["progress"]["artifactsCompleted"] = 0
    operation["progress"]["artifactsTotal"] = 1

    job = download_operation_to_install_job(operation)

    assert job.state.value == "downloading"
    assert job.progress_bytes == 25
    assert job.total_bytes == 100
    assert job.queue_position == 2
    assert job.active is True
    assert job.terminal is False


def test_download_operation_maps_legacy_numeric_progress() -> None:
    from app.source_manager.downloads.models import create_install_plan, create_operation
    from app.source_manager.install_jobs.adapter import download_operation_to_install_job

    plan = create_install_plan(
        component_id="pack_essential_photoreal",
        source_id="src_legacy",
        provider_id="direct_http",
        artifacts=[{"remotePath": "pack.zip", "destinationRelativePath": "pack.zip", "expectedSize": 100}],
        destination_root="C:/Models/Pack",
        estimated_download_bytes=100,
        estimated_extracted_bytes=200,
    )
    operation = create_operation(plan, priority=55)
    operation["phase"] = "downloading"
    operation["progress"] = 0.25

    job = download_operation_to_install_job(operation)

    assert job.state.value == "downloading"
    assert job.percent == 25.0
    assert job.progress_bytes is None
    assert job.total_bytes is None


def test_build_provider_plan_uses_official_pack_source_without_saved_assignment(
    isolated_install_jobs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.setup.pack_providers.base import ResolvedPackDownload
    from app.source_manager.install_jobs import service

    monkeypatch.setenv("ADEPT_PACK_PROVIDER", "fixture_http")

    def fake_resolve_pack_download(component_id: str, *, force_refresh: bool = False) -> ResolvedPackDownload:
        assert component_id == "pack_essential_photoreal"
        return ResolvedPackDownload(
            pack_id=component_id,
            version="1.0.0",
            source_provider="fixture_http",
            download_url="http://127.0.0.1:8765/assets/pack_essential_photoreal/pack_essential_photoreal-1.0.0.zip",
            expected_bytes=422,
            checksum_algorithm="sha256",
            checksum="deadbeef",
            archive_format="zip",
            required_files=["pack.json"],
            tag_name="v1.0.0",
            archive_asset_name="pack_essential_photoreal-1.0.0.zip",
            repository="fixture/pack_essential_photoreal",
        )

    monkeypatch.setattr(service, "get_assignment", lambda _component_id: None)
    monkeypatch.setattr(service, "get_source", lambda _source_id: None)
    monkeypatch.setattr("app.setup.pack_manifests.resolve_pack_download", fake_resolve_pack_download)

    plan, source_record, assignment = service._build_provider_plan(
        "pack_essential_photoreal",
        install_path=str(isolated_install_jobs / "packs" / "photoreal"),
    )

    assert assignment == {}
    assert source_record["officialDefault"] is True
    assert source_record["provider"] == "fixture"
    assert plan["providerId"] == "fixture"
    assert plan["artifacts"][0]["downloadUrl"].startswith("http://127.0.0.1:8765/assets/")


def test_error_normalization_maps_to_install_star_codes() -> None:
    from app.source_manager.install_jobs.errors import normalize_failure

    failure = {
        "category": "disk_full",
        "message": "No free space left on device.",
        "phase": "preflighting",
        "details": {"requiredFreeBytes": 123},
    }

    error = normalize_failure(failure)

    assert error.code.value == "INSTALL_DISK_SPACE_INSUFFICIENT"
    assert error.title == "Not enough disk space"
    assert error.user_message == "No free space left on device."
    assert error.recommended_action == "change_destination"
    assert error.details["requiredFreeBytes"] == 123


def test_multi_phase_percent_never_reaches_100_until_ready() -> None:
    from app.source_manager.install_jobs.phases import build_phase_steps, overall_percent
    from app.source_manager.install_jobs.states import InstallState

    steps = build_phase_steps(InstallState.DOWNLOADING, phase="downloading")
    assert steps[0]["status"] == "complete"
    assert steps[1]["status"] == "active"
    assert steps[-1]["status"] == "pending"

    percent = overall_percent(
        state=InstallState.DOWNLOADING,
        phase="downloading",
        download_percent=100.0,
        ready=False,
    )
    assert percent is not None
    assert percent < 100.0

    ready_percent = overall_percent(
        state=InstallState.READY,
        phase="completed",
        download_percent=100.0,
        ready=True,
    )
    assert ready_percent == 100.0


def test_stall_detector_distinguishes_slow_alive_interrupted_and_source_silent() -> None:
    from app.source_manager.install_jobs.heartbeat import (
        InstallHeartbeat,
        evaluate_stall,
        stall_recovery_actions,
        stall_threshold_seconds,
    )
    from app.source_manager.install_jobs.states import InstallState

    assert stall_threshold_seconds("index_tts2") >= 300
    assert stall_threshold_seconds("comfyui_hunyuan_nodes") <= 120

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(seconds=10)).isoformat()
    old = (now - timedelta(seconds=900)).isoformat()

    alive = InstallHeartbeat(
        jobId="j1",
        lastProgressAt=recent,
        lastBytesDownloaded=10,
        lastPhaseChangeAt=recent,
        workerAlive=True,
        networkActive=True,
    )
    assert evaluate_stall(state=InstallState.DOWNLOADING, component_id="pack_essential_photoreal", heartbeat=alive, now=now) == "none"

    stalled = InstallHeartbeat(
        jobId="j2",
        lastProgressAt=old,
        lastBytesDownloaded=10,
        lastPhaseChangeAt=old,
        workerAlive=True,
        networkActive=False,
    )
    assert (
        evaluate_stall(state=InstallState.DOWNLOADING, component_id="pack_essential_photoreal", heartbeat=stalled, now=now)
        == "possible_stall"
    )

    waiting = InstallHeartbeat(
        jobId="j3",
        lastProgressAt=old,
        lastBytesDownloaded=10,
        lastPhaseChangeAt=old,
        workerAlive=True,
        networkActive=True,
    )
    assert (
        evaluate_stall(state=InstallState.DOWNLOADING, component_id="pack_essential_photoreal", heartbeat=waiting, now=now)
        == "waiting_for_source"
    )

    dead = InstallHeartbeat(
        jobId="j4",
        lastProgressAt=recent,
        lastBytesDownloaded=10,
        lastPhaseChangeAt=recent,
        workerAlive=False,
    )
    assert evaluate_stall(state=InstallState.INSTALLING, component_id="index_tts2", heartbeat=dead, now=now) == "interrupted"

    actions = stall_recovery_actions("possible_stall")
    assert {item["action"] for item in actions} >= {
        "retry_connection",
        "resume",
        "restart_worker",
        "open_diagnostics",
        "cancel_safely",
    }


def test_requirements_resolution_for_hunyuan_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.source_manager.install_jobs import requirements

    def fake_readiness(workflow_id: str, *, node_types=None, model_states=None):
        return {
            "requiredNodeTypes": ["HunyuanVideo15Loader", "VHS_VideoCombine"],
            "missingExtensions": ["HunyuanVideo15Loader"],
            "requiredComponentIds": ["hunyuan_video_15"],
            "missingModels": [],
            "message": f"{workflow_id} is blocked on Hunyuan nodes.",
        }

    monkeypatch.setattr(requirements, "_live_node_types", lambda: set())
    monkeypatch.setattr(requirements, "workflow_readiness", fake_readiness)

    resolution = requirements.resolve_requirements("hunyuan15")

    assert resolution.workflow_ids
    assert "HunyuanVideo15Loader" in resolution.missing_node_types
    assert resolution.node_resolutions[0].extension_component_id is None
    assert resolution.node_resolutions[0].source_status == "user_required"
    assert "No catalogued extension component" in resolution.node_resolutions[0].message
    assert resolution.recommended_action == "install_comfyui_extensions"


def test_source_validate_rejects_bad_url() -> None:
    from app.source_manager.install_jobs.sources import validate_source

    result = validate_source("pack_essential_photoreal", "file:///tmp/not-allowed")

    assert result["ok"] is False
    assert result["blocking_errors"]


def test_index_tts2_install_does_not_silently_enable_model_download(
    isolated_install_jobs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.source_manager.install_jobs import service
    from app.source_manager.install_jobs.schema import InstallJob
    from app.source_manager.install_jobs.states import InstallState

    captured: dict[str, bool] = {}

    def fake_start(component_id: str, *, confirm_download_models: bool, force: bool):
        captured["confirm_download_models"] = confirm_download_models
        captured["force"] = force
        job = InstallJob(
            id="ij_index",
            componentId=component_id,
            componentName="IndexTTS2",
            state=InstallState.QUEUED,
            kind="custom_install",
            phase="queued",
            message="queued",
            indeterminate=True,
            active=True,
            terminal=False,
            source={"providerId": "index-tts2-local", "confirmDownloadModels": confirm_download_models},
            createdAt="2026-08-01T00:00:00+00:00",
            updatedAt="2026-08-01T00:00:00+00:00",
        )
        service._persist_job(job)
        return job

    monkeypatch.setattr(service, "_start_index_tts2_job", fake_start)

    job = service.create_or_resume_install(
        "index_tts2",
        confirm=True,
        confirm_download_models=False,
    )

    assert captured == {"confirm_download_models": False, "force": False}
    assert job["source"]["confirmDownloadModels"] is False


def test_avatar_runtime_component_registration_uses_isolated_runtime_path(
    isolated_install_jobs: Path,
) -> None:
    from app.setup.catalog import get_component
    from app.setup.paths import suggested_install_path

    component = get_component("musetalk-1-5-local")

    assert component.installer == "avatar_runtime"
    assert component.verifier == "avatar_runtime"
    assert component.category == "Avatar Runtimes"
    assert suggested_install_path("musetalk-1-5-local").endswith("runtimes\\avatar\\musetalk-1-5")


def test_avatar_runtime_install_requires_confirm_download_models(
    isolated_install_jobs: Path,
) -> None:
    from app.source_manager.install_jobs import service

    job = service.create_or_resume_install(
        "musetalk-1-5-local",
        confirm=True,
        confirm_download_models=False,
    )

    assert job["state"] == "awaiting_confirmation"
    assert job["error"]["code"] == "INSTALL_CONFIRM_REQUIRED"
    assert "model-download confirmation" in job["message"]


def test_avatar_runtime_install_dispatches_custom_job(
    isolated_install_jobs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.source_manager.install_jobs import service
    from app.source_manager.install_jobs.schema import InstallJob
    from app.source_manager.install_jobs.states import InstallState

    captured: dict[str, object] = {}

    def fake_start(
        component_id: str,
        *,
        confirm_download_models: bool,
        force: bool,
        source_url: str | None,
        install_path: str | None,
    ):
        captured.update(
            {
                "component_id": component_id,
                "confirm_download_models": confirm_download_models,
                "force": force,
                "source_url": source_url,
                "install_path": install_path,
            }
        )
        job = InstallJob(
            id="ij_avatar",
            componentId=component_id,
            componentName="MuseTalk 1.5",
            state=InstallState.QUEUED,
            kind="custom_install",
            phase="queued",
            message="queued",
            indeterminate=True,
            active=True,
            terminal=False,
            source={"providerId": component_id, "confirmDownloadModels": confirm_download_models},
            destination=install_path,
            createdAt="2026-08-01T00:00:00+00:00",
            updatedAt="2026-08-01T00:00:00+00:00",
        )
        service._persist_job(job)
        return job

    monkeypatch.setattr(service, "_start_avatar_runtime_job", fake_start)

    job = service.create_or_resume_install(
        "musetalk-1-5-local",
        confirm=True,
        confirm_download_models=True,
        install_path=str(isolated_install_jobs / "avatar-runtime"),
    )

    assert captured == {
        "component_id": "musetalk-1-5-local",
        "confirm_download_models": True,
        "force": False,
        "source_url": None,
        "install_path": str(isolated_install_jobs / "avatar-runtime"),
    }
    assert job["id"] == "ij_avatar"
    assert job["state"] == "queued"


def test_create_job_and_get_job_roundtrip(
    isolated_install_jobs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.source_manager.install_jobs import service

    monkeypatch.setattr(service, "_CUSTOM_THREADS", {})

    created = service.create_or_resume_install("pack_essential_photoreal", confirm=True)
    fetched = service.get_job(created["id"])

    assert created["id"] == fetched["id"]
    assert fetched["componentId"] == "pack_essential_photoreal"
    assert fetched["state"] == "source_required"
    assert (isolated_install_jobs / "source_manager" / "install_jobs" / f"{created['id']}.json").is_file()
    assert fetched["error"]["code"] == "INSTALL_SOURCE_MISSING"


def test_comfy_extension_clone_does_not_mark_ready(
    isolated_install_jobs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer
    from app.source_manager.install_jobs import service
    from app.source_manager.install_jobs.states import InstallState
    import time

    custom_nodes = isolated_install_jobs / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    monkeypatch.setattr(installer, "resolve_custom_nodes_dir", lambda explicit=None: custom_nodes)
    monkeypatch.setattr(
        installer,
        "resolve_extension_source",
        lambda component_id, source_url=None: {
            "url": "https://github.com/example/ComfyUI-HunyuanVideoWrapper",
            "revision": None,
            "packageName": "ComfyUI-HunyuanVideoWrapper",
            "provider": "git",
            "officialDefault": True,
            "executesCode": True,
        },
    )
    monkeypatch.setattr(
        installer,
        "clone_or_update_extension",
        lambda **kwargs: {
            "ok": True,
            "step": "clone",
            "message": "cloned",
            "path": str(custom_nodes / "ComfyUI-HunyuanVideoWrapper"),
        },
    )
    monkeypatch.setattr(
        installer,
        "install_extension_dependencies",
        lambda target: {"ok": True, "skipped": True, "message": "no deps"},
    )
    monkeypatch.setattr(installer, "probe_required_nodes", lambda required=None: {
        "ok": False,
        "available": True,
        "missing": ["HyVideoModelLoader"],
        "detected": [],
        "message": "0 of 1 nodes detected",
    })

    job = service.create_or_resume_install("comfyui_hunyuan_nodes", confirm=True)
    job_id = job["id"]

    deadline = time.time() + 5
    while time.time() < deadline:
        current = service.get_job(job_id)
        if current.get("phase") == "restart_required":
            break
        time.sleep(0.05)
    current = service.get_job(job_id)
    assert current["state"] == InstallState.CONFIGURING.value
    assert current["phase"] == "restart_required"
    assert current.get("raw", {}).get("nodesReady") is False
    assert current["state"] != "ready"

    # Simulate restart + still missing nodes
    monkeypatch.setattr(
        installer,
        "restart_comfyui_best_effort",
        lambda: {"ok": True, "method": "fixture"},
    )
    repaired = service.repair(job_id, "restart_comfyui")
    assert repaired["state"] == "repair_required"
    assert repaired["error"]["code"] == "INSTALL_EXTENSION_MISSING"

    # Nodes appear after restart probe
    monkeypatch.setattr(
        installer,
        "probe_required_nodes",
        lambda required=None: {
            "ok": True,
            "available": True,
            "missing": [],
            "detected": ["HyVideoModelLoader"],
            "message": "1 of 1 nodes detected",
        },
    )
    ready = service.repair(job_id, "reverify")
    assert ready["state"] == "ready"
    assert ready["progress"]["percent"] == 100.0


def test_serialize_includes_heartbeat_and_phase_steps(
    isolated_install_jobs: Path,
) -> None:
    from app.source_manager.install_jobs import service
    from app.source_manager.install_jobs.schema import InstallJob
    from app.source_manager.install_jobs.states import InstallState

    job = InstallJob(
        id="ij_heartbeat",
        componentId="index_tts2",
        componentName="IndexTTS2",
        state=InstallState.DOWNLOADING,
        kind="custom_install",
        phase="download_models",
        message="Downloading",
        progressBytes=100,
        totalBytes=1000,
        percent=10,
        active=True,
        terminal=False,
        createdAt="2026-08-01T00:00:00+00:00",
        updatedAt="2026-08-01T00:00:00+00:00",
    )
    payload = service._serialize(job)
    assert payload["heartbeat"]["jobId"] == "ij_heartbeat"
    assert payload["phaseSteps"]
    assert payload["progress"]["phaseSteps"]
    assert payload["percent"] is None or payload["percent"] < 100
