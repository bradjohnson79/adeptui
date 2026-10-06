"""Isolation tests for Adept Background Services dual-runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime_supervisor.identity import PortState
from runtime_supervisor.paths import RuntimePaths
from runtime_supervisor.state import SupervisorState
from runtime_supervisor.studio_api_child import (
    classify_owned_listener,
    restart_studio_api_child,
    start_studio_api_child,
    stop_studio_api_child,
)


@pytest.fixture
def state(tmp_path: Path) -> SupervisorState:
    return SupervisorState(tmp_path / "sup")


@pytest.fixture
def fake_paths(tmp_path: Path) -> RuntimePaths:
    py = tmp_path / "python.exe"
    py.write_text("", encoding="utf-8")
    api = tmp_path / "studio-api"
    api.mkdir()
    return RuntimePaths(
        repo_root=tmp_path,
        studio_api_dir=api,
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


def test_stale_shim_pid_stop_inspects_listener(state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    state.write_pid("studio_api", 111, "venv shim", owned=True)
    alive = {222}

    def _alive(pid):
        return pid in alive

    def _kill(pid):
        alive.discard(pid)
        return True

    monkeypatch.setattr("runtime_supervisor.studio_api_child.process_alive", _alive)
    monkeypatch.setattr(
        "runtime_supervisor.studio_api_child.verify_studio_api_identity",
        lambda pid, port=8758: pid == 222,
    )
    monkeypatch.setattr("runtime_supervisor.studio_api_child.kill_process_tree", _kill)
    monkeypatch.setattr("runtime_supervisor.studio_api_child.wait_port_released", lambda *_a, **_k: True)
    monkeypatch.setattr("runtime_supervisor.studio_api_child.time.sleep", lambda *_a, **_k: None)

    def classify():
        return PortState("healthy", pid=222, cmd="python -m uvicorn app.main:app --port 8758")

    result = stop_studio_api_child(state, classify_fn=classify, allow_migrate=False)
    assert result.ok is True
    assert result.pid == 222
    assert state.read_pid("studio_api") is None


def test_foreign_8758_is_port_conflict(fake_paths: RuntimePaths, state: SupervisorState):
    def classify():
        return PortState("healthy", pid=77, cmd="notepad.exe")

    result = start_studio_api_child(fake_paths, state, classify_fn=classify, spawn=False)
    assert result.ok is False
    assert "PORT_CONFLICT" in result.message


def test_known_adept_without_owned_record_is_port_conflict(fake_paths: RuntimePaths, state: SupervisorState):
    def classify():
        return PortState("healthy", pid=61732, cmd="uv python -m uvicorn app.main:app --workers 1 --port 8758")

    result = start_studio_api_child(fake_paths, state, classify_fn=classify, spawn=False, allow_migrate=False)
    assert result.ok is False
    assert "PORT_CONFLICT" in result.message


def test_owned_listener_is_not_conflict(fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    state.write_pid("studio_api", 88, "python -m uvicorn app.main:app --port 8758", owned=True)
    monkeypatch.setattr("runtime_supervisor.studio_api_child.process_alive", lambda pid: pid == 88)
    monkeypatch.setattr(
        "runtime_supervisor.studio_api_child.verify_studio_api_identity",
        lambda pid, port=8758: pid == 88,
    )
    monkeypatch.setattr("runtime_supervisor.studio_api_child.studio_api_healthy", lambda: True)

    def classify():
        return PortState("healthy", pid=88, cmd="python -m uvicorn app.main:app --port 8758")

    result = start_studio_api_child(fake_paths, state, classify_fn=classify, spawn=False)
    assert result.ok is True
    assert result.ownership == "owned"
    assert result.pid == 88


def test_restart_api_reports_comfy_unchanged(fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("runtime_supervisor.studio_api_child._comfy_pid", lambda: 22220)
    monkeypatch.setattr(
        "runtime_supervisor.studio_api_child.stop_studio_api_child",
        lambda *_a, **_k: type("R", (), {"ok": True, "message": "stopped", "pid": 10, "ownership": "owned"})(),
    )
    monkeypatch.setattr(
        "runtime_supervisor.studio_api_child.start_studio_api_child",
        lambda *_a, **_k: type("R", (), {"ok": True, "message": "healthy PID 20", "pid": 20, "ownership": "owned"})(),
    )
    monkeypatch.setattr("runtime_supervisor.studio_api_child.port_owner_pid", lambda _p: 10)
    recycled = restart_studio_api_child(fake_paths, state, spawn=False)
    assert recycled["ok"] is True
    assert recycled["oldPid"] == 10
    assert recycled["newPid"] == 20
    assert recycled["comfyPid"] == 22220
    assert recycled["comfyPidUnchanged"] is True


def test_classify_foreign_vs_owned(state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("runtime_supervisor.studio_api_child.process_alive", lambda pid: True)
    monkeypatch.setattr(
        "runtime_supervisor.studio_api_child.verify_studio_api_identity",
        lambda pid, port=8758: pid == 5,
    )
    state.write_pid("studio_api", 5, "uvicorn app.main:app --port 8758", owned=True)
    st, role = classify_owned_listener(
        state,
        classify_fn=lambda: PortState("healthy", pid=5, cmd="uvicorn app.main:app --port 8758"),
    )
    assert role == "owned"
    st, role = classify_owned_listener(
        state,
        classify_fn=lambda: PortState("healthy", pid=9, cmd="python -m http.server 8758"),
    )
    assert role == "foreign"


def test_production_writers_have_no_hardcoded_user_paths():
    root = Path(__file__).resolve().parents[1] / "runtime_supervisor"
    for rel in (
        "canonical_config.py",
        "studio_api_child.py",
        "bootstrap.py",
        "serve.py",
        "windows_task.py",
        "headless_comfy/config_yaml.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "C:\\Users\\bradj" not in text
        assert "D:\\01_Models" not in text


def test_api_spawn_has_no_detached_or_workers():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "studio_api_child.py"
    text = source.read_text(encoding="utf-8")
    spawn = text.split("def _spawn_studio_api")[1].split("def ")[0]
    assert "DETACHED_PROCESS" not in spawn
    assert "--workers" not in spawn
    assert "CREATE_NO_WINDOW" in spawn
    assert "CREATE_NEW_PROCESS_GROUP" in spawn


def test_control_plane_exposes_per_child_routes():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "control_plane.py"
    text = source.read_text(encoding="utf-8")
    for path in (
        "/restart-api",
        "/restart-comfy",
        "/start-api",
        "/stop-api",
        "/start-comfy",
        "/stop-comfy",
        "/start-ollama",
        "/stop-ollama",
        "/restart-ollama",
    ):
        assert path in text


def test_frontend_build_script_does_not_restart_runtimes():
    pkg = Path(__file__).resolve().parents[2] / "studio-web" / "package.json"
    text = pkg.read_text(encoding="utf-8")
    assert "run_runtime_supervisor" not in text
    assert "8188" not in text
    assert "restart_all" not in text


def test_watch_recovers_api_when_port_free(fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.watch import watch_once
    from runtime_supervisor.services import ServiceResult

    monkeypatch.setattr("runtime_supervisor.watch.studio_api_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.watch.classify_api_port", lambda: PortState("free"))
    monkeypatch.setattr(
        "runtime_supervisor.watch.start_studio_api",
        lambda *_a, **_k: ServiceResult("studio_api", True, "recovered", 99, "owned"),
    )
    notes = watch_once(state, fake_paths, {"studio_api": 0}, services=("studio_api",))
    assert any("studio_api: restart ok" in n for n in notes)


def test_watch_does_not_adopt_healthy_unknown(fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.watch import watch_once

    started = {"n": 0}

    def boom(*_a, **_k):
        started["n"] += 1
        raise AssertionError("must not spawn over a foreign listener")

    monkeypatch.setattr("runtime_supervisor.watch.studio_api_healthy", lambda: False)
    monkeypatch.setattr(
        "runtime_supervisor.watch.classify_api_port",
        lambda: PortState("healthy", pid=61732, cmd="uvicorn app.main:app --port 8758"),
    )
    monkeypatch.setattr("runtime_supervisor.watch.start_studio_api", boom)
    notes = watch_once(state, fake_paths, {"studio_api": 0}, services=("studio_api",))
    assert started["n"] == 0
    assert any("PORT_CONFLICT" in n for n in notes)


def test_serve_watches_both_children():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "serve.py"
    text = source.read_text(encoding="utf-8")
    assert 'watched = ("studio_api", "comfyui", "ollama")' in text or 'watched = ("studio_api", "comfyui")' in text
    assert "allow_migrate=True" in text
    assert "on_restart_api" in text
    assert "on_restart_comfy" in text


def test_thin_recycle_script_is_control_plane_client():
    script = Path(__file__).resolve().parents[2] / "scripts" / "restart_studio_api_only.py"
    text = script.read_text(encoding="utf-8")
    assert "restart-api" in text
    assert "start_all" not in text
    assert "stop_owned_service" not in text


def test_watch_api_recovery_does_not_touch_comfy(fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.services import ServiceResult
    from runtime_supervisor.watch import watch_once

    comfy = {"n": 0}

    def no_comfy(*_a, **_k):
        comfy["n"] += 1
        raise AssertionError("API recovery must not start Comfy")

    monkeypatch.setattr("runtime_supervisor.watch.studio_api_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.watch.comfy_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.watch.classify_api_port", lambda: PortState("free"))
    monkeypatch.setattr(
        "runtime_supervisor.watch.start_studio_api",
        lambda *_a, **_k: ServiceResult("studio_api", True, "recovered", 99, "owned"),
    )
    monkeypatch.setattr("runtime_supervisor.watch.start_comfy", no_comfy)
    notes = watch_once(state, fake_paths, {"studio_api": 0, "comfyui": 0}, services=("studio_api", "comfyui"))
    assert comfy["n"] == 0
    assert any("studio_api: restart ok" in n for n in notes)


def test_parse_studio_api_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.canonical_config import parse_runtime_config, write_runtime_config, RuntimeConfig, StudioApiSettings

    comfy = tmp_path / "ComfyInstall" / "ComfyUI"
    comfy.mkdir(parents=True)
    (comfy / "main.py").write_text("#", encoding="utf-8")
    py = tmp_path / "python.exe"
    py.write_text("", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setenv("ADEPT_RUNTIME_CONFIG", str(tmp_path / "runtime.json"))
    cfg = RuntimeConfig(
        comfyRoot=str(tmp_path / "ComfyInstall"),
        comfyPython=str(py),
        modelRoot=str(models),
        logDir=str(tmp_path / "logs"),
        stateDir=str(tmp_path / "state"),
        servicePython=str(py),
        repoRoot=str(tmp_path),
        studioApi=StudioApiSettings(enabled=True, python=str(py), appRoot=str(tmp_path / "studio-api"), port=8758),
    )
    (tmp_path / "studio-api").mkdir()
    path = write_runtime_config(cfg)
    raw = path.read_text(encoding="utf-8")
    assert "studioApi" in raw
    assert "8758" in raw
    parsed = parse_runtime_config(__import__("json").loads(raw))
    assert parsed.studioApi.enabled is True
    assert parsed.studioApi.port == 8758
    assert parsed.autostart is True


def test_settings_and_wizard_use_manager_actions():
    settings = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "components" / "Settings" / "LocalRuntime.tsx"
    wizard = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "components" / "SetupWizard.tsx"
    settings_text = settings.read_text(encoding="utf-8")
    wizard_text = wizard.read_text(encoding="utf-8")
    assert "runtimeManagerRestartApi" in settings_text
    assert "runtimeManagerRestartComfy" in settings_text
    assert "Adept Background Services" in settings_text
    assert "adept-background-services" in wizard_text
    assert "Adept Runtime — Managed Automatically" in wizard_text
    assert "runtimeManagerValidateConfig" in wizard_text
    assert "runtimeManagerStart" not in wizard_text
    assert "runtimeManagerRestartApi" not in wizard_text
    assert "runtimeManagerRestartComfy" not in wizard_text
    assert "if (!comfyuiReady) return null" not in wizard_text


def test_package_beta_restart_is_thin_client():
    pkg = Path(__file__).resolve().parents[2] / "package.json"
    text = pkg.read_text(encoding="utf-8")
    assert "restart_studio_api_only.py" in text


def test_start_all_does_not_spawn_api_when_manager_down(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    from runtime_supervisor.services import start_all

    spawned = {"api": 0, "comfy": 0}

    def boom_api(*_a, **_k):
        spawned["api"] += 1
        raise AssertionError("start_all must not spawn Studio API")

    def boom_comfy(*_a, **_k):
        spawned["comfy"] += 1
        raise AssertionError("start_all must not spawn Comfy")

    monkeypatch.setenv("ADEPT_SUPERVISOR_STATE_DIR", str(state.state_dir))
    monkeypatch.setattr("runtime_supervisor.services.discover_paths", lambda _r=None: fake_paths)
    monkeypatch.setattr("runtime_supervisor.services.SupervisorState.from_env", lambda _root: state)
    monkeypatch.setattr("runtime_supervisor.control_client.control_plane_reachable", lambda: False)
    monkeypatch.setattr("runtime_supervisor.windows_task.task_exists", lambda *_a, **_k: False)
    monkeypatch.setattr("runtime_supervisor.services.start_studio_api", boom_api)
    monkeypatch.setattr("runtime_supervisor.services.start_comfy", boom_comfy)
    monkeypatch.setattr(
        "runtime_supervisor.services.adopt_route_a",
        lambda *_a, **_k: __import__("runtime_supervisor.services", fromlist=["ServiceResult"]).ServiceResult(
            "minimax_h3_route_a", True, "skip", None, "external"
        ),
    )
    monkeypatch.setattr(
        "runtime_supervisor.services.start_ollama",
        lambda *_a, **_k: __import__("runtime_supervisor.services", fromlist=["ServiceResult"]).ServiceResult(
            "ollama", True, "skip", None, "external"
        ),
    )
    report = start_all(spawn=True, no_cloudflare=True, state=state, repo_root=fake_paths.repo_root)
    assert spawned["api"] == 0
    assert spawned["comfy"] == 0
    assert report.results["studio_api"].ok is False
    assert "unavailable" in report.results["studio_api"].message.lower()


def test_restart_all_does_not_spawn_when_manager_down(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    from runtime_supervisor.services import restart_all

    called = {"start_all": 0}

    def boom(*_a, **_k):
        called["start_all"] += 1
        raise AssertionError("restart_all must not fall through to start_all")

    monkeypatch.setattr("runtime_supervisor.control_client.control_plane_reachable", lambda: False)
    monkeypatch.setattr("runtime_supervisor.services.start_all", boom)
    report = restart_all(repo_root=fake_paths.repo_root)
    assert called["start_all"] == 0
    assert report.results["studio_api"].ok is False
    assert report.results["comfyui"].ok is False


def test_cli_watch_does_not_start_children(monkeypatch: pytest.MonkeyPatch, capsys):
    from runtime_supervisor import cli

    monkeypatch.setattr(cli, "load_beta_env", lambda *_a, **_k: None)
    monkeypatch.setattr(cli, "discover_paths", lambda *_a, **_k: None)
    monkeypatch.setattr(cli, "repo_root_from", lambda: Path("."))
    monkeypatch.setattr("runtime_supervisor.control_client.control_plane_reachable", lambda: False)
    started = {"watch_loop": 0}

    def boom(*_a, **_k):
        started["watch_loop"] += 1
        raise AssertionError("CLI watch must not run watch_loop")

    monkeypatch.setattr("runtime_supervisor.watch.watch_loop", boom)
    code = cli.main(["watch", "--once"])
    assert code == 1
    assert started["watch_loop"] == 0
    err = capsys.readouterr().err
    assert "unavailable" in err.lower()


def test_retired_beta_register_script_cannot_create_old_task():
    script = Path(__file__).resolve().parents[2] / "Register-AdeptBetaBackendStartup.ps1"
    text = script.read_text(encoding="utf-8")
    assert "Register-ScheduledTask" not in text
    assert "AdeptRuntimeService" in text
    assert "will not create" in text.lower() or "RETIRED" in text
