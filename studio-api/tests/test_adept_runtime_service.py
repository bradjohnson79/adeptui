"""Hermetic tests for Adept Runtime Service config, control plane, and Setup Wizard chain."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime_supervisor.canonical_config import (
    ConfigurationError,
    RuntimeConfig,
    parse_runtime_config,
    validate_runtime_config,
    write_runtime_config,
)
from runtime_supervisor.control_plane import assert_loopback_bind, ControlPlaneError, peer_is_loopback
from runtime_supervisor.control_token import ensure_token, token_matches
from runtime_supervisor.headless_comfy import config_yaml
from runtime_supervisor.windows_task import TASK_NAME


def test_config_yaml_has_no_hardcoded_machine_paths():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "headless_comfy" / "config_yaml.py"
    text = source.read_text(encoding="utf-8")
    assert "D:\\01_Models" not in text
    assert "C:\\Users\\bradj" not in text
    assert "bradj" not in text


def test_invalid_config_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_RUNTIME_CONFIG", str(tmp_path / "runtime.json"))
    cfg = RuntimeConfig(comfyRoot="", comfyPython="", modelRoot="")
    errors = validate_runtime_config(cfg)
    assert errors
    with pytest.raises(ConfigurationError):
        write_runtime_config(cfg)


def test_valid_config_writes_runtime_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    comfy = tmp_path / "ComfyInstall" / "ComfyUI"
    comfy.mkdir(parents=True)
    (comfy / "main.py").write_text("# main", encoding="utf-8")
    py = tmp_path / "python.exe"
    py.write_text("", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setenv("ADEPT_RUNTIME_CONFIG", str(tmp_path / "runtime.json"))
    monkeypatch.setenv("ADEPT_RUNTIME_HOME", str(tmp_path / "home"))
    cfg = RuntimeConfig(
        comfyRoot=str(tmp_path / "ComfyInstall"),
        comfyPython=str(py),
        modelRoot=str(models),
        logDir=str(tmp_path / "logs"),
        stateDir=str(tmp_path / "state"),
        servicePython=str(py),
    )
    path = write_runtime_config(cfg)
    assert path.is_file()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["port"] == 8188
    assert raw["controlPort"] != 8760


def test_retired_control_port_rejected():
    cfg = parse_runtime_config(
        {
            "comfyRoot": "x",
            "comfyPython": "y",
            "modelRoot": "z",
            "controlPort": 8760,
        }
    )
    errors = validate_runtime_config(cfg)
    assert any("8760" in e for e in errors)


def test_loopback_bind_and_peer():
    assert assert_loopback_bind("127.0.0.1") == "127.0.0.1"
    with pytest.raises(ControlPlaneError):
        assert_loopback_bind("0.0.0.0")
    with pytest.raises(ControlPlaneError):
        assert_loopback_bind("192.168.1.10")
    assert peer_is_loopback("127.0.0.1") is True
    assert peer_is_loopback("10.0.0.5") is False


def test_token_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_RUNTIME_TOKEN_FILE", str(tmp_path / "control.token"))
    token = ensure_token()
    assert token
    assert token_matches(token) is True
    assert token_matches("nope") is False
    assert token_matches(None) is False
    again = ensure_token()
    assert again == token


def test_enable_invalid_config_does_not_register_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import bootstrap

    called = {"register": 0}

    def fail_register(*_a, **_k):
        called["register"] += 1
        raise AssertionError("register_task must not run on invalid config")

    monkeypatch.setattr(bootstrap, "build_discovered_config", lambda **_k: RuntimeConfig("", "", ""))
    monkeypatch.setattr(bootstrap, "try_load_runtime_config", lambda: None)
    monkeypatch.setattr(bootstrap, "list_legacy_owners", lambda: [])
    monkeypatch.setattr(bootstrap, "register_task", fail_register)
    report = bootstrap.enable_recommended(repo_root=tmp_path, wait=False)
    assert report.ok is False
    assert "CONFIGURATION ERROR" in report.message
    assert called["register"] == 0
    assert report.taskRegistered is False


def test_enable_valid_config_registers_canonical_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import bootstrap

    comfy = tmp_path / "ComfyInstall" / "ComfyUI"
    comfy.mkdir(parents=True)
    (comfy / "main.py").write_text("#", encoding="utf-8")
    py = tmp_path / "pythonw.exe"
    py.write_text("", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    cfg = RuntimeConfig(
        comfyRoot=str(tmp_path / "ComfyInstall"),
        comfyPython=str(py),
        modelRoot=str(models),
        logDir=str(tmp_path / "logs"),
        stateDir=str(tmp_path / "state"),
        servicePython=str(py),
        repoRoot=str(tmp_path),
    )
    monkeypatch.setenv("ADEPT_RUNTIME_CONFIG", str(tmp_path / "runtime.json"))
    registered = {"name": None}

    monkeypatch.setattr(bootstrap, "build_discovered_config", lambda **_k: cfg)
    monkeypatch.setattr(bootstrap, "try_load_runtime_config", lambda: None)
    monkeypatch.setattr(bootstrap, "list_legacy_owners", lambda: ["AdeptBetaBackendManager"])
    monkeypatch.setattr(bootstrap, "register_task", lambda _c: registered.update(name=TASK_NAME) or type("T", (), {"exists": True})())
    monkeypatch.setattr(bootstrap, "start_task", lambda: None)
    monkeypatch.setattr(bootstrap, "task_exists", lambda: True)
    monkeypatch.setattr(bootstrap, "control_plane_reachable", lambda: True)
    monkeypatch.setattr(
        bootstrap,
        "call_control",
        lambda *_a, **_k: {"ok": True, "comfyState": "ready", "serviceState": "running"},
    )
    monkeypatch.setattr(bootstrap, "_wait_ready", lambda timeout_sec=180: {"ok": True, "comfyState": "ready"})
    monkeypatch.setattr(bootstrap, "retire_legacy_tasks", lambda: ["AdeptBetaBackendManager"])

    report = bootstrap.enable_recommended(repo_root=tmp_path, wait=True)
    assert report.ok is True
    assert registered["name"] == "AdeptRuntimeService"
    assert report.legacyDetected == ["AdeptBetaBackendManager"]
    assert report.legacyRetired == ["AdeptBetaBackendManager"]
    assert (tmp_path / "runtime.json").is_file()


def test_start_with_windows_reflects_actual_task(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import bootstrap
    from runtime_supervisor.windows_task import TaskStatus

    monkeypatch.setattr(bootstrap, "query_task", lambda: TaskStatus(name=TASK_NAME, exists=False))
    assert bootstrap.actual_start_with_windows() is False
    monkeypatch.setattr(bootstrap, "query_task", lambda: TaskStatus(name=TASK_NAME, exists=True))
    assert bootstrap.actual_start_with_windows() is True


def test_json_true_without_task_is_not_enabled(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.service_status import collect_runtime_view
    from runtime_supervisor.windows_task import TaskStatus

    monkeypatch.setattr(
        "runtime_supervisor.service_status.try_load_runtime_config",
        lambda: RuntimeConfig("c", "p", "m"),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.query_task",
        lambda: TaskStatus(name=TASK_NAME, exists=False),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.headless_status",
        lambda: {"healthy": False, "ownership": "down", "owned": False, "pid": None, "queueRunning": 0},
    )
    view = collect_runtime_view()
    assert view["startWithWindows"] is False
    assert view["taskRegistered"] is False


def test_fal_offline_does_not_fail_local_ready(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.service_status import collect_runtime_view
    from runtime_supervisor.windows_task import TaskStatus

    monkeypatch.setattr(
        "runtime_supervisor.service_status.try_load_runtime_config",
        lambda: RuntimeConfig("c", "p", "m", controlPort=8759),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.query_task",
        lambda: TaskStatus(name=TASK_NAME, exists=True, running=True),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.headless_status",
        lambda: {"healthy": True, "ownership": "owned", "owned": True, "pid": 4242, "queueRunning": 0},
    )
    monkeypatch.setattr("runtime_supervisor.service_status.probe_fal_connected", lambda: False)
    monkeypatch.setattr("runtime_supervisor.service_status.comfy_healthy", lambda: True)
    view = collect_runtime_view()
    assert view["comfyState"] == "ready"
    assert view["falConnected"] is False
    assert view["serviceState"] == "running"


def test_start_all_does_not_spawn_comfy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.services import ServiceResult, StartReport, start_all
    from runtime_supervisor.state import SupervisorState
    from runtime_supervisor.paths import RuntimePaths
    from runtime_supervisor.identity import PortState

    py = tmp_path / "python.exe"
    py.write_text("", encoding="utf-8")
    paths = RuntimePaths(
        repo_root=tmp_path,
        studio_api_dir=tmp_path / "studio-api",
        studio_api_python=py,
        comfy_install_root=None,
        comfy_root=None,
        comfy_python=None,
        comfy_main=None,
        comfy_shared_paths=None,
        comfy_input_dir=tmp_path / "in",
        comfy_output_dir=tmp_path / "out",
        cloudflared=None,
        tunnel_config=None,
        tunnel_name="adept-ui-beta",
        ollama=None,
        logs_dir=tmp_path / "logs",
    )
    state = SupervisorState(tmp_path / "sup")
    spawned = {"comfy": 0}

    def boom(*_a, **_k):
        spawned["comfy"] += 1
        raise AssertionError("start_comfy must not be called from start_all")

    monkeypatch.setenv("ADEPT_SUPERVISOR_STATE_DIR", str(tmp_path / "sup"))
    monkeypatch.setattr("runtime_supervisor.services.start_comfy", boom)
    monkeypatch.setattr(
        "runtime_supervisor.services.start_studio_api",
        lambda *_a, **_k: ServiceResult("studio_api", True, "ok", 1, "owned"),
    )
    monkeypatch.setattr(
        "runtime_supervisor.services.adopt_route_a",
        lambda *_a, **_k: ServiceResult("minimax_h3_route_a", True, "skip", None, "external"),
    )
    monkeypatch.setattr(
        "runtime_supervisor.services.start_ollama",
        lambda *_a, **_k: ServiceResult("ollama", True, "skip", None, "external"),
    )
    monkeypatch.setattr("runtime_supervisor.services.discover_paths", lambda _r=None: paths)
    monkeypatch.setattr("runtime_supervisor.control_client.control_plane_reachable", lambda: False)
    monkeypatch.setattr("runtime_supervisor.services.SupervisorState.from_env", lambda _root: state)
    monkeypatch.setattr("runtime_supervisor.windows_task.task_exists", lambda *_a, **_k: False)

    report = start_all(spawn=False, no_cloudflare=True, state=state, repo_root=tmp_path)
    assert spawned["comfy"] == 0
    assert report.results["studio_api"].ok is False
    assert "unavailable" in report.results["studio_api"].message.lower()
    assert report.results["comfyui"].ok is False


def test_request_qwen_payload_does_not_double_ok(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import serve as serve_mod

    monkeypatch.setattr(serve_mod, "collect_runtime_view", lambda: {"comfyPid": 99, "ok": True})
    result = {"ok": True, "samePid": True, "comfyPid": 99, "message": "Qwen Image Edit is ready."}
    extra = dict(result)
    ok = bool(extra.pop("ok", False))
    body = serve_mod._payload(ok, **extra)
    assert body["ok"] is True
    assert body["samePid"] is True
    assert body["comfyPid"] == 99


def test_request_qwen_keeps_pid(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import qwen_residency

    monkeypatch.setattr(
        qwen_residency,
        "headless_status",
        lambda: {"owned": True, "ownership": "owned", "pid": 99, "healthy": True},
    )
    monkeypatch.setattr(qwen_residency, "comfy_healthy", lambda: True)
    monkeypatch.setattr(qwen_residency, "comfy_queue_running", lambda: 0)
    monkeypatch.setattr(qwen_residency, "assess_gpu_admission", lambda _s: {"allowed": True})
    monkeypatch.setattr(qwen_residency, "qwen_nodes_present", lambda: True)
    result = qwen_residency.request_qwen()
    assert result["ok"] is True
    assert result["samePid"] is True
    assert result["comfyPid"] == 99


def test_request_qwen_reuses_healthy_external_comfy(monkeypatch: pytest.MonkeyPatch):
    """A healthy Comfy Desktop on :8188 is reused for Qwen, not a port conflict."""
    from runtime_supervisor import qwen_residency

    monkeypatch.setattr(
        qwen_residency,
        "headless_status",
        lambda: {"owned": False, "ownership": "reused", "pid": 18452, "healthy": True},
    )
    monkeypatch.setattr(qwen_residency, "comfy_healthy", lambda: True)
    monkeypatch.setattr(qwen_residency, "comfy_queue_running", lambda: 0)
    monkeypatch.setattr(qwen_residency, "assess_gpu_admission", lambda _s: {"allowed": True})
    monkeypatch.setattr(qwen_residency, "qwen_nodes_present", lambda: True)
    result = qwen_residency.request_qwen()
    assert result["ok"] is True
    assert result["state"] == "ready"
    assert result["comfyPid"] == 18452


def test_headless_status_marks_healthy_external_as_reused(monkeypatch: pytest.MonkeyPatch):
    """status() reports a healthy non-Adept Comfy as 'reused' (green), not external/down."""
    from runtime_supervisor.headless_comfy import service as svc

    monkeypatch.setattr(svc, "comfy_healthy", lambda: True)
    monkeypatch.setattr(svc, "comfy_queue_running", lambda: 0)
    monkeypatch.setattr(svc, "_port_identity", lambda _y: (18452, "ComfyUI main.py"))
    monkeypatch.setattr(svc.ownership, "read_record", lambda _d: None)
    out = svc.status()
    assert out["healthy"] is True
    assert out["ownership"] == "reused"
    assert out["owned"] is False
    assert out["pid"] == 18452


def test_runtime_view_running_when_manager_up_without_task(monkeypatch: pytest.MonkeyPatch):
    """A running, configured manager is 'running' even if Start-with-Windows is off."""
    from runtime_supervisor.canonical_config import RuntimeConfig
    from runtime_supervisor.service_status import collect_runtime_view
    from runtime_supervisor.windows_task import TaskStatus

    monkeypatch.setattr(
        "runtime_supervisor.service_status.try_load_runtime_config",
        lambda: RuntimeConfig("c", "p", "m"),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.query_task",
        lambda: TaskStatus(name="AdeptRuntimeService", exists=False),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.headless_status",
        lambda: {"healthy": True, "ownership": "reused", "owned": False, "pid": 18452, "queueRunning": 0},
    )
    monkeypatch.setattr("runtime_supervisor.service_status.comfy_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.service_status.manager_is_running", lambda: True)
    view = collect_runtime_view()
    assert view["serviceState"] == "running"
    assert view["comfyState"] == "ready"


def test_wizard_source_uses_enable_recommended():
    wizard = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "components" / "SetupWizard.tsx"
    text = wizard.read_text(encoding="utf-8")
    assert "runtimeManagerEnableRecommended" in text
    section = text.split("function BackgroundServicesSection")[1].split("function SetupDialogShell")[0]
    assert "runtimeManagerEnableRecommended" in section
    assert "runtimeManagerValidateConfig" in section
    assert "runtimeManagerRepair" in section
    assert "start_all" not in section
    assert "runtimeManagerStart" not in section
    assert "runtimeManagerStop" not in section
    assert "runtimeManagerRestartApi" not in section
    assert "runtimeManagerRestartComfy" not in section
    assert "Adept Runtime — Managed Automatically" in section


def test_startup_modal_still_auto_boots_via_supervisor():
    gauge = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "components" / "StartupSystemsGauge.tsx"
    text = gauge.read_text(encoding="utf-8")
    assert "runtimeManagerStart" in text


def test_validate_config_does_not_start_services(monkeypatch: pytest.MonkeyPatch):
    from app.runtime_manager.service import _validate_config_sync

    def boom(*_a, **_k):
        raise AssertionError("validate-config must not start or stop services")

    monkeypatch.setattr("app.runtime_manager.service.start_services", boom)
    monkeypatch.setattr("app.runtime_manager.service.stop_services", boom)
    monkeypatch.setattr("app.runtime_manager.service.restart_services", boom)
    monkeypatch.setattr("app.runtime_manager.service.restart_api_service", boom)
    monkeypatch.setattr("app.runtime_manager.service.restart_comfy_service", boom)
    result = _validate_config_sync()
    assert result.message
    assert isinstance(result.errors, list)
    assert result.source in {"saved", "discovered"}


def test_privilege_denied_is_not_a_weaker_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from runtime_supervisor.windows_task import PrivilegeRequired, register_task
    from runtime_supervisor.canonical_config import RuntimeConfig, validate_runtime_config

    comfy = tmp_path / "ComfyInstall" / "ComfyUI"
    comfy.mkdir(parents=True)
    (comfy / "main.py").write_text("#", encoding="utf-8")
    py = tmp_path / "pythonw.exe"
    py.write_text("", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    cfg = RuntimeConfig(
        comfyRoot=str(tmp_path / "ComfyInstall"),
        comfyPython=str(py),
        modelRoot=str(models),
        logDir=str(tmp_path / "logs"),
        stateDir=str(tmp_path / "state"),
        servicePython=str(py),
        repoRoot=str(tmp_path),
    )
    assert validate_runtime_config(cfg) == []

    class Fake:
        returncode = 1
        stdout = ""
        stderr = "ERROR: Access is denied."

    monkeypatch.setattr("runtime_supervisor.windows_task._run_schtasks", lambda *_a, **_k: Fake())
    monkeypatch.setattr("runtime_supervisor.windows_task._register_current_user_powershell", lambda *_a, **_k: Fake())
    monkeypatch.setattr("runtime_supervisor.windows_task.query_task", lambda *_a, **_k: type("T", (), {"exists": False, "name": "AdeptRuntimeService", "running": False, "raw": ""})())
    monkeypatch.setattr(
        "runtime_supervisor.windows_task._elevate_and_register",
        lambda *_a, **_k: None,
    )
    with pytest.raises(PrivilegeRequired) as exc:
        register_task(cfg)
    assert "weaker startup method" in str(exc.value).lower() or "permission" in str(exc.value).lower()


def test_windows_task_source_is_single_registrar():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "windows_task.py"
    text = source.read_text(encoding="utf-8")
    assert "AdeptRuntimeService" in text
    constants = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "constants.py"
    assert "AdeptRuntimeService" in constants.read_text(encoding="utf-8")
    assert "LEGACY_TASK_NAMES" in constants.read_text(encoding="utf-8")


def test_elevation_does_not_claim_success_without_query(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from runtime_supervisor.windows_task import PrivilegeRequired, register_task
    from runtime_supervisor.canonical_config import RuntimeConfig, validate_runtime_config

    comfy = tmp_path / "ComfyInstall" / "ComfyUI"
    comfy.mkdir(parents=True)
    (comfy / "main.py").write_text("#", encoding="utf-8")
    py = tmp_path / "pythonw.exe"
    py.write_text("", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    cfg = RuntimeConfig(
        comfyRoot=str(tmp_path / "ComfyInstall"),
        comfyPython=str(py),
        modelRoot=str(models),
        logDir=str(tmp_path / "logs"),
        stateDir=str(tmp_path / "state"),
        servicePython=str(py),
        repoRoot=str(tmp_path),
    )
    assert validate_runtime_config(cfg) == []

    class Fake:
        returncode = 1
        stdout = ""
        stderr = "ERROR: Access is denied."

    elevated = {"n": 0}

    def fake_elevate(*_a, **_k):
        elevated["n"] += 1

    monkeypatch.setattr("runtime_supervisor.windows_task._run_schtasks", lambda *_a, **_k: Fake())
    monkeypatch.setattr("runtime_supervisor.windows_task._register_current_user_powershell", lambda *_a, **_k: Fake())
    monkeypatch.setattr(
        "runtime_supervisor.windows_task.query_task",
        lambda *_a, **_k: type("T", (), {"exists": False, "name": "AdeptRuntimeService", "running": False, "raw": ""})(),
    )
    monkeypatch.setattr("runtime_supervisor.windows_task._elevate_and_register", fake_elevate)
    with pytest.raises(PrivilegeRequired):
        register_task(cfg)
    assert elevated["n"] == 1


def test_save_preferences_cannot_store_start_with_windows_without_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from app.runtime_manager.preferences import save_preferences
    from app.runtime_manager.schemas import RuntimeManagerPreferences

    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "runtime_supervisor.bootstrap.actual_start_with_windows",
        lambda: False,
    )
    saved = save_preferences(
        RuntimeManagerPreferences(
            comfyuiBackgroundManagerEnabled=False,
            localhostBackgroundManagerEnabled=False,
            startWithWindows=True,
            remoteAccessEnabled=False,
        )
    )
    assert saved.startWithWindows is False
    raw = (tmp_path / "runtime_manager" / "preferences.json").read_text(encoding="utf-8")
    assert '"startWithWindows": false' in raw or '"startWithWindows":false' in raw


def test_retire_legacy_requires_new_task(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import windows_task

    monkeypatch.setattr(windows_task, "task_exists", lambda name="AdeptRuntimeService": name != "AdeptRuntimeService")
    monkeypatch.setattr(windows_task, "list_legacy_owners", lambda: ["AdeptBetaBackendManager"])
    assert windows_task.retire_legacy_tasks() == []
