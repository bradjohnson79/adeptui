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
