"""Hermetic tests: Ollama joins the Adept Runtime Supervisor fabric."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime_supervisor.constants import LOGICAL_COMFY, LOGICAL_LOCAL_LLM, LOGICAL_VIDEO
from runtime_supervisor.health import ollama_model_names, ollama_model_ready
from runtime_supervisor.paths import RuntimePaths
from runtime_supervisor.services import ServiceResult, start_ollama
from runtime_supervisor.state import SupervisorState
from runtime_supervisor.watch import watch_once


@pytest.fixture
def state(tmp_path: Path) -> SupervisorState:
    d = tmp_path / "supervisor"
    d.mkdir()
    return SupervisorState(d)


@pytest.fixture
def fake_paths(tmp_path: Path) -> RuntimePaths:
    exe = tmp_path / "ollama.exe"
    exe.write_text("", encoding="utf-8")
    return RuntimePaths(
        repo_root=tmp_path,
        studio_api_dir=tmp_path / "studio-api",
        studio_api_python=tmp_path / "python.exe",
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
        ollama=exe,
        logs_dir=tmp_path / "logs",
    )


def test_start_ollama_keeps_adept_ownership_when_already_healthy(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    state.write_pid("ollama", 7777, "ollama serve", owned=True)
    monkeypatch.setattr("runtime_supervisor.services.ollama_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.services.port_owner_pid", lambda _p: 8888)
    monkeypatch.setattr("runtime_supervisor.services.process_alive", lambda pid: pid == 7777)

    result = start_ollama(fake_paths, state, start_if_down=True, spawn=False)
    rec = state.read_pid("ollama")
    assert result.ok is True
    assert result.ownership == "owned"
    assert rec is not None
    assert rec.owned is True
    assert rec.pid == 7777


def test_start_ollama_adopts_external_when_not_owned(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("runtime_supervisor.services.ollama_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.services.port_owner_pid", lambda _p: 4242)

    result = start_ollama(fake_paths, state, start_if_down=True, spawn=False)
    rec = state.read_pid("ollama")
    assert result.ok is True
    assert result.ownership == "external"
    assert rec is not None
    assert rec.owned is False
    assert rec.pid == 4242


def test_watch_restarts_owned_ollama_after_two_alive_health_misses(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    state.write_pid("ollama", 5555, "ollama serve", owned=True)
    started = {"n": 0}

    def _start(*_a, **_k):
        started["n"] += 1
        return ServiceResult("ollama", True, "restarted", 202, "owned")

    monkeypatch.setattr("runtime_supervisor.watch.ollama_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.watch.process_alive", lambda _pid: True)
    monkeypatch.setattr("runtime_supervisor.watch.start_ollama", _start)
    monkeypatch.setattr("runtime_supervisor.watch.time.sleep", lambda _s: None)

    busy = {"ollama": 0}
    watch_once(state, fake_paths, busy, services=("ollama",))
    assert started["n"] == 0
    watch_once(state, fake_paths, busy, services=("ollama",))
    assert started["n"] == 1


def test_watch_restarts_owned_ollama(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    state.write_pid("ollama", 999999, "ollama serve", owned=True)
    started = {"n": 0}

    def _start(*_a, **_k):
        started["n"] += 1
        return ServiceResult("ollama", True, "restarted", 101, "owned")

    monkeypatch.setattr("runtime_supervisor.watch.ollama_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.watch.process_alive", lambda _pid: False)
    monkeypatch.setattr("runtime_supervisor.watch.start_ollama", _start)

    notes = watch_once(state, fake_paths, {"ollama": 0}, services=("ollama",))
    assert started["n"] == 1
    assert any("ollama: restart ok" in n for n in notes)


def test_watch_leaves_external_ollama(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    state.write_pid("ollama", 424242, "ollama serve", owned=False)
    started = {"n": 0}

    def boom(*_a, **_k):
        started["n"] += 1
        raise AssertionError("must not start external Ollama")

    monkeypatch.setattr("runtime_supervisor.watch.ollama_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.watch.start_ollama", boom)

    notes = watch_once(state, fake_paths, {"ollama": 0}, services=("ollama",))
    assert started["n"] == 0
    assert not any("restart" in n for n in notes)


def test_collect_status_exposes_logical_local_llm(
    fake_paths: RuntimePaths, state: SupervisorState, monkeypatch: pytest.MonkeyPatch
):
    from runtime_supervisor.services import collect_status

    monkeypatch.setattr("runtime_supervisor.services.discover_paths", lambda _r=None: fake_paths)
    monkeypatch.setattr("runtime_supervisor.services.studio_api_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.services.comfy_healthy", lambda **_k: False)
    monkeypatch.setattr("runtime_supervisor.services.ollama_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.services.tunnel_process_healthy", lambda _s: False)
    monkeypatch.setattr("runtime_supervisor.services.port_owner_pid", lambda _p: 11)
    monkeypatch.setattr("runtime_supervisor.services.required_local_llm_model", lambda: "gemma4:31b-it-qat")
    monkeypatch.setattr(
        "runtime_supervisor.services.fetch_json",
        lambda *_a, **_k: {"models": [{"name": "gemma4:31b-it-qat"}]},
    )
    monkeypatch.setattr("runtime_supervisor.services.SupervisorState.from_env", lambda _root: state)

    snap = collect_status(repo_root=fake_paths.repo_root, state=state, include_gpu=False)
    row = snap["ollama"]
    assert row["logicalId"] == LOGICAL_LOCAL_LLM
    assert snap["logicalServices"][LOGICAL_LOCAL_LLM]["logicalId"] == LOGICAL_LOCAL_LLM
    assert snap["logicalServices"][LOGICAL_COMFY]["logicalId"] == LOGICAL_COMFY
    assert snap["logicalServices"][LOGICAL_VIDEO]["logicalId"] == LOGICAL_VIDEO
    assert snap["logicalServices"][LOGICAL_COMFY]["availability"] in {
        "ONLINE",
        "STARTING",
        "FAILED",
        "ON_DEMAND",
        "DEGRADED",
    }
    assert snap["logicalServices"][LOGICAL_VIDEO]["availability"] == "ON_DEMAND"
    assert "port" not in snap["logicalServices"][LOGICAL_COMFY]
    assert "port" not in snap["logicalServices"][LOGICAL_VIDEO]
    assert row["daemonOnline"] is True
    assert row["modelReady"] is True
    assert "port" not in row


def test_model_ready_is_not_tags_alone():
    tags = {"models": [{"name": "llama3.2:latest"}]}
    assert ollama_model_names(tags) == ["llama3.2:latest"]
    assert ollama_model_ready("gemma4:31b-it-qat", tags=tags) is False
    assert ollama_model_ready("llama3.2:latest", tags=tags) is True


def test_control_plane_exposes_ollama_routes():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "control_plane.py"
    text = source.read_text(encoding="utf-8")
    assert "/start-ollama" in text
    assert "/stop-ollama" in text
    assert "/restart-ollama" in text


def test_serve_boots_and_watches_ollama():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "serve.py"
    text = source.read_text(encoding="utf-8")
    assert "start_ollama" in text
    assert 'watched = ("studio_api", "comfyui", "ollama")' in text
    assert "on_start_ollama" in text


def test_runtime_down_does_not_use_listening_fallback():
    from app.codirector.errors import CONNECTION_REFUSED, CoDirectorError

    assert "tell me about" not in CoDirectorError(
        CONNECTION_REFUSED, "down"
    ).message


def test_posecraft_what_is_deterministic():
    from unittest.mock import MagicMock

    from app.codirector.routing.situational_replies import resolve_situational_turn

    turn = resolve_situational_turn(MagicMock(), "proj", "What is PoseCraft used for?")
    assert turn.block is True
    assert turn.kind == "posecraft_what"
    assert "staging" in turn.spoken.lower()
