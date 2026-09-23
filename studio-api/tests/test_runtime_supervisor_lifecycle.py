"""Hermetic lifecycle tests for the Python Runtime Supervisor.

Never mutates the live .runtime/supervisor store or binds :8758.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime_supervisor.constants import API_PORT, RETIRED_WEB_PORT
from runtime_supervisor.identity import PortState, classify_api_port, classify_listener
from runtime_supervisor.ports import parse_netstat_owner
from runtime_supervisor.services import (
    LifecycleError,
    ServiceResult,
    start_all,
    start_studio_api,
    stop_owned_service,
)
from runtime_supervisor.state import SupervisorState
from runtime_supervisor.paths import RuntimePaths


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    d = tmp_path / "supervisor"
    d.mkdir()
    return d


@pytest.fixture
def state(state_dir: Path) -> SupervisorState:
    return SupervisorState(state_dir)


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


def test_port_free_parser_unbound():
    assert parse_netstat_owner("  TCP    127.0.0.1:80    0.0.0.0:0    LISTENING    4\n", 59999) is None


def test_port_owner_parser_extracts_pid():
    text = "  TCP    127.0.0.1:59998         0.0.0.0:0              LISTENING       12345"
    assert parse_netstat_owner(text, 59998) == 12345


def test_port_owner_uses_ip_helper_not_netstat_exe():
    import inspect
    import os
    import socket
    import sys

    from runtime_supervisor import ports
    from runtime_supervisor.ports import port_owner_pid

    src = inspect.getsource(ports)
    assert '["netstat"' not in src
    assert "subprocess.run" not in src
    if sys.platform != "win32":
        return
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = int(server.getsockname()[1])
    try:
        assert port_owner_pid(port) == os.getpid()
    finally:
        server.close()


def test_pid_round_trip(state: SupervisorState):
    rec = state.write_pid("test_rt", 4242, "cmd", True)
    assert rec.owned is True
    loaded = state.read_pid("test_rt")
    assert loaded is not None
    assert loaded.pid == 4242
    assert loaded.owned is True
    state.remove_pid("test_rt")
    assert state.read_pid("test_rt") is None


def test_stale_pid_not_alive(state: SupervisorState):
    state.write_pid("test_stale", 999999, "fake", True)
    assert state.pid_alive("test_stale") is False
    state.remove_pid("test_stale")


def test_exclusive_lock_and_stale_reclaim(state: SupervisorState):
    assert state.lock_held() is False
    assert state.try_lock("studio_api") is True
    assert state.lock_held() is True
    assert state.try_lock("studio_api") is False
    state.clear_lock()
    assert state.lock_held() is False
    state.lock_path.write_text(
        json.dumps({"service": "x", "holderPid": 999999, "at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    assert state.try_lock("studio_api") is True
    state.clear_lock()


def test_storm_protection(state: SupervisorState):
    state.add_restart_event("test_storm")
    assert state.storm_active("test_storm") is False
    for _ in range(5):
        state.add_restart_event("test_storm")
    assert state.storm_active("test_storm") is True


def test_classify_phantom():
    st = classify_listener(owner_pid=25408, alive=False, healthy=False, cmd="", is_ours=False)
    assert st.state == "phantom"
    assert st.pid == 25408


def test_classify_healthy_reuses():
    st = classify_listener(owner_pid=10, alive=True, healthy=True, cmd="uvicorn app.main:app", is_ours=True)
    assert st.state == "healthy"


def test_classify_unrelated():
    st = classify_listener(owner_pid=22, alive=True, healthy=False, cmd="notepad.exe", is_ours=False)
    assert st.state == "unrelated"


def test_classify_free():
    st = classify_listener(owner_pid=None, alive=False, healthy=False, cmd="", is_ours=False)
    assert st.state == "free"


def test_classify_starting():
    st = classify_listener(
        owner_pid=33,
        alive=True,
        healthy=False,
        cmd="python -m uvicorn app.main:app --port 8758",
        is_ours=True,
    )
    assert st.state == "starting"


def test_authoritative_start_fails_closed_on_phantom(fake_paths: RuntimePaths, state: SupervisorState):
    def classify():
        return PortState("phantom", pid=25408)

    with pytest.raises(LifecycleError) as exc:
        start_studio_api(fake_paths, state, classify_fn=classify, spawn=False)
    assert "PHANTOM" in str(exc.value)


def test_authoritative_start_fails_closed_on_unrelated(fake_paths: RuntimePaths, state: SupervisorState):
    def classify():
        return PortState("unrelated", pid=77, cmd="other")

    with pytest.raises(LifecycleError) as exc:
        start_studio_api(fake_paths, state, classify_fn=classify, spawn=False)
    assert "unrelated" in str(exc.value)


def test_authoritative_start_port_conflict_on_unknown_healthy(fake_paths: RuntimePaths, state: SupervisorState):
    def classify():
        return PortState("healthy", pid=88, cmd="uvicorn app.main:app --port 8758")

    result = start_studio_api(fake_paths, state, classify_fn=classify, spawn=False)
    assert result.ok is False
    assert "PORT_CONFLICT" in result.message
    rec = state.read_pid("studio_api")
    assert rec is None or rec.owned is False


def test_start_all_never_starts_8760(tmp_path: Path, fake_paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_SUPERVISOR_STATE_DIR", str(tmp_path / "sup"))
    state = SupervisorState(tmp_path / "sup")

    def classify():
        return PortState("healthy", pid=1, cmd="uvicorn app.main:app")

    monkeypatch.setattr("runtime_supervisor.services.classify_api_port", classify)
    monkeypatch.setattr(
        "runtime_supervisor.services.start_comfy",
        lambda paths, state, spawn=True: ServiceResult("comfyui", True, "headless stub", None, "owned"),
    )
    monkeypatch.setattr("runtime_supervisor.services.ollama_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.services.tunnel_process_healthy", lambda _s: False)
    monkeypatch.setattr("runtime_supervisor.services.port_owner_pid", lambda _p: 1)
    monkeypatch.setattr("runtime_supervisor.services.discover_paths", lambda _r=None: fake_paths)
    monkeypatch.setattr("runtime_supervisor.services.SupervisorState.from_env", lambda _root: state)
    monkeypatch.setattr("runtime_supervisor.control_client.control_plane_reachable", lambda: False)
    monkeypatch.setattr("runtime_supervisor.windows_task.task_exists", lambda *_a, **_k: False)
    monkeypatch.setattr(
        "runtime_supervisor.services.start_studio_api",
        lambda *_a, **_k: ServiceResult("studio_api", True, "ok", 1, "owned"),
    )

    report = start_all(spawn=False, no_cloudflare=True, state=state, repo_root=tmp_path)
    assert report.started_web_8760 is False
    assert RETIRED_WEB_PORT == 8760
    joined = "\n".join(report.lines())
    assert "8760" in joined
    assert "not started" in joined


def test_stop_leaves_external_ollama(state: SupervisorState):
    state.write_pid("ollama", 424242, "ollama serve", owned=False)
    result = stop_owned_service(state, "ollama", force=False, allow_external=False)
    assert result.ok is True
    assert "EXTERNAL" in result.message
    assert state.read_pid("ollama") is not None


def test_injected_classify_api_port_uses_hooks():
    st = classify_api_port(
        API_PORT,
        owner_fn=lambda _p: None,
        alive_fn=lambda _p: False,
        healthy_fn=lambda: False,
        cmd_fn=lambda _p: "",
    )
    assert st.state == "free"


def test_start_args_never_include_workers_or_8760():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "services.py"
    text = source.read_text(encoding="utf-8")
    assert "--workers" not in text
    assert "web_server.py" not in text
    assert "8760" not in text or "RETIRED_WEB_PORT" in text


def test_gpu_admission_blocks_second_stack_when_other_is_busy(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import gpu_admission as ga

    monkeypatch.setattr(ga, "comfy_healthy", lambda host="127.0.0.1", port=8188: port == 8188)
    monkeypatch.setattr(ga, "comfy_queue_running", lambda host="127.0.0.1", port=8188: 1 if port == 8188 else 0)
    monkeypatch.setattr(ga, "nvidia_snapshot", lambda: {"ok": True, "name": "RTX"})
    monkeypatch.setattr(ga, "port_owner_pid", lambda _p: 11)
    monkeypatch.setattr(ga, "process_command_line", lambda _p: "python ComfyUI/main.py")
    blocked = ga.assess_gpu_admission("minimax_h3_route_a")
    assert blocked["allowed"] is False
    assert blocked["action"] == "block"


def test_gpu_admission_reuses_healthy_route_a(monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor import gpu_admission as ga

    monkeypatch.setattr(ga, "comfy_healthy", lambda host="127.0.0.1", port=8188: port == 8192)
    monkeypatch.setattr(ga, "comfy_queue_running", lambda host="127.0.0.1", port=8188: 0)
    monkeypatch.setattr(ga, "nvidia_snapshot", lambda: {"ok": True, "name": "RTX"})
    monkeypatch.setattr(ga, "port_owner_pid", lambda _p: 22)
    monkeypatch.setattr(ga, "process_command_line", lambda _p: "python minimax-h3/comfyui/main.py --port 8192")
    reused = ga.assess_gpu_admission("minimax_h3_route_a")
    assert reused["allowed"] is True
    assert reused["action"] == "reuse"


def test_adopt_route_a_does_not_claim_owned_ready(state: SupervisorState, monkeypatch: pytest.MonkeyPatch):
    from runtime_supervisor.services import adopt_route_a

    monkeypatch.setattr("runtime_supervisor.services.comfy_healthy", lambda host="127.0.0.1", port=8188: port == 8192)
    monkeypatch.setattr("runtime_supervisor.services.port_owner_pid", lambda _p: 33)
    monkeypatch.setattr(
        "runtime_supervisor.services.process_command_line",
        lambda _p: "python runtime/minimax-h3/comfyui/main.py --port 8192",
    )
    result = adopt_route_a(state)
    assert result.ok is True
    assert result.ownership in {"reused", "external"}
    assert result.ownership != "owned"
    assert "not Adept-owned Ready" in result.message
