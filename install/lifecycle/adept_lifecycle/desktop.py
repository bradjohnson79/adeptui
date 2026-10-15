"""Desktop and menu launchers. Updates do not create a second shortcut."""

from __future__ import annotations

from pathlib import Path


def linux_desktop_entry(exec_path: Path) -> str:
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=Adept UI",
            "Comment=AI filmmaking and production studio",
            f"Exec=\"{exec_path}\"",
            "Icon=Adept UI",
            "Terminal=false",
            "Categories=Video;",
            "",
        ]
    )


def windows_launcher(exec_path: Path) -> str:
    """Start the lifecycle command with no console window.

    The shortcut must not start the application executable directly.
    """
    command = str(exec_path).replace('"', '""')
    return (
        'Set shell = CreateObject("Wscript.Shell")\r\n'
        f'shell.Run """{command}""", 0, False\r\n'
    )


def macos_launcher(exec_path: Path) -> str:
    return f'#!/bin/sh\nopen "{exec_path}"\n'


def write_launcher(destination: Path, exec_path: Path, os_name: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    if os_name == "linux":
        destination.write_text(linux_desktop_entry(exec_path), encoding="utf-8")
    elif os_name == "darwin":
        destination.write_text(macos_launcher(exec_path), encoding="utf-8")
    else:
        destination.write_text(windows_launcher(exec_path), encoding="utf-8")


def menu_entry(applications_dir: Path, exec_path: Path) -> Path:
    path = applications_dir / "adept-ui.desktop"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(linux_desktop_entry(exec_path), encoding="utf-8")
    return path
