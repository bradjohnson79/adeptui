"""Adept Headless Comfy Service — ownership, YAML, no Desktop adopt."""

from __future__ import annotations

from pathlib import Path

import pytest

import os

from runtime_supervisor.headless_comfy import config_yaml, ownership
from runtime_supervisor.process import process_command_line, process_parent_pid
from runtime_supervisor.headless_comfy.service import request_start, request_stop
from runtime_supervisor.paths import RuntimePaths
from runtime_supervisor.services import start_comfy, stop_owned_service
from runtime_supervisor.state import SupervisorState


@pytest.fixture
def state(tmp_path: Path) -> SupervisorState:
    return SupervisorState(tmp_path / "supervisor")


@pytest.fixture
def fake_paths(tmp_path: Path) -> RuntimePaths:
    py = tmp_path / "python.exe"
    py.write_text("", encoding="utf-8")
    return RuntimePaths(
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


def test_windows_command_line_does_not_need_wmic():
    cmd = process_command_line(os.getpid())
    assert cmd
    assert "python" in cmd.lower()
    parent = process_parent_pid(os.getpid())
    assert parent is None or parent > 0


def test_yaml_missing_unet_is_configuration_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config_yaml, "QWEN_BASE", tmp_path / "missing-qwen")
    monkeypatch.setattr(config_yaml, "QWEN_UNET", tmp_path / "missing.safetensors")
    dest, errors = config_yaml.write_and_validate()
    assert errors
    assert dest.name == "extra_model_paths.yaml"
    assert not dest.exists() or "qwen" in " ".join(errors).lower()


def test_yaml_write_uses_adept_path_not_desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    unet = tmp_path / "qwen" / "split_files" / "diffusion_models" / "qwen_image_edit_2509_fp8_e4m3fn.safetensors"
    unet.parent.mkdir(parents=True)
    unet.write_bytes(b"x")
    monkeypatch.setattr(config_yaml, "QWEN_BASE", tmp_path / "qwen")
    monkeypatch.setattr(config_yaml, "QWEN_UNET", unet)
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(tmp_path / "adept-comfy"))
    dest, errors = config_yaml.write_and_validate()
    assert errors == []
    text = dest.read_text(encoding="utf-8")
    assert "adept_qwen_edit_2509" in text
    assert "shared_model_paths.yaml" not in text
    assert "Adept Headless Comfy" in text
    assert dest == tmp_path / "adept-comfy" / "extra_model_paths.yaml"


def test_command_identity_requires_adept_yaml_and_8188(tmp_path: Path):
    yaml = tmp_path / "Adept" / "Comfy" / "extra_model_paths.yaml"
    yaml.parent.mkdir(parents=True)
    yaml.write_text("x", encoding="utf-8")
    adept = (
        r"C:\Comfy\python.exe -s ComfyUI\main.py --listen 127.0.0.1 --port 8188 "
        f"--extra-model-paths-config {yaml}"
    )
    desktop = r"C:\Comfy Desktop\ComfyUI\main.py --extra-model-paths-config C:\Users\x\AppData\Roaming\Comfy Desktop\shared_model_paths.yaml"
    route_a = r"python runtime\minimax-h3\comfyui\main.py --port 8192"
    assert ownership.command_is_adept_headless(adept, yaml) is True
    assert ownership.command_is_adept_headless(desktop, yaml) is False
    assert ownership.command_is_adept_headless(route_a, yaml) is False


def test_start_comfy_reuses_healthy_external_without_adopting(
    fake_paths: RuntimePaths, state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A healthy Comfy Desktop on :8188 is reused (green), never adopted or killed.

    Adept does not take ownership: the pid record stays un-owned so stop/restart
    will never target the external process.
    """
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(tmp_path / "adept-comfy"))
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.comfy_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.port_owner_pid", lambda _p: 999)
    monkeypatch.setattr(
        "runtime_supervisor.headless_comfy.service.process_command_line",
        lambda _p: r"Comfy Desktop.exe --extra-model-paths-config C:\Users\x\AppData\Roaming\Comfy Desktop\shared_model_paths.yaml",
    )
    result = start_comfy(fake_paths, state, spawn=False)
    assert result.ok is True
    assert result.ownership == "reused"
    rec = state.read_pid("comfyui")
    assert rec is None or rec.owned is False


def test_start_comfy_reuses_matching_owned_record(
    fake_paths: RuntimePaths, state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cfg = tmp_path / "adept-comfy"
    cfg.mkdir()
    yaml = cfg / "extra_model_paths.yaml"
    yaml.write_text("adept_qwen_edit_2509:\n", encoding="utf-8")
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(cfg))
    cmd = f"python -s ComfyUI\\main.py --listen 127.0.0.1 --port 8188 --extra-model-paths-config {yaml}"
    ownership.write_record(cfg, {"pid": 4242, "cmd": cmd, "cwd": str(tmp_path), "yaml": str(yaml), "python": "py"})
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.comfy_healthy", lambda: True)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.port_owner_pid", lambda _p: 4242)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.process_alive", lambda _p: True)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.process_command_line", lambda _p: cmd)
    result = start_comfy(fake_paths, state, spawn=False)
    assert result.ok is True
    assert result.ownership == "owned"
    assert result.pid == 4242
    rec = state.read_pid("comfyui")
    assert rec is not None
    assert rec.owned is True
    assert rec.pid == 4242


def test_stop_refuses_external_even_with_force(
    state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(tmp_path / "adept-comfy"))
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.port_owner_pid", lambda _p: 777)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.process_alive", lambda _p: True)
    monkeypatch.setattr(
        "runtime_supervisor.headless_comfy.service.process_command_line",
        lambda _p: "Comfy Desktop.exe",
    )
    result = stop_owned_service(state, "comfyui", force=True)
    assert result.ok is False
    assert "EXTERNAL" in result.message or "refused" in result.message.lower()
    assert result.ownership == "external"


def test_stop_owned_verifies_identity(
    state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cfg = tmp_path / "adept-comfy"
    cfg.mkdir()
    yaml = cfg / "extra_model_paths.yaml"
    yaml.write_text("x", encoding="utf-8")
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(cfg))
    cmd = f"python -s ComfyUI\\main.py --port 8188 --extra-model-paths-config {yaml}"
    ownership.write_record(cfg, {"pid": 555, "cmd": cmd, "yaml": str(yaml)})
    state.write_pid("comfyui", 555, cmd, owned=True)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.process_alive", lambda _p: True)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.process_command_line", lambda _p: "notepad.exe")
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.comfy_queue_running", lambda: 0)
    result = request_stop(state, force=True)
    assert result.ok is False
    assert "identity" in result.message.lower()


def test_spawn_disabled_does_not_launch(
    fake_paths: RuntimePaths, state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    unet = tmp_path / "qwen" / "split_files" / "diffusion_models" / "qwen_image_edit_2509_fp8_e4m3fn.safetensors"
    unet.parent.mkdir(parents=True)
    unet.write_bytes(b"x")
    monkeypatch.setattr(config_yaml, "QWEN_BASE", tmp_path / "qwen")
    monkeypatch.setattr(config_yaml, "QWEN_UNET", unet)
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(tmp_path / "adept-comfy"))
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.comfy_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.port_owner_pid", lambda _p: None)
    monkeypatch.setattr(
        "runtime_supervisor.headless_comfy.service.assess_gpu_admission",
        lambda _s: {"allowed": True},
        raising=False,
    )
    monkeypatch.setattr(
        "runtime_supervisor.gpu_admission.assess_gpu_admission",
        lambda _s: {"allowed": True},
    )
    install = tmp_path / "Comfy-Install"
    (install / "ComfyUI").mkdir(parents=True)
    (install / "ComfyUI" / "main.py").write_text("# comfy", encoding="utf-8")
    (install / "python.exe").write_text("", encoding="utf-8")
    monkeypatch.setenv("ADEPT_COMFY_ROOT", str(install))
    monkeypatch.setenv("ADEPT_COMFY_PYTHON", str(install / "python.exe"))
    result = request_start(fake_paths, state, spawn=False)
    assert result.ok is False
    assert "spawn disabled" in result.message


def test_services_source_delegates_comfy_to_headless():
    source = Path(__file__).resolve().parents[1] / "runtime_supervisor" / "services.py"
    text = source.read_text(encoding="utf-8")
    assert "shared_model_paths.yaml" not in text
    assert "request_start" in text
    assert "request_stop" in text
    assert "already healthy — reused" not in text.split("def start_comfy")[1].split("def ")[0]


def _prime_start_env(fake_paths: RuntimePaths, state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Shared setup: Comfy down, port free, valid engine + yaml, spawn disabled."""
    unet = tmp_path / "qwen" / "split_files" / "diffusion_models" / "qwen_image_edit_2509_fp8_e4m3fn.safetensors"
    unet.parent.mkdir(parents=True)
    unet.write_bytes(b"x")
    monkeypatch.setattr(config_yaml, "QWEN_BASE", tmp_path / "qwen")
    monkeypatch.setattr(config_yaml, "QWEN_UNET", unet)
    monkeypatch.setenv("ADEPT_COMFY_CONFIG_DIR", str(tmp_path / "adept-comfy"))
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.comfy_healthy", lambda: False)
    monkeypatch.setattr("runtime_supervisor.headless_comfy.service.port_owner_pid", lambda _p: None)
    install = tmp_path / "Comfy-Install"
    (install / "ComfyUI").mkdir(parents=True)
    (install / "ComfyUI" / "main.py").write_text("# comfy", encoding="utf-8")
    (install / "python.exe").write_text("", encoding="utf-8")
    monkeypatch.setenv("ADEPT_COMFY_ROOT", str(install))
    monkeypatch.setenv("ADEPT_COMFY_PYTHON", str(install / "python.exe"))


def test_start_comfy_uses_route_a_handoff_admission(
    fake_paths: RuntimePaths, state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression: request_start must admit via request_comfy_admission_with_route_a_handoff,
    not bare assess_gpu_admission — otherwise an idle-resident Route A :8192 blocks the
    canonical Comfy :8188 start forever (the 2026-09-08 restart gap)."""
    _prime_start_env(fake_paths, state, tmp_path, monkeypatch)
    calls: list[str] = []

    def _handoff():
        calls.append("handoff")
        return {"allowed": True, "action": "start_after_handoff", "reason": "Route A warm models freed"}

    def _bare(_requesting: str):  # bare assess must NOT be the admission path anymore
        calls.append("bare")
        return {"allowed": False, "action": "handoff_required", "reason": "Route A holds GPU"}

    monkeypatch.setattr(
        "runtime_supervisor.gpu_admission.request_comfy_admission_with_route_a_handoff",
        _handoff,
    )
    monkeypatch.setattr(
        "runtime_supervisor.gpu_admission.assess_gpu_admission",
        _bare,
    )
    result = request_start(fake_paths, state, spawn=False)
    assert calls == ["handoff"], f"request_start must use the handoff admission, got calls={calls}"
    assert result.ok is False
    assert "spawn disabled" in result.message  # reached the spawn gate => admission passed


def test_start_comfy_blocks_when_route_a_busy(
    fake_paths: RuntimePaths, state: SupervisorState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When Route A is actively generating, the handoff admission refuses and request_start
    must not spawn — never interrupt a render."""
    _prime_start_env(fake_paths, state, tmp_path, monkeypatch)
    monkeypatch.setattr(
        "runtime_supervisor.gpu_admission.request_comfy_admission_with_route_a_handoff",
        lambda: {"allowed": False, "action": "block", "reason": "MiniMax Route A is using the GPU"},
    )
    result = request_start(fake_paths, state, spawn=False)
    assert result.ok is False
    assert "Route A" in result.message
    assert "spawn disabled" not in result.message
