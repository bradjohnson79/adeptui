"""Operating system and hardware identification."""

from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass


SUPPORTED = {
    ("windows", "x64"),
    ("linux", "x64"),
    ("darwin", "arm64"),
}


@dataclass(frozen=True)
class SystemProfile:
    os_name: str
    os_version: str
    arch: str
    linux_family: str | None
    ram_bytes: int
    disk_free_bytes: int
    gpu_vendor: str | None = None
    gpu_memory_bytes: int | None = None

    @property
    def supported(self) -> bool:
        return (self.os_name, self.arch) in SUPPORTED

    @property
    def unsupported_reason(self) -> str:
        if self.supported:
            return ""
        if self.os_name == "darwin":
            return (
                "This Mac is not a supported Adept UI install target. "
                "A compatible, certified Apple Silicon build is required."
            )
        if self.os_name == "linux" and self.linux_family not in {"fedora", "debian"}:
            return "This Linux distribution is not an approved Adept UI install target."
        return f"Adept UI does not have a certified build for {self.os_name} {self.arch}."


def normalize_arch(machine: str) -> str:
    value = machine.lower()
    if value in {"amd64", "x86_64"}:
        return "x64"
    if value in {"arm64", "aarch64"}:
        return "arm64"
    return value


def normalize_os(name: str) -> str:
    value = name.lower()
    if value.startswith("win"):
        return "windows"
    if value == "darwin" or value == "mac":
        return "darwin"
    if "linux" in value:
        return "linux"
    return value


def linux_family_from_os_release(text: str) -> str | None:
    lowered = text.lower()
    if "fedora" in lowered or "rhel" in lowered or "centos" in lowered:
        return "fedora"
    if "debian" in lowered or "ubuntu" in lowered or "linuxmint" in lowered:
        return "debian"
    if not text.strip():
        return None
    return "other"


def live_profile(install_root_parent: str | None = None) -> SystemProfile:
    os_name = normalize_os(platform.system())
    family = None
    if os_name == "linux":
        try:
            family = linux_family_from_os_release(open("/etc/os-release", encoding="utf-8").read())
        except OSError:
            family = None
    ram = 0
    try:
        import os

        if hasattr(os, "sysconf"):
            page = int(os.sysconf("SC_PAGE_SIZE"))
            pages = int(os.sysconf("SC_PHYS_PAGES"))
            ram = page * pages
    except (OSError, ValueError, AttributeError):
        ram = 0
    disk = 0
    if install_root_parent:
        try:
            disk = int(shutil.disk_usage(install_root_parent).free)
        except OSError:
            disk = 0
    return SystemProfile(
        os_name=os_name,
        os_version=platform.version(),
        arch=normalize_arch(platform.machine()),
        linux_family=family,
        ram_bytes=ram,
        disk_free_bytes=disk,
        gpu_vendor=None,
        gpu_memory_bytes=None,
    )
