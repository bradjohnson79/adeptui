"""Persisted InstalledRuntimeRegistry under data/docker_runtime/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..config import settings
from .contracts import DockerRuntimeDescriptor, InstalledRuntimeRegistry, RuntimeOwnership
from .storage import load_refs, save_refs


def _path() -> Path:
    base = Path(getattr(settings, "data_dir", None) or Path(__file__).resolve().parents[3] / "data")
    root = base / "docker_runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root / "registry.json"


def load_registry() -> InstalledRuntimeRegistry:
    path = _path()
    if not path.exists():
        reg = InstalledRuntimeRegistry(sharedRefs=load_refs())
        seed_core_runtimes(reg)
        save_registry(reg)
        return reg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        reg = InstalledRuntimeRegistry.model_validate(data)
        reg.sharedRefs = load_refs() or reg.sharedRefs
        if not any(r.classification == "core_mandatory" for r in reg.runtimes.values()):
            seed_core_runtimes(reg)
            save_registry(reg)
        return reg
    except Exception:
        reg = InstalledRuntimeRegistry()
        seed_core_runtimes(reg)
        save_registry(reg)
        return reg


def save_registry(reg: InstalledRuntimeRegistry) -> None:
    save_refs(reg.sharedRefs or {})
    _path().write_text(reg.model_dump_json(indent=2), encoding="utf-8")


def seed_core_runtimes(reg: InstalledRuntimeRegistry) -> None:
    """Host services classified as core / official — never Docker-wrapped fakes."""
    if "core-comfyui" not in reg.runtimes:
        reg.runtimes["core-comfyui"] = DockerRuntimeDescriptor(
            id="core-comfyui",
            name="ComfyUI Core",
            classification="core_mandatory",
            ownership="adept_core",
            modality="multi",
            readiness="ready",
            lifecycle="running",
            executionClass="native_local",
            image="host://comfyui",
            uninstallAllowed=False,
            healthOk=True,
        )
    if "core-ltx" not in reg.runtimes:
        reg.runtimes["core-ltx"] = DockerRuntimeDescriptor(
            id="core-ltx",
            name="LTX Core",
            classification="core_mandatory",
            ownership="adept_core",
            modality="video",
            readiness="ready",
            lifecycle="running",
            executionClass="native_local",
            image="host://ltx",
            uninstallAllowed=False,
            healthOk=True,
        )
    if "optional-wan" not in reg.runtimes:
        reg.runtimes["optional-wan"] = DockerRuntimeDescriptor(
            id="optional-wan",
            name="WAN",
            classification="official_optional",
            ownership="adept_official",
            modality="video",
            readiness="ready",
            lifecycle="stopped",
            executionClass="native_local",
            image="host://wan",
            uninstallAllowed=True,
            healthOk=False,
        )


def get_runtime(runtime_id: str) -> Optional[DockerRuntimeDescriptor]:
    return load_registry().runtimes.get(runtime_id)


def upsert_runtime(desc: DockerRuntimeDescriptor) -> DockerRuntimeDescriptor:
    reg = load_registry()
    reg.runtimes[desc.id] = desc
    save_registry(reg)
    return desc


def remove_runtime(runtime_id: str) -> bool:
    reg = load_registry()
    if runtime_id not in reg.runtimes:
        return False
    desc = reg.runtimes[runtime_id]
    if desc.classification == "core_mandatory":
        raise PermissionError("core_mandatory_uninstall_blocked")
    del reg.runtimes[runtime_id]
    save_registry(reg)
    return True
