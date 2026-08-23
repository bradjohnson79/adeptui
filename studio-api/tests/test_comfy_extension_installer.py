from __future__ import annotations

import subprocess
from pathlib import Path


def test_install_extension_dependencies_falls_back_to_uv_for_pep668(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example-package\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, cwd=None):
        calls.append(cmd)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout="",
                stderr="error: externally-managed-environment",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="installed with uv", stderr="")

    monkeypatch.setattr(installer, "_run", fake_run)

    result = installer.install_extension_dependencies(tmp_path)

    assert result["ok"] is True
    assert result["method"] == "uv_pip_system"
    assert calls[0][-2:] == ["-r", str(requirements)]
    assert calls[1][0:5] == ["python", "-m", "uv", "pip", "install"]
    assert "--system" in calls[1]


def test_install_extension_dependencies_falls_back_to_uv_cli_when_module_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example-package\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, cwd=None):
        calls.append(cmd)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout="",
                stderr="error: externally-managed-environment",
            )
        if len(calls) == 2:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout="",
                stderr="No module named uv",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="installed with uv.exe", stderr="")

    monkeypatch.setattr(installer, "_run", fake_run)
    monkeypatch.setattr(installer, "_find_uv_executable", lambda: r"C:\tools\uv.exe")

    result = installer.install_extension_dependencies(tmp_path)

    assert result["ok"] is True
    assert result["method"] == "uv_cli_python"
    assert calls[0][0:4] == ["python", "-m", "pip", "install"]
    assert calls[1][0:5] == ["python", "-m", "uv", "pip", "install"]
    assert calls[2] == [
        r"C:\tools\uv.exe",
        "pip",
        "install",
        "--python",
        "python",
        "-r",
        str(requirements),
    ]


def test_sensenova_install_job_never_runs_plain_pip_requirements(tmp_path: Path, monkeypatch) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "httpx\n"
        "sensenova-u1 @ https://github.com/OpenSenseNova/SenseNova-U1/archive/refs/tags/comfyui-v0.2.0.tar.gz\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, cwd=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(installer, "_run", fake_run)
    result = installer.install_extension_dependencies(
        tmp_path, component_id="comfyui_sensenova_nodes"
    )
    assert result["ok"] is True
    assert result["method"] == "pip_no_deps"
    assert calls, "installer must invoke pip"
    for cmd in calls:
        joined = " ".join(cmd)
        assert "--no-deps" in cmd, joined
        install_idx = next(i for i, part in enumerate(cmd) if part == "install")
        dash_r = cmd.index("-r")
        assert "--no-deps" in cmd[install_idx:dash_r], joined


def _assert_cmd_cannot_install_cpu_torch(cmd: list[str]) -> Path:
    joined = " ".join(cmd)
    assert "--no-deps" in cmd, joined
    assert "torch==2.8.0" not in joined
    assert "-r" in cmd
    req_file = Path(cmd[cmd.index("-r") + 1])
    text = req_file.read_text(encoding="utf-8") if req_file.is_file() else ""
    lowered = text.lower()
    assert "torch==2.8" not in lowered
    assert "torchvision" not in lowered
    assert "torchaudio" not in lowered
    for line in text.splitlines():
        from app.source_manager.install_jobs.comfy_extension_installer import (
            is_protected_torch_requirement,
        )

        assert not is_protected_torch_requirement(line), line
    return req_file


def test_sensenova_pip_install_never_replaces_comfy_cuda_torch(tmp_path: Path) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "httpx\n"
        "sensenova-u1 @ https://github.com/OpenSenseNova/SenseNova-U1/archive/refs/tags/comfyui-v0.2.0.tar.gz\n",
        encoding="utf-8",
    )
    cmd = installer.build_extension_pip_install_cmd(
        "python",
        requirements,
        component_id="comfyui_sensenova_nodes",
    )
    filtered = _assert_cmd_cannot_install_cpu_torch(cmd)
    assert filtered != requirements
    assert "httpx" in filtered.read_text(encoding="utf-8")
    assert installer.pip_should_isolate_torch("comfyui_sensenova_nodes", requirements) is True
    hunyuan = installer.build_extension_pip_install_cmd("python", tmp_path / "missing.txt")
    assert "--no-deps" not in hunyuan


def test_official_sensenova_requirements_text_isolates_torch(tmp_path: Path) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "torch==2.8.0\n"
        "torchvision==0.23.0\n"
        "torchaudio==2.8.0\n"
        "httpx\n"
        "sensenova-u1 @ https://github.com/OpenSenseNova/SenseNova-U1/archive/refs/tags/comfyui-v0.2.0.tar.gz\n",
        encoding="utf-8",
    )
    cmd = installer.build_extension_pip_install_cmd("python", requirements)
    filtered = _assert_cmd_cannot_install_cpu_torch(cmd)
    kept = filtered.read_text(encoding="utf-8")
    assert "httpx" in kept
    assert "sensenova-u1" in kept
    assert "torch==2.8.0" in requirements.read_text(encoding="utf-8")


def test_sensenova_install_cannot_reintroduce_torch_28_cpu(tmp_path: Path, monkeypatch) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "torch==2.8.0\n"
        "torchvision\n"
        "torchaudio\n"
        "httpx\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, cwd=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(installer, "_run", fake_run)
    result = installer.install_extension_dependencies(
        tmp_path, component_id="comfyui_sensenova_nodes"
    )
    assert result["ok"] is True
    assert result["torchIsolated"] is True
    assert calls, "installer must invoke pip"
    for cmd in calls:
        _assert_cmd_cannot_install_cpu_torch(cmd)


def test_preflight_uses_live_wrapper_node_inventory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    custom_nodes = tmp_path / "custom_nodes"
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

    preflight = installer.preflight_extension("comfyui_hunyuan_nodes")

    assert preflight["ok"] is True
    assert preflight["requiredNodes"] == [
        "DownloadAndLoadHyVideoTextEncoder",
        "HyVideoI2VEncode",
        "HyVideoModelLoader",
        "HyVideoSampler",
        "HyVideoTextEncode",
        "HyVideoVAELoader",
    ]


def test_any_plugin_torch_pin_is_isolated(tmp_path: Path) -> None:
    from app.source_manager.install_jobs import comfy_extension_installer as installer

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("httpx\ntorch==2.1.0\n", encoding="utf-8")
    cmd = installer.build_extension_pip_install_cmd("python", requirements, component_id="some_other_nodes")
    filtered = _assert_cmd_cannot_install_cpu_torch(cmd)
    assert "httpx" in filtered.read_text(encoding="utf-8")
    assert installer.pip_should_isolate_torch("some_other_nodes", requirements) is True
