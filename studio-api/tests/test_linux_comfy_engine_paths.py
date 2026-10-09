"""Linux Creator Engine path resolution. These tests do not spawn ComfyUI."""

from __future__ import annotations

from pathlib import Path

from runtime_supervisor.headless_comfy.service import comfy_main_argument, engine_python_candidates


def test_linux_candidates_include_bin_python() -> None:
    root = Path("/opt/adept/ComfyUI")
    rendered = {path.as_posix() for path in engine_python_candidates(root)}
    assert "/opt/adept/ComfyUI/bin/python" in rendered
    assert "/opt/adept/ComfyUI/ComfyUI/.venv/bin/python" in rendered
    assert "/opt/adept/ComfyUI/python.exe" in rendered


def test_main_argument_uses_the_host_separator() -> None:
    argument = comfy_main_argument()
    assert argument == str(Path("ComfyUI") / "main.py")
    assert argument.endswith("main.py")
    assert "python.exe" not in argument
